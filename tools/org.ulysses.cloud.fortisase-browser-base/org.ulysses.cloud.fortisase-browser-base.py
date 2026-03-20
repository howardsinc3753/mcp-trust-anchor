#!/usr/bin/env python3
from __future__ import annotations

"""
FortiSASE Browser Automation Base Library

Provides browser automation foundation for FortiSASE portal operations.
Used by other FortiSASE tools for login, navigation, and session management.

This tool handles:
- FortiSASE portal authentication
- Session management with cookies
- TOTP/MFA handling
- Navigation and screenshot utilities

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Portal URLs
FORTISASE_LOGIN_URL = "https://login.forticloud.com"
FORTISASE_PORTAL_BASE = "https://www.fortisase.com"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# Session storage
SESSION_DIR = Path("C:/ProgramData/Ulysses/sessions")


def load_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load FortiSASE portal credentials."""
    creds = {
        "username": None,
        "password": None,
        "tenant_id": None,
        "mfa_secret": None
    }

    # Check parameters first
    for key in ["username", "password", "tenant_id", "mfa_secret"]:
        if params.get(key):
            creds[key] = params[key]

    if creds["username"] and creds["password"]:
        return creds

    # Check environment variables
    if os.environ.get("FORTISASE_USERNAME"):
        creds["username"] = os.environ["FORTISASE_USERNAME"]
    if os.environ.get("FORTISASE_PASSWORD"):
        creds["password"] = os.environ["FORTISASE_PASSWORD"]
    if os.environ.get("FORTISASE_TENANT_ID"):
        creds["tenant_id"] = os.environ["FORTISASE_TENANT_ID"]
    if os.environ.get("FORTISASE_MFA_SECRET"):
        creds["mfa_secret"] = os.environ["FORTISASE_MFA_SECRET"]

    if creds["username"] and creds["password"]:
        return creds

    # Try credential files
    for cred_path in CREDENTIAL_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, "r") as f:
                    config = yaml.safe_load(f)
                if config and "fortisase" in config:
                    sase_config = config["fortisase"]
                    if "username" in sase_config:
                        creds["username"] = sase_config["username"]
                    if "password" in sase_config:
                        creds["password"] = sase_config["password"]
                    if "tenant_id" in sase_config:
                        creds["tenant_id"] = sase_config["tenant_id"]
                    if "mfa_secret" in sase_config:
                        creds["mfa_secret"] = sase_config["mfa_secret"]
                    if creds["username"] and creds["password"]:
                        logger.info(f"Loaded FortiSASE credentials from {cred_path}")
                        return creds
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


def generate_totp(secret: str) -> str:
    """Generate TOTP code from base32 secret."""
    try:
        import hmac
        import hashlib
        import struct

        # Decode base32 secret
        secret_bytes = base64.b32decode(secret.upper().replace(" ", ""))

        # Get current time step (30 second intervals)
        counter = int(time.time()) // 30

        # Generate HMAC-SHA1
        counter_bytes = struct.pack(">Q", counter)
        hmac_hash = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()

        # Extract 6-digit code
        offset = hmac_hash[-1] & 0x0F
        code = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
        code = (code & 0x7FFFFFFF) % 1000000

        return str(code).zfill(6)
    except Exception as e:
        logger.error(f"TOTP generation failed: {e}")
        raise


async def login_to_fortisase(
    page,
    username: str,
    password: str,
    tenant_id: Optional[str] = None,
    mfa_secret: Optional[str] = None
) -> Dict[str, Any]:
    """
    Login to FortiSASE portal.

    Args:
        page: Playwright page object
        username: FortiSASE portal username (email)
        password: Portal password
        tenant_id: Optional tenant/organization ID
        mfa_secret: Optional TOTP secret for MFA

    Returns:
        Login result with session status
    """
    try:
        # Navigate to login
        logger.info("Navigating to FortiSASE login...")
        await page.goto(FORTISASE_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # Enter username
        logger.info("Entering username...")
        username_field = await page.wait_for_selector(
            'input[type="email"], input[name="username"], input[id="username"]',
            timeout=10000
        )
        await username_field.fill(username)

        # Click next/continue if separate username/password flow
        next_button = await page.query_selector('button[type="submit"], button:has-text("Next")')
        if next_button:
            await next_button.click()
            await asyncio.sleep(2)

        # Enter password
        logger.info("Entering password...")
        password_field = await page.wait_for_selector(
            'input[type="password"]',
            timeout=10000
        )
        await password_field.fill(password)

        # Submit login
        submit_button = await page.wait_for_selector(
            'button[type="submit"], button:has-text("Sign In"), button:has-text("Login")',
            timeout=5000
        )
        await submit_button.click()
        await asyncio.sleep(3)

        # Check for MFA prompt
        mfa_field = await page.query_selector(
            'input[name="otp"], input[name="totp"], input[placeholder*="code"]'
        )
        if mfa_field and mfa_secret:
            logger.info("MFA detected, entering TOTP code...")
            totp_code = generate_totp(mfa_secret)
            await mfa_field.fill(totp_code)

            # Submit MFA
            mfa_submit = await page.query_selector('button[type="submit"]')
            if mfa_submit:
                await mfa_submit.click()
                await asyncio.sleep(3)

        # Select tenant if required
        if tenant_id:
            tenant_selector = await page.query_selector(f'[data-tenant="{tenant_id}"], .tenant-item')
            if tenant_selector:
                logger.info(f"Selecting tenant: {tenant_id}")
                await tenant_selector.click()
                await asyncio.sleep(2)

        # Wait for dashboard
        await page.wait_for_load_state("networkidle")

        # Verify login success
        current_url = page.url
        if "fortisase.com" in current_url or "dashboard" in current_url.lower():
            logger.info("Login successful!")
            return {
                "success": True,
                "message": "Login successful",
                "current_url": current_url
            }
        else:
            # Check for error messages
            error_elem = await page.query_selector('.error-message, .alert-danger, [role="alert"]')
            error_text = ""
            if error_elem:
                error_text = await error_elem.text_content()

            return {
                "success": False,
                "error": error_text or "Login failed - unexpected page state",
                "current_url": current_url
            }

    except Exception as e:
        logger.exception(f"Login error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def navigate_to_section(page, section: str) -> Dict[str, Any]:
    """
    Navigate to a specific section in FortiSASE portal.

    Args:
        page: Playwright page object
        section: Section name (e.g., "users", "policies", "endpoints")

    Returns:
        Navigation result
    """
    section_map = {
        "dashboard": "/dashboard",
        "users": "/users",
        "endpoints": "/endpoints",
        "policies": "/policies",
        "security-policies": "/security-policies",
        "web-filter": "/web-filter",
        "dns-filter": "/dns-filter",
        "ssl-inspection": "/ssl-inspection",
        "logs": "/logs",
        "reports": "/reports",
        "settings": "/settings",
        "admin": "/admin",
    }

    try:
        path = section_map.get(section.lower(), f"/{section}")
        url = f"{FORTISASE_PORTAL_BASE}{path}"

        logger.info(f"Navigating to {section}...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)

        return {
            "success": True,
            "section": section,
            "url": page.url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def take_screenshot(page, name: str = "screenshot") -> Dict[str, Any]:
    """Take a screenshot of the current page."""
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SESSION_DIR / f"{name}_{timestamp}.png"

        await page.screenshot(path=str(screenshot_path), full_page=True)

        return {
            "success": True,
            "path": str(screenshot_path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def get_page_data(page) -> Dict[str, Any]:
    """Extract data from current page."""
    try:
        title = await page.title()
        url = page.url

        # Try to get any table data
        tables = await page.query_selector_all("table")
        table_data = []

        for table in tables[:3]:  # Limit to first 3 tables
            rows = await table.query_selector_all("tr")
            for row in rows[:20]:  # Limit rows
                cells = await row.query_selector_all("td, th")
                row_data = []
                for cell in cells:
                    text = await cell.text_content()
                    row_data.append(text.strip() if text else "")
                if row_data:
                    table_data.append(row_data)

        return {
            "success": True,
            "title": title,
            "url": url,
            "table_data": table_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute browser automation action."""
    logger.info("Executing FortiSASE Browser Base")

    action = params.get("action", "login")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"
        }

    # Load credentials
    creds = load_credentials(params)

    if action == "login" and (not creds["username"] or not creds["password"]):
        return {
            "success": False,
            "error": "FortiSASE credentials not configured. Set username/password in credentials file or parameters."
        }

    try:
        async with async_playwright() as p:
            # Launch browser
            headless = params.get("headless", True)
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            )
            page = await context.new_page()

            result = {"success": False, "action": action}

            if action == "login":
                result = await login_to_fortisase(
                    page,
                    creds["username"],
                    creds["password"],
                    creds.get("tenant_id"),
                    creds.get("mfa_secret")
                )
                result["action"] = "login"

            elif action == "navigate":
                section = params.get("section", "dashboard")
                # Login first
                login_result = await login_to_fortisase(
                    page,
                    creds["username"],
                    creds["password"],
                    creds.get("tenant_id"),
                    creds.get("mfa_secret")
                )
                if login_result.get("success"):
                    result = await navigate_to_section(page, section)
                else:
                    result = login_result
                result["action"] = "navigate"

            elif action == "screenshot":
                name = params.get("screenshot_name", "fortisase")
                result = await take_screenshot(page, name)
                result["action"] = "screenshot"

            elif action == "get_data":
                result = await get_page_data(page)
                result["action"] = "get_data"

            else:
                result = {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "available_actions": ["login", "navigate", "screenshot", "get_data"]
                }

            await browser.close()
            return result

    except Exception as e:
        logger.exception(f"Browser automation error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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

    test_params = {"action": "login"}
    if len(sys.argv) > 1:
        test_params["action"] = sys.argv[1]

    result = main(test_params)
    print(json.dumps(result, indent=2))
