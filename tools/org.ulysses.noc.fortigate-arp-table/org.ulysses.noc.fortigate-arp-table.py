#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate ARP Table Tool

Retrieves the ARP table from a FortiGate device via REST API.
Supports filtering by IP, MAC address, and interface.
Useful for troubleshooting Layer 2 connectivity and identifying devices.

Author: Ulysses Project
Version: 1.0.0
"""

import urllib.request
import urllib.error
import ssl
import json
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


def make_api_request(host: str, endpoint: str, api_token: str,
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """Make a request to FortiGate REST API.

    Args:
        host: FortiGate IP address
        endpoint: API endpoint path
        api_token: API authentication token
        verify_ssl: Whether to verify SSL certificate
        timeout: Request timeout in seconds

    Returns:
        Parsed JSON response
    """
    url = f"https://{host}{endpoint}?access_token={api_token}"

    # Create SSL context
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()

    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(response.read().decode())


def format_arp_entry(entry: dict) -> dict:
    """Format an ARP entry for output.

    Extracts and normalizes relevant fields from FortiGate ARP data.
    """
    return {
        "ip": entry.get("ip", ""),
        "mac": entry.get("mac", "").upper(),
        "interface": entry.get("interface", ""),
        "age": entry.get("age", 0),
    }


def main(context) -> dict[str, Any]:
    """
    FortiGate ARP Table - returns ARP cache entries.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, filters, etc.)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict: ARP data including:
            - total_entries: Total ARP entry count
            - returned_count: Entries after filtering
            - entries: Array of ARP entries
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    filter_ip = args.get("filter_ip")
    filter_mac = args.get("filter_mac")
    filter_interface = args.get("filter_interface")
    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)

    if not target_ip:
        return {
            "error": "target_ip is required",
            "success": False,
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
            "error": f"No API credentials found for {target_ip}. Configure in ~/.config/mcp/fortigate_credentials.yaml",
            "success": False,
        }

    try:
        # Fetch ARP table
        response = make_api_request(
            target_ip, "/api/v2/monitor/network/arp",
            api_token, verify_ssl, timeout
        )

        # Parse results - ARP entries are in results[]
        arp_list = response.get("results", [])
        total_entries = len(arp_list)

        # Format entries
        entries = [format_arp_entry(e) for e in arp_list]

        # Apply filters
        if filter_ip:
            filter_ip_lower = filter_ip.lower()
            entries = [e for e in entries if filter_ip_lower in e["ip"].lower()]

        if filter_mac:
            filter_mac_upper = filter_mac.upper().replace("-", ":").replace(".", ":")
            entries = [e for e in entries if filter_mac_upper in e["mac"]]

        if filter_interface:
            entries = [e for e in entries if e["interface"] == filter_interface]

        # Sort by IP address
        entries.sort(key=lambda e: tuple(int(p) for p in e["ip"].split(".") if p.isdigit()) or (0,))

        return {
            "success": True,
            "target_ip": target_ip,
            "total_entries": total_entries,
            "returned_count": len(entries),
            "entries": entries,
        }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}. {error_body}",
            "target_ip": target_ip,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e.reason}",
            "target_ip": target_ip,
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON response: {e}",
            "target_ip": target_ip,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "target_ip": target_ip,
        }


if __name__ == "__main__":
    # Test execution against lab FortiGate
    result = main({"target_ip": "192.168.209.62"})
    print(json.dumps(result, indent=2))
