#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate API Token Create Tool

Creates a REST API admin user on FortiGate using session-based authentication.
Returns the generated API token for future automation use.

This tool is used during initial device onboarding when only admin/password
credentials are available.
"""

import urllib.request
import urllib.error
import urllib.parse
import ssl
import json
import gzip
import http.cookiejar
from typing import Any, Optional


def decode_response(response) -> str:
    """Decode response handling gzip compression."""
    data = response.read()

    # Check if gzip compressed
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)

    return data.decode('utf-8')


def create_ssl_context(verify_ssl: bool = False) -> ssl.SSLContext:
    """Create SSL context for HTTPS requests."""
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()
    return ctx


def login_session(host: str, username: str, password: str,
                  verify_ssl: bool = False, timeout: int = 30) -> tuple[str, http.cookiejar.CookieJar]:
    """
    Login to FortiGate and get session cookie + CSRF token.

    Returns:
        tuple: (csrf_token, cookie_jar)
    """
    url = f"https://{host}/logincheck"

    # Prepare form data
    data = urllib.parse.urlencode({
        "username": username,
        "secretkey": password,
        "ajax": "1"
    }).encode('utf-8')

    # Create cookie jar to store session
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPSHandler(context=create_ssl_context(verify_ssl))
    )

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    response = opener.open(req, timeout=timeout)
    result = decode_response(response)

    # Check login success - FortiGate returns "1" on success
    if result.strip() not in ["1", ""]:
        raise Exception(f"Login failed: {result}")

    # Extract CSRF token from cookies
    csrf_token = None
    for cookie in cookie_jar:
        if cookie.name == "ccsrftoken":
            # Token is URL-encoded and quoted
            csrf_token = urllib.parse.unquote(cookie.value).strip('"')
            break

    if not csrf_token:
        raise Exception("Failed to get CSRF token from login response")

    return csrf_token, cookie_jar, opener


def create_api_admin(host: str, opener: urllib.request.OpenerDirector,
                     csrf_token: str, api_username: str,
                     accprofile: str = "super_admin",
                     trusthost: Optional[str] = None,
                     comments: str = "Created by Project Ulysses",
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """
    Create REST API admin user on FortiGate.

    Args:
        host: FortiGate IP/hostname
        opener: Authenticated opener with session cookies
        csrf_token: CSRF token from login
        api_username: Name for the API admin user
        accprofile: Admin profile (default: super_admin)
        trusthost: Allowed source IP/network (optional)
        comments: Description for the admin user

    Returns:
        dict: API response with generated token
    """
    url = f"https://{host}/api/v2/cmdb/system/api-user"

    # Build API user payload
    payload = {
        "name": api_username,
        "accprofile": accprofile,
        "comments": comments,
        "api-key": True,  # Generate API key
    }

    # Add trusthost if specified
    if trusthost:
        payload["trusthost"] = [
            {
                "id": 1,
                "ipv4-trusthost": trusthost
            }
        ]

    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-CSRFTOKEN", csrf_token)

    response = opener.open(req, timeout=timeout)
    return json.loads(decode_response(response))


def logout_session(host: str, opener: urllib.request.OpenerDirector,
                   verify_ssl: bool = False, timeout: int = 30):
    """Logout from FortiGate session."""
    try:
        url = f"https://{host}/logout"
        req = urllib.request.Request(url, method="POST")
        opener.open(req, timeout=timeout)
    except Exception:
        pass  # Best effort logout


def main(context) -> dict[str, Any]:
    """
    FortiGate API Token Create - Creates REST API admin user.

    This tool uses session-based authentication (admin/password) to create
    a new REST API admin user on the FortiGate. The generated API token
    can then be used for all subsequent API operations.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters
                - target_ip: FortiGate management IP
                - admin_user: Admin username for login
                - admin_password: Admin password for login
                - api_username: Name for new API admin (default: ulysses-api)
                - accprofile: Admin profile (default: super_admin)
                - trusthost: Allowed source IP (optional)
                - timeout: Request timeout in seconds
                - verify_ssl: Verify SSL certificate

    Returns:
        dict: Result containing:
            - success: Whether operation succeeded
            - api_token: Generated API token (if success)
            - api_username: Created username
            - target_ip: Target device IP
            - error: Error message (if failed)
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    target_ip = args.get("target_ip")
    admin_user = args.get("admin_user", "admin")
    admin_password = args.get("admin_password")
    api_username = args.get("api_username", "ulysses-api")
    accprofile = args.get("accprofile", "super_admin")
    trusthost = args.get("trusthost")
    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)
    comments = args.get("comments", "Created by Project Ulysses for automated management")

    # Validate required parameters
    if not target_ip:
        return {
            "success": False,
            "error": "target_ip is required"
        }

    if not admin_password:
        return {
            "success": False,
            "error": "admin_password is required for session authentication"
        }

    opener = None
    try:
        # Step 1: Login with admin credentials
        csrf_token, cookie_jar, opener = login_session(
            target_ip, admin_user, admin_password, verify_ssl, timeout
        )

        # Step 2: Create API admin user
        result = create_api_admin(
            host=target_ip,
            opener=opener,
            csrf_token=csrf_token,
            api_username=api_username,
            accprofile=accprofile,
            trusthost=trusthost,
            comments=comments,
            verify_ssl=verify_ssl,
            timeout=timeout
        )

        # Extract the generated API key from response
        # FortiGate returns the key in the response body
        api_token = None
        if "results" in result:
            api_token = result["results"].get("api_key")

        if not api_token:
            # Try alternate response format
            api_token = result.get("api_key")

        if not api_token:
            return {
                "success": False,
                "error": "API user created but token not returned. Check FortiGate GUI.",
                "target_ip": target_ip,
                "api_username": api_username,
                "raw_response": result
            }

        return {
            "success": True,
            "target_ip": target_ip,
            "api_username": api_username,
            "api_token": api_token,
            "accprofile": accprofile,
            "trusthost": trusthost,
            "message": f"API admin '{api_username}' created successfully"
        }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass

        # Check for duplicate user error
        if e.code == 500 and "already exists" in error_body.lower():
            return {
                "success": False,
                "error": f"API user '{api_username}' already exists on {target_ip}",
                "target_ip": target_ip,
                "api_username": api_username,
                "suggestion": "Use a different api_username or delete existing user"
            }

        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "target_ip": target_ip,
            "details": error_body[:500] if error_body else None
        }

    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e.reason}",
            "target_ip": target_ip
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "target_ip": target_ip
        }

    finally:
        # Always try to logout
        if opener:
            logout_session(target_ip, opener, verify_ssl, timeout)


if __name__ == "__main__":
    # Test execution - requires interactive input
    import getpass

    target = input("FortiGate IP: ")
    user = input("Admin username [admin]: ") or "admin"
    password = getpass.getpass("Admin password: ")

    result = main({
        "target_ip": target,
        "admin_user": user,
        "admin_password": password,
        "api_username": "ulysses-api"
    })

    print(json.dumps(result, indent=2))
