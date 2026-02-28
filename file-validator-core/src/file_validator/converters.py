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

"""Fixed-Width Format (FWF) to Parquet converter using Polars."""

import logging
from pathlib import Path

import polars as pl

from file_validator.config import FileConfig

logger: logging.Logger = logging.getLogger(__name__)


class PolarsFWFConverter:
    """High-performance Fixed-Width Format to Parquet converter using Polars."""

    @staticmethod
    def _build_column_slices(
        col_specs: list[tuple[int, int]], column_names: list[str] | None = None
    ) -> list[pl.Expr]:
        """
        Build Polars column slice expressions from column specifications.

        Args:
            col_specs: List of (start, end) position tuples
            column_names: Optional list of column names to use

        Returns:
            List of Polars expressions for column extraction
        """
        slices: list[pl.Expr] = []
        for i, (start, end) in enumerate(col_specs):
            length: int = end - start
            # Use provided column name if available, otherwise default to col_i
            if column_names and i < len(column_names):
                col_name: str = column_names[i].strip()
            else:
                col_name: str = f"column{i}"
            slices.append(pl.col("raw_line").str.slice(start, length).str.strip_chars().alias(col_name))
        return slices

    @staticmethod
    def _apply_trailer_filters(lazy_df: pl.LazyFrame, patterns: list[str]) -> pl.LazyFrame:
        """
        Filter out trailer rows based on starting patterns.

        Args:
            lazy_df: Polars LazyFrame to filter
            patterns: List of patterns that identify trailer rows

        Returns:
            Filtered LazyFrame
        """
        if not patterns:
            return lazy_df

        logger.debug("Filtering trailer rows starting with: %s", patterns)
        filter_expr = pl.lit(True)
        for pattern in patterns:
            filter_expr = filter_expr & (~pl.col("raw_line").str.starts_with(pattern))
        return lazy_df.filter(filter_expr)

    @staticmethod
    def _extract_fwf_header_names(file_path: Path, col_specs: list[tuple[int, int]]) -> list[str]:
        """
        Extract column names from the first line of an FWF file.

        Args:
            file_path: Path to the FWF file
            col_specs: List of (start, end) position tuples

        Returns:
            List of column names with leading/trailing spaces stripped
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                header_line: str = f.readline().rstrip("\n\r")

            column_names: list[str] = []
            for i, (start, end) in enumerate(col_specs):
                col_name: str = header_line[start:end].strip()
                if not col_name:
                    col_name = f"column{i}"
                    logger.warning("Empty column name at position %d, using default: %s", i, col_name)
                column_names.append(col_name)

            logger.debug("Extracted and trimmed column names: %s", column_names)
            return column_names
        except Exception as e:
            logger.warning("Could not extract header names: %s", e)
            return [f"column{i}" for i in range(len(col_specs))]

    @classmethod
    def convert_to_parquet(cls, config: FileConfig, output_path: str | Path) -> Path:
        """
        Convert Fixed-Width Format file to Parquet with header/trailer handling.

        Args:
            config: FileConfig with FWF specifications
            output_path: Destination path for Parquet file

        Returns:
            Path to the created Parquet file
        """
        output_path = Path(output_path)
        logger.info("Processing FWF: %s", config.path)

        try:
            # Extract column names from header if present
            column_names: list[str] | None = config.column_names
            if config.header_rows > 0 and config.col_specs and not column_names:
                column_names: list[str] = cls._extract_fwf_header_names(config.path, config.col_specs)

            # Read entire file as single-column lines, then slice into FWF columns
            lazy_df = pl.scan_csv(
                str(config.path),
                has_header=False,
                separator="\x1f",  # Unit separator - forces single column read
                quote_char=None,
                new_columns=["raw_line"],
            )

            if config.header_rows > 0:
                logger.debug("Skipping top %d header row(s)", config.header_rows)
                lazy_df = lazy_df.slice(config.header_rows, None)

            # Filter out trailer rows
            lazy_df = cls._apply_trailer_filters(lazy_df, config.trailer_patterns)

            # Extract columns based on specifications
            if config.col_specs:
                slices = cls._build_column_slices(config.col_specs, column_names)
                final_df = lazy_df.select(slices)
            else:
                final_df = lazy_df

            final_df.sink_parquet(str(output_path))
            logger.info("Conversion complete: %s", output_path)
            return output_path

        except Exception as e:
            logger.exception("CRITICAL ERROR in Polars Conversion: %s", e)
            raise
