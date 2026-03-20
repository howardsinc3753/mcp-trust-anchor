#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud Asset Folder Create Tool

Create asset folders in FortiCloud Asset Management API V3.

API Reference: https://support.fortinet.com/ES/api/registration/v3/
Client ID: assetmanagement

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# API Configuration
AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
ASSET_API_BASE = "https://support.fortinet.com/ES/api/registration/v3"
CLIENT_ID = "assetmanagement"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]


def load_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load API credentials and account_id from parameters or config file."""
    creds = {
        "api_username": None,
        "api_password": None,
        "account_id": None
    }

    # Check parameters first
    for key in creds.keys():
        if params.get(key):
            creds[key] = params[key]

    if creds["api_username"] and creds["api_password"]:
        return creds

    # Check environment variables
    if os.environ.get("FORTICLOUD_API_USERNAME"):
        creds["api_username"] = os.environ["FORTICLOUD_API_USERNAME"]
    if os.environ.get("FORTICLOUD_API_PASSWORD"):
        creds["api_password"] = os.environ["FORTICLOUD_API_PASSWORD"]
    if os.environ.get("FORTICLOUD_ACCOUNT_ID"):
        creds["account_id"] = int(os.environ["FORTICLOUD_ACCOUNT_ID"])

    if creds["api_username"] and creds["api_password"]:
        return creds

    # Try credential files
    for cred_path in CREDENTIAL_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, "r") as f:
                    config = yaml.safe_load(f)
                if config:
                    if "api_username" in config:
                        creds["api_username"] = config["api_username"]
                    if "api_password" in config:
                        creds["api_password"] = config["api_password"]
                    if "account_id" in config and creds["account_id"] is None:
                        creds["account_id"] = config["account_id"]
                    if creds["api_username"] and creds["api_password"]:
                        logger.info(f"Loaded credentials from {cred_path}")
                        return creds
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


def get_oauth_token(api_username: str, api_password: str) -> str:
    """Get OAuth access token from FortiCloud IAM."""
    payload = {
        "username": api_username,
        "password": api_password,
        "client_id": CLIENT_ID,
        "grant_type": "password"
    }

    logger.info(f"Requesting OAuth token for client_id: {CLIENT_ID}")
    response = requests.post(AUTH_URL, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()

    if result.get("status") != "success":
        raise Exception(f"Authentication failed: {result.get('message', 'Unknown error')}")

    logger.info(f"Token obtained, expires in {result.get('expires_in')}s")
    return result["access_token"]


def create_folder(
    token: str,
    folder_name: str,
    account_id: Optional[int] = None,
    parent_folder_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create an asset folder in FortiCloud.

    Args:
        token: OAuth access token
        folder_name: Name of the new folder
        account_id: Account ID (required for Org scope users)
        parent_folder_id: Optional parent folder ID for nested folders

    Returns:
        API response with created folder details
    """
    url = f"{ASSET_API_BASE}/folders/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload: Dict[str, Any] = {
        "folderName": folder_name
    }
    if account_id is not None:
        payload["accountId"] = account_id
    if parent_folder_id is not None:
        payload["parentFolderId"] = parent_folder_id

    logger.info(f"Creating folder '{folder_name}' for account: {account_id or 'default'}")

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    return response.json()


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool."""
    logger.info("Executing FortiCloud Folder Create")

    try:
        # Validate required parameters
        folder_name = params.get("folder_name")
        if not folder_name:
            return {"success": False, "error": "Missing required parameter: folder_name"}

        # Load credentials (includes account_id from config)
        creds = load_credentials(params)
        if not creds["api_username"] or not creds["api_password"]:
            return {
                "success": False,
                "error": "No credentials found. Provide api_username/api_password parameters, "
                        "set FORTICLOUD_API_USERNAME/FORTICLOUD_API_PASSWORD environment variables, "
                        "or create a credential file."
            }

        # Get OAuth token
        token = get_oauth_token(creds["api_username"], creds["api_password"])

        # Get account_id (from params or config file)
        account_id = creds.get("account_id")
        parent_folder_id = params.get("parent_folder_id")

        # Call API
        result = create_folder(token, folder_name, account_id, parent_folder_id)

        # Check API response status
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract created folder data
        folders = result.get("assetFolders", [])

        if not folders:
            return {
                "success": False,
                "error": "Folder creation returned no folder data"
            }

        # Get the created folder
        created = folders[0]
        folder_info = {
            "folder_id": created.get("folderId"),
            "folder_name": created.get("folderName"),
            "folder_path": created.get("folderPath"),
            "parent_folder_id": created.get("parentFolderId")
        }

        return {
            "success": True,
            "message": f"Folder '{folder_name}' created successfully",
            "folder": folder_info
        }

    except requests.exceptions.HTTPError as e:
        error_detail = str(e)
        try:
            error_body = e.response.json()
            error_detail = error_body.get("message") or error_body.get("error") or str(e)
        except Exception:
            pass
        logger.exception(f"HTTP error: {error_detail}")
        return {"success": False, "error": f"HTTP error: {error_detail}"}

    except Exception as e:
        logger.exception(f"Tool error: {e}")
        return {"success": False, "error": str(e)}


def main(context) -> Dict[str, Any]:
    """Sync wrapper for MCP execution."""
    if hasattr(context, "parameters"):
        params = context.parameters
    elif isinstance(context, dict):
        params = context
    else:
        params = {}

    return asyncio.run(execute(params))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python tool.py <folder_name> [parent_folder_id]")
        sys.exit(1)

    test_params = {"folder_name": sys.argv[1]}
    if len(sys.argv) > 2:
        test_params["parent_folder_id"] = int(sys.argv[2])

    result = main(test_params)
    print(json.dumps(result, indent=2))
