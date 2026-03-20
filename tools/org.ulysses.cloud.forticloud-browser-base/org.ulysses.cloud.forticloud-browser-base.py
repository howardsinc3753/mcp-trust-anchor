#!/usr/bin/env python3
from __future__ import annotations

"""
FortiCloud Browser Automation Base

Base library for Playwright browser automation with FortiCloud portals.
Provides login, MFA handling, session management, and common utilities.

Supported Portals:
- FortiCloud Portal (support.fortinet.com)
- FortiCloud IAM (support.fortinet.com/iam)
- FortiSASE Portal
- FortiGate Cloud

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
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# FortiCloud Portal URLs
FORTICLOUD_LOGIN_URL = "https://support.fortinet.com/login"
FORTICLOUD_IAM_URL = "https://support.fortinet.com/iam"
FORTICLOUD_ASSET_URL = "https://support.fortinet.com/asset"
FORTISASE_URL = "https://portal.fortisase.com"

# Credential file paths
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# Browser session storage
SESSIONS: Dict[str, Any] = {}


class FortiCloudBrowser:
    """
    FortiCloud browser automation handler.

    Manages Playwright browser instance, login state, and common operations.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        session_id: Optional[str] = None
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False

    async def start(self):
        """Start browser instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        # Check for existing session
        if self.session_id in SESSIONS:
            session = SESSIONS[self.session_id]
            self.playwright = session["playwright"]
            self.browser = session["browser"]
            self.context = session["context"]
            self.page = session["page"]
            self.logged_in = session.get("logged_in", False)
            logger.info(f"Resumed session: {self.session_id}")
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout_ms)

        # Store session
        SESSIONS[self.session_id] = {
            "playwright": self.playwright,
            "browser": self.browser,
            "context": self.context,
            "page": self.page,
            "logged_in": False
        }

        logger.info(f"Started new browser session: {self.session_id}")

    async def stop(self):
        """Stop browser instance and clean up session."""
        if self.session_id in SESSIONS:
            del SESSIONS[self.session_id]

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        self.browser = None
        self.playwright = None
        self.page = None
        self.context = None
        self.logged_in = False

        logger.info(f"Stopped browser session: {self.session_id}")

    async def login(
        self,
        username: str,
        password: str,
        mfa_secret: Optional[str] = None
    ) -> bool:
        """
        Log into FortiCloud portal.

        Args:
            username: Portal username (email)
            password: Portal password
            mfa_secret: TOTP secret for 2FA (base32 encoded)

        Returns:
            True if login successful
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"Logging into FortiCloud as: {username}")

        # Navigate to login page
        await self.page.goto(FORTICLOUD_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(1)

        # Check if already logged in
        if "support.fortinet.com" in self.page.url and "/login" not in self.page.url:
            logger.info("Already logged in")
            self.logged_in = True
            if self.session_id in SESSIONS:
                SESSIONS[self.session_id]["logged_in"] = True
            return True

        # Wait for login form
        try:
            await self.page.wait_for_selector('input[name="username"], input[id="username"]', timeout=10000)
        except Exception:
            # Try alternate selectors
            await self.page.wait_for_selector('input[type="email"]', timeout=10000)

        # Enter username
        username_input = await self.page.query_selector(
            'input[name="username"], input[id="username"], input[type="email"]'
        )
        if username_input:
            await username_input.fill(username)
            logger.debug("Entered username")

        # Enter password
        password_input = await self.page.query_selector(
            'input[name="password"], input[id="password"], input[type="password"]'
        )
        if password_input:
            await password_input.fill(password)
            logger.debug("Entered password")

        # Click login button
        login_button = await self.page.query_selector(
            'button[type="submit"], input[type="submit"], button:has-text("Log In"), button:has-text("Sign In")'
        )
        if login_button:
            await login_button.click()
            logger.debug("Clicked login button")

        # Wait for navigation
        await asyncio.sleep(3)

        # Check for MFA prompt
        mfa_input = await self.page.query_selector(
            'input[name="otp"], input[name="mfa"], input[name="totp"], '
            'input[placeholder*="code"], input[placeholder*="OTP"]'
        )

        if mfa_input and mfa_secret:
            logger.info("MFA required, generating TOTP code")
            try:
                import pyotp
                totp = pyotp.TOTP(mfa_secret)
                otp_code = totp.now()
                await mfa_input.fill(otp_code)
                logger.debug(f"Entered TOTP code")

                # Submit MFA
                submit_button = await self.page.query_selector(
                    'button[type="submit"], button:has-text("Verify"), button:has-text("Submit")'
                )
                if submit_button:
                    await submit_button.click()

                await asyncio.sleep(3)
            except ImportError:
                logger.error("pyotp not installed for MFA")
                return False
        elif mfa_input and not mfa_secret:
            logger.warning("MFA required but no secret provided")
            return False

        # Verify login success
        await asyncio.sleep(2)
        current_url = self.page.url

        if "/login" not in current_url and "error" not in current_url.lower():
            logger.info("Login successful")
            self.logged_in = True
            if self.session_id in SESSIONS:
                SESSIONS[self.session_id]["logged_in"] = True
            return True
        else:
            logger.error(f"Login failed, URL: {current_url}")
            return False

    async def navigate(self, url: str) -> Dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: Target URL

        Returns:
            Page state information
        """
        if not self.page:
            raise RuntimeError("Browser not started")

        logger.info(f"Navigating to: {url}")
        await self.page.goto(url, wait_until="networkidle")
        await asyncio.sleep(1)

        return {
            "url": self.page.url,
            "title": await self.page.title()
        }

    async def screenshot(self, path: Optional[str] = None) -> str:
        """
        Take a screenshot.

        Args:
            path: Optional path to save screenshot

        Returns:
            Path to saved screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started")

        if not path:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(screenshots_dir / f"forticloud_{timestamp}.png")

        await self.page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved: {path}")
        return path

    async def get_page_state(self) -> Dict[str, Any]:
        """Get current page state."""
        if not self.page:
            return {"url": None, "title": None, "logged_in": False}

        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "logged_in": self.logged_in
        }


def load_portal_credentials(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Load portal credentials from parameters or config file.

    Returns:
        Dict with portal_username, portal_password, mfa_secret
    """
    creds = {
        "portal_username": None,
        "portal_password": None,
        "mfa_secret": None
    }

    # Check parameters first
    if params.get("portal_username"):
        creds["portal_username"] = params["portal_username"]
    if params.get("portal_password"):
        creds["portal_password"] = params["portal_password"]
    if params.get("mfa_secret"):
        creds["mfa_secret"] = params["mfa_secret"]

    if creds["portal_username"] and creds["portal_password"]:
        return creds

    # Check environment variables
    if os.environ.get("FORTICLOUD_PORTAL_USERNAME"):
        creds["portal_username"] = os.environ["FORTICLOUD_PORTAL_USERNAME"]
    if os.environ.get("FORTICLOUD_PORTAL_PASSWORD"):
        creds["portal_password"] = os.environ["FORTICLOUD_PORTAL_PASSWORD"]
    if os.environ.get("FORTICLOUD_MFA_SECRET"):
        creds["mfa_secret"] = os.environ["FORTICLOUD_MFA_SECRET"]

    if creds["portal_username"] and creds["portal_password"]:
        return creds

    # Try credential files
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
                    logger.info(f"Loaded portal credentials from {cred_path}")
                    return creds
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the browser action.

    Args:
        params: Dictionary with parameters from manifest

    Returns:
        Dictionary with results matching output_schema
    """
    action = params.get("action")
    if not action:
        return {"success": False, "error": "Missing required parameter: action"}

    headless = params.get("headless", True)
    timeout_ms = params.get("timeout_ms", 30000)
    session_id = params.get("session_id")

    browser = FortiCloudBrowser(
        headless=headless,
        timeout_ms=timeout_ms,
        session_id=session_id
    )

    try:
        await browser.start()

        if action == "login":
            creds = load_portal_credentials(params)
            if not creds["portal_username"] or not creds["portal_password"]:
                return {
                    "success": False,
                    "error": "Portal credentials required. Set portal_username/portal_password."
                }

            success = await browser.login(
                creds["portal_username"],
                creds["portal_password"],
                creds["mfa_secret"]
            )

            state = await browser.get_page_state()
            return {
                "success": success,
                "action": "login",
                "logged_in": success,
                "current_url": state["url"],
                "page_title": state["title"],
                "session_id": browser.session_id
            }

        elif action == "navigate":
            target_url = params.get("target_url")
            if not target_url:
                return {"success": False, "error": "Missing target_url for navigate action"}

            result = await browser.navigate(target_url)
            return {
                "success": True,
                "action": "navigate",
                "logged_in": browser.logged_in,
                "current_url": result["url"],
                "page_title": result["title"],
                "session_id": browser.session_id
            }

        elif action == "screenshot":
            screenshot_path = params.get("screenshot_path")
            path = await browser.screenshot(screenshot_path)
            state = await browser.get_page_state()
            return {
                "success": True,
                "action": "screenshot",
                "logged_in": browser.logged_in,
                "current_url": state["url"],
                "page_title": state["title"],
                "screenshot_path": path,
                "session_id": browser.session_id
            }

        elif action == "logout":
            await browser.stop()
            return {
                "success": True,
                "action": "logout",
                "logged_in": False,
                "session_id": browser.session_id
            }

        elif action == "get_session":
            state = await browser.get_page_state()
            return {
                "success": True,
                "action": "get_session",
                "logged_in": browser.logged_in,
                "current_url": state["url"],
                "page_title": state["title"],
                "session_id": browser.session_id
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.exception(f"Browser error: {e}")
        return {
            "success": False,
            "action": action,
            "error": str(e),
            "session_id": browser.session_id if browser else None
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

    # CLI testing
    if len(sys.argv) < 2:
        print("Usage: python tool.py <action> [options]")
        print("Actions: login, navigate, screenshot, logout, get_session")
        sys.exit(1)

    test_params = {"action": sys.argv[1], "headless": False}
    if len(sys.argv) > 2:
        test_params["target_url"] = sys.argv[2]

    result = main(test_params)
    print(json.dumps(result, indent=2))
