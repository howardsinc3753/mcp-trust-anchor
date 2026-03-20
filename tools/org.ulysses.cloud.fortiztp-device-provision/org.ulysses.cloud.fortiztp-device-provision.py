#!/usr/bin/env python3
"""
FortiZTP Device Provision Tool
Provision or unprovision a device for Zero Touch Provisioning.

API: PUT https://fortiztp.forticloud.com/public/api/v2/devices/{deviceSN}
Client ID: fortiztp

Provision targets:
- FortiManager: requires externalControllerSn and externalControllerIp (or fortiManagerOid)
- FortiGateCloud: requires region
- FortiEdgeCloud: requires region
- ExternalController: requires externalControllerIp

IMPORTANT: FortiZTP does NOT support ORG IAM API Users.
Only Local type IAM API Users work with this API.
"""

import json
import os
import sys
import requests
import yaml
from typing import Any, Dict, Optional

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


def provision_device(
    access_token: str,
    device_sn: str,
    device_type: str,
    provision_status: str,
    provision_target: Optional[str] = None,
    region: Optional[str] = None,
    fortimanager_oid: Optional[int] = None,
    script_oid: Optional[int] = None,
    use_default_script: Optional[bool] = None,
    external_controller_sn: Optional[str] = None,
    external_controller_ip: Optional[str] = None,
    firmware_profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Provision or unprovision a device.

    Args:
        access_token: OAuth access token
        device_sn: Device serial number
        device_type: Device type (FortiGate, FortiAP, FortiSwitch, FortiExtender)
        provision_status: 'provisioned' or 'unprovisioned'
        provision_target: FortiManager, FortiGateCloud, FortiEdgeCloud, ExternalController
        region: FortiCloud region (required for cloud targets)
        fortimanager_oid: FortiManager OID (for FortiManager target)
        script_oid: Script OID for pre-run CLI script
        use_default_script: Use the default script
        external_controller_sn: External controller serial number
        external_controller_ip: External controller IP address
        firmware_profile: Firmware profile name

    Returns:
        Dict with success status and provisioning result
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    url = f"{API_BASE}/devices/{device_sn}"

    # Build payload - deviceType is REQUIRED by FortiZTP API
    payload = {
        "deviceType": device_type,
        "provisionStatus": provision_status
    }

    # Add optional fields based on provision target
    if provision_target:
        payload["provisionTarget"] = provision_target

    if region:
        payload["region"] = region

    if fortimanager_oid is not None:
        payload["fortiManagerOid"] = fortimanager_oid

    if script_oid is not None:
        payload["scriptOid"] = script_oid

    if use_default_script is not None:
        payload["useDefaultScript"] = use_default_script

    if external_controller_sn:
        payload["externalControllerSn"] = external_controller_sn

    if external_controller_ip:
        payload["externalControllerIp"] = external_controller_ip

    if firmware_profile:
        payload["firmwareProfile"] = firmware_profile

    response = requests.put(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"Provision request failed: {response.status_code} - {response.text}"
        }

    # Parse response - API may return empty body on success
    try:
        data = response.json() if response.text.strip() else {}
    except Exception:
        data = {}

    return {
        "success": True,
        "message": f"Device {device_sn} ({device_type}) {provision_status} successfully",
        "device": {
            "serial_number": device_sn,
            "device_type": device_type,
            "provision_status": provision_status,
            "provision_target": provision_target,
            "fortimanager_oid": fortimanager_oid,
            "script_oid": script_oid
        },
        "api_response": data
    }


def main(context) -> Dict[str, Any]:
    """
    Main entry point for the tool.

    Parameters:
        device_sn: Device serial number (required)
        device_type: Device type - FortiGate, FortiAP, FortiSwitch, FortiExtender (required)
        provision_status: 'provisioned' or 'unprovisioned' (default: provisioned)
        provision_target: FortiManager, FortiGateCloud, FortiEdgeCloud, ExternalController
        region: FortiCloud region
        fortimanager_oid: FortiManager OID
        script_oid: Script OID for bootstrap script
        use_default_script: Use default script
        external_controller_sn: External controller serial number
        external_controller_ip: External controller IP
        firmware_profile: Firmware profile name
        api_username: Override credential file username
        api_password: Override credential file password

    Returns:
        Dict with success status and provisioning result
    """
    # Extract parameters from context (context is ExecutionContext, not dict)
    params = getattr(context, "parameters", {}) if not isinstance(context, dict) else context

    # Validate required parameters
    device_sn = params.get("device_sn")
    device_type = params.get("device_type")
    provision_status = params.get("provision_status", "provisioned")

    if not device_sn:
        return {
            "success": False,
            "error": "Missing required parameter: device_sn"
        }

    if not device_type:
        return {
            "success": False,
            "error": "Missing required parameter: device_type (FortiGate, FortiAP, FortiSwitch, or FortiExtender)"
        }

    valid_device_types = ["FortiGate", "FortiAP", "FortiSwitch", "FortiExtender"]
    if device_type not in valid_device_types:
        return {
            "success": False,
            "error": f"Invalid device_type: {device_type}. Must be one of: {', '.join(valid_device_types)}"
        }

    if provision_status not in ["provisioned", "unprovisioned"]:
        return {
            "success": False,
            "error": f"Invalid provision_status: {provision_status}. Must be 'provisioned' or 'unprovisioned'"
        }

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

    # Provision device
    result = provision_device(
        access_token=access_token,
        device_sn=device_sn,
        device_type=device_type,
        provision_status=provision_status,
        provision_target=params.get("provision_target"),
        region=params.get("region"),
        fortimanager_oid=params.get("fortimanager_oid"),
        script_oid=params.get("script_oid"),
        use_default_script=params.get("use_default_script"),
        external_controller_sn=params.get("external_controller_sn"),
        external_controller_ip=params.get("external_controller_ip"),
        firmware_profile=params.get("firmware_profile")
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
