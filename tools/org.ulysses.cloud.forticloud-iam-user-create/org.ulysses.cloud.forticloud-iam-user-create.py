#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud IAM API User Create Tool

Create IAM API users in FortiCloud using Playwright browser automation.
This tool automates the IAM portal because there is no API for this operation.

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-16
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# FortiCloud URLs
FORTICLOUD_LOGIN_URL = "https://support.fortinet.com/login"
FORTICLOUD_IAM_URL = "https://support.fortinet.com/iam"
IAM_API_USERS_URL = "https://support.fortinet.com/iam/#/apiusers"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# Portal permission mappings (portal display name -> selector hints)
PORTAL_MAPPINGS = {
    "FlexVM": ["flexvm", "flex-vm", "FortiFlex"],
    "FortiFlex": ["flexvm", "flex-vm", "FortiFlex"],
    "Asset Management": ["asset", "registration"],
    "Organization": ["organization", "org"],
    "IAM": ["iam", "identity"],
    "FortiGate Cloud": ["fortigate-cloud", "fgt-cloud"],
    "FortiAnalyzer Cloud": ["fortianalyzer", "faz"],
    "FortiSASE": ["fortisase", "sase"],
}


def load_portal_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Load portal credentials from parameters or config file."""
    creds = {
        "portal_username": None,
        "portal_password": None,
        "mfa_secret": None
    }

    # Check parameters
    for key in creds.keys():
        if params.get(key):
            creds[key] = params[key]

    if creds["portal_username"] and creds["portal_password"]:
        return creds

    # Check environment
    if os.environ.get("FORTICLOUD_PORTAL_USERNAME"):
        creds["portal_username"] = os.environ["FORTICLOUD_PORTAL_USERNAME"]
    if os.environ.get("FORTICLOUD_PORTAL_PASSWORD"):
        creds["portal_password"] = os.environ["FORTICLOUD_PORTAL_PASSWORD"]
    if os.environ.get("FORTICLOUD_MFA_SECRET"):
        creds["mfa_secret"] = os.environ["FORTICLOUD_MFA_SECRET"]

    if creds["portal_username"] and creds["portal_password"]:
        return creds

    # Check config files
    for cred_path in CREDENTIAL_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, "r") as f:
                    config = yaml.safe_load(f)
                portal_config = config.get("portal", {})
                if portal_config.get("username"):
                    creds["portal_username"] = portal_config["username"]
                if portal_config.get("password"):
                    creds["portal_password"] = portal_config["password"]
                if portal_config.get("mfa_secret"):
                    creds["mfa_secret"] = portal_config["mfa_secret"]
                if creds["portal_username"] and creds["portal_password"]:
                    return creds
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


def save_api_credentials(
    api_username: str,
    api_password: str,
    user_name: str,
    permissions: List[Dict]
) -> str:
    """Save created API credentials to config file."""
    config_path = CREDENTIAL_PATHS[0]
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}

    # Add/update API credentials
    if "api_users" not in config:
        config["api_users"] = {}

    config["api_users"][user_name] = {
        "api_username": api_username,
        "api_password": api_password,
        "permissions": permissions,
        "created_at": datetime.now().isoformat()
    }

    # Also set as default if this is the first API user
    if "api_username" not in config:
        config["api_username"] = api_username
        config["api_password"] = api_password

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    logger.info(f"Saved API credentials to {config_path}")
    return str(config_path)


async def create_iam_api_user(
    page,
    user_name: str,
    description: Optional[str],
    permissions: List[Dict]
) -> Dict[str, Any]:
    """
    Create IAM API user through the portal UI.

    This function handles the actual UI interaction to create the API user.

    Args:
        page: Playwright page object
        user_name: Name for the API user
        description: Optional description
        permissions: List of permission configurations

    Returns:
        Dict with api_username, api_password, or error
    """
    # Navigate to API Users section
    logger.info("Navigating to IAM API Users section")
    await page.goto(IAM_API_USERS_URL, wait_until="networkidle")
    await asyncio.sleep(2)

    # Wait for the page to load
    try:
        # Look for "Add API User" or "Create" button
        add_button = await page.wait_for_selector(
            'button:has-text("Add"), button:has-text("Create"), '
            'a:has-text("Add API User"), button:has-text("New")',
            timeout=15000
        )
        await add_button.click()
        logger.info("Clicked Add API User button")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Could not find Add API User button: {e}")
        # Take debug screenshot
        await page.screenshot(path="screenshots/iam_debug.png")
        return {"error": f"Could not find Add API User button: {e}"}

    # Fill in user name
    try:
        name_input = await page.wait_for_selector(
            'input[name="name"], input[placeholder*="name"], '
            'input[id*="name"], input[aria-label*="name"]',
            timeout=10000
        )
        await name_input.fill(user_name)
        logger.info(f"Entered user name: {user_name}")
    except Exception as e:
        logger.error(f"Could not find name input: {e}")
        return {"error": f"Could not find name input: {e}"}

    # Fill in description if provided
    if description:
        try:
            desc_input = await page.query_selector(
                'input[name="description"], textarea[name="description"], '
                'input[placeholder*="description"], textarea[placeholder*="description"]'
            )
            if desc_input:
                await desc_input.fill(description)
                logger.info("Entered description")
        except Exception:
            pass  # Description is optional

    # Configure permissions
    for perm in permissions:
        portal = perm.get("portal", "")
        access = perm.get("access", "ReadOnly")
        scope = perm.get("scope", "Local")

        logger.info(f"Setting permission: {portal} - {access} - {scope}")

        try:
            # Find the portal row or checkbox
            portal_hints = PORTAL_MAPPINGS.get(portal, [portal.lower()])

            portal_row = None
            for hint in portal_hints:
                try:
                    portal_row = await page.query_selector(
                        f'tr:has-text("{hint}"), div:has-text("{hint}"), '
                        f'label:has-text("{hint}")'
                    )
                    if portal_row:
                        break
                except Exception:
                    continue

            if portal_row:
                # Enable the portal (checkbox)
                checkbox = await portal_row.query_selector('input[type="checkbox"]')
                if checkbox:
                    is_checked = await checkbox.is_checked()
                    if not is_checked:
                        await checkbox.click()

                # Select access level
                access_select = await portal_row.query_selector(
                    'select, [role="combobox"], [role="listbox"]'
                )
                if access_select:
                    await access_select.select_option(value=access)
                    # Or try clicking and selecting
                else:
                    # Try radio buttons or other selectors for access level
                    access_option = await portal_row.query_selector(
                        f'input[value="{access}"], label:has-text("{access}")'
                    )
                    if access_option:
                        await access_option.click()

                # Select scope
                scope_select = await portal_row.query_selector(
                    'select:nth-of-type(2), [data-scope]'
                )
                if scope_select:
                    await scope_select.select_option(value=scope)
        except Exception as e:
            logger.warning(f"Could not configure permission for {portal}: {e}")

    await asyncio.sleep(1)

    # Submit the form
    try:
        submit_button = await page.query_selector(
            'button[type="submit"], button:has-text("Save"), '
            'button:has-text("Create"), button:has-text("OK")'
        )
        if submit_button:
            await submit_button.click()
            logger.info("Clicked submit button")
            await asyncio.sleep(3)
    except Exception as e:
        logger.error(f"Could not submit form: {e}")
        return {"error": f"Could not submit form: {e}"}

    # Capture the credentials (they should appear in a modal or message)
    api_username = None
    api_password = None

    try:
        # Wait for credentials modal/display
        await asyncio.sleep(2)

        # Look for the API ID (UUID format)
        api_id_elements = await page.query_selector_all(
            'input[readonly], span:has-text("-"), code, .api-id, '
            '[data-api-id], td:has-text("-")'
        )

        for elem in api_id_elements:
            text = await elem.text_content() or await elem.get_attribute("value") or ""
            # UUID pattern: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            if len(text) == 36 and text.count("-") == 4:
                api_username = text.strip()
                logger.info(f"Found API ID: {api_username}")
                break

        # Look for the password
        password_elements = await page.query_selector_all(
            'input[type="password"], input[readonly]:not([value*="-"]), '
            '.api-password, [data-password], code'
        )

        for elem in password_elements:
            text = await elem.text_content() or await elem.get_attribute("value") or ""
            # Password is typically longer and contains special chars
            if len(text) > 20 and "!" in text:
                api_password = text.strip()
                logger.info("Found API password")
                break

        # Try to find "Download" button for credentials file
        download_button = await page.query_selector(
            'button:has-text("Download"), a:has-text("Download"), '
            'button:has-text("Export")'
        )
        if download_button:
            await download_button.click()
            await asyncio.sleep(2)
            logger.info("Clicked download button for credentials")

    except Exception as e:
        logger.warning(f"Could not capture credentials automatically: {e}")

    # Take screenshot of the result
    await page.screenshot(path=f"screenshots/iam_created_{user_name}.png")

    if api_username and api_password:
        return {
            "api_username": api_username,
            "api_password": api_password
        }
    elif api_username:
        return {
            "api_username": api_username,
            "api_password": None,
            "warning": "Password not captured. Check the downloaded credentials file."
        }
    else:
        return {
            "error": "Could not capture API credentials. Check screenshots for manual retrieval."
        }


async def login_to_forticloud(page, username: str, password: str, mfa_secret: Optional[str]) -> bool:
    """Login to FortiCloud portal."""
    logger.info(f"Logging into FortiCloud as: {username}")

    await page.goto(FORTICLOUD_LOGIN_URL, wait_until="networkidle")
    await asyncio.sleep(2)

    # Check if already logged in
    if "/login" not in page.url:
        logger.info("Already logged in")
        return True

    # Enter credentials
    try:
        username_input = await page.wait_for_selector(
            'input[name="username"], input[type="email"], input[id="username"]',
            timeout=10000
        )
        await username_input.fill(username)

        password_input = await page.query_selector(
            'input[name="password"], input[type="password"]'
        )
        await password_input.fill(password)

        login_button = await page.query_selector(
            'button[type="submit"], button:has-text("Log In")'
        )
        await login_button.click()

        await asyncio.sleep(3)
    except Exception as e:
        logger.error(f"Login form error: {e}")
        return False

    # Handle MFA if needed
    mfa_input = await page.query_selector(
        'input[name="otp"], input[name="mfa"], input[placeholder*="code"]'
    )
    if mfa_input and mfa_secret:
        try:
            import pyotp
            totp = pyotp.TOTP(mfa_secret)
            await mfa_input.fill(totp.now())

            submit_button = await page.query_selector('button[type="submit"]')
            if submit_button:
                await submit_button.click()
            await asyncio.sleep(3)
        except ImportError:
            logger.error("pyotp not installed for MFA")
            return False
    elif mfa_input:
        logger.error("MFA required but no secret provided")
        return False

    # Verify login
    if "/login" not in page.url:
        logger.info("Login successful")
        return True
    else:
        logger.error("Login failed")
        return False


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"
        }

    # Validate required parameters
    user_name = params.get("user_name")
    if not user_name:
        return {"success": False, "error": "Missing required parameter: user_name"}

    permissions = params.get("permissions", [])
    if not permissions:
        return {"success": False, "error": "Missing required parameter: permissions"}

    # Load portal credentials
    creds = load_portal_credentials(params)
    if not creds["portal_username"] or not creds["portal_password"]:
        return {
            "success": False,
            "error": "Portal credentials required. Set portal_username/portal_password or configure credential file."
        }

    headless = params.get("headless", True)
    description = params.get("description")
    save_creds = params.get("save_credentials", True)

    # Ensure screenshots directory exists
    Path("screenshots").mkdir(exist_ok=True)

    playwright = None
    browser = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        page.set_default_timeout(30000)

        # Login
        logged_in = await login_to_forticloud(
            page,
            creds["portal_username"],
            creds["portal_password"],
            creds["mfa_secret"]
        )

        if not logged_in:
            await page.screenshot(path="screenshots/login_failed.png")
            return {"success": False, "error": "Failed to login to FortiCloud portal"}

        # Create the API user
        result = await create_iam_api_user(page, user_name, description, permissions)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        # Save credentials if requested
        credentials_path = None
        if save_creds and result.get("api_username") and result.get("api_password"):
            credentials_path = save_api_credentials(
                result["api_username"],
                result["api_password"],
                user_name,
                permissions
            )

        return {
            "success": True,
            "api_username": result.get("api_username"),
            "api_password": result.get("api_password"),
            "user_name": user_name,
            "permissions": permissions,
            "credentials_saved_to": credentials_path,
            "warning": result.get("warning")
        }

    except Exception as e:
        logger.exception(f"Tool error: {e}")
        return {"success": False, "error": str(e)}

    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


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

    # Example usage
    test_params = {
        "user_name": "test-api-user",
        "description": "Test API user for automation",
        "permissions": [
            {"portal": "FlexVM", "access": "Admin", "scope": "Organization"},
            {"portal": "Asset Management", "access": "ReadWrite", "scope": "Organization"},
            {"portal": "Organization", "access": "ReadWrite", "scope": "Organization"}
        ],
        "headless": False,
        "save_credentials": True
    }

    result = main(test_params)
    print(json.dumps(result, indent=2, default=str))
