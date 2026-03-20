#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud Product List Tool

List registered products/assets from FortiCloud Asset Management API V3.
Returns products with entitlements matching search criteria.

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
from typing import Any, Dict, List, Optional

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


def list_products(
    token: str,
    serial_number: Optional[str] = None,
    expire_before: Optional[str] = None,
    status: Optional[str] = None,
    product_model: Optional[str] = None,
    account_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    List registered products from FortiCloud.

    Args:
        token: OAuth access token
        serial_number: Serial number or search pattern (e.g., "FGT*")
        expire_before: ISO 8601 date - return products expiring before this date
        status: "Registered" or "Pending"
        product_model: Product model filter (e.g., "FortiGate 90D")
        account_id: Account ID (required for Org scope users)

    Returns:
        API response with product list
    """
    url = f"{ASSET_API_BASE}/products/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload: Dict[str, Any] = {}
    if serial_number:
        payload["serialNumber"] = serial_number
    if expire_before:
        payload["expireBefore"] = expire_before
    if status:
        payload["status"] = status
    if product_model:
        payload["productModel"] = product_model
    if account_id is not None:
        payload["accountId"] = account_id

    logger.info(f"Listing products for account: {account_id or 'default'}")

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    return response.json()


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool."""
    logger.info("Executing FortiCloud Product List")

    try:
        # Load credentials (includes account_id from config)
        creds = load_credentials(params)
        if not creds["api_username"] or not creds["api_password"]:
            return {
                "success": False,
                "error": "No credentials found. Provide api_username/api_password parameters, "
                        "set FORTICLOUD_API_USERNAME/FORTICLOUD_API_PASSWORD environment variables, "
                        "or create a credential file."
            }

        # Get search parameters
        serial_number = params.get("serial_number")
        expire_before = params.get("expire_before")
        status = params.get("status")
        product_model = params.get("product_model")
        account_id = creds.get("account_id")

        # API requires at least serialNumber or expireBefore
        if not serial_number and not expire_before:
            # Use wildcard to get all products
            serial_number = "*"

        # Get OAuth token
        token = get_oauth_token(creds["api_username"], creds["api_password"])

        # Call API
        result = list_products(
            token,
            serial_number=serial_number,
            expire_before=expire_before,
            status=status,
            product_model=product_model,
            account_id=account_id
        )

        # Check API response status
        if result.get("status") != 0:
            return {
                "success": False,
                "error": result.get("message") or result.get("error") or "Unknown API error"
            }

        # Extract asset data (handle explicit null from API)
        assets = result.get("assets") or []

        # Format products
        products: List[Dict[str, Any]] = []
        for asset in assets:
            product = {
                "serial_number": asset.get("serialNumber"),
                "product_model": asset.get("productModel"),
                "status": asset.get("status"),
                "description": asset.get("description"),
                "folder_id": asset.get("folderId"),
                "folder_path": asset.get("folderPath"),
                "account_id": asset.get("accountId"),
                "registration_date": asset.get("registrationDate"),
                "is_decommissioned": asset.get("isDecommissioned"),
                "product_model_eor": asset.get("productModelEoR"),
                "product_model_eos": asset.get("productModelEoS"),
            }

            # Add entitlements summary
            entitlements = asset.get("entitlements", [])
            if entitlements:
                product["entitlements"] = [
                    {
                        "type": ent.get("typeDesc"),
                        "level": ent.get("levelDesc"),
                        "start_date": ent.get("startDate"),
                        "end_date": ent.get("endDate")
                    }
                    for ent in entitlements
                ]

            products.append(product)

        return {
            "success": True,
            "product_count": len(products),
            "products": products
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

    test_params = {}
    if len(sys.argv) > 1:
        test_params["serial_number"] = sys.argv[1]

    result = main(test_params)
    print(json.dumps(result, indent=2))
