#!/usr/bin/env python3
"""
FortiFlex Config Create Tool

Create new FortiFlex configurations for FortiGate VMs and other products.
Configurations define the product bundle (CPU cores, services) that tokens are created from.

API Reference: https://support.fortinet.com/ES/api/fortiflex/v2/
Client ID: flexvm

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-18
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# API Configuration
AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
FORTIFLEX_API_BASE = "https://support.fortinet.com/ES/api/fortiflex/v2"
CLIENT_ID = "flexvm"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# Product Type IDs
PRODUCT_TYPES = {
    "fortigate-vm": 1,
    "fortimanager-vm": 2,
    "fortiweb-vm": 3,
    "fortigate-hardware": 4,
    "fortianalyzer-vm": 5,
    "fortiadc-vm": 6,
    "fortiportal-vm": 7,
    "fortiap": 101,
    "fortiswitch": 102,
    "forticlient-ems": 201,
    "fortigate-vm-lcs": 301,
    "forticloudprivate": 401,
}

# Service codes
SERVICE_CODES = {
    "FC": "FortiCare Premium",
    "UTP": "Unified Threat Protection",
    "ENT": "Enterprise Bundle",
    "ATP": "Advanced Threat Protection",
    "IPS": "Intrusion Prevention",
    "AV": "AntiVirus",
    "WEB": "Web Filtering",
    "FAMS": "FortiAnalyzer Management",
    "SWNM": "SD-WAN Orchestrator",
    "AVDB": "AV + Botnet IP/Domain",
    "FURL": "FortiURL",
    "IOTH": "IoT Detection",
    "FGSA": "FortiGate Security Audit",
    "ISSS": "Industrial Security",
}


def load_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load API credentials and program serial number."""
    creds = {
        "api_username": None,
        "api_password": None,
        "program_serial_number": None
    }

    # Check parameters first
    for key in creds.keys():
        if params.get(key):
            creds[key] = params[key]

    # Check environment variables
    if not creds["api_username"] and os.environ.get("FORTICLOUD_API_USERNAME"):
        creds["api_username"] = os.environ["FORTICLOUD_API_USERNAME"]
    if not creds["api_password"] and os.environ.get("FORTICLOUD_API_PASSWORD"):
        creds["api_password"] = os.environ["FORTICLOUD_API_PASSWORD"]
    if not creds["program_serial_number"] and os.environ.get("FORTIFLEX_PROGRAM_SN"):
        creds["program_serial_number"] = os.environ["FORTIFLEX_PROGRAM_SN"]

    if creds["api_username"] and creds["api_password"]:
        # Also load program SN from file if not set
        if not creds["program_serial_number"]:
            for cred_path in CREDENTIAL_PATHS:
                if cred_path.exists():
                    try:
                        with open(cred_path, "r") as f:
                            config = yaml.safe_load(f)
                        if config and "program_serial_number" in config:
                            creds["program_serial_number"] = config["program_serial_number"]
                            break
                    except Exception:
                        pass
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
                    if "program_serial_number" in config:
                        creds["program_serial_number"] = config["program_serial_number"]
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


def create_config(
    token: str,
    program_serial_number: str,
    name: str,
    product_type_id: int,
    cpu: int,
    services: List[str],
    vdom: int = 0,
    account_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a new FortiFlex configuration.

    Args:
        token: OAuth access token
        program_serial_number: Program SN (ELAVMSXXXXXXXX)
        name: Configuration name
        product_type_id: Product type ID (1 = FortiGate VM)
        cpu: Number of CPU cores (1, 2, 4, 8, 16, etc.)
        services: List of service codes (UTP, ENT, etc.)
        vdom: Number of VDOMs (default 0)
        account_id: Optional customer account ID for MSSP multi-tenant

    Returns:
        API response
    """
    url = f"{FORTIFLEX_API_BASE}/configs/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Build parameters array for FortiGate-VM
    # Based on working MSSP toolkit format
    parameters: List[Dict[str, Any]] = [
        {"id": 1, "value": str(cpu)},      # CPU count (as string)
        {"id": 2, "value": services[0] if services else "UTP"},  # Main service pack
        {"id": 10, "value": str(vdom)},    # VDOM count
        {"id": 43, "value": "NONE"},       # Additional service pack 1
        {"id": 44, "value": "NONE"},       # Additional service pack 2
        {"id": 45, "value": "NONE"},       # Additional service pack 3
    ]

    # Add additional services to slots 43, 44, 45 if provided
    addon_services = services[1:] if len(services) > 1 else []
    addon_ids = [43, 44, 45]
    for i, svc in enumerate(addon_services[:3]):
        parameters[3 + i] = {"id": addon_ids[i], "value": svc.upper()}

    payload = {
        "programSerialNumber": program_serial_number,
        "name": name,
        "productTypeId": product_type_id,
        "parameters": parameters
    }

    # Add account_id for MSSP multi-tenant
    if account_id:
        payload["accountId"] = account_id

    logger.info(f"Creating configuration '{name}' with {cpu} CPUs and services: {services}")
    logger.info(f"Parameters: {parameters}")

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    # Capture detailed error on failure
    if response.status_code != 200:
        try:
            error_data = response.json()
            logger.error(f"API Error: {error_data}")
        except Exception:
            logger.error(f"HTTP {response.status_code}: {response.text}")

    response.raise_for_status()

    return response.json()


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool (synchronous)."""
    logger.info("Executing FortiFlex Config Create")

    try:
        # Validate required parameters
        name = params.get("name")
        if not name:
            return {"success": False, "error": "Missing required parameter: name"}

        cpu = params.get("cpu", 2)
        if cpu not in [1, 2, 4, 8, 16, 32, 96]:
            return {
                "success": False,
                "error": f"Invalid CPU value: {cpu}. Valid values: 1, 2, 4, 8, 16, 32, 96"
            }

        # Parse product type
        product_type = params.get("product_type", "fortigate-vm").lower()
        product_type_id = PRODUCT_TYPES.get(product_type)
        if not product_type_id:
            return {
                "success": False,
                "error": f"Unknown product type: {product_type}. Valid types: {list(PRODUCT_TYPES.keys())}"
            }

        # Parse services
        services = params.get("services", ["FC", "UTP", "ENT"])
        if isinstance(services, str):
            services = [s.strip().upper() for s in services.split(",")]
        else:
            services = [s.upper() for s in services]

        # Load credentials
        creds = load_credentials(params)
        if not creds["api_username"] or not creds["api_password"]:
            return {
                "success": False,
                "error": "No credentials found. Provide api_username/api_password or configure credential file."
            }

        program_sn = creds["program_serial_number"]
        if not program_sn:
            return {
                "success": False,
                "error": "Missing program_serial_number. Use fortiflex-programs-list to find it."
            }

        # Get optional parameters
        vdom = params.get("vdom", 0)
        account_id = params.get("account_id")

        # Get OAuth token
        oauth_token = get_oauth_token(creds["api_username"], creds["api_password"])

        # Create configuration
        result = create_config(
            oauth_token,
            program_sn,
            name,
            product_type_id,
            cpu,
            services,
            vdom,
            account_id
        )

        # Check response
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract created config
        configs = result.get("configs", [])
        if not configs:
            return {
                "success": False,
                "error": "No configuration returned in response"
            }

        created_config = configs[0]

        return {
            "success": True,
            "config_id": created_config.get("id"),
            "name": name,
            "product_type": product_type,
            "cpu": cpu,
            "services": services,
            "program_serial_number": program_sn,
            "status": created_config.get("status"),
            "message": f"Configuration created. Use config_id={created_config.get('id')} with fortiflex-token-create"
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
    """Entry point for MCP execution."""
    if hasattr(context, "parameters"):
        params = context.parameters
    elif isinstance(context, dict):
        params = context
    else:
        params = {}

    return execute(params)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python tool.py <name> [cpu] [services]")
        print("Example: python tool.py sdwan-fgt-2cpu 2 FC,UTP,ENT")
        sys.exit(1)

    test_params = {"name": sys.argv[1]}
    if len(sys.argv) > 2:
        test_params["cpu"] = int(sys.argv[2])
    if len(sys.argv) > 3:
        test_params["services"] = sys.argv[3]

    result = main(test_params)
    print(json.dumps(result, indent=2))
