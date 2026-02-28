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

"""File handlers for local, GCS, and compressed file support."""

from __future__ import annotations

import importlib
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Compression utilities
from file_validator.file_handlers.compression import (
    COMPRESSION_EXTENSIONS,
    decompress_file,
    get_compression_type,
)

logger: logging.Logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover
    from file_validator.file_handlers.gcs_handler import (
        GCSFileHandler,
        is_gcs_path,
        prepare_gcs_file_for_duckdb,
    )
    from file_validator.file_handlers.interface import (
        FileHandler,
        FileHandlerProtocol,
    )
    from file_validator.file_handlers.local_handler import (
        LocalFileHandler,
        prepare_local_file_for_duckdb,
    )


# Lazy attribute map to avoid circular imports
_SUBMODULE_ATTRS: dict[str, str] = {
    "GCSFileHandler": "file_validator.file_handlers.gcs_handler",
    "is_gcs_path": "file_validator.file_handlers.gcs_handler",
    "prepare_gcs_file_for_duckdb": "file_validator.file_handlers.gcs_handler",
    "LocalFileHandler": "file_validator.file_handlers.local_handler",
    "prepare_local_file_for_duckdb": "file_validator.file_handlers.local_handler",
    "FileHandlerProtocol": "file_validator.file_handlers.interface",
    "FileHandler": "file_validator.file_handlers.interface",
}


def _get_submodule_attr(attr: str):
    module_name = _SUBMODULE_ATTRS.get(attr)
    if not module_name:
        raise AttributeError(attr)
    mod = importlib.import_module(module_name)
    return getattr(mod, attr)


def __getattr__(name: str) -> Any:  # module-level lazy import
    if name in _SUBMODULE_ATTRS:
        return _get_submodule_attr(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULE_ATTRS.keys()))


# Unified API functions (use lazy imports to avoid circular issues)


def get_file_info(path: str | Path) -> dict:
    path_str = str(path)

    is_gcs = _get_submodule_attr("is_gcs_path")
    if is_gcs(path_str):
        GCSFileHandler = _get_submodule_attr("GCSFileHandler")
        with GCSFileHandler() as handler:
            return handler.get_file_info(path_str)
    else:
        LocalFileHandler = _get_submodule_attr("LocalFileHandler")
        with LocalFileHandler() as handler:
            return handler.get_file_info(path_str)


def prepare_file_for_duckdb(path: str | Path, temp_dir: Path | None = None) -> tuple[Path, list[Path]]:
    path_str = str(path)

    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="file_validator_"))

    is_gcs = _get_submodule_attr("is_gcs_path")
    if is_gcs(path_str):
        prepare = _get_submodule_attr("prepare_gcs_file_for_duckdb")
        return prepare(path_str, temp_dir)
    prepare = _get_submodule_attr("prepare_local_file_for_duckdb")
    return prepare(path_str, temp_dir)


# Eagerly bind common symbols for IDE support (lazy-loaded at runtime)
for _name in (
    "GCSFileHandler",
    "is_gcs_path",
    "prepare_gcs_file_for_duckdb",
    "LocalFileHandler",
    "prepare_local_file_for_duckdb",
    "FileHandlerProtocol",
    "FileHandler",
):
    try:
        globals()[_name] = _get_submodule_attr(_name)
    except Exception:
        globals()[_name] = None

__all__ = [
    # Compression utilities
    "COMPRESSION_EXTENSIONS",
    "get_compression_type",
    "decompress_file",
    # GCS utilities (lazy)
    "is_gcs_path",
    "GCSFileHandler",
    "prepare_gcs_file_for_duckdb",
    # Local utilities (lazy)
    "LocalFileHandler",
    "prepare_local_file_for_duckdb",
    "FileHandlerProtocol",
    "FileHandler",
    "get_file_info",
    "prepare_file_for_duckdb",
]
