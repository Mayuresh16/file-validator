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

"""HTML report generation for file validation results."""

import logging
import shutil
import time
from pathlib import Path
from typing import Any

import pendulum
import polars as pl
from jinja2 import Template

logger: logging.Logger = logging.getLogger(__name__)


def generate_html_report(
    df: pl.DataFrame,
    output_file: str | Path,
    primary_keys: list[str],
    sample_df: pl.DataFrame | None = None,
    header_comparison: list[dict[str, str | int]] | None = None,
    trailer_comparison: list[dict[str, str | int]] | None = None,
    source_rejects: pl.DataFrame | None = None,
    target_rejects: pl.DataFrame | None = None,
    source_file: str | Path | None = None,
    target_file: str | Path | None = None,
    source_file_type: str | None = None,
    target_file_type: str | None = None,
    source_delimiter: str | None = None,
    target_delimiter: str | None = None,
    source_col_specs: list[tuple[int, int]] | None = None,
    target_col_specs: list[tuple[int, int]] | None = None,
    job_id: str | None = None,
    job_name: str | None = None,
    report_dir: str | Path | None = None,
    **summary_stats: int | float | str,
) -> None:
    """
    Generate a professional HTML report from validation data.

    Args:
        df: Polars DataFrame with comparison results
        output_file: Path for output HTML file
        primary_keys: List of primary key column names
        sample_df: Optional sample data for 100% match scenarios
        header_comparison: Header line comparison results
        trailer_comparison: Trailer line comparison results
        source_rejects: Rejected rows from source file
        target_rejects: Rejected rows from target file
        source_file: Path to source file
        target_file: Path to target file
        source_file_type: Source file type (csv, psv, fwf)
        target_file_type: Target file type (csv, psv, fwf)
        source_delimiter: Delimiter character for delimited source
        target_delimiter: Delimiter character for delimited target
        source_col_specs: Column specifications for FWF source
        target_col_specs: Column specifications for FWF target
        job_id: Pre-generated job ID. If None, one is generated automatically
            using the format ``<job_name>_<source_filename>_<timestamp>``.
        job_name: Logical name for the validation job. Used when auto-generating
            ``job_id``. Defaults to ``"validation"`` when neither ``job_id`` nor
            ``job_name`` is supplied.
        report_dir: Optional directory to save a copy of the generated report.
            When provided, the report is copied into this directory and any
            report files older than 7 days are automatically purged.
        **summary_stats: Additional summary statistics
    """
    output_file = Path(output_file)

    working_df: pl.DataFrame = sample_df if sample_df is not None and not sample_df.is_empty() else df

    status_cols: list[str] = [c for c in working_df.columns if c.endswith("_status")]
    data_cols: list[str] = [c.replace("_status", "") for c in status_cols if c != "validation_status"]

    if not data_cols:
        all_cols: list[str] = [
            c for c in working_df.columns if not c.endswith(("_source", "_target", "_status"))
        ]
        data_cols = [c for c in all_cols if c not in primary_keys and c != "validation_status"]

    # Debug output
    logger.debug("DataFrame shape: %s", df.shape)
    logger.debug("Sample DataFrame: %s", "Yes" if sample_df is not None else "No")
    logger.debug("Working DataFrame columns: %s", list(working_df.columns)[:10])
    logger.debug("Status columns found: %s", status_cols[:5])
    logger.debug("Data columns: %s", data_cols)
    logger.debug("Primary keys: %s", primary_keys)

    template_path: Path = Path(__file__).parent / "templates" / "html_report.html"
    try:
        template_str: str = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Template file not found at %s", template_path.resolve())
        template_str: str = _get_fallback_template()

    logger.info("=" * 60)
    logger.info("Generating HTML Report: %s", output_file.resolve())
    logger.info("=" * 60)

    # Convert to list of dicts for Jinja template
    source_rejects_list: list[dict[str, Any]] = []
    target_rejects_list: list[dict[str, Any]] = []

    if source_rejects is not None and not source_rejects.is_empty():
        source_rejects_list = source_rejects.to_dicts()

    if target_rejects is not None and not target_rejects.is_empty():
        target_rejects_list = target_rejects.to_dicts()

    data_list: list[dict[str, Any]] = df.to_dicts() if not df.is_empty() else []
    sample_data_list: list[dict[str, Any]] = (
        sample_df.to_dicts() if sample_df is not None and not sample_df.is_empty() else []
    )

    # Pagination for sample data
    max_initial_display: int = 20
    total_sample_records: int = len(sample_data_list)
    has_more_records: bool = total_sample_records > max_initial_display

    if source_file and str(source_file).startswith("gs://"):
        source_filename = str(source_file).rsplit("/", 1)[-1]
        target_filename = str(target_file).rsplit("/", 1)[-1]
        source_full_path = str(source_file)
        target_full_path = str(target_file)
    else:
        source_filename: str = Path(source_file).name if source_file else "Unknown Source"
        target_filename: str = Path(target_file).name if target_file else "Unknown Target"
        source_full_path: str = str(Path(source_file).resolve()) if source_file else "N/A"
        target_full_path: str = str(Path(target_file).resolve()) if target_file else "N/A"

    # File type and delimiter display labels
    _FILE_TYPE_LABELS: dict[str, str] = {
        "csv": "CSV (Comma-Separated)",
        "psv": "PSV (Pipe-Separated)",
        "fwf": "Fixed-Width",
    }
    source_file_type_display: str = _FILE_TYPE_LABELS.get(
        (source_file_type or "").lower(), source_file_type or "Unknown"
    )
    target_file_type_display: str = _FILE_TYPE_LABELS.get(
        (target_file_type or "").lower(), target_file_type or "Unknown"
    )

    _DELIMITER_LABELS: dict[str, str] = {
        ",": ", (comma)",
        "|": "| (pipe)",
        "\t": "\\t (tab)",
    }
    source_delimiter_display: str = (
        _DELIMITER_LABELS.get(source_delimiter, repr(source_delimiter))
        if source_delimiter and (source_file_type or "").lower() != "fwf"
        else "N/A"
    )
    target_delimiter_display: str = (
        _DELIMITER_LABELS.get(target_delimiter, repr(target_delimiter))
        if target_delimiter and (target_file_type or "").lower() != "fwf"
        else "N/A"
    )

    # Format FWF column specifications for display
    def _fmt_col_specs(specs: list[tuple[int, int]] | None) -> str:
        if not specs:
            return "N/A"
        # Show a compact representation, e.g. "(0,5), (5,15), ..."
        parts = [f"({s},{e})" for s, e in specs]
        preview = ", ".join(parts[:8])
        if len(parts) > 8:
            preview += f", … ({len(parts)} cols total)"
        return preview

    source_col_specs_display: str = _fmt_col_specs(source_col_specs)
    target_col_specs_display: str = _fmt_col_specs(target_col_specs)

    # Generate job ID with UTC timestamp
    utc_now: pendulum.DateTime = pendulum.now("UTC")
    timestamp_utc: str = utc_now.format("YYYYMMDD_HHmmss")

    if job_id is None:
        # Generate job ID: <job_name>_<source_filename>_<timestamp>
        source_basename: str = Path(source_file).stem if source_file else "unknown"
        source_basename = "".join(c if c.isalnum() or c in "_-" else "_" for c in source_basename)
        effective_job_name: str = job_name or "validation"
        effective_job_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in effective_job_name)
        job_id = f"{effective_job_name}_{source_basename}_{timestamp_utc}"

    local_now: pendulum.DateTime = pendulum.now(tz=pendulum.local_timezone())  # ty:ignore[invalid-argument-type]
    local_tz_name: str = str(local_now.timezone_name)

    # Format timestamps for display (UTC, local, IST, ET)
    report_time_utc: str = utc_now.format("YYYY-MM-DD HH:mm:ss")
    report_time_utc_full: str = f"{report_time_utc} UTC"

    local_time: pendulum.DateTime = utc_now.in_timezone(local_tz_name)
    report_time_local: str = local_time.format("YYYY-MM-DD HH:mm:ss")
    local_tz_abbr: str = local_time.format("zz")
    report_time_local_full: str = f"{report_time_local} {local_tz_abbr}"

    ist_time: pendulum.DateTime = utc_now.in_timezone("Asia/Kolkata")
    report_time_ist: str = ist_time.format("YYYY-MM-DD HH:mm:ss")
    report_time_ist_full: str = f"{report_time_ist} IST"

    et_time: pendulum.DateTime = utc_now.in_timezone("America/New_York")
    report_time_et: str = et_time.format("YYYY-MM-DD HH:mm:ss")
    et_tz_abbr: str = et_time.format("zz")
    report_time_et_full: str = f"{report_time_et} {et_tz_abbr}"

    Template(template_str).stream(
        pks=primary_keys,
        cols=data_cols,
        data=data_list,
        sample_data=sample_data_list,
        max_initial_display=max_initial_display,
        total_sample_records=total_sample_records,
        has_more_records=has_more_records,
        header_comparison=header_comparison or [],
        trailer_comparison=trailer_comparison or [],
        source_rejects=source_rejects_list,
        target_rejects=target_rejects_list,
        source_filename=source_filename,
        target_filename=target_filename,
        source_full_path=source_full_path,
        target_full_path=target_full_path,
        source_file_type=source_file_type_display,
        target_file_type=target_file_type_display,
        source_delimiter=source_delimiter_display,
        target_delimiter=target_delimiter_display,
        source_col_specs=source_col_specs_display,
        target_col_specs=target_col_specs_display,
        source_is_fwf=(source_file_type or "").lower() == "fwf",
        target_is_fwf=(target_file_type or "").lower() == "fwf",
        job_id=job_id,
        timestamp_utc=timestamp_utc,
        report_time_utc=report_time_utc_full,
        report_time_local=report_time_local_full,
        report_time_ist=report_time_ist_full,
        report_time_et=report_time_et_full,
        local_tz_name=local_tz_name,
        local_tz_abbr=local_tz_abbr,
        **summary_stats,
    ).dump(str(output_file))

    logger.info("Report generated successfully: %s", output_file.resolve())

    if report_dir is not None:
        report_dir_path = Path(report_dir)
        try:
            report_dir_path.mkdir(parents=True, exist_ok=True)
            dest_path = report_dir_path / output_file.name
            shutil.copy2(str(output_file), str(dest_path))
            logger.info("Report copied to report directory: %s", dest_path)
            _cleanup_old_reports(report_dir_path)
        except OSError as exc:
            logger.warning("Failed to copy report to %s: %s", report_dir_path, exc)


def _cleanup_old_reports(report_dir: Path, max_age_days: int = 7) -> None:
    """Delete HTML report files older than *max_age_days* from *report_dir*."""
    cutoff = time.time() - (max_age_days * 86_400)
    removed = 0
    for path in report_dir.glob("*_report.html"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
                logger.debug("Removed old report: %s", path.name)
        except OSError as exc:
            logger.warning("Failed to remove old report %s: %s", path.name, exc)
    if removed:
        logger.info("Cleaned up %d report(s) older than %d days from %s", removed, max_age_days, report_dir)


def _get_fallback_template() -> str:
    """Return a minimal fallback template if the main template is missing."""
    html_content: str = """<!DOCTYPE html>
    <html>
    <head>
        <title>Validation Report</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .error { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1 class="error">Template Error</h1>
        <p>The report template file (html_report.html) was not found.</p>
        <p>Please ensure it exists in the same directory as the Python modules.</p>
    </body>
    </html>"""

    return html_content
