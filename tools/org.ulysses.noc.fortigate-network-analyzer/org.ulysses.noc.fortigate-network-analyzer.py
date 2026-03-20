#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Network Analyzer Tool

Retrieves traffic logs, event logs, and session data from FortiGate devices
via REST API for NOC-focused network troubleshooting and capacity planning.

Modes:
    - traffic: Forward traffic logs with filters
    - event: System/VPN event logs
    - session: Sessions for specific IP (convenience wrapper)
"""

import urllib.request
import urllib.error
import ssl
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List


def load_credentials(target_ip: str) -> Optional[Dict[str, Any]]:
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


def make_api_request(host: str, port: int, endpoint: str, api_token: str,
                     verify_ssl: bool = False, timeout: int = 30) -> Dict[str, Any]:
    """Make a request to FortiGate REST API."""
    url = f"https://{host}:{port}{endpoint}"

    # Add access_token as query parameter
    if "?" in url:
        url += f"&access_token={api_token}"
    else:
        url += f"?access_token={api_token}"

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


def build_filter_string(srcip: Optional[str] = None,
                        dstip: Optional[str] = None,
                        policyid: Optional[int] = None,
                        action: Optional[str] = None,
                        service: Optional[str] = None,
                        custom_filter: Optional[str] = None) -> Optional[str]:
    """Build FortiGate filter string from parameters.

    Filter operators:
        == : Equals (case insensitive)
        != : Not equals
        =@ : Contains
        >= : Greater than or equal
        <= : Less than or equal
        ,  : Logical OR
        &  : Logical AND
    """
    filters = []

    if srcip:
        filters.append(f"srcip=={srcip}")
    if dstip:
        filters.append(f"dstip=={dstip}")
    if policyid is not None:
        filters.append(f"policyid=={policyid}")
    if action:
        filters.append(f"action=={action}")
    if service:
        filters.append(f"service=={service}")
    if custom_filter:
        filters.append(custom_filter)

    if filters:
        return "&".join(filters)
    return None


def get_traffic_logs(host: str, port: int, api_token: str, verify_ssl: bool,
                     timeout: int, rows: int = 100,
                     srcip: Optional[str] = None,
                     dstip: Optional[str] = None,
                     policyid: Optional[int] = None,
                     action: Optional[str] = None,
                     service: Optional[str] = None,
                     custom_filter: Optional[str] = None,
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve forward traffic logs from FortiGate.

    API Endpoint: /api/v2/log/disk/traffic/forward
    """
    endpoint = "/api/v2/log/disk/traffic/forward"

    # Build query parameters
    params = [f"rows={min(rows, 2000)}"]  # Max 2000 rows

    # Build filter
    filter_str = build_filter_string(srcip, dstip, policyid, action, service, custom_filter)
    if filter_str:
        params.append(f"filter={filter_str}")

    # Time range filters
    if start_time:
        params.append(f"start={start_time}")
    if end_time:
        params.append(f"end={end_time}")

    endpoint_with_params = f"{endpoint}?{'&'.join(params)}"

    response = make_api_request(host, port, endpoint_with_params, api_token, verify_ssl, timeout)

    # Parse response
    results = response.get("results", [])

    # Format results for cleaner output
    formatted_logs = []
    for log in results:
        formatted_logs.append({
            "timestamp": log.get("date", "") + "T" + log.get("time", ""),
            "srcip": log.get("srcip", ""),
            "srcport": log.get("srcport", 0),
            "dstip": log.get("dstip", ""),
            "dstport": log.get("dstport", 0),
            "action": log.get("action", ""),
            "policyid": log.get("policyid", 0),
            "service": log.get("service", ""),
            "app": log.get("app", ""),
            "sentbyte": log.get("sentbyte", 0),
            "rcvdbyte": log.get("rcvdbyte", 0),
            "duration": log.get("duration", 0),
            "srcintf": log.get("srcintf", ""),
            "dstintf": log.get("dstintf", ""),
            "dstcountry": log.get("dstcountry", ""),
            "user": log.get("user", ""),
        })

    return {
        "logs": formatted_logs,
        "total_available": response.get("total_lines", len(results)),
        "rows_returned": len(results),
        "session_id": response.get("session_id"),
        "filter_applied": filter_str,
    }


def get_event_logs(host: str, port: int, api_token: str, verify_ssl: bool,
                   timeout: int, rows: int = 100,
                   subtype: str = "system",
                   custom_filter: Optional[str] = None,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve event logs from FortiGate.

    API Endpoint: /api/v2/log/disk/event/{subtype}
    Subtypes: system, vpn, user, router, wireless, security-rating
    """
    endpoint = f"/api/v2/log/disk/event/{subtype}"

    # Build query parameters
    params = [f"rows={min(rows, 2000)}"]

    if custom_filter:
        params.append(f"filter={custom_filter}")
    if start_time:
        params.append(f"start={start_time}")
    if end_time:
        params.append(f"end={end_time}")

    endpoint_with_params = f"{endpoint}?{'&'.join(params)}"

    response = make_api_request(host, port, endpoint_with_params, api_token, verify_ssl, timeout)

    results = response.get("results", [])

    # Format event logs
    formatted_logs = []
    for log in results:
        formatted_logs.append({
            "timestamp": log.get("date", "") + "T" + log.get("time", ""),
            "type": log.get("type", ""),
            "subtype": log.get("subtype", ""),
            "level": log.get("level", ""),
            "logdesc": log.get("logdesc", ""),
            "msg": log.get("msg", ""),
            "action": log.get("action", ""),
            "status": log.get("status", ""),
            "user": log.get("user", ""),
            "ui": log.get("ui", ""),
            "logid": log.get("logid", ""),
        })

    return {
        "logs": formatted_logs,
        "total_available": response.get("total_lines", len(results)),
        "rows_returned": len(results),
        "session_id": response.get("session_id"),
        "subtype": subtype,
    }


def get_session_by_ip(host: str, port: int, api_token: str, verify_ssl: bool,
                      timeout: int, ip_address: str, rows: int = 100,
                      direction: str = "both") -> Dict[str, Any]:
    """Get all sessions for a specific IP address.

    Convenience wrapper around get_traffic_logs that searches for
    sessions where the IP is either source or destination.

    Args:
        ip_address: IP to search for
        direction: 'src' (source only), 'dst' (destination only), 'both' (either)
    """
    srcip = ip_address if direction in ("src", "both") else None
    dstip = ip_address if direction in ("dst", "both") else None

    # If searching both directions, we need two queries
    if direction == "both":
        # Search as source
        src_results = get_traffic_logs(
            host, port, api_token, verify_ssl, timeout,
            rows=rows // 2, srcip=ip_address
        )
        # Search as destination
        dst_results = get_traffic_logs(
            host, port, api_token, verify_ssl, timeout,
            rows=rows // 2, dstip=ip_address
        )

        # Combine results
        all_logs = src_results.get("logs", []) + dst_results.get("logs", [])

        # Sort by timestamp descending
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return {
            "logs": all_logs[:rows],
            "total_as_source": src_results.get("total_available", 0),
            "total_as_destination": dst_results.get("total_available", 0),
            "rows_returned": len(all_logs[:rows]),
            "ip_searched": ip_address,
            "direction": direction,
        }
    else:
        results = get_traffic_logs(
            host, port, api_token, verify_ssl, timeout,
            rows=rows, srcip=srcip, dstip=dstip
        )
        results["ip_searched"] = ip_address
        results["direction"] = direction
        return results


def get_device_info(host: str, port: int, api_token: str, verify_ssl: bool, timeout: int) -> Dict[str, Any]:
    """Get basic device information for context."""
    try:
        response = make_api_request(
            host, port, "/api/v2/monitor/system/status",
            api_token, verify_ssl, timeout
        )
        results = response.get("results", {})
        return {
            "serial": response.get("serial", "unknown"),
            "hostname": results.get("hostname", "unknown"),
            "version": response.get("version", "unknown"),
            "model": results.get("model", "unknown"),
        }
    except Exception:
        return {
            "serial": "unknown",
            "hostname": "unknown",
            "version": "unknown",
            "model": "unknown",
        }


def main(context) -> Dict[str, Any]:
    """
    FortiGate Network Analyzer - retrieves traffic and event logs.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters
            - credentials: Credential vault data (optional)

    Returns:
        dict: Log data with device info and query metadata
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    # Required parameter
    target_ip = args.get("target_ip")
    if not target_ip:
        return {
            "success": False,
            "error": "target_ip is required",
        }

    # Mode selection
    mode = args.get("mode", "traffic").lower()
    if mode not in ("traffic", "event", "session"):
        return {
            "success": False,
            "error": f"Invalid mode '{mode}'. Must be: traffic, event, session",
        }

    # Common parameters
    port = int(args.get("port", 443))
    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)
    rows = args.get("rows", 100)

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
            "success": False,
            "error": f"No API credentials found for {target_ip}. Configure in ~/.config/mcp/fortigate_credentials.yaml",
        }

    try:
        # Get device info for context
        device_info = get_device_info(target_ip, port, api_token, verify_ssl, timeout)

        # Execute based on mode
        if mode == "traffic":
            log_data = get_traffic_logs(
                host=target_ip,
                port=port,
                api_token=api_token,
                verify_ssl=verify_ssl,
                timeout=timeout,
                rows=rows,
                srcip=args.get("srcip"),
                dstip=args.get("dstip"),
                policyid=args.get("policyid"),
                action=args.get("action"),
                service=args.get("service"),
                custom_filter=args.get("filter"),
                start_time=args.get("start_time"),
                end_time=args.get("end_time"),
            )
        elif mode == "event":
            log_data = get_event_logs(
                host=target_ip,
                port=port,
                api_token=api_token,
                verify_ssl=verify_ssl,
                timeout=timeout,
                rows=rows,
                subtype=args.get("event_subtype", "system"),
                custom_filter=args.get("filter"),
                start_time=args.get("start_time"),
                end_time=args.get("end_time"),
            )
        elif mode == "session":
            # Session mode requires an IP to search
            search_ip = args.get("srcip") or args.get("dstip")
            if not search_ip:
                return {
                    "success": False,
                    "error": "session mode requires srcip or dstip parameter",
                }
            direction = "both"
            if args.get("srcip") and not args.get("dstip"):
                direction = "src"
            elif args.get("dstip") and not args.get("srcip"):
                direction = "dst"

            log_data = get_session_by_ip(
                host=target_ip,
                port=port,
                api_token=api_token,
                verify_ssl=verify_ssl,
                timeout=timeout,
                ip_address=search_ip,
                rows=rows,
                direction=direction,
            )

        return {
            "success": True,
            "target_ip": target_ip,
            "port": port,
            "mode": mode,
            "device": device_info,
            "query": {
                "rows_requested": rows,
                "rows_returned": log_data.get("rows_returned", 0),
                "total_available": log_data.get("total_available", 0),
                "filter_applied": log_data.get("filter_applied"),
            },
            "results": log_data.get("logs", []),
            "pagination": {
                "session_id": log_data.get("session_id"),
                "has_more": log_data.get("total_available", 0) > log_data.get("rows_returned", 0),
            },
        }

    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "target_ip": target_ip,
            "mode": mode,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e.reason}",
            "target_ip": target_ip,
            "mode": mode,
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON response: {e}",
            "target_ip": target_ip,
            "mode": mode,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "target_ip": target_ip,
            "mode": mode,
        }


if __name__ == "__main__":
    import sys

    # Default test: traffic logs from lab FortiGate
    test_args = {
        "target_ip": "192.168.209.62",
        "port": 10443,
        "mode": "traffic",
        "rows": 10,
    }

    # Parse command line args
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                if key == "rows":
                    value = int(value)
                test_args[key] = value

    result = main(test_args)
    print(json.dumps(result, indent=2, default=str))
