#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Session Table Tool

Retrieves active firewall sessions from a FortiGate device via REST API.
Supports filtering by source/destination IP, port, and policy.
Useful for troubleshooting connectivity and identifying top talkers.

Author: Ulysses Project
Version: 1.0.0
"""

import urllib.request
import urllib.error
import urllib.parse
import ssl
import json
import os
from pathlib import Path
from typing import Any, Optional


# Protocol number to name mapping
PROTO_MAP = {
    1: "ICMP",
    6: "TCP",
    17: "UDP",
    47: "GRE",
    50: "ESP",
    51: "AH",
    58: "ICMPv6",
    89: "OSPF",
    132: "SCTP",
}


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
                     verify_ssl: bool = False, timeout: int = 30,
                     params: Optional[dict] = None) -> dict:
    """Make a request to FortiGate REST API.

    Args:
        host: FortiGate IP address
        endpoint: API endpoint path
        api_token: API authentication token
        verify_ssl: Whether to verify SSL certificate
        timeout: Request timeout in seconds
        params: Optional query parameters

    Returns:
        Parsed JSON response
    """
    # Build URL with parameters
    url = f"https://{host}{endpoint}?access_token={api_token}"
    if params:
        url += "&" + urllib.parse.urlencode(params)

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


def format_session(session: dict) -> dict:
    """Format a session entry for output.

    Extracts and normalizes relevant fields from FortiGate session data.
    FortiGate API returns:
    - saddr/daddr for IP addresses
    - proto as string ("tcp", "udp")
    - sentbyte/rcvdbyte for byte counts
    - tx_packets/rx_packets for packet counts
    """
    # Proto is returned as string ("tcp", "udp") or we look in apps
    proto_str = session.get("proto", "")
    if isinstance(proto_str, str):
        proto_name = proto_str.upper()
        # Map string to number
        proto_num = {"TCP": 6, "UDP": 17, "ICMP": 1, "GRE": 47, "ESP": 50}.get(proto_name, 0)
    else:
        proto_num = proto_str
        proto_name = PROTO_MAP.get(proto_num, f"proto-{proto_num}")

    # Expiry can be string or int
    expiry = session.get("expiry", 0)
    if isinstance(expiry, str):
        try:
            expiry = int(expiry)
        except ValueError:
            expiry = 0

    return {
        "src_ip": session.get("saddr", ""),
        "src_port": session.get("sport", 0),
        "dst_ip": session.get("daddr", ""),
        "dst_port": session.get("dport", 0),
        "proto": proto_name,
        "proto_num": proto_num,
        "policy_id": session.get("policyid", 0),
        "bytes_in": session.get("rcvdbyte", 0),
        "bytes_out": session.get("sentbyte", 0),
        "packets_in": session.get("rx_packets", 0),
        "packets_out": session.get("tx_packets", 0),
        "duration": session.get("duration", 0),
        "expiry": expiry,
        "state": session.get("state", "established"),  # Most sessions are established
        "src_intf": session.get("srcintf", ""),
        "dst_intf": session.get("dstintf", ""),
        "country": session.get("country", ""),
    }


def main(context) -> dict[str, Any]:
    """
    FortiGate Session Table - returns active firewall sessions.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, count, filters, etc.)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict: Session data including:
            - total_sessions: Total count on device
            - returned_count: Number returned
            - sessions: Array of session details
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    count = min(args.get("count", 20), 1000)  # Cap at 1000
    filter_srcip = args.get("filter_srcip")
    filter_dstip = args.get("filter_dstip")
    filter_dport = args.get("filter_dport")
    filter_policy = args.get("filter_policy")
    sort_by = args.get("sort_by", "bytes")
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
        # Build API parameters
        params = {
            "count": count,
            "start": 0,
        }

        # Build filter string for FortiGate API
        # FortiGate uses format: filter=field==value,field==value
        filters = []
        if filter_srcip:
            filters.append(f"src=={filter_srcip}")
        if filter_dstip:
            filters.append(f"dst=={filter_dstip}")
        if filter_dport:
            filters.append(f"dport=={filter_dport}")
        if filter_policy:
            filters.append(f"policyid=={filter_policy}")

        if filters:
            params["filter"] = ",".join(filters)

        # Map sort field to FortiGate API field names
        sort_map = {
            "bytes": "bytes_total",
            "packets": "packets_total",
            "duration": "duration",
            "expiry": "timeout",
        }
        if sort_by in sort_map:
            params["sortby"] = sort_map[sort_by]
            params["sortdesc"] = "1"  # Descending order

        # Fetch sessions
        response = make_api_request(
            target_ip, "/api/v2/monitor/firewall/session",
            api_token, verify_ssl, timeout, params
        )

        # Parse results - FortiGate returns sessions in results.details[]
        results_obj = response.get("results", {})
        if isinstance(results_obj, dict):
            session_list = results_obj.get("details", [])
        else:
            session_list = results_obj if isinstance(results_obj, list) else []

        # Total from API or count what we got
        total = response.get("total", len(session_list))

        # Format sessions for output
        sessions = [format_session(s) for s in session_list]

        # Sort locally if API doesn't support the sort parameter
        sort_key_map = {
            "bytes": lambda s: s["bytes_in"] + s["bytes_out"],
            "packets": lambda s: s["packets_in"] + s["packets_out"],
            "duration": lambda s: s["duration"],
            "expiry": lambda s: s["expiry"],
        }
        if sort_by in sort_key_map:
            sessions.sort(key=sort_key_map[sort_by], reverse=True)

        return {
            "success": True,
            "target_ip": target_ip,
            "total_sessions": total,
            "returned_count": len(sessions),
            "sessions": sessions,
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
    result = main({"target_ip": "192.168.209.62", "count": 5})
    print(json.dumps(result, indent=2))
