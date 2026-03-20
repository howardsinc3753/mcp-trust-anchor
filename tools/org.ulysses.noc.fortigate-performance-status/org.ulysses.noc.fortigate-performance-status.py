#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Performance Status Tool

Retrieves detailed performance statistics from a FortiGate device via REST API.
Returns CPU, memory, uptime, and session information from /api/v2/monitor/system/performance/status.
"""

import urllib.request
import urllib.error
import ssl
import json
import os
from pathlib import Path
from typing import Any, Optional, Dict


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


def make_api_request(host: str, endpoint: str, api_token: str,
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """Make a request to FortiGate REST API."""
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


def main(context) -> Dict[str, Any]:
    """
    FortiGate Performance Status - returns detailed performance metrics.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (target_ip, timeout, verify_ssl)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict: Performance metrics from /api/v2/monitor/system/performance/status
    """
    # Support both old dict format and new context format
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
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
            "error": f"No API credentials found for {target_ip}. Configure in config/fortigate_credentials.yaml",
            "success": False,
        }

    try:
        # Fetch performance status
        resp = make_api_request(
            target_ip, "/api/v2/monitor/system/performance/status",
            api_token, verify_ssl, timeout
        )

        results = resp.get("results", {})

        return {
            "success": True,
            "target_ip": target_ip,
            "cpu": {
                "current": results.get("cpu", 0),
                "idle": results.get("cpu_idle", 0),
                "user": results.get("cpu_user", 0),
                "system": results.get("cpu_system", 0),
                "nice": results.get("cpu_nice", 0),
                "iowait": results.get("cpu_iowait", 0),
                "irq": results.get("cpu_irq", 0),
                "softirq": results.get("cpu_softirq", 0),
            },
            "memory": {
                "total_mb": results.get("mem_total", 0) // 1024 if results.get("mem_total") else 0,
                "used_percent": results.get("mem", 0),
                "cached": results.get("mem_cached", 0),
                "buffers": results.get("mem_buffers", 0),
            },
            "uptime_seconds": results.get("uptime", 0),
            "sessions": {
                "current": results.get("sessions", 0),
                "rate": results.get("session_rate", 0),
                "max": results.get("maxsessions", 0),
            },
            "npu_sessions": results.get("npu_session", 0),
            "nturbo_sessions": results.get("nturbo_session", 0),
            "http_proxy_sessions": results.get("http_proxy_session", 0),
            "disk_percent": results.get("disk", 0),
            "low_memory": results.get("low_mem", False),
            "conserve_mode": results.get("con_mode", 0),
        }

    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
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
