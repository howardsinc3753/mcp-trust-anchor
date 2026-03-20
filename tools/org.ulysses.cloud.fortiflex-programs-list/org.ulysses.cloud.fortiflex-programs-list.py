#!/usr/bin/env python3
"""
FortiFlex Programs List Tool

List all FortiFlex programs available in your FortiCloud account.
Returns program serial numbers needed for other FortiFlex operations.

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


def load_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load API credentials."""
    creds = {
        "api_username": None,
        "api_password": None
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


def list_programs(token: str) -> Dict[str, Any]:
    """
    List all FortiFlex programs.

    Args:
        token: OAuth access token

    Returns:
        API response with programs list
    """
    url = f"{FORTIFLEX_API_BASE}/programs/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    logger.info("Listing FortiFlex programs")

    response = requests.post(url, headers=headers, json={}, timeout=60)
    response.raise_for_status()

    return response.json()


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool (synchronous)."""
    logger.info("Executing FortiFlex Programs List")

    try:
        # Load credentials
        creds = load_credentials(params)
        if not creds["api_username"] or not creds["api_password"]:
            return {
                "success": False,
                "error": "No credentials found. Provide api_username/api_password or configure credential file."
            }

        # Get OAuth token
        oauth_token = get_oauth_token(creds["api_username"], creds["api_password"])

        # List programs
        result = list_programs(oauth_token)

        # Check response
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract programs
        programs = result.get("programs", [])

        # Format output
        formatted_programs: List[Dict[str, Any]] = []
        for prog in programs:
            formatted_programs.append({
                "serial_number": prog.get("serialNumber"),
                "account_id": prog.get("accountId"),
                "start_date": prog.get("startDate"),
                "end_date": prog.get("endDate"),
                "has_support_coverage": prog.get("hasSupportCoverage", False),
                "points": {
                    "available": prog.get("availablePoints", 0),
                    "used": prog.get("usedPoints", 0)
                }
            })

        return {
            "success": True,
            "program_count": len(formatted_programs),
            "programs": formatted_programs
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
    logging.basicConfig(level=logging.INFO)
    result = main({})
    print(json.dumps(result, indent=2))
