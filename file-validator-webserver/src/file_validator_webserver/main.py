# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the MIT License (the "License"); you may not
# use this file except in compliance with the License.
#
# MIT License
#
# Copyright (c) 2026 Mayuresh Kedari
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""File Validator App - FastAPI Web Interface."""

import asyncio
import contextlib
import functools
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import polars as pl
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from file_validator_webserver.fs_utils import (
    async_list_files,
    async_path_exists,
    async_resolve,
    async_rmtree,
    async_unlink,
)

try:
    from file_validator.auditor import FileAuditor
    from file_validator.config import COLS_SPEC, FileConfig, NormalizationConfig
    from file_validator.credentials import auto_refresh_oidc_token_if_needed
    from file_validator.excel_exporter import build_and_save_excel_file
    from file_validator.file_handlers import GCSFileHandler
    from file_validator.report_generator import generate_html_report
    from file_validator.utils import (
        calculate_time,
        format_bytes,
        parse_fwf_column_specification,
        setup_logging,
    )
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "The 'file_validator' core package is not importable.\n"
        "Make sure you run `uv sync` from the repository root to link workspace packages,\n"
        "or install the core package into the environment (e.g., `pip install -e ../file-validator-core`)."
    ) from exc


def _build_excel_sync(
    df: pl.DataFrame,
    primary_keys: list[str],
    excel_path: Path,
    sample_df: pl.DataFrame | None = None,
    header_comparison: list[dict[str, Any]] | None = None,
    trailer_comparison: list[dict[str, Any]] | None = None,
    source_rejects: pl.DataFrame | None = None,
    target_rejects: pl.DataFrame | None = None,
) -> None:
    build_and_save_excel_file(
        df,
        primary_keys,
        excel_path,
        sample_df=sample_df,
        header_comparison=header_comparison,
        trailer_comparison=trailer_comparison,
        source_rejects=source_rejects,
        target_rejects=target_rejects,
    )


_path_exists = async_path_exists
_list_files = async_list_files


logger: logging.Logger = logging.getLogger(__name__)

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
CONFIG_DIR: Path = REPO_ROOT / "configs"
LOGS_DIR: Path = REPO_ROOT / "logs" / "webserver"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
setup_logging(log_level="INFO", log_file=str(LOGS_DIR / "file_validator_webserver.log"))


def _log_file_size(file_path: str | Path, label: str = "File") -> None:
    """Log file size in human-readable format. Supports local and GCS (gs://) paths."""
    path_str = str(file_path)

    if path_str.startswith("gs:"):
        try:
            with GCSFileHandler() as handler:
                bucket_name, blob_path = handler.parse_gcs_uri(path_str)
                client = handler.gcs_client
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_path)

            blob.reload(timeout=10)
            file_size = blob.size or 0
            filename = Path(blob_path).name
            logger.info("%s: %s (%s) [GCS]", label, filename, format_bytes(file_size))
        except Exception as e:
            logger.warning("%s - could not retrieve GCS file info for %s: %s", label, path_str, e)
    else:
        path = Path(file_path)
        if path.exists():
            file_size = path.stat().st_size
            logger.info("%s: %s (%s)", label, path.name, format_bytes(file_size))
        else:
            logger.warning("%s not found: %s", label, path)


EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max(os.cpu_count() or 1, 4))


async def cleanup_uploaded_files() -> None:
    """Asynchronously cleanup all uploaded files."""
    if not await _path_exists(UPLOADS_DIR):
        return

    files_to_delete = await _list_files(UPLOADS_DIR)

    async def delete_file(file_path: Path) -> None:
        try:
            await async_unlink(file_path)
            logger.debug("Deleted upload file: %s", file_path.name)
        except Exception as e:
            logger.warning("Failed to delete upload file %s: %s", file_path, e)

    if files_to_delete:
        logger.info("Cleaning up %d uploaded file(s)...", len(files_to_delete))
        await asyncio.gather(*[delete_file(f) for f in files_to_delete])
        logger.info("Upload cleanup completed")


# TTL for cached parquet artifacts (seconds) and periodic cleanup interval
CACHE_TTL_SECONDS: int = 12 * 60 * 60  # 12 hours
CLEANUP_INTERVAL_SECONDS: int = 60 * 60  # 1 hour

# Simple lock to protect result_cache during concurrent access
_cache_lock = threading.Lock()


def _delete_cached_files_sync(job_id: str) -> None:
    """Delete parquet cache files and metadata for a job and remove from result_cache."""
    try:
        with _cache_lock:
            entry: dict[str, Any] | None = result_cache.get(job_id)
            if not entry:
                return
            df_path: str | Path | None = entry.get("df_path")
            sample_path: str | Path | None = entry.get("sample_df_path")
            with contextlib.suppress(KeyError):
                del result_cache[job_id]
        with contextlib.suppress(FileNotFoundError, OSError):
            if df_path:
                p = Path(df_path)
                if p.exists():
                    p.unlink()
        with contextlib.suppress(FileNotFoundError, OSError):
            if sample_path:
                sp = Path(sample_path)
                if sp.exists():
                    sp.unlink()
        meta_path = RESULT_CACHE_DIR / f"{job_id}_meta.json"
        with contextlib.suppress(FileNotFoundError, OSError):
            if meta_path.exists():
                meta_path.unlink()
    except Exception:
        return


def _cleanup_older_cached(ttl_seconds: int) -> None:
    """Remove cached parquet artifacts older than `ttl_seconds` and clear result_cache entries."""
    cutoff = time.time() - ttl_seconds
    try:
        for p in RESULT_CACHE_DIR.glob("*_results.parquet"):
            try:
                mtime = p.stat().st_mtime
                if mtime < cutoff:
                    name = p.name
                    job_id = name.rsplit("_results.parquet", 1)[0]
                    _delete_cached_files_sync(job_id)
                    with contextlib.suppress(FileNotFoundError):
                        if p.exists():
                            p.unlink()

                    sample_candidate = RESULT_CACHE_DIR / f"{job_id}_sample.parquet"
                    with contextlib.suppress(FileNotFoundError):
                        if sample_candidate.exists():
                            sample_candidate.unlink()

                    meta_candidate = RESULT_CACHE_DIR / f"{job_id}_meta.json"
                    with contextlib.suppress(FileNotFoundError):
                        if meta_candidate.exists():
                            meta_candidate.unlink()
            except Exception:
                continue
    except Exception:
        return


async def _periodic_cache_cleaner(
    ttl_seconds: int = CACHE_TTL_SECONDS, interval_seconds: int = CLEANUP_INTERVAL_SECONDS
):
    """Background coroutine that periodically removes old cached artifacts."""
    try:
        while True:
            await asyncio.to_thread(functools.partial(_cleanup_older_cached, ttl_seconds))
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        return


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("File Validator App starting up...")

    # Sweep stale temp dirs left by a previous unclean shutdown
    await asyncio.to_thread(_sweep_stale_temp_dirs)

    cleaner_task = asyncio.create_task(_periodic_cache_cleaner())

    try:
        yield
    finally:
        try:
            cleaner_task.cancel()
            await cleaner_task
        except Exception:
            pass

        # Shutdown executor gracefully
        logger.info("Shutting down executor...")
        await asyncio.to_thread(functools.partial(EXECUTOR.shutdown, wait=True, cancel_futures=True))
        await cleanup_uploaded_files()

        # Cleanup persisted result cache to free disk space using a sync helper
        try:
            await async_rmtree(RESULT_CACHE_DIR)
        except Exception as e:
            logger.warning("Failed to cleanup result cache on shutdown: %s", e)

        # Sweep stale temp dirs left by hard kills (safety net)
        logger.info("Sweeping stale auditor temp directories...")
        await asyncio.to_thread(_sweep_stale_temp_dirs)

        logger.info("File Validator App shutdown complete")


app = FastAPI(title="File Validator UI", lifespan=lifespan)

_PKG_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_PKG_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(_PKG_DIR / "static")), name="static")

job_store: dict[str, dict[str, Any]] = {}
result_cache: dict[str, dict[str, Any]] = {}

# Safety net for hard kills: sweep leftover temp dirs matching our prefixes
_TEMP_DIR_PREFIXES: tuple[str, ...] = ("duckdb_work_", "file_validator_")


def _sweep_stale_temp_dirs() -> None:
    """Last-resort sweep: remove any dirs in the system temp that match our prefixes."""
    tmp_root = Path(tempfile.gettempdir())
    removed = 0
    for prefix in _TEMP_DIR_PREFIXES:
        for d in tmp_root.glob(f"{prefix}*"):
            if d.is_dir():
                try:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
                    logger.debug("Swept stale temp dir: %s", d)
                except Exception as err:
                    logger.warning("Failed to sweep stale temp dir %s: %s", d, err)
    if removed:
        logger.info("Swept %d stale temp director(ies) from %s", removed, tmp_root)


REPORTS_DIR = REPO_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RESULT_CACHE_DIR = REPORTS_DIR / "_cache"
RESULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = _PKG_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class ValidatorConfig(BaseModel):
    """Configuration model for file validation requests."""

    job_name: str = Field(..., description="Job name/identifier")
    source_path: str
    source_filename: str | None = None
    target_path: str
    target_filename: str | None = None
    header_rows: int = 0
    trailer_patterns: list[str] | None = None
    delimiter: str = ","
    file_type: str = "csv"
    encoding: str = "utf-8"
    compression: str | None = None
    primary_keys: list[str] = Field(..., description="Primary key columns")
    column_specification: str | None = None
    normalization: NormalizationConfig = NormalizationConfig()


def generate_job_id(job_name: str, source_filename: str) -> str:
    """Generate a job ID in the format: <job_name>_<source_filename>_<timestamp>."""
    filename = Path(source_filename).stem if source_filename else "file"
    filename = "".join(c if c.isalnum() or c in "_-" else "_" for c in filename)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    job_name_clean = "".join(c if c.isalnum() or c in "_-" else "_" for c in job_name)

    return f"{job_name_clean}_{filename}_{timestamp}"


def build_normalization_config(norm: dict) -> NormalizationConfig:
    """Build a NormalizationConfig from a UI-provided dict."""
    logger.debug("Building normalization config from: %s", norm)
    normalization = norm.get("normalization", ["none"])
    normalize_dates = norm.get("normalize_dates", False)
    treat_null_as_empty = norm.get("treat_null_as_empty", False)
    ltrim_columns = norm.get("ltrim_columns", [])
    rtrim_columns = norm.get("rtrim_columns", [])
    trim_columns = norm.get("trim_columns", [])
    float_epsilon = norm.get("float_epsilon", None)
    trim_strings = "trim" in normalization
    return NormalizationConfig(
        trim_strings=trim_strings,
        normalize_dates=normalize_dates,
        treat_null_as_empty=treat_null_as_empty,
        ltrim_columns=ltrim_columns,
        rtrim_columns=rtrim_columns,
        trim_columns=trim_columns,
        float_epsilon=float_epsilon,
    )


# =============================================================
# API Endpoints
# =============================================================


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main UI page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon from the static directory."""
    return FileResponse(_PKG_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.post("/validate", response_class=JSONResponse)
async def start_validation(config: dict = Body(...)):
    normalization_config = build_normalization_config(config.get("normalization", {}))
    header_rows = config.get("header_rows", 0)
    if isinstance(header_rows, str) and not header_rows.strip().isdigit():
        header_rows = 0
    else:
        header_rows = int(header_rows)

    validator_config = ValidatorConfig(
        job_name=config["job_name"],
        source_path=config["source_path"],
        source_filename=config.get("source_filename"),
        target_path=config["target_path"],
        target_filename=config.get("target_filename"),
        header_rows=header_rows,
        trailer_patterns=config.get("trailer_patterns", []),
        delimiter=config.get("delimiter", ","),
        file_type=config.get("file_type", "csv"),
        encoding=config.get("encoding", "utf-8"),
        compression=config.get("compression"),
        primary_keys=config["primary_keys"],
        column_specification=config.get("column_specification"),
        normalization=normalization_config,
    )
    job_id = generate_job_id(
        validator_config.job_name, validator_config.source_filename or validator_config.source_path
    )
    job_store[job_id] = {"status": "pending", "progress": 0, "message": "Initializing...", "result": None}
    logger.info("Job %s: Validation job created (name: %s)", job_id, validator_config.job_name)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(EXECUTOR, run_validation_job, job_id, validator_config)
    return {"job_id": job_id, "status": "started"}


@app.post("/upload", response_class=JSONResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a local file and return its server path and original filename."""
    CHUNK_SIZE: int = 8 * (1024**2)  # 8 MB
    try:
        file_path = UPLOADS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        async with aiofiles.open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                await buffer.write(chunk)
        # Resolve saved path asynchronously
        try:
            resolved_path = await async_resolve(file_path)
            resolved = str(resolved_path)
        except Exception:
            resolved = str(file_path)
        return {"success": True, "path": resolved, "filename": file.filename}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/status/{job_id}", response_class=JSONResponse)
async def job_status(job_id: str):
    """Get the status of a validation job."""
    job = job_store.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
        "result": job["result"],
    }


@app.get("/report/{job_id}", response_class=FileResponse)
async def download_report(job_id: str):
    """Download the validation report for a job."""
    job = job_store.get(job_id)
    if not job or not job["result"]:
        return HTMLResponse(
            content=_ERROR_PAGE.format(
                msg="Report not found. Re-run the validation job to generate it again."
            ),
            status_code=404,
        )
    report_path = job["result"].get("html_report")
    if not report_path or not await _path_exists(Path(report_path)):
        return HTMLResponse(
            content=_ERROR_PAGE.format(
                msg="Report file missing. Re-run the validation job to generate it again."
            ),
            status_code=404,
        )
    return FileResponse(report_path, filename=f"{job_id}_report.html")


_ERROR_PAGE = (
    "<!DOCTYPE html><html><head><style>"
    "body{{font-family:'Segoe UI',Tahoma,sans-serif;display:flex;"
    "align-items:center;justify-content:center;height:100vh;margin:0;"
    "background:#1e1e1e;color:#e0e0e0}}"
    "@media(prefers-color-scheme:light){{body{{background:#f5f5f5;color:#333}}}}"
    "h1{{font-size:1.4rem}}"
    "</style></head><body><h1>{msg}</h1></body></html>"
)


@app.get("/report/{job_id}/view", response_class=HTMLResponse)
async def view_report(job_id: str):
    """View the validation report HTML inline (for iframe embedding)."""
    job = job_store.get(job_id)
    if not job or not job["result"]:
        return HTMLResponse(content=_ERROR_PAGE.format(msg="Report not found"), status_code=404)
    report_path = job["result"].get("html_report")
    if not report_path or not await _path_exists(Path(report_path)):
        return HTMLResponse(content=_ERROR_PAGE.format(msg="Report file missing"), status_code=404)
    async with aiofiles.open(report_path, encoding="utf-8") as f:
        content = await f.read()
    return HTMLResponse(content=content)


def _restore_cache_from_disk(job_id: str) -> dict[str, Any] | None:
    """
    Try to reconstruct a result_cache entry from on-disk parquet + metadata files.

    Returns the cache dict if the parquet results file and metadata JSON exist,
    otherwise returns None.  The restored entry is also inserted into the in-memory
    ``result_cache`` so subsequent calls are fast.
    """
    df_path = RESULT_CACHE_DIR / f"{job_id}_results.parquet"
    if not df_path.exists():
        return None

    meta_path = RESULT_CACHE_DIR / f"{job_id}_meta.json"
    primary_keys: list[str] = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            primary_keys = meta.get("primary_keys", [])
        except Exception:
            pass

    sample_df_path = RESULT_CACHE_DIR / f"{job_id}_sample.parquet"
    entry: dict[str, Any] = {
        "df_path": str(df_path),
        "sample_df_path": str(sample_df_path) if sample_df_path.exists() else None,
        "primary_keys": primary_keys,
    }
    with _cache_lock:
        result_cache[job_id] = entry
    return entry


@app.get("/report/{job_id}/excel-available", response_class=JSONResponse)
async def excel_available(job_id: str):
    """
    Check whether parquet cache exists for a job, enabling Excel export.

    Returns 200 with ``{"available": true}`` when the results parquet is on disk
    (regardless of whether the job is still in ``job_store``).  The HTML report
    template uses this endpoint to decide whether to show the Download Excel button.
    """
    # Fast path: already in memory
    if result_cache.get(job_id):
        return JSONResponse(content={"available": True})

    # Try restoring from disk
    restored = await asyncio.to_thread(_restore_cache_from_disk, job_id)
    if restored:
        return JSONResponse(content={"available": True})

    return JSONResponse(status_code=404, content={"available": False})


@app.get("/report/{job_id}/excel")
async def download_report_excel(job_id: str):
    """
    Generate and stream Excel report for a job on-demand without keeping large bytes in memory.

    This implementation builds the .xlsx on disk using a write-only workbook (incremental)
    to keep memory usage bounded, then streams the file to the client. After streaming
    completes the background task deletes the generated .xlsx file.

    The endpoint works for both current-session jobs (in ``job_store``) and saved
    reports whose parquet cache still exists on disk — enabling Excel download from
    the "Recent Reports" viewer without re-validating.
    """
    # Try in-memory cache first, then fall back to disk restoration
    cached: dict[str, Any] | None = result_cache.get(job_id)
    if not cached:
        cached = await asyncio.to_thread(_restore_cache_from_disk, job_id)
    if not cached:
        return HTMLResponse(
            content=_ERROR_PAGE.format(
                msg="Report data not found. Re-run the validation job to generate it again."
            ),
            status_code=404,
        )

    try:
        df: pl.DataFrame = pl.read_parquet(cached["df_path"]) if cached.get("df_path") else pl.DataFrame()
        sample_df: pl.DataFrame | None = (
            pl.read_parquet(cached["sample_df_path"]) if cached.get("sample_df_path") else None
        )

        excel_path = RESULT_CACHE_DIR / f"{job_id}_report.xlsx"

        await asyncio.to_thread(
            functools.partial(
                _build_excel_sync,
                df,
                cached.get("primary_keys", []),
                excel_path,
                sample_df,
                cached.get("header_comparison"),
                cached.get("trailer_comparison"),
                cached.get("source_rejects"),
                cached.get("target_rejects"),
            )
        )

        # Clean up only the generated xlsx after the response is sent.
        # Keep the parquet cache so the user can re-download Excel later;
        # the periodic TTL cleaner will eventually reclaim old cache files.
        def _cleanup_xlsx_after_download(excel_path_local: str) -> None:
            try:
                p = Path(excel_path_local)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        bg = BackgroundTask(lambda: _cleanup_xlsx_after_download(str(excel_path)))

        return FileResponse(
            path=str(excel_path),
            filename=f"{job_id}_report.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            background=bg,
        )

    except Exception as e:
        logger.exception("Failed to generate Excel for job %s: %s", job_id, e)
        return HTMLResponse(
            content=_ERROR_PAGE.format(
                msg="Failed to generate Excel report. Re-run the validation job to generate it again."
            ),
            status_code=500,
        )


@app.get("/cache/stats", response_class=JSONResponse)
async def cache_stats():
    """
    Return simple statistics about the on-disk result cache.

    Example output:
    {
      "files": 3,
      "total_bytes": 12345,
      "oldest_mtime": 167...,
      "newest_mtime": 167...
    }
    """
    stats = await asyncio.to_thread(functools.partial(_get_cache_stats_sync))
    return JSONResponse(content=stats)


def _get_cache_stats_sync() -> dict[str, Any]:
    """Compute cache statistics (synchronous helper)."""
    try:
        stats = {"files": 0, "total_bytes": 0, "oldest_mtime": None, "newest_mtime": None}
        if not RESULT_CACHE_DIR.exists():
            return stats
        files = [p for p in RESULT_CACHE_DIR.rglob("*") if p.is_file()]
        stats["files"] = len(files)
        total = 0
        mtimes = []
        for f in files:
            try:
                s = f.stat()
                total += s.st_size
                mtimes.append(s.st_mtime)
            except Exception:
                continue
        stats["total_bytes"] = total
        if mtimes:
            stats["oldest_mtime"] = min(mtimes)
            stats["newest_mtime"] = max(mtimes)
        return stats
    except Exception:
        return {"files": 0, "total_bytes": 0, "oldest_mtime": None, "newest_mtime": None}


# =============================================================
# Recent Reports (persisted HTML reports on disk)
# =============================================================

_MAX_RECENT_REPORTS: int = 10


def _list_recent_reports_sync(limit: int = _MAX_RECENT_REPORTS) -> list[dict[str, Any]]:
    """Scan REPORTS_DIR for the most recent HTML report files and return metadata."""
    try:
        if not REPORTS_DIR.exists():
            return []
        report_files: list[Path] = sorted(
            REPORTS_DIR.glob("*_report.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        results: list[dict[str, Any]] = []
        for f in report_files:
            try:
                stat = f.stat()
                job_id: str = f.stem.removesuffix("_report")
                has_excel: bool = (RESULT_CACHE_DIR / f"{job_id}_results.parquet").exists()
                results.append(
                    {
                        "job_id": job_id,
                        "filename": f.name,
                        "size_bytes": stat.st_size,
                        "size_human": format_bytes(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "modified_ts": stat.st_mtime,
                        "has_excel": has_excel,
                    }
                )
            except Exception:
                continue
        return results
    except Exception:
        return []


@app.get("/reports/recent", response_class=JSONResponse)
async def recent_reports():
    """Return metadata for the last N HTML reports on disk."""
    reports = await asyncio.to_thread(_list_recent_reports_sync)
    return JSONResponse(content={"reports": reports})


@app.get("/reports/{filename}/view", response_class=HTMLResponse)
async def view_saved_report(filename: str):
    """View a previously saved HTML report inline (iframe-safe)."""
    # Sanitize: only allow filenames ending in _report.html, no path traversal
    if not filename.endswith("_report.html") or "/" in filename or "\\" in filename:
        return HTMLResponse(content=_ERROR_PAGE.format(msg="Invalid filename"), status_code=400)
    report_path = REPORTS_DIR / filename
    if not await _path_exists(report_path):
        return HTMLResponse(content=_ERROR_PAGE.format(msg="Report not found"), status_code=404)
    async with aiofiles.open(report_path, encoding="utf-8") as f:
        content = await f.read()
    return HTMLResponse(content=content)


@app.get("/reports/{filename}/download")
async def download_saved_report(filename: str):
    """Download a previously saved HTML report file."""
    if not filename.endswith("_report.html") or "/" in filename or "\\" in filename:
        return HTMLResponse(
            content=_ERROR_PAGE.format(msg="Invalid filename."),
            status_code=400,
        )
    report_path = REPORTS_DIR / filename
    if not await _path_exists(report_path):
        return HTMLResponse(
            content=_ERROR_PAGE.format(
                msg="Report not found. Re-run the validation job to generate it again."
            ),
            status_code=404,
        )
    return FileResponse(str(report_path), filename=filename)


# =============================================================
# Background Job Runner
# =============================================================


def update_job_progress(job_id: str, progress: int, message: str, status: str = "running"):
    """Update job progress and status."""
    if job_id in job_store:
        job_store[job_id]["progress"] = progress
        job_store[job_id]["message"] = message
        job_store[job_id]["status"] = status
        logger.info("Job %s: [%s%%] %s", job_id, progress, message)


def run_validation_job(job_id: str, config: ValidatorConfig):
    """Run the file validation job (background task)."""
    start_time = time.monotonic()

    try:
        logger.info("=" * 60)
        logger.info("Job %s: Starting File Validation", job_id)
        logger.info("=" * 60)

        # Step 1: Initialize (5%)
        update_job_progress(job_id, 5, "Initializing configuration...")

        _env_file: Path = CONFIG_DIR / ".env"
        logger.debug("Loading environment variables from %s", _env_file)
        load_dotenv(dotenv_path=_env_file)

        # Refresh OIDC token upfront so GCS operations don't hit stale credentials
        try:
            auto_refresh_oidc_token_if_needed()
            logger.info("Job %s: OIDC token refreshed successfully", job_id)
        except Exception as e:
            logger.warning("Job %s: OIDC token refresh failed (may not be needed): %s", job_id, e)

        fwf_cols_specs: COLS_SPEC | None = None
        if config.file_type.lower() == "fwf" and config.column_specification:
            fwf_cols_specs: COLS_SPEC | None = parse_fwf_column_specification(config.column_specification)

        source_conf = FileConfig(
            path=config.source_path,
            file_type=config.file_type,
            delimiter=config.delimiter,
            header_rows=config.header_rows,
            trailer_patterns=config.trailer_patterns or [],
            encoding=config.encoding,
            compression=config.compression,
            col_specs=fwf_cols_specs,
        )

        target_conf = FileConfig(
            path=config.target_path,
            file_type=config.file_type,
            delimiter=config.delimiter,
            header_rows=config.header_rows,
            trailer_patterns=config.trailer_patterns or [],
            encoding=config.encoding,
            compression=config.compression,
            col_specs=fwf_cols_specs,
        )

        logger.info("Job %s: Source path: %s", job_id, config.source_path)
        logger.info("Job %s: Target path: %s", job_id, config.target_path)
        logger.info("Job %s: Primary keys: %s", job_id, ", ".join(config.primary_keys))
        logger.info("Job %s: Delimiter: %s", job_id, config.delimiter)
        logger.info("Job %s: Header rows: %s", job_id, config.header_rows)
        logger.info("Job %s: File type: %s", job_id, config.file_type)
        logger.info("Job %s: Encoding: %s", job_id, config.encoding)

        _log_file_size(config.source_path, f"Job {job_id}: Source file")
        _log_file_size(config.target_path, f"Job {job_id}: Target file")

        update_job_progress(job_id, 10, "Configuration initialized")

        # Step 2: Create auditor (15%)
        update_job_progress(job_id, 15, "Creating file auditor...")

        with FileAuditor(
            source_config=source_conf,
            target_config=target_conf,
            primary_keys=config.primary_keys,
            norm_config=config.normalization,
        ) as auditor:
            # Step 3: Load data (40%)
            update_job_progress(job_id, 20, "Loading source file...")
            auditor.load_data()
            update_job_progress(job_id, 40, "Data loaded successfully")

            logger.info("Job %s: Source rows: %s", job_id, f"{auditor.source_row_count:,}")
            logger.info("Job %s: Target rows: %s", job_id, f"{auditor.target_row_count:,}")

            # Step 4: Run comparison (70%)
            update_job_progress(job_id, 50, "Running comparison...")
            results = auditor.run_comparison()
            update_job_progress(job_id, 70, "Comparison completed")

            logger.info("Job %s: Matching rows: %s", job_id, f"{auditor.matching_rows_count:,}")
            logger.info(
                "Job %s: Mismatched rows (value diffs): %s", job_id, f"{auditor.mismatched_rows_count:,}"
            )
            logger.info("Job %s: Missing in source: %s", job_id, f"{auditor.missing_in_source_count:,}")
            logger.info("Job %s: Match percentage: %s%%", job_id, f"{auditor.match_percentage:.2f}")
            logger.info("Job %s: Row count diff (Source - Target): %s", job_id, f"{auditor.row_count_diff:,}")
            logger.info("Job %s: Match percentage: %.2f%%", job_id, auditor.match_percentage)

            # Step 5: Generate sample data if 100% match (75%)
            sample_df: pl.DataFrame | None = None
            if results.is_empty():
                update_job_progress(job_id, 75, "Generating sample data (100% match)...")
                sample_df = auditor.get_sample_data()

            # Step 6: Generate HTML report (90%)
            update_job_progress(job_id, 80, "Generating HTML report...")

            report_path: Path = REPORTS_DIR / f"{job_id}_report.html"
            generate_html_report(
                df=results,
                output_file=report_path,
                primary_keys=auditor.primary_keys,
                sample_df=sample_df,
                header_comparison=auditor.header_comparison,
                trailer_comparison=auditor.trailer_comparison,
                source_rejects=auditor.source_rejects,
                target_rejects=auditor.target_rejects,
                source_file=config.source_path,
                target_file=config.target_path,
                source_file_type=auditor.source.file_type,
                target_file_type=auditor.target.file_type,
                source_delimiter=auditor.source.delimiter,
                target_delimiter=auditor.target.delimiter,
                source_col_specs=auditor.source.col_specs,
                target_col_specs=auditor.target.col_specs,
                job_id=job_id,
                source_count=auditor.source_row_count,
                target_count=auditor.target_row_count,
                matching_rows=auditor.matching_rows_count,
                mismatched_rows=auditor.mismatched_rows_count,
                match_percentage=auditor.match_percentage,
                missing_in_source=auditor.missing_in_source_count,
                missing_in_target=auditor.missing_in_target_count,
                row_count_diff=auditor.row_count_diff,
            )

            update_job_progress(job_id, 90, "Report generated")
            logger.info("Job %s: Report saved to: %s", job_id, report_path)

            # Persist results to disk as Parquet for later Excel export
            df_path: Path = RESULT_CACHE_DIR / f"{job_id}_results.parquet"
            sample_df_path: Path | None = (
                RESULT_CACHE_DIR / f"{job_id}_sample.parquet" if sample_df is not None else None
            )

            try:
                results.write_parquet(df_path, compression="snappy")
                logger.info("Job %s: Results DataFrame persisted to: %s", job_id, df_path)
            except Exception as e:
                logger.warning("Job %s: Failed to persist results DataFrame: %s", job_id, e)

            # if sample_df is not None:
            if sample_df and sample_df_path:
                try:
                    sample_df.write_parquet(sample_df_path, compression="snappy")
                    logger.info("Job %s: Sample DataFrame persisted to: %s", job_id, sample_df_path)
                except Exception as e:
                    logger.warning("Job %s: Failed to persist sample DataFrame: %s", job_id, e)

            result_cache[job_id] = {
                "df_path": str(df_path),
                "sample_df_path": str(sample_df_path) if sample_df_path else None,
                "primary_keys": auditor.primary_keys,
            }

            meta_path = RESULT_CACHE_DIR / f"{job_id}_meta.json"
            try:
                meta_path.write_text(json.dumps({"primary_keys": auditor.primary_keys}), encoding="utf-8")
            except Exception as e:
                logger.warning("Job %s: Failed to persist cache metadata: %s", job_id, e)

            # Cleanup (95%) — auditor.close() runs automatically on exit
            update_job_progress(job_id, 95, "Cleaning up resources...")

            # Capture (100%) summary before context manager exits
            summary: dict[str, int | float] = {
                "source_count": auditor.source_row_count,
                "target_count": auditor.target_row_count,
                "matching_rows": auditor.matching_rows_count,
                "mismatched_rows": auditor.mismatched_rows_count,
                "missing_in_source": auditor.missing_in_source_count,
                "missing_in_target": auditor.missing_in_target_count,
                "match_percentage": auditor.match_percentage,
                "row_count_diff": auditor.row_count_diff,
            }

        end_time: float = time.monotonic()
        elapsed_time: str = calculate_time(start_time, end_time)

        job_store[job_id]["status"] = "completed"
        job_store[job_id]["progress"] = 100
        job_store[job_id]["message"] = f"Completed in {elapsed_time}"
        job_store[job_id]["result"] = {"html_report": str(report_path), "summary": summary}

        result_cache[job_id]["summary"] = summary

        logger.info("=" * 60)
        logger.info("Job %s: Validation completed successfully", job_id)
        logger.info("Job %s: Total time elapsed: %s", job_id, elapsed_time)
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("Job %s: Validation failed with error: %s", job_id, e)
        job_store[job_id]["status"] = "error"
        job_store[job_id]["progress"] = 0
        job_store[job_id]["message"] = str(e)
        job_store[job_id]["result"] = {"error": str(e)}


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting File Validator App...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
