#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Set Hostname Tool

Sets the hostname on a FortiGate device via REST API.
Uses Bearer token authentication (FortiOS 7.6+ compatible).
"""

import urllib.request
import urllib.error
import ssl
import json
import gzip
import os
from pathlib import Path
from typing import Any, Optional


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from local config file.

    MCP credential search order (uses FIRST match):
    1. ~/.config/mcp/ (PRIMARY - MCP server checks this first)
    2. ~/AppData/Local/mcp/ (Windows secondary)
    3. C:/ProgramData/mcp/ or /etc/mcp/ (System-wide)

    Note: We ONLY check MCP paths to ensure consistency with credential-manager.
    Tool-relative and CWD-relative paths are NOT checked to avoid stale credentials.
    """
    config_paths = [
        # PRIMARY: User config (MCP server checks this FIRST)
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

    # Platform-specific paths
    if os.name == 'nt':
        # Windows secondary
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
        # Windows system-wide
        config_paths.append(Path("C:/ProgramData/mcp/fortigate_credentials.yaml"))
    else:
        # Linux/Mac system-wide
        config_paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                # Check default_lookup first (IP -> device_id mapping)
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    device_name = config["default_lookup"][target_ip]
                    if device_name in config.get("devices", {}):
                        return config["devices"][device_name]

                # Search devices by host
                for device in config.get("devices", {}).values():
                    if device.get("host") == target_ip:
                        return device

            except Exception:
                continue

    return None


def decode_response(response) -> str:
    """Decode response handling gzip compression."""
    data = response.read()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return data.decode('utf-8')


def make_api_request(host: str, endpoint: str, api_token: str,
                     method: str = "GET", data: dict = None,
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """Make a request to FortiGate REST API using Bearer token auth."""
    url = f"https://{host}{endpoint}"

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    if data:
        body = json.dumps(data).encode('utf-8')
    else:
        body = None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(decode_response(response))


def main(context) -> dict[str, Any]:
    """
    FortiGate Set Hostname - Configure device hostname.

    Sets the hostname on a FortiGate device using the REST API.
    The hostname appears in CLI prompt, logs, and device identity.

    Args:
        context: ExecutionContext containing:
            - parameters:
                - target_ip: FortiGate management IP
                - hostname: New hostname to set
                - timeout: Request timeout (default: 30)
                - verify_ssl: Verify SSL certificate (default: false)

    Returns:
        dict: Result containing:
            - success: Whether operation succeeded
            - target_ip: Target device IP
            - hostname: New hostname that was set
            - previous_hostname: Previous hostname (if available)
            - error: Error message if failed
    """
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    target_ip = args.get("target_ip")
    hostname = args.get("hostname")
    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if not hostname:
        return {"success": False, "error": "hostname is required"}

    # Validate hostname (FortiGate rules)
    if len(hostname) > 35:
        return {"success": False, "error": "hostname cannot exceed 35 characters"}

    if not hostname[0].isalnum():
        return {"success": False, "error": "hostname must start with alphanumeric character"}

    # Get credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {
            "success": False,
            "error": f"No credentials found for {target_ip}"
        }

    api_token = creds.get("api_token")
    if creds.get("verify_ssl") is not None:
        verify_ssl = creds["verify_ssl"]

    try:
        # Get current hostname first
        current = make_api_request(
            target_ip, "/api/v2/cmdb/system/global",
            api_token, "GET", verify_ssl=verify_ssl, timeout=timeout
        )
        previous_hostname = current.get("results", {}).get("hostname", "unknown")

        # Set new hostname
        result = make_api_request(
            target_ip, "/api/v2/cmdb/system/global",
            api_token, "PUT",
            data={"hostname": hostname},
            verify_ssl=verify_ssl, timeout=timeout
        )

        # Verify the change
        verify = make_api_request(
            target_ip, "/api/v2/cmdb/system/global",
            api_token, "GET", verify_ssl=verify_ssl, timeout=timeout
        )
        new_hostname = verify.get("results", {}).get("hostname", "unknown")

        if new_hostname == hostname:
            return {
                "success": True,
                "target_ip": target_ip,
                "hostname": hostname,
                "previous_hostname": previous_hostname,
                "message": f"Hostname changed from '{previous_hostname}' to '{hostname}'"
            }
        else:
            return {
                "success": False,
                "target_ip": target_ip,
                "hostname": hostname,
                "error": f"Hostname change not verified. Current: {new_hostname}"
            }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "target_ip": target_ip,
            "details": error_body[:300] if error_body else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "target_ip": target_ip
        }


if __name__ == "__main__":
    result = main({
        "target_ip": "192.168.215.15",
        "hostname": "howard-sdwan-hub-1"
    })
    print(json.dumps(result, indent=2))
