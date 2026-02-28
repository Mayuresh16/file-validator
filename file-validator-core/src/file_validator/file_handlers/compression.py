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

"""Compression utilities for detecting and decompressing .gz, .Z, .bz2, and .zip files."""

import gzip
import logging
import shutil
import subprocess
from pathlib import Path

logger: logging.Logger = logging.getLogger(__name__)

# Supported compression types
COMPRESSION_EXTENSIONS = {
    ".gz": "gzip",
    ".gzip": "gzip",
    ".z": "compress",
    ".Z": "compress",
    ".bz2": "bzip2",
    ".zip": "zip",
}


def get_compression_type(path: str | Path) -> str | None:
    """Detect compression type from file extension, or None if not compressed."""
    path_str: str = str(path).lower()

    for ext, comp_type in COMPRESSION_EXTENSIONS.items():
        if path_str.endswith(ext.lower()):
            return comp_type

    return None


def decompress_file(
    input_path: Path,
    output_path: Path | None = None,
    compression_type: str | None = None,
) -> Path:
    """Decompress a file based on its compression type. Auto-detects if not specified."""
    if compression_type is None:
        compression_type = get_compression_type(input_path)

    if compression_type is None:
        logger.debug("File is not compressed: %s", input_path)
        return input_path

    if output_path is None:
        stem = input_path.name
        for ext in COMPRESSION_EXTENSIONS.keys():
            if stem.lower().endswith(ext.lower()):
                stem = stem[: -len(ext)]
                break
        output_path = input_path.parent / f"decompressed_{stem}"

    logger.info("Decompressing %s to: %s", compression_type, input_path.name)

    if compression_type in ("gzip", "gz"):
        _decompress_gzip(input_path, output_path)
    elif compression_type == "compress":
        _decompress_unix_compress(input_path, output_path)
    elif compression_type == "bzip2":
        _decompress_bzip2(input_path, output_path)
    elif compression_type == "zip":
        _decompress_zip(input_path, output_path)
    else:
        raise ValueError("Unsupported compression type: %s", compression_type)

    logger.info("Decompressed to: %s", output_path.name)
    return output_path


def _decompress_gzip(input_path: Path, output_path: Path) -> None:
    with gzip.open(input_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)


def _decompress_bzip2(input_path: Path, output_path: Path) -> None:
    import bz2

    with bz2.open(input_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)


def _decompress_zip(input_path: Path, output_path: Path) -> None:
    import zipfile

    with zipfile.ZipFile(input_path, "r") as zip_ref:
        # Extract first file
        file_list = zip_ref.namelist()
        if file_list:
            with zip_ref.open(file_list[0]) as f_in:
                with open(output_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            raise ValueError(f"Empty zip file: {input_path}")


def _decompress_unix_compress(input_path: Path, output_path: Path) -> None:
    """
    Decompress a Unix compress (.Z) file.

    Tries multiple strategies in order:
    1. unlzw3 library
    2. System uncompress command
    3. System gunzip command
    4. Python gzip library (fallback)
    """
    # Strategy 1: unlzw3 library
    try:
        import unlzw3

        with open(input_path, "rb") as f_in:
            compressed_data = f_in.read()
        decompressed_data = unlzw3.unlzw(compressed_data)
        with open(output_path, "wb") as f_out:
            f_out.write(decompressed_data)
        logger.debug("Decompressed using unlzw3 library")
        return
    except ImportError:
        logger.debug("unlzw3 not installed, trying system commands")
    except Exception as e:
        logger.debug("unlzw3 failed: %s, trying system commands", e)

    # Strategy 2: system uncompress command
    try:
        temp_z_path = output_path.with_suffix(".Z")
        shutil.copy(input_path, temp_z_path)

        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["uncompress", "-f", str(temp_z_path)],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            decompressed_path = temp_z_path.with_suffix("")
            if decompressed_path.exists():
                shutil.move(decompressed_path, output_path)
                logger.debug("Decompressed using system uncompress")
                return
    except FileNotFoundError:
        logger.debug("System uncompress command not available")
    except Exception as e:
        logger.debug("System uncompress failed: %s", e)

    # Strategy 3: gunzip
    try:
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            ["gunzip", "-c", str(input_path)],
            check=False,
            capture_output=True,
        )

        if result.returncode == 0:
            with open(output_path, "wb") as f_out:
                f_out.write(result.stdout)
            logger.debug("Decompressed using gunzip")
            return
    except FileNotFoundError:
        logger.debug("System gunzip command not available")
    except Exception as e:
        logger.debug("gunzip failed: %s", e)

    # Strategy 4: gzip library fallback
    try:
        with gzip.open(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        logger.debug("Decompressed using gzip library (fallback)")
        return
    except Exception as e:
        logger.debug("gzip fallback failed: %s", e)

    raise RuntimeError(
        f"Failed to decompress Unix compress file: {input_path}. Install 'unlzw3' package: pip install unlzw3"
    )
