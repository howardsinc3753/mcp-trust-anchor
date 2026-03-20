#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Config Backup Tool

Export FortiGate configuration via REST API.
Returns full device configuration for backup/archival purposes.

Author: SecBot
Version: 1.0.2
Created: 2026-02-07
Updated: 2026-02-07 - FortiOS 7.6+ uses POST with JSON body per API spec
"""

import urllib.request
import urllib.error
import ssl
import json
import os
from pathlib import Path
from typing import Any, Optional
from datetime import datetime


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from local config file.

    Credential search order (uses FIRST match):
    1. ~/.config/mcp/ (PRIMARY - MCP server checks this first)
    2. ~/AppData/Local/mcp/ (Windows secondary)
    3. C:/ProgramData/mcp/ or /etc/mcp/ (System-wide)
    4. C:/ProgramData/Ulysses/config/ (Ulysses legacy)
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
        # Ulysses legacy
        config_paths.append(Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"))
    else:
        # Linux/Mac system-wide
        config_paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))
        config_paths.append(Path("/opt/ulysses/config/fortigate_credentials.yaml"))

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


def get_device_info(host: str, api_token: str, verify_ssl: bool = False,
                    timeout: int = 30) -> dict:
    """Get device hostname, serial, and firmware for backup metadata."""
    url = f"https://{host}/api/v2/monitor/system/status"

    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()

    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            data = json.loads(response.read().decode())
            return {
                "hostname": data.get("results", {}).get("hostname", "unknown"),
                "serial_number": data.get("serial", "unknown"),
                "firmware_version": data.get("version", "unknown"),
            }
    except Exception:
        return {
            "hostname": "unknown",
            "serial_number": "unknown",
            "firmware_version": "unknown",
        }


def backup_config(host: str, api_token: str, scope: str = "global",
                  vdom: str = "root", verify_ssl: bool = False,
                  timeout: int = 60, password_mask: bool = False,
                  file_format: str = "fos") -> tuple[bool, str, str]:
    """
    Download FortiGate configuration via REST API.

    Args:
        host: FortiGate IP or hostname
        api_token: REST API token
        scope: 'global' or 'vdom'
        vdom: VDOM name (only used when scope='vdom')
        verify_ssl: Verify SSL certificate
        timeout: Request timeout in seconds
        password_mask: If True, mask secrets/passwords in backup
        file_format: Output format - 'fos' (CLI) or 'yaml'

    Returns:
        Tuple of (success, config_content, error_message)
    """
    # Build backup URL (no query params - FortiOS 7.6 uses POST body)
    url = f"https://{host}/api/v2/monitor/system/config/backup"

    # Build request body per FortiOS 7.6 API spec
    body = {
        "destination": "file",
        "scope": scope,
        "file_format": file_format,
        "password_mask": password_mask
    }
    if scope == "vdom" and vdom:
        body["vdom"] = vdom

    # Create SSL context
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()

    # FortiOS 7.6+ requires POST method with JSON body
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(body).encode('utf-8')
    )
    req.add_header("Authorization", f"Bearer {api_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            # Config backup returns plain text, not JSON
            content = response.read().decode('utf-8', errors='replace')
            return True, content, ""

    except urllib.error.HTTPError as e:
        return False, "", f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, "", f"Connection failed: {e.reason}"
    except Exception as e:
        return False, "", f"Unexpected error: {str(e)}"


def save_backup(content: str, backup_path: str, hostname: str,
                serial: str) -> tuple[bool, str, str]:
    """
    Save backup content to file.

    Args:
        content: Configuration content
        backup_path: Directory to save backup
        hostname: Device hostname for filename
        serial: Device serial number for filename

    Returns:
        Tuple of (success, file_path, error_message)
    """
    try:
        # Create backup directory if needed
        backup_dir = Path(backup_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename: hostname_serial_YYYYMMDD_HHMMSS.conf
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_hostname = "".join(c if c.isalnum() or c in "-_" else "_" for c in hostname)
        filename = f"{safe_hostname}_{serial}_{timestamp}.conf"
        file_path = backup_dir / filename

        # Write configuration
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True, str(file_path), ""

    except Exception as e:
        return False, "", f"Failed to save backup: {str(e)}"


def main(context) -> dict[str, Any]:
    """
    FortiGate Config Backup - exports device configuration.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, scope, etc.)
            - credentials: Credential vault data (optional)

    Returns:
        dict: Backup result including config content or file path
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    scope = args.get("scope", "global")
    vdom = args.get("vdom", "root")
    file_format = args.get("file_format", "fos")  # fos = CLI format, yaml = YAML format
    password_mask = args.get("password_mask", False)
    save_to_file = args.get("save_to_file", False)
    backup_path = args.get("backup_path", "C:/ProgramData/Ulysses/backups/fortigate")
    timeout = args.get("timeout", 60)
    verify_ssl = args.get("verify_ssl", False)

    if not target_ip:
        return {
            "success": False,
            "error": "target_ip is required",
        }

    # Get credentials - check context first, then local config
    api_token = None
    if creds and creds.get("api_token"):
        api_token = creds["api_token"]
        if creds.get("verify_ssl") is not None:
            verify_ssl = creds["verify_ssl"]
    else:
        # Load from local credential file
        local_creds = load_credentials(target_ip)
        if local_creds:
            api_token = local_creds.get("api_token")
            if local_creds.get("verify_ssl") is not None:
                verify_ssl = local_creds["verify_ssl"]

    if not api_token:
        return {
            "success": False,
            "error": f"No API credentials found for {target_ip}. Configure in fortigate_credentials.yaml",
            "target_ip": target_ip,
        }

    # Get device info for metadata
    device_info = get_device_info(target_ip, api_token, verify_ssl, timeout)

    # Perform backup
    success, config_content, error = backup_config(
        target_ip, api_token, scope, vdom, verify_ssl, timeout,
        password_mask, file_format
    )

    if not success:
        return {
            "success": False,
            "error": error,
            "target_ip": target_ip,
            "hostname": device_info["hostname"],
        }

    # Build result
    result = {
        "success": True,
        "target_ip": target_ip,
        "hostname": device_info["hostname"],
        "serial_number": device_info["serial_number"],
        "firmware_version": device_info["firmware_version"],
        "scope": scope,
        "backup_size_bytes": len(config_content.encode('utf-8')),
        "backup_timestamp": datetime.now().isoformat(),
    }

    # Save to file if requested
    if save_to_file:
        save_success, file_path, save_error = save_backup(
            config_content, backup_path,
            device_info["hostname"], device_info["serial_number"]
        )
        if save_success:
            result["saved_to"] = file_path
            result["config_content"] = f"[Saved to {file_path}]"
        else:
            result["save_error"] = save_error
            # Still include truncated content
            if len(config_content) > 10000:
                result["config_content"] = config_content[:10000] + "\n... [TRUNCATED - use save_to_file=true for full backup]"
            else:
                result["config_content"] = config_content
    else:
        # Return content (may truncate for large configs)
        if len(config_content) > 50000:
            result["config_content"] = config_content[:50000] + "\n... [TRUNCATED - use save_to_file=true for full backup]"
            result["truncated"] = True
        else:
            result["config_content"] = config_content

    return result


if __name__ == "__main__":
    import sys
    # Test execution
    target = sys.argv[1] if len(sys.argv) > 1 else "192.168.209.30"
    result = main({
        "target_ip": target,
        "save_to_file": True
    })
    print(json.dumps(result, indent=2))
