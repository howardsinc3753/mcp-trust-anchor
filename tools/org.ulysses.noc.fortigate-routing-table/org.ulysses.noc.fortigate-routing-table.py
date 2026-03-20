#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Routing Table Tool

Retrieves the IPv4 routing table from a FortiGate device via REST API.
Supports filtering by destination, type, and interface.
Useful for troubleshooting connectivity and verifying route existence.

Author: Ulysses Project
Version: 1.0.0
"""

import urllib.request
import urllib.error
import ssl
import json
import os
import ipaddress
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
        # Ulysses config path
        config_paths.append(Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"))
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


def format_route(route: dict) -> dict:
    """Format a route entry for output.

    Extracts and normalizes relevant fields from FortiGate route data.
    """
    return {
        "destination": route.get("ip_mask", ""),
        "gateway": route.get("gateway", "0.0.0.0"),
        "interface": route.get("interface", ""),
        "type": route.get("type", "unknown"),
        "distance": route.get("distance", 0),
        "metric": route.get("metric", 0),
        "priority": route.get("priority", 0),
        "is_tunnel": route.get("is_tunnel_route", False),
    }


def ip_in_network(ip_str: str, network_str: str) -> bool:
    """Check if an IP address falls within a network.

    Args:
        ip_str: IP address to check (e.g., "192.168.1.50")
        network_str: Network in CIDR notation (e.g., "192.168.1.0/24")

    Returns:
        True if IP is in network, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network(network_str, strict=False)
        return ip in network
    except ValueError:
        return False


def main(context) -> dict[str, Any]:
    """
    FortiGate Routing Table - returns IPv4 routing table.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, filters, etc.)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict: Routing data including:
            - total_routes: Total route count
            - returned_count: Routes after filtering
            - routes: Array of route entries
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    filter_destination = args.get("filter_destination")
    filter_type = args.get("filter_type", "all")
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
        # Fetch routing table
        response = make_api_request(
            target_ip, "/api/v2/monitor/router/ipv4",
            api_token, verify_ssl, timeout
        )

        # Parse results - routes are in results[]
        route_list = response.get("results", [])
        total_routes = len(route_list)

        # Format routes
        routes = [format_route(r) for r in route_list]

        # Apply filters
        if filter_type and filter_type != "all":
            routes = [r for r in routes if r["type"] == filter_type]

        if filter_interface:
            routes = [r for r in routes if r["interface"] == filter_interface]

        if filter_destination:
            # Check if destination matches any route
            # This finds routes that would match a specific IP
            filtered = []
            for r in routes:
                # Check if the filter IP would be routed by this entry
                if ip_in_network(filter_destination, r["destination"]):
                    filtered.append(r)
                # Also match exact network specification
                elif filter_destination in r["destination"]:
                    filtered.append(r)
            routes = filtered

        # Sort by destination network
        routes.sort(key=lambda r: r["destination"])

        return {
            "success": True,
            "target_ip": target_ip,
            "total_routes": total_routes,
            "returned_count": len(routes),
            "routes": routes,
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
