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
Local file handler for file operations.

This module provides utilities for handling local files:
- File information retrieval
- Path validation
- Temporary file management
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from file_validator.file_handlers.compression import (
    COMPRESSION_EXTENSIONS,
    decompress_file,
    get_compression_type,
)
from file_validator.file_handlers.interface import FileHandler

logger: logging.Logger = logging.getLogger(__name__)


class LocalFileHandler(FileHandler):
    """
    Handler for local file operations.

    Supports:
    - File information retrieval
    - Automatic decompression
    - Temporary file management
    """

    def __init__(self, temp_dir: Path | None = None):
        super().__init__(temp_dir=temp_dir, prefix="file_validator_local_")
        logger.debug("Local file handler temp directory: %s", self.temp_dir)

    def get_file(
        self,
        path: str | Path,
        decompress: bool = True,
    ) -> Path:
        """
        Get a local file, handling decompression if needed.

        Args:
            path: Local file path
            decompress: Whether to decompress compressed files

        Returns:
            Path to the ready-to-use file
        """
        local_path = Path(path)

        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        if decompress:
            compression_type = get_compression_type(local_path)
            if compression_type:
                stem = local_path.name
                for ext in COMPRESSION_EXTENSIONS.keys():
                    if stem.lower().endswith(ext.lower()):
                        stem = stem[: -len(ext)]
                        break
                decompressed_path = self.temp_dir / stem

                decompressed_path = decompress_file(
                    local_path,
                    decompressed_path,
                    compression_type,
                )
                self.temp_files.append(decompressed_path)
                return decompressed_path

        return local_path

    def get_file_info(self, path: str | Path) -> dict:
        """
        Get information about a local file.

        Args:
            path: Local file path

        Returns:
            Dictionary with file information
        """
        local_path = Path(path)

        info = {
            "original_path": str(path),
            "is_local": True,
            "compression": get_compression_type(path),
            "filename": local_path.name,
        }

        if local_path.exists():
            info["size_bytes"] = local_path.stat().st_size
            info["exists"] = True
        else:
            info["exists"] = False

        return info

    def prepare_for_duckdb(self, path: str | Path, temp_dir: Path | None = None) -> tuple[Path, list[Path]]:
        return prepare_local_file_for_duckdb(path, temp_dir)

    # cleanup/close/context methods are inherited from FileHandler


def prepare_local_file_for_duckdb(
    path: str | Path,
    temp_dir: Path | None = None,
) -> tuple[Path, list[Path]]:
    """
    Prepare a local file for DuckDB, handling compression.

    DuckDB handles gzip natively; other formats (.Z, .bz2, .zip) are decompressed first.
    """
    local_path = Path(path)
    temp_files: list[Path] = []

    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="file_validator_local_"))
        temp_files.append(temp_dir)

    compression_type = get_compression_type(local_path)

    if compression_type in ("gzip", "gz"):
        logger.info("DuckDB will handle gzip decompression natively")
        return local_path, temp_files

    if compression_type:
        stem = local_path.name
        for ext in COMPRESSION_EXTENSIONS.keys():
            if stem.lower().endswith(ext.lower()):
                stem = stem[: -len(ext)]
                break
        decompressed_path = temp_dir / stem

        decompressed_path = decompress_file(local_path, decompressed_path, compression_type)
        temp_files.append(decompressed_path)
        return decompressed_path, temp_files

    return local_path, temp_files
