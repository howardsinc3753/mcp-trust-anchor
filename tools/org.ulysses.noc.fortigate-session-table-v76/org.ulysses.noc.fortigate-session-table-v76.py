#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Session Table Tool (FortiOS 7.6+)

Retrieves active firewall sessions from FortiGate devices running FortiOS 7.6+.
Uses the updated /api/v2/monitor/firewall/sessions endpoint (plural).

For FortiOS 7.4 and earlier, use org.ulysses.noc.fortigate-session-table instead.

API Reference: FortiOS 7.6.5 Monitor API - firewall.json swagger spec
Endpoint: GET /api/v2/monitor/firewall/sessions

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
from typing import Any, Optional, Dict


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


def load_credentials(target_ip: str) -> Optional[Dict[str, Any]]:
    """Load API credentials from local config file.

    MCP credential search order (uses FIRST match):
    1. ~/.config/mcp/ (PRIMARY - MCP server checks this first)
    2. ~/AppData/Local/mcp/ (Windows secondary)
    3. C:/ProgramData/mcp/ or /etc/mcp/ (System-wide)
    """
    config_paths = [
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

    if os.name == 'nt':
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
        config_paths.append(Path("C:/ProgramData/mcp/fortigate_credentials.yaml"))
    else:
        config_paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    device_name = config["default_lookup"][target_ip]
                    if device_name in config.get("devices", {}):
                        return config["devices"][device_name]

                for device in config.get("devices", {}).values():
                    if device.get("host") == target_ip:
                        return device

            except Exception:
                continue

    return None


def make_api_request(host: str, endpoint: str, api_token: str,
                     verify_ssl: bool = False, timeout: int = 30,
                     params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a request to FortiGate REST API.

    Args:
        host: FortiGate IP address
        endpoint: API endpoint path (without base URL)
        api_token: API authentication token
        verify_ssl: Whether to verify SSL certificate
        timeout: Request timeout in seconds
        params: Optional query parameters

    Returns:
        Parsed JSON response
    """
    # Build URL with parameters
    url = f"https://{host}/api/v2/monitor{endpoint}?access_token={api_token}"
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


def format_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Format a session entry for output.

    FortiOS 7.6 API returns:
    - saddr/daddr for IP addresses (not srcaddr/dstaddr)
    - proto as string ("tcp", "udp")
    - sentbyte/rcvdbyte for byte counts
    - tx_packets/rx_packets for packet counts
    - duration as integer seconds
    """
    # Proto is returned as string ("tcp", "udp", etc.)
    proto_str = session.get("proto", "")
    if isinstance(proto_str, str):
        proto_name = proto_str.upper()
        proto_num = {"TCP": 6, "UDP": 17, "ICMP": 1, "GRE": 47, "ESP": 50}.get(proto_name, 0)
    else:
        proto_num = proto_str
        proto_name = PROTO_MAP.get(proto_num, f"proto-{proto_num}")

    # Expiry can be string or int in 7.6
    expiry = session.get("expiry", "0")
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
        "policy_type": session.get("policytype", ""),
        "bytes_in": session.get("rcvdbyte", 0),
        "bytes_out": session.get("sentbyte", 0),
        "packets_in": session.get("rx_packets", 0),
        "packets_out": session.get("tx_packets", 0),
        "duration": session.get("duration", 0),
        "expiry": expiry,
        "src_intf": session.get("srcintf", ""),
        "dst_intf": session.get("dstintf", ""),
        "country": session.get("country", ""),
        "username": session.get("username", ""),
        "vdom": session.get("vf", ""),
        # NAT info (7.6 specific)
        "nat_src_ip": session.get("snaddr", ""),
        "nat_src_port": session.get("snport", 0),
        "nat_dst_ip": session.get("dnaddr", ""),
        "nat_dst_port": session.get("dnport", 0),
        # Application info
        "apps": session.get("apps", []),
        # Shaper info
        "shaper": session.get("shaper", ""),
        "tx_shaper_drops": session.get("tx_shaper_drops", 0),
        "rx_shaper_drops": session.get("rx_shaper_drops", 0),
        # NPU acceleration
        "fortiasic": session.get("fortiasic", ""),
    }


def main(context) -> Dict[str, Any]:
    """
    FortiGate Session Table (FortiOS 7.6+) - returns active firewall sessions.

    This tool is specifically for FortiOS 7.6 and later which uses the
    /api/v2/monitor/firewall/sessions (plural) endpoint.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, count, filters, etc.)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict: Session data including:
            - summary: Session counts and setup rate
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
    count = args.get("count", 100)
    # Clamp count to valid range [20, 1000] per API spec
    count = max(20, min(count, 1000))

    # Filters
    filter_srcip = args.get("filter_srcip") or args.get("srcaddr")
    filter_dstip = args.get("filter_dstip") or args.get("dstaddr")
    filter_srcport = args.get("filter_srcport") or args.get("srcport")
    filter_dstport = args.get("filter_dstport") or args.get("dstport")
    filter_policy = args.get("filter_policy") or args.get("policyid")
    filter_protocol = args.get("filter_protocol") or args.get("protocol")
    filter_srcintf = args.get("filter_srcintf") or args.get("srcintf")
    filter_dstintf = args.get("filter_dstintf") or args.get("dstintf")
    filter_country = args.get("filter_country") or args.get("country")
    filter_username = args.get("filter_username") or args.get("username")
    ip_version = args.get("ip_version", "ipv4")
    include_summary = args.get("include_summary", True)

    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)

    if not target_ip:
        return {
            "error": "target_ip is required",
            "success": False,
        }

    # Get credentials
    api_token = None
    if creds and creds.get("api_token"):
        api_token = creds["api_token"]
        if creds.get("verify_ssl") is not None:
            verify_ssl = creds["verify_ssl"]
    else:
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
        # Build API parameters for FortiOS 7.6 endpoint
        # count is required in 7.6
        params: Dict[str, Any] = {
            "count": count,
        }

        # IP version filter
        if ip_version:
            params["ip_version"] = ip_version

        # Include summary statistics
        if include_summary:
            params["summary"] = "true"

        # Apply filters using 7.6 parameter names
        if filter_srcip:
            params["srcaddr"] = filter_srcip
        if filter_dstip:
            params["dstaddr"] = filter_dstip
        if filter_srcport:
            params["srcport"] = str(filter_srcport)
        if filter_dstport:
            params["dstport"] = str(filter_dstport)
        if filter_policy:
            params["policyid"] = str(filter_policy)
        if filter_protocol:
            params["protocol"] = filter_protocol
        if filter_srcintf:
            params["srcintf"] = filter_srcintf
        if filter_dstintf:
            params["dstintf"] = filter_dstintf
        if filter_country:
            params["country"] = filter_country
        if filter_username:
            params["username"] = filter_username

        # Fetch sessions using FortiOS 7.6 endpoint (plural!)
        response = make_api_request(
            target_ip, "/firewall/sessions",
            api_token, verify_ssl, timeout, params
        )

        # Parse results - FortiOS 7.6 returns sessions in results.details[]
        results_obj = response.get("results", {})

        # Get summary if available
        summary = {}
        if isinstance(results_obj, dict):
            summary = results_obj.get("summary", {})
            session_list = results_obj.get("details", [])
        else:
            session_list = results_obj if isinstance(results_obj, list) else []

        # Format sessions for output
        sessions = [format_session(s) for s in session_list]

        # Build response
        result = {
            "success": True,
            "target_ip": target_ip,
            "firmware_version": "7.6+",
            "total_sessions": summary.get("session_count", len(sessions)),
            "matched_sessions": summary.get("matched_count", len(sessions)),
            "returned_count": len(sessions),
            "sessions": sessions,
        }

        # Include additional summary stats if available
        if summary:
            result["summary"] = {
                "session_count": summary.get("session_count", 0),
                "matched_count": summary.get("matched_count", 0),
                "setup_rate": summary.get("setup_rate", 0),
                "npu_session_count": summary.get("npu_session_count", 0),
                "nturbo_session_count": summary.get("nturbo_session_count", 0),
            }

        return result

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
            "hint": "Ensure FortiGate is running FortiOS 7.6+. For 7.4 and earlier, use fortigate-session-table tool.",
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
    # Test execution against lab FortiGate running 7.6
    result = main({"target_ip": "192.168.209.62", "count": 20})
    print(json.dumps(result, indent=2))
