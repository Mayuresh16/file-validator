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

"""File System Utilities for File Validator Webserver."""

import asyncio
import contextlib
import functools
import os
import shutil
import stat
from pathlib import Path

try:
    from anyio import Path as AnyIOPath  # type: ignore

    _HAS_ANYIO = True
except ImportError:
    _HAS_ANYIO = False

# ==================================================================
#               Async File System Utilities & Wrappers
# ==================================================================


async def async_path_exists(path: Path | str) -> bool:
    """Async-safe path.exists(). Prefers AnyIO's Path when available."""
    p = Path(path)
    if _HAS_ANYIO:
        ap = AnyIOPath(str(p))
        return await ap.exists()
    return await asyncio.to_thread(p.exists)


async def async_list_files(path: Path | str) -> list[Path]:
    """Return a list of files under `path` in an async-friendly way."""
    p = Path(path)
    if _HAS_ANYIO:
        ap = AnyIOPath(str(p))
        files: list[Path] = []
        async for child in ap.iterdir():
            if await child.is_file():
                files.append(Path(str(child)))
        return files

    def _iter_dir() -> list[Path]:
        try:
            return [x for x in p.iterdir() if x.is_file()]
        except OSError:
            return []

    return await asyncio.to_thread(_iter_dir)


async def async_resolve(path: Path | str) -> Path:
    """Resolve a path asynchronously and return a pathlib.Path."""
    p = Path(path)
    if _HAS_ANYIO:
        ap = AnyIOPath(str(p))
        rp = await ap.resolve()
        return Path(str(rp))
    return await asyncio.to_thread(p.resolve)


async def async_unlink(path: Path | str) -> None:
    """Unlink (delete) a file asynchronously."""
    p = Path(path)
    if _HAS_ANYIO:
        ap = AnyIOPath(str(p))
        await ap.unlink()
        return
    await asyncio.to_thread(p.unlink)


def _on_rm_error(func, path, _exc_info):
    """
    On-error handler for rmtree: try to make file writable then retry.

    The third argument (exception info) is intentionally unused; prefixed with an
    underscore to satisfy linters that flag unused parameters.
    """
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IWRITE)
        func(path)


async def async_rmtree(path: Path | str) -> None:
    """Recursively remove a directory tree asynchronously (best-effort)."""
    p = Path(path)
    if not await async_path_exists(p):
        return
    # shutil.rmtree doesn't have an async API; run it in a thread
    await asyncio.to_thread(functools.partial(shutil.rmtree, p, onerror=_on_rm_error))
