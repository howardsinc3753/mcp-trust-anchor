#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Device Register Tool

Registers a FortiGate device in the local credentials file.
Adds the device entry with API token for use by other tools.
"""

import os
import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    yaml = None


def get_mcp_credential_path() -> Path:
    """
    Get the PRIMARY MCP credential path for writes.

    The MCP server searches paths in this order:
    1. ~/.config/mcp/ (PRIMARY - we write here)
    2. ~/AppData/Local/mcp/
    3. C:/ProgramData/mcp/ or /etc/mcp/
    4. Project-relative paths

    To ensure tools can find credentials, we ALWAYS write to the primary path.
    """
    return Path.home() / ".config" / "mcp"


def find_credentials_file() -> Optional[Path]:
    """
    Get the credential file path.

    IMPORTANT: Always returns the PRIMARY MCP path to ensure consistency.
    The MCP server searches ~/.config/mcp/ FIRST, so we write there.
    """
    # Always use the primary MCP path for writes
    primary_path = get_mcp_credential_path() / "fortigate_credentials.yaml"

    # Ensure directory exists
    primary_path.parent.mkdir(parents=True, exist_ok=True)

    return primary_path


def load_credentials(path: Path) -> dict:
    """Load existing credentials file."""
    if not yaml:
        raise ImportError("PyYAML is required: pip install pyyaml")

    if not path.exists():
        return {
            "devices": {},
            "default_device": None,
            "default_lookup": {}
        }

    with open(path, 'r') as f:
        config = yaml.safe_load(f) or {}

    # Ensure required keys exist
    if "devices" not in config:
        config["devices"] = {}
    if "default_lookup" not in config:
        config["default_lookup"] = {}

    return config


def save_credentials(path: Path, config: dict) -> None:
    """Save credentials file with proper formatting."""
    if not yaml:
        raise ImportError("PyYAML is required: pip install pyyaml")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Add header comment
    header = "# FortiGate Credentials - DO NOT COMMIT\n"

    with open(path, 'w') as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def main(context) -> dict[str, Any]:
    """
    FortiGate Device Register - Add device to local credentials.

    Registers a FortiGate device in the local credentials file with
    its API token. This enables other tools to authenticate automatically.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters
                - device_id: Unique identifier for the device (e.g., "lab-vm02")
                - host: FortiGate management IP address
                - api_token: REST API token
                - verify_ssl: Whether to verify SSL (default: false)
                - set_default: Set as default device (default: false)
                - model: Device model (optional, for documentation)
                - firmware: Firmware version (optional, for documentation)

    Returns:
        dict: Result containing:
            - success: Whether registration succeeded
            - device_id: Registered device ID
            - host: Registered host IP
            - credentials_file: Path to credentials file
            - error: Error message if failed
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    device_id = args.get("device_id")
    host = args.get("host")
    api_token = args.get("api_token")
    verify_ssl = args.get("verify_ssl", False)
    set_default = args.get("set_default", False)
    model = args.get("model")
    firmware = args.get("firmware")

    # Validate required parameters
    if not device_id:
        return {
            "success": False,
            "error": "device_id is required (e.g., 'lab-vm02')"
        }

    if not host:
        return {
            "success": False,
            "error": "host is required (FortiGate IP address)"
        }

    if not api_token:
        return {
            "success": False,
            "error": "api_token is required"
        }

    try:
        # Find credentials file
        cred_path = find_credentials_file()
        if not cred_path:
            return {
                "success": False,
                "error": "Could not determine credentials file path"
            }

        # Load existing config
        config = load_credentials(cred_path)

        # Check if device already exists
        existing = device_id in config["devices"]

        # Build device entry
        device_entry = {
            "host": host,
            "api_token": api_token,
            "verify_ssl": verify_ssl
        }

        # Add optional metadata as comments (stored in entry)
        if model or firmware:
            device_entry["_metadata"] = {}
            if model:
                device_entry["_metadata"]["model"] = model
            if firmware:
                device_entry["_metadata"]["firmware"] = firmware
            device_entry["_metadata"]["registered_at"] = datetime.now(timezone.utc).isoformat()

        # Add/update device
        config["devices"][device_id] = device_entry

        # Add to lookup table
        config["default_lookup"][host] = device_id

        # Set as default if requested or if first device
        if set_default or not config.get("default_device"):
            config["default_device"] = device_id

        # Save config
        save_credentials(cred_path, config)

        return {
            "success": True,
            "device_id": device_id,
            "host": host,
            "credentials_file": str(cred_path),
            "action": "updated" if existing else "created",
            "is_default": config.get("default_device") == device_id,
            "total_devices": len(config["devices"]),
            "message": f"Device '{device_id}' {'updated' if existing else 'registered'} successfully"
        }

    except ImportError as e:
        return {
            "success": False,
            "error": str(e)
        }

    except PermissionError as e:
        return {
            "success": False,
            "error": f"Permission denied writing to credentials file: {e}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


if __name__ == "__main__":
    # Test execution
    result = main({
        "device_id": "test-device",
        "host": "192.168.1.1",
        "api_token": "test-token-123",
        "model": "FGT-VM02",
        "firmware": "7.6.5"
    })
    print(json.dumps(result, indent=2))
