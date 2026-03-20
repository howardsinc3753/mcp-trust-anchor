#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud Organization Unit List Tool

List Organization Units (OUs) from FortiCloud Organization API.
Returns all OUs that the API user has access to with optional filtering.

API Reference: https://support.fortinet.com/ES/api/organization/v1/
Client ID: organization

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

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
ORG_API_BASE = "https://support.fortinet.com/ES/api/organization/v1"
CLIENT_ID = "organization"

# Credential file paths (MCP standard locations)
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]


def load_credentials(params: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Load API credentials from parameters or config file.

    Priority:
    1. Parameters (api_username, api_password)
    2. Environment variables (FORTICLOUD_API_USERNAME, FORTICLOUD_API_PASSWORD)
    3. Credential config file

    Returns:
        Tuple of (api_username, api_password)
    """
    # Check parameters first
    if params.get("api_username") and params.get("api_password"):
        logger.info("Using credentials from parameters")
        return params["api_username"], params["api_password"]

    # Check environment variables
    env_user = os.environ.get("FORTICLOUD_API_USERNAME")
    env_pass = os.environ.get("FORTICLOUD_API_PASSWORD")
    if env_user and env_pass:
        logger.info("Using credentials from environment variables")
        return env_user, env_pass

    # Try credential files
    for cred_path in CREDENTIAL_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, "r") as f:
                    creds = yaml.safe_load(f)
                if creds and "api_username" in creds and "api_password" in creds:
                    logger.info(f"Using credentials from {cred_path}")
                    return creds["api_username"], creds["api_password"]
            except Exception as e:
                logger.warning(f"Failed to load credentials from {cred_path}: {e}")

    return None, None


def get_oauth_token(api_username: str, api_password: str) -> str:
    """
    Get OAuth access token from FortiCloud IAM.

    Args:
        api_username: FortiCloud API username (UUID format)
        api_password: FortiCloud API password

    Returns:
        OAuth access token

    Raises:
        Exception: On authentication failure
    """
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


def list_organization_units(
    token: str,
    parent_id: Optional[int] = None,
    name_pattern: Optional[str] = None
) -> Dict[str, Any]:
    """
    List Organization Units from FortiCloud.

    Args:
        token: OAuth access token
        parent_id: Optional parent OU ID to filter results
        name_pattern: Optional search pattern for OU name

    Returns:
        API response with organization units
    """
    url = f"{ORG_API_BASE}/units/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Build request payload
    payload: Dict[str, Any] = {}
    if parent_id is not None:
        payload["parentId"] = parent_id
    if name_pattern:
        payload["name"] = name_pattern

    logger.info(f"Listing OUs with filters: {payload}")

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    return response.json()


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the tool.

    Args:
        params: Dictionary with parameters from manifest

    Returns:
        Dictionary with results matching output_schema
    """
    logger.info(f"Executing FortiCloud OU List with params: {list(params.keys())}")

    try:
        # Load credentials
        api_username, api_password = load_credentials(params)
        if not api_username or not api_password:
            return {
                "success": False,
                "error": "No credentials found. Provide api_username/api_password parameters, "
                        "set FORTICLOUD_API_USERNAME/FORTICLOUD_API_PASSWORD environment variables, "
                        "or create a credential file."
            }

        # Get OAuth token
        token = get_oauth_token(api_username, api_password)

        # Extract optional filters
        parent_id = params.get("parent_id")
        name_pattern = params.get("name_pattern")

        # Call API
        result = list_organization_units(token, parent_id, name_pattern)

        # Check API response status
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract OU data
        org_units_data = result.get("organizationUnits", {})
        org_id = org_units_data.get("orgId")
        org_units = org_units_data.get("orgUnits", [])

        # Transform to output format
        formatted_units = []
        for ou in org_units:
            formatted_units.append({
                "id": ou.get("id"),
                "name": ou.get("name"),
                "desc": ou.get("desc"),
                "parent_id": ou.get("parentId")
            })

        return {
            "success": True,
            "org_id": org_id,
            "ou_count": len(formatted_units),
            "org_units": formatted_units
        }

    except requests.exceptions.HTTPError as e:
        error_detail = str(e)
        try:
            error_body = e.response.json()
            error_detail = error_body.get("message") or error_body.get("error") or str(e)
        except Exception:
            pass
        logger.exception(f"HTTP error: {error_detail}")
        return {
            "success": False,
            "error": f"HTTP error: {error_detail}"
        }

    except Exception as e:
        logger.exception(f"Tool error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def main(context) -> Dict[str, Any]:
    """Sync wrapper for MCP execution."""
    import asyncio

    if hasattr(context, "parameters"):
        params = context.parameters
    elif isinstance(context, dict):
        params = context
    else:
        params = {}

    return asyncio.run(execute(params))


if __name__ == "__main__":
    import sys

    # CLI testing support
    logging.basicConfig(level=logging.INFO)

    test_params = {}
    if len(sys.argv) > 1:
        test_params["parent_id"] = int(sys.argv[1])

    result = main(test_params)
    print(json.dumps(result, indent=2))
