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

"""
Main file auditing and comparison engine.

This module contains the FileAuditor class that orchestrates file loading,
comparison, and validation using DuckDB.

DuckDB natively supports:
- GCS files via httpfs extension (gs://bucket/path)
- Gzip compressed files (.gz)
- Various CSV/delimited formats
"""

import contextlib
import itertools
import logging
import os
import re
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, Self

import duckdb
import polars as pl

from file_validator.config import FileConfig, NormalizationConfig
from file_validator.converters import PolarsFWFConverter
from file_validator.file_handlers import (
    GCSFileHandler,
    decompress_file,
    get_compression_type,
    is_gcs_path,
)

logger: logging.Logger = logging.getLogger(__name__)


def _char_diff(src: str, tgt: str) -> list[dict]:
    """
    Compare two strings character-by-character and return a list of per-character diff entries.

    Each entry is a dict with:
        pos   - 0-based character position
        src   - character from source (or None if past end)
        tgt   - character from target (or None if past end)
        match - True when both characters are identical

    Only positions that differ are included to keep the payload small.
    If the lines are identical the returned list is empty.
    """
    diffs: list[dict] = []
    max_len: int = max(len(src), len(tgt))
    for pos in range(max_len):
        s_ch: str | None = src[pos] if pos < len(src) else None
        t_ch: str | None = tgt[pos] if pos < len(tgt) else None
        if s_ch != t_ch:
            diffs.append({"pos": pos, "src": s_ch, "tgt": t_ch, "match": False})
    return diffs


def _normalize_column_names(columns: str | Sequence[str], sep: str = ",") -> list[str]:
    cols: list[str] = columns.split(sep) if isinstance(columns, str) else list(columns)
    return [col.strip().lower().replace(" ", "_") for col in cols]


def _enclosed_double_quotes(s: str) -> str:
    return f'"{s}"'


class FileAuditor:
    """Main engine for file comparison and validation with sophisticated normalization."""

    def __init__(
        self,
        source_config: FileConfig,
        target_config: FileConfig,
        primary_keys: list[str],
        norm_config: NormalizationConfig | None = None,
        memory_limit: str = "6GB",
        threads: int = 4,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        """
        Initialize the FileAuditor.

        Args:
            source_config: Configuration for source file
            target_config: Configuration for target file
            primary_keys: List of column names that form the primary key
            norm_config: Normalization rules
            memory_limit: DuckDB memory limit
            threads: Number of threads for DuckDB
            conn: Optional pre-existing DuckDB connection to reuse.
                  When supplied the auditor does **not** own the connection
                  and will not close it on ``close()`` / context-manager exit.
        """
        self._has_duplicate_keys: bool = False
        self.source: FileConfig = source_config
        self.target: FileConfig = target_config
        self.primary_keys: list[str] = _normalize_column_names(list(dict.fromkeys(primary_keys)))
        self.norm: NormalizationConfig = norm_config or NormalizationConfig()

        if conn is not None:
            # Reuse an externally-managed connection (e.g. from a test fixture).
            self.conn: duckdb.DuckDBPyConnection = conn
            self._owns_conn: bool = False
            self._duckdb_work_dir: Path = Path(tempfile.mkdtemp(prefix="duckdb_work_"))
            logger.info("Reusing external DuckDB connection")
        else:
            # File-backed DB so the buffer manager can spill to disk instead of OOM.
            # Each auditor gets its own temp dir to avoid collisions across concurrent runs.
            self._duckdb_work_dir = Path(tempfile.mkdtemp(prefix="duckdb_work_"))
            _db_path = (self._duckdb_work_dir / "work.duckdb").as_posix()
            self.conn = duckdb.connect(database=_db_path)
            self._owns_conn: bool = True

            _memory_limit: str = str(os.getenv("DUCKDB_MEMORY_LIMIT", memory_limit)).strip().upper()
            self.conn.execute(f"PRAGMA memory_limit='{_memory_limit}'")
            logger.debug("DuckDB memory_limit=%s", _memory_limit)

            self.conn.execute(f"PRAGMA threads={threads}")

            _preserve_order: str = str(os.getenv("DUCKDB_PRESERVE_INSERTION_ORDER", "false")).strip().lower()
            self.conn.execute(f"SET preserve_insertion_order={_preserve_order}")
            logger.debug("DuckDB preserve_insertion_order=%s", _preserve_order)

            # Spill dir for intermediate operators (ORDER BY, hash-join, window functions)
            _temp_dir = self._duckdb_work_dir.resolve().as_posix()
            self.conn.execute(f"PRAGMA temp_directory='{_temp_dir}'")

            # allocator_flush_threshold — env var overrides the default (256MB)
            _flush_threshold: str = (
                str(os.getenv("DUCKDB_ALLOCATOR_FLUSH_THRESHOLD", "256MB")).strip().upper()
            )
            with contextlib.suppress(Exception):
                self.conn.execute(f"PRAGMA allocator_flush_threshold='{_flush_threshold}'")
                logger.debug("DuckDB allocator_flush_threshold=%s", _flush_threshold)

            logger.info("DuckDB file-backed database: %s", _db_path)
            logger.info("DuckDB temp/spill directory: %s", _temp_dir)
            logger.info(
                "DuckDB config: memory_limit=%s, threads=%s, preserve_insertion_order=%s, allocator_flush_threshold=%s",
                _memory_limit,
                threads,
                _preserve_order,
                _flush_threshold,
            )

        self.source_headers: list[str] = []
        self.target_headers: list[str] = []
        self.source_trailers: list[str] = []
        self.target_trailers: list[str] = []
        self.header_comparison: list[dict[str, str | int]] | None = None
        self.trailer_comparison: list[dict[str, str | int]] | None = None
        self.source_rejects: pl.DataFrame | None = None
        self.target_rejects: pl.DataFrame | None = None
        self.temp_files: list[Path] = []

        self.temp_dir: Path = Path(tempfile.mkdtemp(prefix="file_validator_"))
        self.file_handler: GCSFileHandler = GCSFileHandler(self.temp_dir)

        # Only load httpfs and configure GCS credentials when at least one
        # file is actually on GCS to avoid expensive credential-chain probes.
        self._needs_gcs: bool = self.source.is_gcs or self.target.is_gcs
        if self._needs_gcs:
            self._setup_gcs_support()

        self._source_resolved_path: str | None = None
        self._target_resolved_path: str | None = None

        self._source_local_path: Path | None = None
        self._target_local_path: Path | None = None

        self.source_row_count: int = 0
        self.target_row_count: int = 0
        self.missing_in_source_count: int = 0
        self.missing_in_target_count: int = 0
        self.mismatched_rows_count: int = 0
        self.matching_rows_count: int = 0
        self.match_percentage: float = 0.0
        self.row_count_diff: int = 0
        self._closed: bool = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """
        Close the DuckDB connection and clean up all resources.

        When using an externally-provided connection (``_owns_conn=False``),
        the connection itself is left open but tables/views created by this
        auditor are dropped so the next auditor starts with a clean slate.

        Alternatively, use the auditor as a context manager:

            with FileAuditor(source, target, pks) as auditor:
                auditor.run_comparison()
        """
        if self._closed:
            return
        self._closed = True

        if self._owns_conn:
            # Close DuckDB before cleanup to release .duckdb file handle
            # (Windows blocks open handles during deletion).
            try:
                self.conn.close()
                logger.info("DuckDB connection closed")
            except Exception as e:
                logger.warning("Error closing DuckDB connection: %s", e)
        else:
            for obj in ("source_data", "target_data"):
                with contextlib.suppress(Exception):
                    self.conn.execute(f"DROP VIEW IF EXISTS {obj}")
                    self.conn.execute(f"DROP TABLE IF EXISTS {obj}")
            logger.info("DuckDB shared connection cleaned (views/tables dropped)")

        self.cleanup_temp_files()

    def __del__(self) -> None:
        if not getattr(self, "_closed", True) and getattr(self, "_owns_conn", False):
            with contextlib.suppress(Exception):
                self.conn.close()

    def _setup_gcs_support(self) -> None:
        """
        Set up DuckDB httpfs extension for reading GCS URIs directly.

        Authenticates via GOOGLE_APPLICATION_CREDENTIALS (service account key
        or Workload Identity Pool config). Falls back to credential_chain
        if explicit token acquisition fails.
        """
        try:
            self.conn.execute("LOAD httpfs;")

            gcp_creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if gcp_creds_path:
                logger.debug("Using GCP credentials from: %s", gcp_creds_path)
                try:
                    access_token: str | None = self.file_handler.get_gcs_access_token()
                    if not access_token:
                        raise ValueError("get_gcs_access_token() returned None or empty token")

                    logger.debug(
                        "Access token obtained (length=%d) access_token=%r",
                        len(access_token),
                        access_token[:20],
                    )

                    self.conn.execute("DROP SECRET IF EXISTS gcs_secret;")
                    self.conn.execute(f"""
                        CREATE SECRET gcs_secret (
                            TYPE HTTP,
                            BEARER_TOKEN '{access_token}'
                        );
                    """)

                    logger.info("GCS authentication configured successfully for DuckDB")
                except Exception as auth_err:
                    logger.warning("Failed to configure GCS authentication: %s", auth_err)
                    logger.warning("Falling back to credential chain provider")
                    with contextlib.suppress(Exception):
                        self.conn.execute("""
                            CREATE SECRET IF NOT EXISTS gcs_secret (
                                TYPE GCS,
                                PROVIDER CREDENTIAL_CHAIN
                            )
                        """)
            else:
                logger.warning(
                    "GOOGLE_APPLICATION_CREDENTIALS not set. "
                    "GCS authentication may not work. "
                    "Set it to the path of your service account JSON key file."
                )
                with contextlib.suppress(Exception):
                    self.conn.execute("""
                        CREATE SECRET IF NOT EXISTS gcs_secret (
                            TYPE GCS,
                            PROVIDER CREDENTIAL_CHAIN
                        )
                    """)

            logger.info("GCS support enabled via httpfs extension")
        except Exception as e:
            logger.warning("Could not setup GCS support: %s", e)
            logger.warning("GCS files may not be accessible. Local files will still work.")

    def _extract_headers_trailers(self, config: FileConfig, label: str) -> tuple[list[str], list[str]]:
        """
        Extract header and trailer lines from a file.

        Streams line-by-line to avoid loading multi-GB files into memory.
        Handles local, GCS, and compressed files (.gz, .Z, .bz2, .zip).
        """
        import collections

        headers: list[str] = []
        trailers: list[str] = []

        try:
            local_path = self._get_local_path(config, label)

            if config.trailer_patterns:
                logger.info(f"Trailer patterns for {label}: {'\n'.join(config.trailer_patterns)}")  # noqa: G004

            compression_type = get_compression_type(local_path)

            if compression_type == "gzip":
                import gzip

                fh = gzip.open(local_path, "rt", encoding=config.encoding)
            else:
                fh = open(local_path, encoding=config.encoding)

            SAMPLE_RECORDS: int = 5
            sample_lines: collections.deque[str] = collections.deque(maxlen=SAMPLE_RECORDS)
            line_idx = 0

            try:
                for line in fh:
                    line_idx += 1

                    if line_idx <= SAMPLE_RECORDS:
                        sample_lines.append(line.rstrip())

                    if config.header_rows > 0 and line_idx <= config.header_rows:
                        headers.append(line.rstrip("\n"))

                    # Match lines that BEGIN with any trailer pattern
                    if config.trailer_patterns:
                        line_stripped = line.rstrip("\n")
                        if any(
                            line_stripped.startswith((pattern, f'"{pattern}'))
                            for pattern in config.trailer_patterns
                        ):
                            trailers.append(line_stripped)
            finally:
                fh.close()

            # Debug: log sample lines
            for idx, sample in enumerate(sample_lines, 1):
                logger.debug("%s sample line ==> %d: ``%r``", label, idx, sample)

            if headers:
                logger.info("Extracted %d header line(s) from %s", len(headers), label)
            if trailers:
                logger.info("Extracted %d trailer line(s) from %s", len(trailers), label)

            logger.info("Streamed %d line(s) from %s for header/trailer extraction", line_idx, label)

        except Exception as e:
            logger.warning("Could not extract headers/trailers from %s: %s", label, e)

        return headers, trailers

    def _get_local_path(self, config: FileConfig, label: str) -> Path:
        """
        Resolve a local file path, downloading from GCS and/or decompressing .Z as needed.

        Results are cached so repeated calls don't re-download.
        """
        cached = self._source_local_path if label == "source" else self._target_local_path
        if cached is not None:
            logger.debug("Reusing cached local path for %s: %s", label, cached)
            return cached

        path_str = str(config.path)

        if is_gcs_path(path_str):
            logger.info("Downloading %s from GCS for header/trailer extraction: %s", label, path_str)
            local_path = self.file_handler.download_from_gcs(path_str)
        else:
            local_path = Path(path_str)

        compression_type = get_compression_type(local_path)
        if compression_type == "compress":
            logger.info("Decompressing Unix compress file: %s", local_path.name)
            stem = local_path.stem
            decompressed_path = self.temp_dir / stem
            local_path = decompress_file(local_path, decompressed_path, compression_type)
            self.temp_files.append(decompressed_path)

        # Cache for reuse (avoids re-downloading in _register_fwf_view)
        if label == "source":
            self._source_local_path = local_path
        else:
            self._target_local_path = local_path

        return local_path

    def _download_gcs_files_async(self) -> None:
        source_path_str = str(self.source.path)
        target_path_str = str(self.target.path)

        source_is_gcs = is_gcs_path(source_path_str)
        target_is_gcs = is_gcs_path(target_path_str)

        if not source_is_gcs and not target_is_gcs:
            logger.debug("Neither file is on GCS — skipping concurrent download")
            return

        # Same URI: download once, share for both
        if source_is_gcs and target_is_gcs and source_path_str == target_path_str:
            if self._source_local_path is not None:
                self._target_local_path = self._source_local_path
                logger.debug("Same GCS URI — reusing already-cached source path for target")
                return

            logger.info("Source and target share the same GCS URI - downloading once: %s", source_path_str)
            local_path = self._get_local_path(self.source, "source")
            # Point target at the same local file
            self._target_local_path = local_path
            logger.info("Single download complete, shared path: %s", local_path)
            return

        tasks: dict[str, tuple[FileConfig, str]] = {}
        if source_is_gcs and self._source_local_path is None:
            tasks["source"] = (self.source, "source")
        if target_is_gcs and self._target_local_path is None:
            tasks["target"] = (self.target, "target")

        if not tasks:
            logger.debug("All GCS files already cached — nothing to download")
            return

        logger.info("Downloading %d GCS file(s) concurrently…", len(tasks))

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_label = {
                executor.submit(self._get_local_path, config, label): label
                for label, (config, label) in tasks.items()
            }
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    result_path = future.result()
                    logger.info("Concurrently download complete for %s: %s", label, result_path)
                except Exception:
                    logger.exception("Failed to download %s from GCS", label)
                    raise

    def _get_duckdb_path(self, config: FileConfig, label: str) -> str:
        """
        Get a path that DuckDB can read directly.

        DuckDB handles local, GCS (httpfs), and .gz files natively.
        Only .Z files need manual decompression.
        """
        path_str = str(config.path)

        if label == "source" and self._source_resolved_path:
            return self._source_resolved_path
        if label == "target" and self._target_resolved_path:
            return self._target_resolved_path

        compression_type = get_compression_type(path_str)

        if compression_type == "compress":
            if is_gcs_path(path_str):
                logger.info("Downloading %s from GCS for decompression: %s", label, path_str)
                local_path = self.file_handler.download_from_gcs(path_str)
            else:
                local_path = Path(path_str)

            logger.info("Decompressing Unix compress file: %s", local_path.name)
            stem = local_path.stem
            decompressed_path = self.temp_dir / stem
            decompressed_path = decompress_file(local_path, decompressed_path, compression_type)
            self.temp_files.append(decompressed_path)
            result_path = str(decompressed_path.resolve())
        else:
            if is_gcs_path(path_str):
                # Prefer the already-downloaded local copy to avoid double memory pressure
                cached = self._source_local_path if label == "source" else self._target_local_path
                if cached is not None and cached.exists():
                    result_path = str(cached.resolve())
                    logger.debug("Using cached local copy for DuckDB: %s", result_path)
                else:
                    result_path = path_str
                    logger.debug("Using GCS path directly for DuckDB: %s", path_str)
            else:
                result_path = str(Path(path_str).resolve())

        if label == "source":
            self._source_resolved_path = result_path
        else:
            self._target_resolved_path = result_path

        return result_path

    @staticmethod
    def _compare_lines(source_lines: list[str], target_lines: list[str]) -> list[dict]:
        """
        Compare two lists of lines (headers or trailers) character-by-character.

        For lines present in both source and target that are NOT identical,
        a character-level diff is computed so the report can pinpoint the
        exact positions where values diverge.

        Each result dict contains:
            line_number      - 1-based line index
            source           - full source line text ('' if missing)
            target           - full target line text ('' if missing)
            status           - MATCH | MISMATCH | Missing in Source | Missing in Target
            first_diff_pos   - 0-based position of the first differing character
                               (None when status != MISMATCH)
            diff_count       - total number of character positions that differ
            char_diffs       - list of per-position diffs (see _char_diff)
            source_len       - length of the source line
            target_len       - length of the target line
        """
        comparison: list[dict] = []
        max_lines: int = max(len(source_lines), len(target_lines))
        src_line: str | None
        tgt_line: str | None

        for i in range(max_lines):
            src_line = source_lines[i] if i < len(source_lines) else None
            tgt_line = target_lines[i] if i < len(target_lines) else None

            entry: dict = {
                "line_number": i + 1,
                "source": src_line if src_line else "",
                "target": tgt_line if tgt_line else "",
                "first_diff_pos": None,
                "diff_count": 0,
                "char_diffs": [],
                "source_len": len(src_line) if src_line else 0,
                "target_len": len(tgt_line) if tgt_line else 0,
            }

            if src_line == tgt_line:
                entry["status"] = "MATCH"
            elif src_line is None:
                entry["status"] = "Missing in Source"
            elif tgt_line is None:
                entry["status"] = "Missing in Target"
            else:
                entry["status"] = "MISMATCH"
                char_diffs = _char_diff(src_line, tgt_line)
                entry["char_diffs"] = char_diffs
                entry["diff_count"] = len(char_diffs)
                entry["first_diff_pos"] = char_diffs[0]["pos"] if char_diffs else None

                logger.debug(
                    f"Line {i + 1} MISMATCH: {len(char_diffs)} char diff(s), "  # noqa: G004
                    f"first at pos {entry['first_diff_pos']} "
                    f"(src_len={len(src_line)}, tgt_len={len(tgt_line)})"
                )

            comparison.append(entry)

        return comparison

    def _compare_headers_trailers(self) -> None:
        logger.info("=" * 60)
        logger.info("COMPARING HEADERS AND TRAILERS")
        logger.info("=" * 60)

        if self.source_headers or self.target_headers:
            self.header_comparison = self._compare_lines(self.source_headers, self.target_headers)
            match_count = sum(1 for h in self.header_comparison if h["status"] == "MATCH")
            logger.info("Header Lines: %d compared, %d match", len(self.header_comparison), match_count)

        if self.source_trailers or self.target_trailers:
            self.trailer_comparison = self._compare_lines(self.source_trailers, self.target_trailers)
            match_count = sum(1 for t in self.trailer_comparison if t["status"] == "MATCH")
            logger.info("Trailer Lines: %d compared, %d match", len(self.trailer_comparison), match_count)

    def _register_view(self, config: FileConfig, table_name: str, trailer_startswith: str) -> None:
        """
        Register a file as a DuckDB view, excluding header and trailer lines.

        DuckDB natively handles:
        - Local files
        - GCS files (gs://bucket/path) via httpfs extension
        - Gzip compressed files (.gz)

        Only .Z files are pre-decompressed.
        """
        if config.file_type == "fwf":
            self._register_fwf_view(config, table_name)
        else:
            self._register_delimited_view(config, table_name, trailer_startswith)

    def _register_fwf_view(self, config: FileConfig, table_name: str) -> None:
        if is_gcs_path(config.path):
            label: str = "source" if table_name == "source_data" else "target"
            local_path: Path = self._get_local_path(config, label)
            logger.info("Reusing downloaded %s FWF file for view registration: %s", label, local_path)
            local_config = FileConfig(
                path=str(local_path),
                delimiter=config.delimiter,
                file_type=config.file_type,
                header_rows=config.header_rows,
                trailer_patterns=config.trailer_patterns,
                encoding=config.encoding,
                col_specs=config.col_specs,
                column_names=config.column_names,
            )
            parquet_path: Path = local_path.with_suffix(".optimized.parquet")
        else:
            local_config = config
            parquet_path: Path = Path(config.path).with_suffix(".optimized.parquet")

        PolarsFWFConverter.convert_to_parquet(local_config, parquet_path)

        self.temp_files.append(parquet_path)

        logger.info("Loading %s from Parquet...", table_name)

        table_query: str = f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM read_parquet('{parquet_path}');
        """
        logger.debug("Creating %s table\n %s\n", table_name, table_query)
        self.conn.execute(table_query)
        columns = [row[0] for row in self.conn.execute(f"DESCRIBE {table_name}").fetchall()]

        logger.debug("Loaded with columns: %s", columns)

        self._create_pk_index(table_name)

    def _register_delimited_view(self, config: FileConfig, table_name: str, trailer_startswith: str) -> None:
        header_opt: Literal["header=True", "header=False"] = (
            "header=True" if config.header_rows > 0 else "header=False"
        )

        label: Literal["source", "target"] = "source" if table_name == "source_data" else "target"
        duckdb_path: str = self._get_duckdb_path(config, label)

        logger.info("Loading %s from %s...", table_name, config.file_type.upper())
        logger.debug("DuckDB path: %s", duckdb_path)

        temp_table = f"temp_{table_name}"
        error_table = f"{table_name}_errors"
        reject_scan_name = f"{table_name}_reject_scan"

        create_table_query: str = f"""
            CREATE OR REPLACE TABLE {temp_table} AS
            SELECT * FROM read_csv_auto(
                '{duckdb_path}',
                delim='{config.delimiter}',
                {header_opt},
                all_varchar=True,
                ignore_errors=True,
                store_rejects=True,
                rejects_table='{error_table}',
                rejects_scan='{reject_scan_name}',
                null_padding=True,
                max_line_size=10485760
            );
        """
        logger.debug("Creating table...\n\n%s\n", create_table_query)
        self.conn.execute(create_table_query)

        with contextlib.suppress(Exception):
            error_count: int = self._execute_safe_count_query(f"SELECT COUNT(1) FROM {error_table}")
            if error_count > 0:
                logger.warning("%d bad row(s) detected in %s", error_count, table_name)
                rejects_df: pl.DataFrame = self.conn.execute(f"SELECT * FROM {error_table} LIMIT 500").pl()

                if table_name == "source_data":
                    self.source_rejects = rejects_df
                elif table_name == "target_data":
                    self.target_rejects = rejects_df

                logger.warning("Sample errors:")
                for row in rejects_df.head(3).iter_rows(named=True):
                    error = row.get("error", "Unknown error")
                    line_num = row.get("line", "N/A")
                    logger.warning("Line %s: %s", line_num, error)

        # Normalize column names and remap DuckDB's zero-padded auto-generated
        # names (column00 → column0) so user-supplied PKs match correctly
        columns: list[str] = [row[0] for row in self.conn.execute(f"DESCRIBE {temp_table}").fetchall()]
        normalized_columns: list[str] = _normalize_column_names(columns)

        if config.header_rows == 0:
            # Remap DuckDB auto-names: "column00" -> "column0", "column09" -> "column9", etc.
            _auto_col_re = re.compile(r"^column(\d+)$", re.IGNORECASE)
            remapped: list[str] = []
            for col in normalized_columns:
                m = _auto_col_re.match(col)
                if m:
                    remapped.append(f"column{int(m.group(1))}")
                else:
                    remapped.append(col)
            normalized_columns = remapped

        first_col = columns[0].strip() if columns else "COALESCE(NULL, '')"
        where_clause = (
            trailer_startswith.format(trailer_column=f'"{first_col}"') if trailer_startswith else "1=1"
        )
        logger.debug("Normalizing column names:")
        for col, norm_col in itertools.zip_longest(columns, normalized_columns, fillvalue="NA_Column"):
            logger.debug("\t - %s --> %s", col, norm_col)
        column_mapping = ",\n\t".join(
            [
                f"{_enclosed_double_quotes(col)} AS {_enclosed_double_quotes(norm_col)}"
                for col, norm_col in zip(columns, normalized_columns)
            ]
        )
        view_query: str = f"""
            CREATE OR REPLACE VIEW {table_name} AS
            SELECT {column_mapping} FROM {temp_table}
            WHERE {where_clause};
        """
        logger.debug("Creating view %s...\n\n%s\n", table_name, view_query)
        self.conn.execute(view_query)
        logger.debug("Loaded with normalized columns: %s", normalized_columns)

        self._create_pk_index(temp_table, index_suffix=table_name)

    def _log_primary_keys(self):
        logger.info("Primary Keys:")
        for pk in self.primary_keys:
            logger.info("\t - %s", pk)

    def load_data(self) -> None:
        """Load both source and target files into DuckDB views."""
        logger.info("=" * 60)
        logger.info("LOADING DATA FILES")
        logger.info("=" * 60)

        self._log_primary_keys()

        self._download_gcs_files_async()

        self.source_headers, self.source_trailers = self._extract_headers_trailers(self.source, "source")
        self.target_headers, self.target_trailers = self._extract_headers_trailers(self.target, "target")

        SINGLE_QUOTE: str = "'"
        ESCAPED_QUOTE: str = "\\'"
        source_trailers = " OR ".join(
            [
                f"{{trailer_column}} NOT LIKE '{line.replace(SINGLE_QUOTE, ESCAPED_QUOTE)}%'"
                for line in self.source_trailers
            ]
        )
        target_trailers = " OR ".join(
            [
                f"{{trailer_column}} NOT LIKE '{line.replace(SINGLE_QUOTE, ESCAPED_QUOTE)}%'"
                for line in self.target_trailers
            ]
        )
        self._register_view(self.source, "source_data", source_trailers)
        self._register_view(self.target, "target_data", target_trailers)
        logger.info("Data loaded successfully")

        # Free downloaded GCS temp copies (DuckDB has already ingested them);
        # never delete original local files.
        for config, cached in (
            (self.source, self._source_local_path),
            (self.target, self._target_local_path),
        ):
            if cached is not None and cached.exists() and config.is_gcs:
                try:
                    cached.unlink()
                    logger.debug("Deleted cached GCS download: %s", cached.name)
                except Exception as e:
                    logger.debug("Could not delete cached download %s: %s", cached.name, e)

        try:
            self.flush_db_buffer()
            logger.debug("DuckDB checkpoint completed — buffers flushed to disk")
        except Exception as e:
            logger.debug("Checkpoint advisory failed (non-fatal): %s", e)

        import gc

        gc.collect()
        logger.debug("Python GC completed")

        self._compare_headers_trailers()

    @staticmethod
    def _escape_column_name(col: str) -> str:
        escaped = col.replace('"', '""')
        return f'"{escaped}"'

    def _normalize_col_exprs(self, col: str) -> tuple[str, str]:
        """
        Return ``(s_col, t_col)`` SQL expressions with normalization applied.

        The expressions honor all normalization rules (trim, upper/lower,
        accent stripping, null-as-empty) so they can be reused both in the
        detailed CASE comparison and in the lightweight mismatch boolean.
        """
        escaped_col: str = self._escape_column_name(col)
        s_col, t_col = f"s.{escaped_col}", f"t.{escaped_col}"

        if col in self.norm.ltrim_columns or escaped_col in self.norm.ltrim_columns:
            s_col = f"LTRIM({s_col})"
            t_col = f"LTRIM({t_col})"
        elif col in self.norm.rtrim_columns or escaped_col in self.norm.rtrim_columns:
            s_col = f"RTRIM({s_col})"
            t_col = f"RTRIM({t_col})"
        elif col in self.norm.trim_columns or escaped_col in self.norm.trim_columns:
            s_col = f"TRIM({s_col})"
            t_col = f"TRIM({t_col})"
        elif self.norm.trim_strings:
            s_col = f"TRIM({s_col})"
            t_col = f"TRIM({t_col})"

        if col in self.norm.upper_columns or escaped_col in self.norm.upper_columns:
            s_col = f"UPPER({s_col})"
            t_col = f"UPPER({t_col})"
        if col in self.norm.lower_columns or escaped_col in self.norm.lower_columns:
            s_col = f"LOWER({s_col})"
            t_col = f"LOWER({t_col})"
        if col in self.norm.strip_accents_columns or escaped_col in self.norm.strip_accents_columns:
            s_col = f"UNACCENT({s_col})"
            t_col = f"UNACCENT({t_col})"

        if self.norm.treat_null_as_empty:
            s_col = f"COALESCE({s_col}, '')"
            t_col = f"COALESCE({t_col}, '')"

        return s_col, t_col

    def _build_comparison_case(self, col: str) -> str:
        escaped_col: str = self._escape_column_name(col)
        s_col, t_col = self._normalize_col_exprs(col)

        checks = [f"WHEN {s_col} IS NOT DISTINCT FROM {t_col} THEN 'MATCH'"]

        if self.norm.float_epsilon:
            checks.append(f"""
                WHEN TRY_CAST({s_col} AS DOUBLE) IS NOT NULL
                     AND TRY_CAST({t_col} AS DOUBLE) IS NOT NULL
                     AND ABS(TRY_CAST({s_col} AS DOUBLE) - TRY_CAST({t_col} AS DOUBLE)) <= {self.norm.float_epsilon}
                     THEN 'MATCH'
            """)

        if self.norm.normalize_dates:
            checks.append(f"""
                WHEN TRY_CAST({s_col} AS TIMESTAMP) IS NOT NULL
                     AND TRY_CAST({t_col} AS TIMESTAMP) IS NOT NULL
                     AND TRY_CAST({s_col} AS TIMESTAMP) = TRY_CAST({t_col} AS TIMESTAMP)
                     THEN 'MATCH'
            """)

        checks.append(
            f"ELSE 'MISMATCH: ' || COALESCE(s.{escaped_col}, 'NULL') || ' || ' || COALESCE(t.{escaped_col}, 'NULL')"
        )

        return " ".join(checks)

    def _execute_safe_count_query(self, query: str) -> int:
        """Execute a count query safely, returning 0 if no result."""
        result = self.conn.execute(query).fetchone()
        return result[0] if result else 0

    def _create_pk_index(self, table_name: str, index_suffix: str | None = None) -> None:
        """
        Create an ART index on the primary-key columns of a persistent table.

        DuckDB indexes live only on real TABLEs (not VIEWs or parquet scans),
        so callers must ensure `table_name` refers to a materialized table.
        The index dramatically speeds up the hash-join / semi-join / anti-join
        queries used during comparison — especially for files > 100 MB.

        The method introspects the table's actual column names and maps
        normalised PK names back to them (e.g. column0 → column00) so the
        index DDL always uses names the table really has.
        """
        if not self.primary_keys:
            return

        suffix = index_suffix or table_name
        idx_name = f"idx_pk_{suffix}"

        # Build a lookup from the table's real column names to normalized form
        actual_cols: list[str] = [row[0] for row in self.conn.execute(f"DESCRIBE {table_name}").fetchall()]
        normalised_to_actual: dict[str, str] = {}
        pattern: re.Pattern = re.compile(r"^column(\d+)$", re.IGNORECASE)
        for actual in actual_cols:
            norm: str = _normalize_column_names([actual])[0]
            # Apply the same zero-pad stripping used in _register_delimited_view
            m: re.Match[str] | None = pattern.match(norm)
            if m:
                norm = f"column{int(m.group(1))}"
            normalised_to_actual[norm] = actual

        resolved_pks: list[str] = []
        for pk in self.primary_keys:
            resolved = normalised_to_actual.get(pk)
            if resolved is None:
                logger.debug("PK column %r not found in %s columns — skipping index", pk, table_name)
                return
            resolved_pks.append(self._escape_column_name(resolved))

        pk_cols = ", ".join(resolved_pks)

        try:
            self.conn.execute(f"DROP INDEX IF EXISTS {idx_name}")
            create_idx = f"CREATE INDEX {idx_name} ON {table_name} ({pk_cols})"
            logger.debug("Creating PK index: %s", create_idx)
            self.conn.execute(create_idx)
            logger.info("PK index created on %s (%s)", table_name, pk_cols)
        except Exception as e:
            logger.debug("Could not create index on %s (non-fatal): %s", table_name, e)

    def flush_db_buffer(self):
        with contextlib.suppress(Exception):
            self.conn.execute("CHECKPOINT")

    def run_comparison(self) -> pl.DataFrame:
        """
        Execute the comparison between source and target files.

        Uses memory-efficient anti-join/semi-join queries instead of FULL OUTER JOIN.
        Materializes only differing PKs (max ~1500 rows) for detailed comparison.
        """
        logger.info("=" * 60)
        logger.info("RUNNING COMPARISON ENGINE")
        logger.info("=" * 60)

        cols = [r[0] for r in self.conn.execute("DESCRIBE source_data").fetchall()]
        non_key_cols = [c for c in cols if c not in self.primary_keys]
        logger.debug("columns: %s", cols)
        logger.debug("non-key columns: %s", non_key_cols)

        pk_join = " AND ".join(
            [
                f"s.{self._escape_column_name(pk)} = t.{self._escape_column_name(pk)}"
                for pk in self.primary_keys
            ]
        )

        diff_logic: list[str] = []
        lightweight_mismatch: list[str] = []

        if non_key_cols:
            for col in non_key_cols:
                escaped_col = self._escape_column_name(col)
                safe_col_alias = col.replace(" ", "_").replace('"', "")
                case_sql = self._build_comparison_case(col)

                diff_logic.append(
                    f"CASE {case_sql} END as {self._escape_column_name(safe_col_alias + '_status')}"
                )
                diff_logic.append(
                    f"s.{escaped_col} as {self._escape_column_name(safe_col_alias + '_source')}"
                )
                diff_logic.append(
                    f"t.{escaped_col} as {self._escape_column_name(safe_col_alias + '_target')}"
                )
                s_norm, t_norm = self._normalize_col_exprs(col)
                lightweight_mismatch.append(f"{s_norm} IS DISTINCT FROM {t_norm}")
        else:
            logger.warning("All columns are primary keys. No non-key columns to compare.")

        # Statistics via EXCEPT set operations on PKs — sort-merge friendly, low memory
        source_count: int = self._execute_safe_count_query("SELECT COUNT(1) FROM source_data")
        target_count: int = self._execute_safe_count_query("SELECT COUNT(1) FROM target_data")
        logger.info("Row counts - source: %s, target: %s", f"{source_count:,}", f"{target_count:,}")
        logger.info("Diff counts — (source - target): %s", f"{source_count - target_count:,}")

        pk_select: str = ", ".join([self._escape_column_name(pk) for pk in self.primary_keys])

        # Detect duplicate PKs — cartesian joins would explode row counts
        src_distinct: int = self._execute_safe_count_query(
            f"SELECT COUNT(DISTINCT ({pk_select})) FROM source_data"
        )
        tgt_distinct: int = self._execute_safe_count_query(
            f"SELECT COUNT(DISTINCT ({pk_select})) FROM target_data"
        )

        self._has_duplicate_keys: bool = src_distinct < source_count or tgt_distinct < target_count
        if self._has_duplicate_keys:
            logger.warning("=" * 60)
            logger.warning(
                "DUPLICATE PRIMARY KEYS DETECTED — source has %s distinct keys "
                "out of %s rows; target has %s distinct keys out of %s rows. "
                "Comparison results may be inflated. Consider choosing a more "
                "specific set of primary keys.",
                f"{src_distinct:,}",
                f"{source_count:,}",
                f"{tgt_distinct:,}",
                f"{target_count:,}",
            )
            logger.warning("=" * 60)

        # Materialize de-duplicated tables once to avoid repeated ROW_NUMBER() overhead
        if self._has_duplicate_keys:
            pk_partition: str = ", ".join([self._escape_column_name(pk) for pk in self.primary_keys])
            logger.info("Materializing de-duplicated tables to disk (one ROW_NUMBER pass per side)...")

            self.conn.execute("DROP TABLE IF EXISTS _dedup_source")
            self.conn.execute(
                f"CREATE TABLE _dedup_source AS "
                f"SELECT * EXCLUDE (_rn) FROM ("
                f"  SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition}) AS _rn "
                f"  FROM source_data"
                f") WHERE _rn = 1"
            )
            self.flush_db_buffer()
            logger.info("De-duplicated source table materialized")

            self.conn.execute("DROP TABLE IF EXISTS _dedup_target")
            self.conn.execute(
                f"CREATE TABLE _dedup_target AS "
                f"SELECT * EXCLUDE (_rn) FROM ("
                f"  SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition}) AS _rn "
                f"  FROM target_data"
                f") WHERE _rn = 1"
            )
            self.flush_db_buffer()
            logger.info("De-duplicated target table materialized")

            self._create_pk_index("_dedup_source")
            self._create_pk_index("_dedup_target")

        missing_in_source_query = f"""
            SELECT COUNT(1) FROM (
                SELECT {pk_select} FROM target_data
                EXCEPT
                SELECT {pk_select} FROM source_data
            )
        """
        logger.debug("Missing in Source Query:\n%s\n", missing_in_source_query)
        missing_in_source: int = self._execute_safe_count_query(missing_in_source_query)
        missing_in_source: int = max(missing_in_source, 0)
        self.flush_db_buffer()

        missing_in_target_query: str = f"""
            SELECT COUNT(1) FROM (
                SELECT {pk_select} FROM source_data
                EXCEPT
                SELECT {pk_select} FROM target_data
            )
        """
        logger.debug("Missing in Target Query:\n%s\n", missing_in_target_query)
        missing_in_target: int = self._execute_safe_count_query(missing_in_target_query)

        missing_in_target = max(missing_in_target, 0)
        found_in_both = source_count - missing_in_target

        self.flush_db_buffer()

        # Mismatched rows: only needed when there are non-key columns
        mismatched_rows: int = 0
        if lightweight_mismatch:
            lightweight_or = " OR ".join(lightweight_mismatch)

            if self._has_duplicate_keys:
                dedup_source = "_dedup_source s"
                dedup_target = "_dedup_target t"
            else:
                dedup_source = "source_data s"
                dedup_target = "target_data t"

            lightweight_mismatch_query: str = f"""
                SELECT COUNT(1) FROM {dedup_source}
                INNER JOIN {dedup_target} ON {pk_join}
                WHERE {lightweight_or}
            """
            logger.debug("Computing mismatched row count with lightweight INNER JOIN on PKs only...")
            logger.debug("Lightweight Mismatch Query:\n%s\n", lightweight_mismatch_query)
            mismatched_rows: int = self._execute_safe_count_query(lightweight_mismatch_query)

        logger.debug("Statistics computed")

        total_rows: int = max(source_count, target_count)
        matching_rows: int = abs(found_in_both - mismatched_rows)
        match_percentage: float = (matching_rows / total_rows * 100) if total_rows > 0 else 0.0
        row_count_diff: int = abs(source_count - target_count)

        self.source_row_count: int = source_count
        self.target_row_count: int = target_count
        self.missing_in_source_count: int = missing_in_source
        self.missing_in_target_count: int = missing_in_target
        self.mismatched_rows_count: int = mismatched_rows
        self.matching_rows_count: int = matching_rows
        self.match_percentage: float = match_percentage
        self.row_count_diff: int = row_count_diff

        logger.info("Row Counts:")
        logger.info(f"Source: {source_count:,} rows")  # noqa: G004
        logger.info(f"Target: {target_count:,} rows")  # noqa: G004
        logger.info(f"Row Count Diff (Source - Target): {row_count_diff:,}")  # noqa: G004
        logger.info(f"Found in Both: {found_in_both:,} rows")  # noqa: G004
        logger.info(f"Mismatched Rows (value diffs): {mismatched_rows:,} rows")  # noqa: G004
        logger.info(f"Matching Rows: {matching_rows:,} rows ({match_percentage:.2f}%)")  # noqa: G004
        logger.info(f"Missing in Source: {missing_in_source:,} rows")  # noqa: G004
        logger.info(f"Missing in Target: {missing_in_target:,} rows")  # noqa: G004

        # Short-circuit when no differences exist
        total_diffs = mismatched_rows + missing_in_source + missing_in_target
        if total_diffs == 0:
            logger.info("No differences found — skipping detail query (100% match)")
            return pl.DataFrame()

        # Materialize differing PKs into a small table (max ~1500 rows) using EXCEPT
        pk_cols_list: list[str] = [self._escape_column_name(pk) for pk in self.primary_keys]
        pk_select: str = ", ".join(pk_cols_list)
        lightweight_or: str = " OR ".join(lightweight_mismatch) if lightweight_mismatch else "FALSE"

        self.conn.execute("DROP TABLE IF EXISTS _diff_keys")
        create_diff_keys_table_query = f"""
            CREATE TABLE _diff_keys (
                validation_status VARCHAR,
                {", ".join([f"{pk} VARCHAR" for pk in pk_cols_list])}
            )
        """
        logger.debug(
            "Creating _diff_keys table for materializing differing keys...\n%s\n",
            create_diff_keys_table_query,
        )
        self.conn.execute(create_diff_keys_table_query)

        # Leg 1: mismatched rows
        if mismatched_rows > 0:
            pk_cols_select_s = ", ".join([f"s.{pk}" for pk in pk_cols_list])

            if self._has_duplicate_keys:
                mismatch_src = "_dedup_source s"
                mismatch_tgt = "_dedup_target t"
            else:
                mismatch_src = "source_data s"
                mismatch_tgt = "target_data t"

            insert_diff_key_mismatch_rows_query = f"""
                INSERT INTO _diff_keys
                SELECT 'Found in Both', {pk_cols_select_s}
                FROM {mismatch_src}
                INNER JOIN {mismatch_tgt} ON {pk_join}
                WHERE {lightweight_or}
                LIMIT 500
            """
            logger.debug("Materialized mismatched keys")
            logger.debug("Mismatched Diff Query:\n%s\n", insert_diff_key_mismatch_rows_query)

            try:
                self.conn.execute(insert_diff_key_mismatch_rows_query)
            except duckdb.OutOfMemoryException:
                logger.warning("Could not materialize mismatched keys (OOM) — skipping detail for this leg")
                raise RuntimeError("Out of Memory error occurred")

        # Leg 2: missing in source
        if missing_in_source > 0:
            insert_diff_key_src_query: str = f"""
                INSERT INTO _diff_keys
                SELECT 'Missing in Source', *
                FROM (
                    SELECT {pk_select} FROM target_data
                    EXCEPT
                    SELECT {pk_select} FROM source_data
                ) sub
                LIMIT 500
            """
            logger.debug("Materializing missing-in-source keys with EXCEPT-based query")
            logger.debug("Source Diff Query:\n%s\n", insert_diff_key_src_query)
            try:
                self.conn.execute(insert_diff_key_src_query)
            except duckdb.OutOfMemoryException:
                logger.warning("EXCEPT for missing-in-source diff keys OOM'd — trying anti-join fallback")
                raise RuntimeError("Out of Memory error occurred")

        self.flush_db_buffer()

        # Leg 3: missing in target
        if missing_in_target > 0:
            insert_diff_key_tgt_query: str = f"""
                INSERT INTO _diff_keys
                SELECT 'Missing in Target', *
                FROM (
                    SELECT {pk_select} FROM source_data
                    EXCEPT
                    SELECT {pk_select} FROM target_data
                ) sub
                LIMIT 500
            """
            logger.debug("Materializing missing-in-target keys with EXCEPT-based query")
            logger.debug("Target Diff Query:\n%s\n", insert_diff_key_tgt_query)
            try:
                self.conn.execute(insert_diff_key_tgt_query)
            except duckdb.OutOfMemoryException:
                logger.warning("EXCEPT for missing-in-target diff keys OOM'd — trying anti-join fallback")
                raise RuntimeError("Out of Memory error occurred")

        diff_count: int = self._execute_safe_count_query("SELECT COUNT(1) FROM _diff_keys")
        logger.info("Materialized %d diff key(s) into _diff_keys table", diff_count)

        self._create_pk_index("_diff_keys")

        # Join diff_keys back to source/target for full detail
        if self._has_duplicate_keys:
            source_subquery = "_dedup_source s"
            target_subquery = "_dedup_target t"
            logger.info("Using pre-materialized de-duplicated tables for detail join")
        else:
            source_subquery = "source_data s"
            target_subquery = "target_data t"

        detail_s_join = " AND ".join(
            [
                f"s.{self._escape_column_name(pk)} = dk.{self._escape_column_name(pk)}"
                for pk in self.primary_keys
            ]
        )
        detail_t_join = " AND ".join(
            [
                f"t.{self._escape_column_name(pk)} = dk.{self._escape_column_name(pk)}"
                for pk in self.primary_keys
            ]
        )

        detail_query = f"""
        SELECT
            dk.validation_status,
            {", ".join([f"dk.{pk}" for pk in pk_cols_list])},
            {", ".join(diff_logic) if diff_logic else "1 as _placeholder"}
        FROM _diff_keys dk
        LEFT JOIN {source_subquery} ON {detail_s_join}
        LEFT JOIN {target_subquery} ON {detail_t_join}
        ORDER BY
            CASE dk.validation_status
                WHEN 'Found in Both' THEN 1
                WHEN 'Missing in Source' THEN 2
                WHEN 'Missing in Target' THEN 3
            END
        LIMIT 500
        """

        logger.info("Executing detail query on materialized diff keys...")
        logger.debug("Detail Query:\n%s\n", detail_query)
        result_df = self.conn.execute(detail_query).pl()

        if not diff_logic:
            result_df = result_df.drop("_placeholder")

        logger.info("Found %d difference(s) (capped at 500)", len(result_df))

        self.conn.execute("DROP TABLE IF EXISTS _diff_keys")

        # Drop the de-duplicated tables to free disk space
        if self._has_duplicate_keys:
            self.conn.execute("DROP TABLE IF EXISTS _dedup_source")
            self.conn.execute("DROP TABLE IF EXISTS _dedup_target")
            self.flush_db_buffer()
            logger.info("Dropped de-duplicated tables (_dedup_source, _dedup_target)")

        return result_df

    def get_sample_data(self) -> pl.DataFrame | None:
        """Get sample matching data for 100% match scenarios."""
        pk_join = " AND ".join(
            [
                f"s.{self._escape_column_name(pk)} = t.{self._escape_column_name(pk)}"
                for pk in self.primary_keys
            ]
        )

        # De-duplicate when PKs are not unique to avoid cartesian explosion
        if getattr(self, "_has_duplicate_keys", False):
            tables = [
                r[0]
                for r in self.conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_name IN ('_dedup_source', '_dedup_target')"
                ).fetchall()
            ]
            if "_dedup_source" in tables and "_dedup_target" in tables:
                sample_source = "_dedup_source s"
                sample_target = "_dedup_target t"
            else:
                pk_partition = ", ".join([self._escape_column_name(pk) for pk in self.primary_keys])
                sample_source = (
                    f"(SELECT * FROM (SELECT *, ROW_NUMBER() OVER "
                    f"(PARTITION BY {pk_partition}) AS _rn FROM source_data) "
                    f"WHERE _rn = 1) s"
                )
                sample_target = (
                    f"(SELECT * FROM (SELECT *, ROW_NUMBER() OVER "
                    f"(PARTITION BY {pk_partition}) AS _rn FROM target_data) "
                    f"WHERE _rn = 1) t"
                )
        else:
            sample_source = "source_data s"
            sample_target = "target_data t"

        sample_query = f"""
        SELECT s.*, t.*
        FROM {sample_source}
        INNER JOIN {sample_target} ON {pk_join}
        LIMIT 500
        """

        logger.debug("Sample data Query:\n%s\n", sample_query)
        sample_df = self.conn.execute(sample_query).pl()
        sample_df.columns = _normalize_column_names(sample_df.columns)

        # Rename columns properly
        source_cols: list[str] = [
            c for c in sample_df.columns if c not in self.primary_keys and not c.endswith("_1")
        ]

        # Build column expressions for renaming
        col_exprs: list[pl.Expr] = [pl.col(pk) for pk in self.primary_keys]

        for col in source_cols:
            col_exprs.append(pl.col(col).alias(col + "_source"))
            col_exprs.append(pl.col(col + "_1").alias(col + "_target"))
            col_exprs.append(pl.lit("MATCH").alias(col + "_status"))

        clean_sample = sample_df.select(col_exprs)
        return clean_sample

    def cleanup_temp_files(self) -> None:
        logger.info("=" * 60)
        logger.info("CLEANING UP TEMPORARY FILES")
        logger.info("=" * 60)

        deleted_count = 0

        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug("Deleted: %s", temp_file.name)
                    deleted_count += 1
            except Exception as e:
                logger.warning("Could not delete %s: [ERROR] - %s", temp_file.name, e)

        try:
            self.file_handler.cleanup()
            logger.debug("Cleaned up GCS handler temp files")
        except Exception as e:
            logger.warning("Could not clean up GCS handler: %s", e)

        import shutil

        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug("Deleted temp directory: %s", self.temp_dir)
            except Exception as e:
                logger.warning("Could not delete temp directory: %s", e)

        if self._duckdb_work_dir.exists():
            try:
                shutil.rmtree(self._duckdb_work_dir)
                logger.debug("Deleted DuckDB work directory: %s", self._duckdb_work_dir)
            except Exception as e:
                logger.warning("Could not delete DuckDB work directory: %s", e)

        if deleted_count > 0:
            logger.info("Cleaned up %d temporary file(s)", deleted_count)
        else:
            logger.info("No temporary files to clean up")
