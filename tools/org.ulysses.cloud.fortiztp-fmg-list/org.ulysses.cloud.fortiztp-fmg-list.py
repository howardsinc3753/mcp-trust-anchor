#!/usr/bin/env python3
"""
FortiZTP FortiManager List Tool
List FortiManagers registered for Zero Touch Provisioning.

API: GET https://fortiztp.forticloud.com/public/api/v2/setting/fortimanagers
Client ID: fortiztp

IMPORTANT: FortiZTP does NOT support ORG IAM API Users.
Only Local type IAM API Users work with this API.
"""

import json
import os
import sys
import requests
import yaml
from typing import Any, Dict

# FortiZTP API endpoints
AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
API_BASE = "https://fortiztp.forticloud.com/public/api/v2"
CLIENT_ID = "fortiztp"

DEFAULT_CRED_FILE = r"C:\ProgramData\Ulysses\config\forticloud_credentials.yaml"


def load_credentials(cred_file: str = DEFAULT_CRED_FILE) -> Dict[str, Any]:
    if not os.path.exists(cred_file):
        return {}
    with open(cred_file, 'r') as f:
        return yaml.safe_load(f) or {}


def get_oauth_token(username: str, password: str) -> Dict[str, Any]:
    payload = {
        "username": username,
        "password": password,
        "client_id": CLIENT_ID,
        "grant_type": "password"
    }
    response = requests.post(AUTH_URL, json=payload, timeout=30)
    if response.status_code != 200:
        return {"success": False, "error": f"Authentication failed: {response.status_code} - {response.text}"}
    data = response.json()
    if "access_token" not in data:
        return {"success": False, "error": f"No access_token in response: {data}"}
    return {"success": True, "access_token": data["access_token"]}


def list_fortimanagers(access_token: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{API_BASE}/setting/fortimanagers"
    response = requests.get(url, headers=headers, timeout=60)
    if response.status_code != 200:
        return {"success": False, "error": f"API request failed: {response.status_code} - {response.text}"}

    data = response.json()
    fortimanagers = data.get("fortiManagers") or []

    transformed = []
    for fmg in fortimanagers:
        transformed.append({
            "oid": fmg.get("oid"),
            "serial_number": fmg.get("sn"),
            "ip_address": fmg.get("ip"),
            "script_oid": fmg.get("scriptOid"),
            "update_time": fmg.get("updateTime")
        })

    return {
        "success": True,
        "fortimanager_count": len(transformed),
        "fortimanagers": transformed
    }


def main(context) -> Dict[str, Any]:
    # Extract parameters from context (context is ExecutionContext, not dict)
    params = getattr(context, "parameters", {}) if not isinstance(context, dict) else context

    creds = load_credentials()
    # Get authentication credentials - FortiZTP requires Local IAM users
    # Check local_iam.fortiztp first, then fall back to general credentials
    local_creds = creds.get("local_iam", {}).get("fortiztp", {})
    username = params.get("api_username") or local_creds.get("api_username") or creds.get("api_username")
    password = params.get("api_password") or local_creds.get("api_password") or creds.get("api_password")

    if not username or not password:
        return {"success": False, "error": "Missing API credentials. Configure forticloud_credentials.yaml or provide api_username/api_password parameters."}

    auth_result = get_oauth_token(username, password)
    if not auth_result["success"]:
        return auth_result

    return list_fortimanagers(auth_result["access_token"])


if __name__ == "__main__":
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
