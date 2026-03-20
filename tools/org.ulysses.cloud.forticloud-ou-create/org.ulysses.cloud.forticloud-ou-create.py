#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud Organization Unit Create Tool

Create a new Organization Unit (OU) in FortiCloud Organization API.
Used for MSSP multi-tenant customer provisioning.

API Reference: https://support.fortinet.com/ES/api/organization/v1/
Client ID: organization

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

import json
import logging
import os
import re
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

# Input validation patterns
BLOCKED_PATTERNS = [
    r"[<>]",        # XSS prevention
    r"[;&|`$]",     # Shell metacharacters
]


def validate_name(name: str) -> tuple[bool, Optional[str]]:
    """Validate OU name for security and format."""
    if not name or not name.strip():
        return False, "Name cannot be empty"

    if len(name) > 255:
        return False, "Name cannot exceed 255 characters"

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, name):
            return False, f"Name contains invalid characters: {pattern}"

    return True, None


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


def create_organization_unit(
    token: str,
    parent_id: int,
    name: str,
    desc: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new Organization Unit in FortiCloud.

    Args:
        token: OAuth access token
        parent_id: Parent OU ID
        name: Name for the new OU
        desc: Optional description

    Returns:
        API response with created OU details
    """
    url = f"{ORG_API_BASE}/units/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Build request payload
    payload: Dict[str, Any] = {
        "parentId": parent_id,
        "name": name
    }
    if desc:
        payload["desc"] = desc

    logger.info(f"Creating OU: {name} under parent {parent_id}")

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
    logger.info(f"Executing FortiCloud OU Create")

    try:
        # Validate required parameters
        parent_id = params.get("parent_id")
        name = params.get("name")

        if parent_id is None:
            return {
                "success": False,
                "error": "Missing required parameter: parent_id"
            }

        if not name:
            return {
                "success": False,
                "error": "Missing required parameter: name"
            }

        # Validate name
        is_valid, error_msg = validate_name(name)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid name: {error_msg}"
            }

        # Get optional description
        desc = params.get("desc")
        if desc:
            is_valid, error_msg = validate_name(desc)
            if not is_valid:
                return {
                    "success": False,
                    "error": f"Invalid description: {error_msg}"
                }

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

        # Call API
        result = create_organization_unit(token, parent_id, name, desc)

        # Check API response status
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract created OU data
        org_units_data = result.get("organizationUnits", {})
        org_id = org_units_data.get("orgId")
        org_units = org_units_data.get("orgUnits", [])

        # Should be exactly one OU created
        if not org_units:
            return {
                "success": False,
                "error": "No OU returned in response"
            }

        created_ou = org_units[0]

        return {
            "success": True,
            "org_id": org_id,
            "created_ou": {
                "id": created_ou.get("id"),
                "name": created_ou.get("name"),
                "desc": created_ou.get("desc"),
                "parent_id": created_ou.get("parentId")
            }
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

    if len(sys.argv) < 3:
        print("Usage: python tool.py <parent_id> <name> [description]")
        sys.exit(1)

    test_params = {
        "parent_id": int(sys.argv[1]),
        "name": sys.argv[2]
    }
    if len(sys.argv) > 3:
        test_params["desc"] = sys.argv[3]

    result = main(test_params)
    print(json.dumps(result, indent=2))
