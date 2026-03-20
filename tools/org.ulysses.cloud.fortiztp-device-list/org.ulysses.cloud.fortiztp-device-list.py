#!/usr/bin/env python3
"""
FortiZTP Device List Tool
List all devices with their ZTP provisioning status.

API: GET https://fortiztp.forticloud.com/public/api/v2/devices
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


def list_devices(
    access_token: str,
    device_type: Optional[str] = None,
    provision_status: Optional[str] = None,
    provision_target: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all devices with their ZTP provisioning status.

    Args:
        access_token: OAuth access token
        device_type: Filter by device type (FortiGate, FortiAP, FortiSwitch, FortiExtender)
        provision_status: Filter by status (provisioned, unprovisioned, hidden, incomplete)
        provision_target: Filter by target (FortiManager, FortiGateCloud, FortiEdgeCloud, ExternalController)

    Returns:
        Dict with success status and device list
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    url = f"{API_BASE}/devices"

    response = requests.get(url, headers=headers, timeout=60)

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"API request failed: {response.status_code} - {response.text}"
        }

    data = response.json()

    # Handle potential null or missing devices
    devices = data.get("devices") or []

    # Apply client-side filters if specified
    if device_type:
        devices = [d for d in devices if d.get("deviceType") == device_type]

    if provision_status:
        devices = [d for d in devices if d.get("provisionStatus") == provision_status]

    if provision_target:
        devices = [d for d in devices if d.get("provisionTarget") == provision_target]

    # Transform device data for cleaner output
    transformed_devices = []
    for device in devices:
        transformed = {
            "serial_number": device.get("deviceSN"),
            "device_type": device.get("deviceType"),
            "platform": device.get("platform"),
            "provision_status": device.get("provisionStatus"),
            "provision_sub_status": device.get("provisionSubStatus"),
            "provision_target": device.get("provisionTarget"),
            "region": device.get("region"),
            "firmware_profile": device.get("firmwareProfile"),
            "fortimanager_oid": device.get("fortiManagerOid"),
            "script_oid": device.get("scriptOid"),
            "use_default_script": device.get("useDefaultScript"),
            "external_controller_sn": device.get("externalControllerSn"),
            "external_controller_ip": device.get("externalControllerIp")
        }
        # Remove None values for cleaner output
        transformed = {k: v for k, v in transformed.items() if v is not None}
        transformed_devices.append(transformed)

    return {
        "success": True,
        "device_count": len(transformed_devices),
        "devices": transformed_devices
    }


def main(context) -> Dict[str, Any]:
    """
    Main entry point for the tool.

    Parameters:
        device_type: Filter by device type (FortiGate, FortiAP, FortiSwitch, FortiExtender)
        provision_status: Filter by status (provisioned, unprovisioned, hidden, incomplete)
        provision_target: Filter by target (FortiManager, FortiGateCloud, etc.)
        api_username: Override credential file username
        api_password: Override credential file password

    Returns:
        Dict with success status and device list
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

    # Get optional filters
    device_type = params.get("device_type")
    provision_status = params.get("provision_status")
    provision_target = params.get("provision_target")

    # List devices
    result = list_devices(
        access_token=access_token,
        device_type=device_type,
        provision_status=provision_status,
        provision_target=provision_target
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
