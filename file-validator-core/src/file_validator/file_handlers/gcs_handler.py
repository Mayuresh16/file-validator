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

"""Google Cloud Storage (GCS) file handler with OAuth2 and DuckDB httpfs support."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from google.auth import exceptions as auth_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest

from file_validator.credentials import get_credentials_and_project, impersonate_self
from file_validator.exceptions import GCSConnectionError
from file_validator.file_handlers.compression import (
    COMPRESSION_EXTENSIONS,
    decompress_file,
    get_compression_type,
)
from file_validator.file_handlers.interface import FileHandler

logger: logging.Logger = logging.getLogger(__name__)

# Load environment variables from .env file in the file_validator directory
_env_file = Path(__file__).parent.parent / ".env"
load_dotenv(_env_file)


def is_gcs_path(path: str | Path) -> bool:
    """Check if a path is a GCS URI (gs://...)."""
    path_str = str(path)
    return path_str.startswith("gs://")


class GCSFileHandler(FileHandler):
    """
    Handler for Google Cloud Storage file operations.

    Supports:
    - Downloading files from GCS
    - Automatic decompression
    - OAuth2 authentication for DuckDB
    - Temporary file management
    """

    def __init__(self, temp_dir: Path | None = None):
        super().__init__(temp_dir=temp_dir, prefix="file_validator_gcs_")
        self._gcs_client = None
        self._credentials = None
        self._project_id = None

        logger.debug("GCS temp directory: %s", self.temp_dir)

    @property
    def gcs_client(self):
        """Lazy-load GCS client using credentials module."""
        if self._gcs_client is not None:
            return self._gcs_client

        logger.debug("Initializing GCS client...")
        try:
            from google.cloud import storage
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS support. "
                "Install with: pip install google-cloud-storage"
            )

        try:
            self._credentials, self._project_id = get_credentials_and_project()
            self._gcs_client = storage.Client(project=self._project_id, credentials=self._credentials)
            logger.info("GCS client initialized successfully")
            return self._gcs_client
        except auth_exceptions.DefaultCredentialsError as error:
            raise GCSConnectionError from error
        except Exception as error:
            logger.error("Failed to initialize GCS client: %s", error)
            raise GCSConnectionError from error

    def get_gcs_access_token(self) -> str | None:
        """
        Get a GCS OAuth2 access token for DuckDB httpfs.

        Uses impersonated credentials to obtain a bearer token for the GCS JSON API.
        """
        if self._gcs_client is None:
            self._gcs_client = self.gcs_client  # Trigger lazy loading

        source_credentials = self._gcs_client._credentials
        target_principal = os.getenv("TARGET_PRINCIPAL")

        if not target_principal:
            logger.error("TARGET_PRINCIPAL not set")
            return None

        bypass_hosts = {
            "metadata.google.internal",
            "googleapis.com",
            "*.googleapis.com",
            "iamcredentials.googleapis.com",
            "sts.googleapis.com",
            "oauth2.googleapis.com",
            "storage.googleapis.com",
        }
        os.environ["no_proxy"] = ",".join(bypass_hosts)

        logger.debug("Source credentials type: %s", type(source_credentials).__name__)
        logger.debug("Target principal: %s", target_principal)

        target_credentials = impersonate_self(source_credentials, target_principal)

        ga_request = GoogleAuthRequest()
        target_credentials.refresh(ga_request)

        access_token = target_credentials.token
        if not access_token:
            logger.error("Failed to obtain access token from impersonated credentials")
            return None

        logger.debug("Access token obtained (length=%d)", len(access_token))
        return access_token

    def parse_gcs_uri(self, uri: str) -> tuple[str, str]:
        """Parse a GCS URI into (bucket_name, blob_path)."""
        parsed = urlparse(uri)
        if parsed.scheme != "gs":
            raise ValueError(f"Invalid GCS URI: {uri}")

        bucket = parsed.netloc
        blob_path = parsed.path.lstrip("/")

        return bucket, blob_path

    def download_from_gcs(
        self,
        gcs_uri: str,
        local_path: Path | None = None,
    ) -> Path:
        """Download a file from GCS to a local path (auto-generated if None)."""
        bucket_name, blob_path = self.parse_gcs_uri(gcs_uri)

        if local_path is None:
            filename = Path(blob_path).name
            local_path = self.temp_dir / filename

        logger.info("Downloading from GCS: %s", gcs_uri)

        bucket = self.gcs_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        blob.download_to_filename(str(local_path))
        logger.debug("Downloaded from GCS: %s to %s", gcs_uri, local_path)
        self.temp_files.append(local_path)

        logger.info("Downloaded to: %s", local_path)
        return local_path

    def get_file(
        self,
        path: str | Path,
        decompress: bool = True,
    ) -> Path:
        """
        Get a file from GCS, handling download and decompression.

        Args:
            path: GCS URI
            decompress: Whether to decompress compressed files

        Returns:
            Path to the ready-to-use file
        """
        path_str = str(path)

        if is_gcs_path(path_str):
            local_path = self.download_from_gcs(gcs_uri=path_str)
        else:
            raise ValueError(f"Not a GCS path: {path_str}")

        if decompress:
            compression_type = get_compression_type(local_path)
            if compression_type:
                stem: str = local_path.name
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

    def get_file_info(self, gcs_uri: str) -> dict:
        """Get information about a GCS file."""
        bucket_name, blob_path = self.parse_gcs_uri(gcs_uri)

        info = {
            "original_path": gcs_uri,
            "is_gcs": True,
            "compression": get_compression_type(gcs_uri),
            "filename": Path(blob_path).name,
            "bucket": bucket_name,
            "blob_path": blob_path,
        }

        try:
            bucket = self.gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.reload(timeout=10)

            info["size_bytes"] = blob.size or 0
            info["exists"] = True
            info["updated"] = blob.updated
            info["content_type"] = blob.content_type
        except Exception as e:
            logger.warning("Failed to get GCS file info for %s: %s", gcs_uri, e)
            info["exists"] = False

        return info

    def prepare_for_duckdb(
        self,
        gcs_uri: str,
        temp_dir: Path | None = None,
    ) -> tuple[Path, list[Path]]:
        """
        Prepare a GCS file for DuckDB, handling download and compression.

        DuckDB handles gzip natively; other formats are decompressed first.
        """
        temp_files: list[Path] = []

        if temp_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="file_validator_gcs_"))
            temp_files.append(temp_dir)

        local_path = self.download_from_gcs(gcs_uri)
        temp_files.append(local_path)

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

            decompressed_path = decompress_file(
                local_path,
                decompressed_path,
                compression_type,
            )
            temp_files.append(decompressed_path)
            return decompressed_path, temp_files

        return local_path, temp_files


def prepare_gcs_file_for_duckdb(gcs_uri: str, temp_dir: Path | None = None) -> tuple[Path, list[Path]]:
    """Backward-compatible wrapper that delegates to GCSFileHandler.prepare_for_duckdb."""
    handler = GCSFileHandler(temp_dir)
    try:
        return handler.prepare_for_duckdb(gcs_uri, temp_dir)
    finally:
        pass
