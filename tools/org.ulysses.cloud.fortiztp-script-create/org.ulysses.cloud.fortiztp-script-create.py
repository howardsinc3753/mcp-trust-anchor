#!/usr/bin/env python3
"""
FortiZTP Script Create Tool
Create pre-run CLI scripts for device provisioning.

API:
  POST https://fortiztp.forticloud.com/public/api/v2/setting/scripts
  PUT  https://fortiztp.forticloud.com/public/api/v2/setting/scripts/{oid}/content

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
from typing import Any, Dict, Optional

# FortiZTP API endpoints
AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
API_BASE = "https://fortiztp.forticloud.com/public/api/v2"
API_V1_BASE = "https://fortiztp.forticloud.com/api/v1"
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


def create_script(
    access_token: str,
    name: str,
    content: str,
    account_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new pre-run CLI script.

    Args:
        access_token: OAuth access token
        name: Script name
        content: FortiGate CLI commands
        account_email: FortiCloud account email (enables v1 API with content support)

    Returns:
        Dict with success status and created script details
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Note: v1 API (/api/v1/accounts/{account}/cliscripts) uses session auth, not OAuth
    # So we can only use the v2 public API with OAuth tokens
    v1_attempted = False
    v1_error = None

    # Try v1 API if account_email provided (may work with some auth configs)
    if account_email:
        import urllib.parse
        encoded_account = urllib.parse.quote(account_email, safe='')
        v1_url = f"{API_V1_BASE}/accounts/{encoded_account}/cliscripts"
        v1_payload = {"name": name, "content": content}
        v1_attempted = True

        try:
            v1_response = requests.post(
                v1_url,
                headers=headers,
                json=v1_payload,
                timeout=30
            )

            if v1_response.status_code in [200, 201]:
                try:
                    v1_data = v1_response.json()
                    script_oid = v1_data.get("oid") or v1_data.get("id")
                    if script_oid:
                        return {
                            "success": True,
                            "message": f"Script '{name}' created successfully with content (v1 API)",
                            "script": {
                                "oid": script_oid,
                                "name": name,
                                "content_length": len(content)
                            }
                        }
                except Exception:
                    pass
            v1_error = f"v1 API returned {v1_response.status_code}"
        except Exception as e:
            v1_error = f"v1 API error: {str(e)}"
        # If v1 fails, fall through to v2 API

    # v2 API: Create script metadata first
    create_url = f"{API_BASE}/setting/scripts"
    create_payload = {"name": name}

    create_response = requests.post(
        create_url,
        headers=headers,
        json=create_payload,
        timeout=30
    )

    if create_response.status_code not in [200, 201]:
        return {
            "success": False,
            "error": f"Failed to create script: {create_response.status_code} - {create_response.text}"
        }

    create_data = create_response.json()
    script_oid = create_data.get("oid")

    if not script_oid:
        return {
            "success": False,
            "error": f"No OID returned from script creation: {create_data}"
        }

    # Step 2: Upload content - try multiple methods
    content_url = f"{API_BASE}/setting/scripts/{script_oid}/content"
    content_saved = False

    def is_success(resp: requests.Response) -> bool:
        return resp.status_code in (200, 201, 204)

    def format_error(resp: requests.Response) -> str:
        detail = str(resp.status_code)
        try:
            body = resp.text.strip()
            if body:
                body = " ".join(body.split())
                if len(body) > 200:
                    body = f"{body[:200]}..."
                detail = f"{resp.status_code} {body}"
        except Exception:
            pass
        return detail

    errors = []

    # Method 1: JSON with content key (matches GET /content field)
    content_response = requests.put(
        content_url,
        headers=headers,
        json={"content": content},
        timeout=30
    )
    if is_success(content_response):
        content_saved = True
    else:
        errors.append(f"json/content: {format_error(content_response)}")

    # Method 2: Plain text with text/plain
    if not content_saved:
        text_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain; charset=utf-8"
        }
        content_response = requests.put(
            content_url,
            headers=text_headers,
            data=content,
            timeout=30
        )
        if is_success(content_response):
            content_saved = True
        else:
            errors.append(f"text/plain: {format_error(content_response)}")

    # Method 3: Multipart/form-data file upload (portal-style)
    if not content_saved:
        file_headers = {
            "Authorization": f"Bearer {access_token}"
        }
        content_response = requests.put(
            content_url,
            headers=file_headers,
            files={"file": ("script.txt", content, "text/plain")},
            timeout=30
        )
        if is_success(content_response):
            content_saved = True
        else:
            errors.append(f"multipart/file: {format_error(content_response)}")

    # Method 4: JSON with script key (legacy guess)
    if not content_saved:
        content_response = requests.put(
            content_url,
            headers=headers,
            json={"script": content},
            timeout=30
        )
        if is_success(content_response):
            content_saved = True
        else:
            errors.append(f"json/script: {format_error(content_response)}")

    # Method 5: application/octet-stream
    if not content_saved:
        octet_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        }
        content_response = requests.put(
            content_url,
            headers=octet_headers,
            data=content.encode('utf-8'),
            timeout=30
        )
        if is_success(content_response):
            content_saved = True
        else:
            errors.append(f"octet-stream: {format_error(content_response)}")

    # Method 6: Form-urlencoded
    if not content_saved:
        form_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        content_response = requests.put(
            content_url,
            headers=form_headers,
            data={"content": content},
            timeout=30
        )
        if is_success(content_response):
            content_saved = True
        else:
            errors.append(f"form: {format_error(content_response)}")

    if not content_saved:
        # Content upload via API appears to be broken/unsupported
        # Return partial success - script created but content needs manual upload
        error_details = f"v2 API content upload failed ({', '.join(errors)})"
        if v1_attempted:
            error_details = f"v1 API: {v1_error}. {error_details}"
        return {
            "success": True,
            "message": f"Script '{name}' created (OID: {script_oid}). WARNING: Content upload via API failed - please add content via FortiCloud portal.",
            "script": {
                "oid": script_oid,
                "name": name,
                "content_length": 0
            },
            "content_upload_failed": True,
            "content_error": error_details,
            "portal_url": "https://fortiztp.forticloud.com"
        }

    return {
        "success": True,
        "message": f"Script '{name}' created successfully with content",
        "script": {
            "oid": script_oid,
            "name": name,
            "content_length": len(content)
        }
    }


def main(context) -> Dict[str, Any]:
    """
    Main entry point for the tool.

    Parameters:
        name: Script name (required)
        content: FortiGate CLI commands (required)
        account_email: FortiCloud account email (enables v1 API with full content support)
        api_username: Override credential file username
        api_password: Override credential file password

    Returns:
        Dict with success status and created script details
    """
    # Extract parameters from context (context is ExecutionContext, not dict)
    params = getattr(context, "parameters", {}) if not isinstance(context, dict) else context

    # Validate required parameters
    name = params.get("name")
    content = params.get("content")

    if not name:
        return {
            "success": False,
            "error": "Missing required parameter: name"
        }

    if not content:
        return {
            "success": False,
            "error": "Missing required parameter: content"
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

    # Get account email for v1 API (enables content upload)
    account_email = params.get("account_email") or local_creds.get("account_email") or creds.get("account_email")

    # Create script
    result = create_script(
        access_token=access_token,
        name=name,
        content=content,
        account_email=account_email
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
