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

"""Configuration classes for file validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias

COLS_SPEC: TypeAlias = list[tuple[int, int]]  # noqa: UP040


@dataclass
class FileConfig:
    """
    Configuration for file parsing and loading.

    Attributes:
        path: File path (local path, GCS URI like gs://bucket/path, or Path object)
        file_type: File format - 'csv', 'psv', or 'fwf'
        delimiter: Delimiter for CSV/PSV files
        col_specs: Column specifications for FWF as list of (start, end) tuples
        header_rows: Number of header rows to skip
        trailer_patterns: Patterns to identify and filter trailer rows
        column_names: Optional list of column names to use
        compression: Compression type ('auto', 'gzip', 'compress', 'bzip2', 'zip', or None)
                    'auto' will detect from file extension
        encoding: File encoding (default: utf-8)
    """

    path: str | Path
    file_type: str = "csv"
    delimiter: str = ","
    col_specs: COLS_SPEC | None = None
    header_rows: int = 0
    trailer_patterns: list[str] = field(default_factory=list)
    column_names: list[str] | None = None
    compression: str | None = "auto"
    encoding: str = "utf-8"

    def __post_init__(self):
        if isinstance(self.path, str) and not self.path.startswith("gs://"):
            self.path = Path(self.path)

    @property
    def is_gcs(self) -> bool:
        return isinstance(self.path, str) and self.path.startswith("gs://")

    @property
    def is_compressed(self) -> bool:
        path_str: str = str(self.path).lower()
        compressed_extensions: set[str] = {".gz", ".gzip", ".z", ".bz2", ".zip"}
        return any(path_str.endswith(ext) for ext in compressed_extensions)

    @property
    def filename(self) -> str:
        if self.is_gcs:
            _filename: str = self.path.as_posix() if isinstance(self.path, Path) else self.path
            return _filename.split("/")[-1]
        return self.path.name if isinstance(self.path, Path) else Path(self.path).name


@dataclass
class NormalizationConfig:
    """
    Configuration for data normalization and comparison rules.

    Attributes:
        float_epsilon: Tolerance for floating-point comparisons (set as a float, e.g., 1e-6)
        normalize_dates: Enable date format normalization (True to normalize, False to skip)
        trim_strings: Enable automatic string trimming (applies to all string columns)
        treat_null_as_empty: Treat NULL values as empty strings (True to treat, False to skip)
        ltrim_columns: List of column names to apply LTRIM (left trim)
        rtrim_columns: List of column names to apply RTRIM (right trim)
        trim_columns: List of column names to apply TRIM (both sides)
        upper_columns: List of column names to apply UPPER normalization
        lower_columns: List of column names to apply LOWER normalization
        strip_accents_columns: List of column names to apply strip_accents normalization
    """

    float_epsilon: float | None = None
    normalize_dates: bool = False
    trim_strings: bool = False
    treat_null_as_empty: bool = True
    ltrim_columns: list[str] = field(default_factory=list)
    rtrim_columns: list[str] = field(default_factory=list)
    trim_columns: list[str] = field(default_factory=list)
    upper_columns: list[str] = field(default_factory=list)
    lower_columns: list[str] = field(default_factory=list)
    strip_accents_columns: list[str] = field(default_factory=list)
