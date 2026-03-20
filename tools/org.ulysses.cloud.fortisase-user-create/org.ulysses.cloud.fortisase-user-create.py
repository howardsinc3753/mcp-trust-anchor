#!/usr/bin/env python3
from __future__ import annotations

"""
FortiSASE User Create Tool

Create users in FortiSASE via browser automation.
Handles the user creation workflow in the FortiSASE portal.

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Portal URLs
FORTISASE_LOGIN_URL = "https://login.forticloud.com"
FORTISASE_USERS_URL = "https://www.fortisase.com/users"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# Input validation patterns
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_.]+$")


def validate_input(value: str, pattern: re.Pattern, field_name: str) -> tuple[bool, Optional[str]]:
    """Validate input against pattern."""
    if not value:
        return False, f"{field_name} is required"
    if not pattern.match(value):
        return False, f"Invalid {field_name} format"
    return True, None


def load_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load FortiSASE portal credentials."""
    creds = {
        "admin_username": None,
        "admin_password": None,
        "tenant_id": None,
        "mfa_secret": None
    }

    # Check parameters
    if params.get("admin_username"):
        creds["admin_username"] = params["admin_username"]
    if params.get("admin_password"):
        creds["admin_password"] = params["admin_password"]
    if params.get("tenant_id"):
        creds["tenant_id"] = params["tenant_id"]
    if params.get("mfa_secret"):
        creds["mfa_secret"] = params["mfa_secret"]

    if creds["admin_username"] and creds["admin_password"]:
        return creds

    # Check environment variables
    if os.environ.get("FORTISASE_USERNAME"):
        creds["admin_username"] = os.environ["FORTISASE_USERNAME"]
    if os.environ.get("FORTISASE_PASSWORD"):
        creds["admin_password"] = os.environ["FORTISASE_PASSWORD"]
    if os.environ.get("FORTISASE_TENANT_ID"):
        creds["tenant_id"] = os.environ["FORTISASE_TENANT_ID"]
    if os.environ.get("FORTISASE_MFA_SECRET"):
        creds["mfa_secret"] = os.environ["FORTISASE_MFA_SECRET"]

    if creds["admin_username"] and creds["admin_password"]:
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
                        creds["admin_username"] = sase_config["username"]
                    if "password" in sase_config:
                        creds["admin_password"] = sase_config["password"]
                    if "tenant_id" in sase_config:
                        creds["tenant_id"] = sase_config["tenant_id"]
                    if "mfa_secret" in sase_config:
                        creds["mfa_secret"] = sase_config["mfa_secret"]
                    if creds["admin_username"] and creds["admin_password"]:
                        logger.info(f"Loaded credentials from {cred_path}")
                        return creds
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


def generate_totp(secret: str) -> str:
    """Generate TOTP code from base32 secret."""
    import base64
    import hashlib
    import hmac
    import struct

    secret_bytes = base64.b32decode(secret.upper().replace(" ", ""))
    counter = int(time.time()) // 30
    counter_bytes = struct.pack(">Q", counter)
    hmac_hash = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
    code = (code & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


async def login_to_fortisase(page, username: str, password: str, mfa_secret: Optional[str] = None) -> bool:
    """Login to FortiSASE portal."""
    try:
        await page.goto(FORTISASE_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # Enter username
        username_field = await page.wait_for_selector(
            'input[type="email"], input[name="username"]',
            timeout=10000
        )
        await username_field.fill(username)

        # Click next if present
        next_btn = await page.query_selector('button[type="submit"], button:has-text("Next")')
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(2)

        # Enter password
        password_field = await page.wait_for_selector('input[type="password"]', timeout=10000)
        await password_field.fill(password)

        # Submit
        submit_btn = await page.wait_for_selector(
            'button[type="submit"], button:has-text("Sign In")',
            timeout=5000
        )
        await submit_btn.click()
        await asyncio.sleep(3)

        # Handle MFA if needed
        mfa_field = await page.query_selector('input[name="otp"], input[name="totp"]')
        if mfa_field and mfa_secret:
            totp_code = generate_totp(mfa_secret)
            await mfa_field.fill(totp_code)
            mfa_submit = await page.query_selector('button[type="submit"]')
            if mfa_submit:
                await mfa_submit.click()
                await asyncio.sleep(3)

        await page.wait_for_load_state("networkidle")
        return "fortisase.com" in page.url or "dashboard" in page.url.lower()

    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False


async def create_user_via_portal(
    page,
    email: str,
    first_name: str,
    last_name: str,
    user_group: Optional[str] = None,
    send_invite: bool = True
) -> Dict[str, Any]:
    """
    Create a user in FortiSASE portal.

    Args:
        page: Playwright page object
        email: User email address
        first_name: User first name
        last_name: User last name
        user_group: Optional user group to assign
        send_invite: Send invitation email

    Returns:
        Creation result
    """
    try:
        # Navigate to users section
        logger.info("Navigating to users section...")
        await page.goto(FORTISASE_USERS_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # Click Add User / Create button
        add_button = await page.wait_for_selector(
            'button:has-text("Add User"), button:has-text("Create"), button:has-text("New User"), [data-action="add"]',
            timeout=10000
        )
        await add_button.click()
        await asyncio.sleep(2)

        # Fill in user form
        logger.info(f"Creating user: {email}")

        # Email field
        email_field = await page.wait_for_selector(
            'input[name="email"], input[type="email"], input[placeholder*="email"]',
            timeout=10000
        )
        await email_field.fill(email)

        # First name
        first_name_field = await page.query_selector(
            'input[name="firstName"], input[name="first_name"], input[placeholder*="First"]'
        )
        if first_name_field:
            await first_name_field.fill(first_name)

        # Last name
        last_name_field = await page.query_selector(
            'input[name="lastName"], input[name="last_name"], input[placeholder*="Last"]'
        )
        if last_name_field:
            await last_name_field.fill(last_name)

        # User group selection if specified
        if user_group:
            group_selector = await page.query_selector(
                'select[name="group"], select[name="userGroup"], [data-field="group"]'
            )
            if group_selector:
                await group_selector.select_option(label=user_group)

        # Send invite checkbox
        if send_invite:
            invite_checkbox = await page.query_selector(
                'input[name="sendInvite"], input[type="checkbox"][name*="invite"]'
            )
            if invite_checkbox:
                is_checked = await invite_checkbox.is_checked()
                if not is_checked:
                    await invite_checkbox.click()

        # Submit form
        await asyncio.sleep(1)
        submit_button = await page.wait_for_selector(
            'button[type="submit"], button:has-text("Create"), button:has-text("Save"), button:has-text("Add")',
            timeout=5000
        )
        await submit_button.click()
        await asyncio.sleep(3)

        # Check for success
        success_indicator = await page.query_selector(
            '.success, .alert-success, [role="alert"]:has-text("success"), .toast-success'
        )
        error_indicator = await page.query_selector(
            '.error, .alert-danger, .alert-error, [role="alert"]:has-text("error")'
        )

        if error_indicator:
            error_text = await error_indicator.text_content()
            return {
                "success": False,
                "error": error_text or "User creation failed"
            }

        return {
            "success": True,
            "message": f"User {email} created successfully",
            "user": {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "user_group": user_group,
                "invite_sent": send_invite
            }
        }

    except Exception as e:
        logger.exception(f"User creation error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool."""
    logger.info("Executing FortiSASE User Create")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"
        }

    # Validate required parameters
    email = params.get("email")
    if not email:
        return {"success": False, "error": "Missing required parameter: email"}

    is_valid, error = validate_input(email, EMAIL_PATTERN, "email")
    if not is_valid:
        return {"success": False, "error": error}

    first_name = params.get("first_name", "")
    last_name = params.get("last_name", "")

    if first_name:
        is_valid, error = validate_input(first_name, NAME_PATTERN, "first_name")
        if not is_valid:
            return {"success": False, "error": error}

    if last_name:
        is_valid, error = validate_input(last_name, NAME_PATTERN, "last_name")
        if not is_valid:
            return {"success": False, "error": error}

    # Load admin credentials
    creds = load_credentials(params)
    if not creds["admin_username"] or not creds["admin_password"]:
        return {
            "success": False,
            "error": "FortiSASE admin credentials not configured"
        }

    try:
        async with async_playwright() as p:
            headless = params.get("headless", True)
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            # Login
            logger.info("Logging in to FortiSASE...")
            login_success = await login_to_fortisase(
                page,
                creds["admin_username"],
                creds["admin_password"],
                creds.get("mfa_secret")
            )

            if not login_success:
                await browser.close()
                return {
                    "success": False,
                    "error": "Failed to login to FortiSASE portal"
                }

            # Create user
            result = await create_user_via_portal(
                page,
                email=email,
                first_name=first_name,
                last_name=last_name,
                user_group=params.get("user_group"),
                send_invite=params.get("send_invite", True)
            )

            await browser.close()
            return result

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

    if len(sys.argv) < 2:
        print("Usage: python tool.py <email> [first_name] [last_name]")
        sys.exit(1)

    test_params = {"email": sys.argv[1]}
    if len(sys.argv) > 2:
        test_params["first_name"] = sys.argv[2]
    if len(sys.argv) > 3:
        test_params["last_name"] = sys.argv[3]

    result = main(test_params)
    print(json.dumps(result, indent=2))
