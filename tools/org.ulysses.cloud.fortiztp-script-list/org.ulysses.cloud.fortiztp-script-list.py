#!/usr/bin/env python3
"""
FortiZTP Script List Tool
List all pre-run CLI scripts available for device provisioning.

API: GET https://fortiztp.forticloud.com/public/api/v2/setting/scripts
Client ID: fortiztp

IMPORTANT: FortiZTP does NOT support ORG IAM API Users.
Only Local type IAM API Users work with this API.
"""

import json
import os
import sys
import requests
import yaml
from datetime import datetime
from typing import Any, Dict, List, Optional

# FortiZTP API endpoints
AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
API_BASE = "https://fortiztp.forticloud.com/public/api/v2"
CLIENT_ID = "fortiztp"

# Default credential file path
DEFAULT_CRED_FILE = r"C:\ProgramData\Ulysses\config\forticloud_credentials.yaml"


def load_credentials(cred_file: str = DEFAULT_CRED_FILE) -> Dict[str, Any]:
    """Load credentials from YAML file."""
    if not os.path.exists(cred_file):
        return {}

    with open(cred_file, 'r') as f:
        return yaml.safe_load(f) or {}


def get_oauth_token(username: str, password: str) -> Dict[str, Any]:
    """Authenticate and get OAuth token."""
    payload = {
        "username": username,
        "password": password,
        "client_id": CLIENT_ID,
        "grant_type": "password"
    }

    response = requests.post(AUTH_URL, json=payload, timeout=30)

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"Authentication failed: {response.status_code} - {response.text}"
        }

    data = response.json()
    if "access_token" not in data:
        return {
            "success": False,
            "error": f"No access_token in response: {data}"
        }

    return {
        "success": True,
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 3600)
    }


def list_scripts(
    access_token: str,
    include_content: bool = False
) -> Dict[str, Any]:
    """
    List all pre-run CLI scripts.

    Args:
        access_token: OAuth access token
        include_content: If True, fetch content for each script

    Returns:
        Dict with success status and script list
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    url = f"{API_BASE}/setting/scripts"

    response = requests.get(url, headers=headers, timeout=60)

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"API request failed: {response.status_code} - {response.text}"
        }

    data = response.json()

    # FortiZTP API returns scripts under "data" key
    scripts = data.get("data") or []

    # Transform script data for cleaner output
    transformed_scripts = []
    for script in scripts:
        transformed = {
            "oid": script.get("oid"),
            "name": script.get("name"),
            "update_time": script.get("updateTime")
        }

        # Optionally fetch content for each script
        if include_content and transformed["oid"]:
            content_url = f"{API_BASE}/setting/scripts/{transformed['oid']}/content"
            content_response = requests.get(content_url, headers=headers, timeout=30)
            if content_response.status_code == 200:
                # Content may be raw text or JSON
                try:
                    content_data = content_response.json()
                    transformed["content"] = content_data.get("content") or content_data.get("script") or ""
                except Exception:
                    transformed["content"] = content_response.text

        transformed_scripts.append(transformed)

    return {
        "success": True,
        "script_count": len(transformed_scripts),
        "scripts": transformed_scripts
    }


def main(context) -> Dict[str, Any]:
    """
    Main entry point for the tool.

    Parameters:
        include_content: If True, fetch script content (default: False)
        api_username: Override credential file username
        api_password: Override credential file password

    Returns:
        Dict with success status and script list
    """
    # Extract parameters from context (context is ExecutionContext, not dict)
    params = getattr(context, "parameters", {}) if not isinstance(context, dict) else context

    # Load credentials
    creds = load_credentials()

    # Get authentication credentials - FortiZTP requires Local IAM users
    # Check local_iam.fortiztp first, then fall back to general credentials
    local_creds = creds.get("local_iam", {}).get("fortiztp", {})
    username = params.get("api_username") or local_creds.get("api_username") or creds.get("api_username")
    password = params.get("api_password") or local_creds.get("api_password") or creds.get("api_password")

    if not username or not password:
        return {
            "success": False,
            "error": "Missing API credentials. Configure forticloud_credentials.yaml or provide api_username/api_password parameters."
        }

    # Authenticate
    auth_result = get_oauth_token(username, password)
    if not auth_result["success"]:
        return auth_result

    access_token = auth_result["access_token"]

    # Get optional parameters
    include_content = params.get("include_content", False)

    # List scripts
    result = list_scripts(
        access_token=access_token,
        include_content=include_content
    )

    return result


if __name__ == "__main__":
    # Read parameters from stdin if provided
    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
        try:
            params = json.loads(input_data) if input_data.strip() else {}
        except json.JSONDecodeError:
            params = {}
    else:
        params = {}

    result = main(params)
    print(json.dumps(result, indent=2, default=str))
