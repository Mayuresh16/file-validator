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

from __future__ import annotations

import logging
import sys
import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

type Number = int | float
type COLS_SPEC = list[tuple[int, int]]

# Repository root discovery: file-validator repo root is three parents up from this utils module
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
# Default log directory for core package: <repo>/logs/core/
LOGS_ROOT: Path = REPO_ROOT / "logs" / "core"
LOGS_ROOT.mkdir(parents=True, exist_ok=True)
# Default reports directory for entire repo: <repo>/reports/
REPORTS_DIR: Path = REPO_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def format_bytes(value: Number, decimals: int = 2, binary: bool = False) -> str:
    """
    Convert a byte count into a human-readable string.

    Args:
        value: The size in bytes (int or float).
        decimals: Number of decimal places to show for non-bytes units.
        binary: If True, use binary (IEC) units (KiB, MiB, GiB, ... with 1024 base).
                If False, use decimal (SI) units (KB, MB, GB, ... with 1000 base).

    Returns:
        A formatted string like "0 B", "999 B", "1.00 KB", "2.34 MB", "1.00 GiB".

    Notes:
        - Handles negative values by preserving the sign.
        - For values below the first unit, returns "X B" without decimals.
        - Supports up to TB and PB; larger values will continue to scale appropriately.
    """
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"value must be a number of bytes, got: {value!r}")

    # Preserve sign; operate on absolute
    sign = "-" if n < 0 else ""
    n = abs(n)

    base = 1024.0 if binary else 1000.0
    units = [
        ("B", 1.0),
        ("KiB" if binary else "KB", base),
        ("MiB" if binary else "MB", base**2),
        ("GiB" if binary else "GB", base**3),
        ("TiB" if binary else "TB", base**4),
        ("PiB" if binary else "PB", base**5),
        ("EiB" if binary else "EB", base**6),
    ]

    # Bytes: no decimals
    if n < base:
        return f"{sign}{int(n)} B"

    # Find the largest unit not exceeding n
    for unit, factor in reversed(units):
        if n >= factor:
            value_in_unit = n / factor
            return f"{sign}{value_in_unit:.{decimals}f} {unit}"

    # Fallback (should not happen)
    return f"{sign}{n:.{decimals}f} B"


def calculate_time(start: float, end: float) -> str:
    """
    Pretty prints the time taken for an operation.

    Args:
        start (float): Start time of an operation.
        end (float): End time of an operation.

    Returns:
        str: Pretty format the time taken for an operation.
    """
    time_taken = int(round((end - start), 0))
    day: int = time_taken // 86400
    hour: int = (time_taken - (day * 86400)) // 3600
    minutes: int = (time_taken - ((day * 86400) + (hour * 3600))) // 60
    seconds: int = time_taken - ((day * 86400) + (hour * 3600) + (minutes * 60))

    if day != 0:
        output = f"{day} days {hour} hours {minutes} min {seconds} sec"
    elif hour != 0:
        output = f"{hour} hours {minutes} min {seconds} sec"
    elif minutes != 0:
        output = f"{minutes} min {seconds} sec"
    else:
        output = f"{seconds} sec"

    return output


def parse_fwf_column_specification(column_specification: str) -> COLS_SPEC | None:
    """
    Parse a comma-separated string of column lengths for FWF and return a list of tuple (start, end) positions of each column.

    Args:
        column_specification (str): Comma-separated column lengths, e.g. "10,5,8"

    Returns:
        list[tuple[int, int]]: list of tuple (start, end) positions of a column., e.g. [(0, 9), (10, 14), (15, 22), ...]
    """
    if not column_specification:
        return None
    cols_spec: COLS_SPEC = []
    start: int = 0
    try:
        lengths: list[int] = [int(x.strip()) for x in column_specification.split(",") if x.strip().isdigit()]
    except Exception as e:
        raise ValueError(f"Invalid FWF column specification: {column_specification!r} ({e})")

    for length in lengths:
        cols_spec.append((start, start + length - 1))
        start += length
    return cols_spec


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    Configure logging for the file validator app.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, defaults to repository-level logs/core.
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file is None:
        log_path = LOGS_ROOT / "file_validator_core.log"
    else:
        log_path = Path(log_file)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_log: Path = log_path.parent / f"{log_path.stem}_{timestamp}{log_path.suffix}"

    file_handler = TimedRotatingFileHandler(
        filename=str(timestamped_log),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.suffix = "%Y%m%d"
    root_logger.addHandler(file_handler)
    logging.getLogger(__name__).info("Logging to file: %s", timestamped_log)


def utcnow() -> datetime.datetime:
    """Get the current UTC time."""
    return datetime.datetime.now(datetime.UTC)
