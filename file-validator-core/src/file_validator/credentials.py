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

import json
import logging
import os
import time
from pathlib import Path

import requests
from google.auth import identity_pool, impersonated_credentials
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


def auto_refresh_oidc_token_if_needed():
    """
    If using external_account credentials, auto-refresh the OIDC token and save to oidc_token.json.

    Returns True if token file exists after refresh, False otherwise.
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        return False
    with open(creds_path) as f:
        info = json.load(f)
    if info.get("type") != "external_account":
        return True
    oidc_file = info.get("credential_source", {}).get("file")
    if not oidc_file:
        logger.warning("No credential_source.file in WIP config; cannot auto-refresh OIDC token.")
        return False
    oidc_file = Path(oidc_file)

    # Check if existing token is still valid (not expired)
    if oidc_file.exists():
        try:
            with open(oidc_file) as f:
                token_data = json.load(f)
            generated_at = token_data.get("generated_at", 0)
            expires_in = token_data.get("expires_in", 0)
            if generated_at and expires_in:
                # Renew if within 5 minutes of expiry (300s buffer)
                expiry_time = generated_at + expires_in
                remaining = expiry_time - int(time.time())
                if remaining > 300:
                    logger.debug("OIDC token still valid (%d s remaining)", remaining)
                    return True
                logger.info("OIDC token expired or expiring soon (%d s remaining), refreshing...", remaining)
            else:
                logger.info("OIDC token missing generated_at/expires_in, refreshing...")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read existing OIDC token file, refreshing: %s", e)

    client_id = os.environ.get("OIDC_CLIENT_ID")
    client_secret = os.environ.get("OIDC_CLIENT_SECRET")
    token_endpoint = os.environ.get("OIDC_TOKEN_ENDPOINT")
    audience = info.get("audience")
    if not all([client_id, client_secret, token_endpoint]):
        logger.warning(
            "OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, or OIDC_TOKEN_ENDPOINT not set; cannot auto-refresh OIDC token."
        )
        return False

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": os.environ.get("OIDC_SCOPE", "read"),
    }
    if audience:
        payload["audience"] = audience
    try:
        resp = requests.post(
            token_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("No access_token in IdP response: %s", token_data)
            return False
        oidc_json = {
            "access_token": access_token,
            "generated_at": int(time.time()),
            "expires_in": token_data.get("expires_in"),
            "scope": "read",
            "token_type": "Bearer",
        }
        oidc_file.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Saving OIDC token to %s", oidc_file)
        with open(oidc_file, "w") as f:
            json.dump(oidc_json, f, indent=2)
        return True
    except Exception as e:
        logger.exception("OIDC auto-refresh failed: %s", e)
        return False


def get_credentials_and_project():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS not set or file does not exist")
    with open(creds_path) as f:
        info = json.load(f)
    cred_type = info.get("type")
    project_id = os.environ.get("PROJECT_ID")  # or info.get("project_id")
    if cred_type == "external_account":
        oidc_file = info.get("credential_source", {}).get("file")
        if oidc_file:
            oidc_file_path = Path(oidc_file)
            if not oidc_file_path.exists():
                success = auto_refresh_oidc_token_if_needed()
                if not success or not oidc_file_path.exists():
                    raise RuntimeError(f"Failed to create OIDC token file: {oidc_file_path}")
        creds = identity_pool.Credentials.from_file(creds_path)
    elif cred_type == "service_account":
        creds = service_account.Credentials.from_service_account_file(creds_path)
    else:
        raise RuntimeError(f"Unknown credential type: {cred_type}")
    return creds, project_id


def impersonate_self(creds, target_principal):
    scopes: str = os.environ.get("TARGET_SCOPES", "https://www.googleapis.com/auth/cloud-platform")
    target_scopes: list[str] = [
        "https://www.googleapis.com/auth/devstorage.read_only",
    ]
    # Add any extra scopes from env, deduplicating
    for raw_scope in scopes.split(","):
        cleaned = raw_scope.strip()
        if cleaned and cleaned not in target_scopes:
            target_scopes.append(cleaned)
    return impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal=target_principal,
        target_scopes=target_scopes,
        lifetime=3600,
    )
