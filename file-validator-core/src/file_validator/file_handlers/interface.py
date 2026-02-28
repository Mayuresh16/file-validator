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

import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol, Self, runtime_checkable


@runtime_checkable
class FileHandlerProtocol(Protocol):
    """
    Structural typing Protocol for file handlers.

    This defines the methods any file handler should implement so callers can
    type-hint against this Protocol and new handlers remain pluggable.
    """

    temp_dir: Path
    temp_files: list[Path]

    def get_file(self, path: str | Path, decompress: bool = True) -> Path: ...

    def get_file_info(self, path: str | Path) -> dict[str, Any]: ...

    def prepare_for_duckdb(
        self, path: str | Path, temp_dir: Path | None = None
    ) -> tuple[Path, list[Path]]: ...

    def cleanup(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...


class FileHandler(ABC):
    """
    Abstract base class providing common behavior for file handlers.

    Subclasses should implement `get_file`, `get_file_info` and
    `prepare_for_duckdb`. `FileHandler` provides default temp-file management
    and context-manager support to reduce duplication.
    """

    def __init__(self, temp_dir: Path | None = None, *, prefix: str = "file_validator_"):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp(prefix=prefix))
        self.temp_files: list[Path] = []

    @abstractmethod
    def get_file(self, path: str | Path, decompress: bool = True) -> Path:
        raise NotImplementedError

    @abstractmethod
    def get_file_info(self, path: str | Path) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def prepare_for_duckdb(self, path: str | Path, temp_dir: Path | None = None) -> tuple[Path, list[Path]]:
        raise NotImplementedError

    def cleanup(self) -> None:
        """Remove all tracked temporary files and the temp directory."""
        for temp_file in list(self.temp_files):
            try:
                if temp_file.exists():
                    if temp_file.is_file():
                        temp_file.unlink()
                    else:
                        shutil.rmtree(temp_file)
            except Exception:
                # Best-effort cleanup; don't raise during destructor/cleanup
                pass
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
        self.temp_files.clear()

    def close(self) -> None:
        self.cleanup()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
