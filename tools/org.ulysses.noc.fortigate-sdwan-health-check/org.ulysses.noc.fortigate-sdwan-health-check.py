#!/usr/bin/env python3
"""
FortiGate SD-WAN Health Check Tool

Creates SD-WAN health checks on FortiGate devices.
Supports both SPOKE (active ping) and HUB (remote detection) modes.

Based on Fortinet 4D-Demo configurations:
- SPOKE: Active ping to hub loopback with SLA thresholds
- HUB: Remote detection mode for spoke health reporting

FortiOS 7.6+ compatible with REST API Bearer token authentication.
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

    body = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(decode_response(response))


def get_health_checks(host: str, api_token: str, verify_ssl: bool = False) -> list:
    """Get existing health checks."""
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/sdwan/health-check",
                                 api_token, "GET", verify_ssl=verify_ssl)
        return result.get("results", [])
    except:
        return []


def create_spoke_health_check(host: str, api_token: str, name: str, server: str,
                               members: list, latency: int = 200, jitter: int = 50,
                               packetloss: int = 5, verify_ssl: bool = False) -> dict:
    """Create SPOKE-style health check (active ping to hub).

    4D-Demo SPOKE health check settings:
    - Active ping to hub loopback
    - SLA thresholds for latency/jitter/packetloss
    - Embedded measured health for SD-WAN rules
    """
    data = {
        "name": name,
        "server": server,
        "protocol": "ping",
        "update-cascade-interface": "disable",
        "update-static-route": "disable",
        "embed-measured-health": "enable",
        "sla-id-redistribute": 1,
        "sla-fail-log-period": 10,
        "sla-pass-log-period": 10,
        "members": [{"seq-num": m} for m in members],
        "sla": [{
            "id": 1,
            "latency-threshold": latency,
            "jitter-threshold": jitter,
            "packetloss-threshold": packetloss
        }]
    }
    return make_api_request(host, "/api/v2/cmdb/system/sdwan/health-check",
                            api_token, "POST", data, verify_ssl)


def create_hub_health_check(host: str, api_token: str, name: str = "From_Edge",
                             probe_timeout: int = 2500, priority_out_sla: int = 999,
                             verify_ssl: bool = False) -> dict:
    """Create HUB-style health check (remote detection mode).

    4D-Demo HUB health check settings:
    - Remote detection mode (passive - relies on spoke probes)
    - Fast failover (failtime=1, recoverytime=1)
    - High priority-out-sla for failover steering
    """
    data = {
        "name": name,
        "detect-mode": "remote",
        "remote-probe-timeout": probe_timeout,
        "failtime": 1,
        "recoverytime": 1,
        "sla-id-redistribute": 1,
        "sla-fail-log-period": 10,
        "sla-pass-log-period": 10,
        "members": [{"seq-num": 0}],  # 0 = all members
        "sla": [{
            "id": 1,
            "link-cost-factor": "remote",
            "priority-out-sla": priority_out_sla
        }]
    }
    return make_api_request(host, "/api/v2/cmdb/system/sdwan/health-check",
                            api_token, "POST", data, verify_ssl)


def delete_health_check(host: str, api_token: str, name: str,
                        verify_ssl: bool = False) -> dict:
    """Delete a health check."""
    return make_api_request(host, f"/api/v2/cmdb/system/sdwan/health-check/{name}",
                            api_token, "DELETE", verify_ssl=verify_ssl)


def main(context) -> dict[str, Any]:
    """
    Create or manage SD-WAN health checks on FortiGate.

    Args:
        context: ExecutionContext with parameters:
            Required:
            - target_ip: FortiGate management IP
            - action: "create", "list", or "delete"

            For create action:
            - mode: "spoke" or "hub"
            - name: Health check name

            For spoke mode:
            - server: Target IP to ping (usually hub loopback)
            - members: List of member seq-nums (e.g., [100, 101])

            For hub mode (optional):
            - probe_timeout: Remote probe timeout (default: 2500)
            - priority_out_sla: Priority when SLA fails (default: 999)

            For delete action:
            - name: Health check name to delete

            Optional SLA thresholds (spoke mode):
            - latency: Latency threshold ms (default: 200)
            - jitter: Jitter threshold ms (default: 50)
            - packetloss: Packet loss threshold % (default: 5)

    Returns:
        dict: Result with health check details
    """
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    target_ip = args.get("target_ip")
    action = args.get("action", "list").lower()

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    creds = load_credentials(target_ip)
    if not creds:
        return {
            "success": False,
            "error": f"No credentials found for {target_ip}",
            "hint": "Use fortigate-credential-manager to register device first"
        }

    api_token = creds.get("api_token")
    verify_ssl = creds.get("verify_ssl", False)

    result = {
        "success": False,
        "target_ip": target_ip,
        "action": action
    }

    try:
        if action == "list":
            health_checks = get_health_checks(target_ip, api_token, verify_ssl)
            result["success"] = True
            result["health_checks"] = [{
                "name": hc.get("name"),
                "server": hc.get("server"),
                "detect-mode": hc.get("detect-mode", "active"),
                "protocol": hc.get("protocol", "ping"),
                "members": [m.get("seq-num") for m in hc.get("members", [])]
            } for hc in health_checks]
            result["count"] = len(health_checks)

        elif action == "create":
            mode = args.get("mode", "").lower()
            name = args.get("name")

            if not name:
                return {"success": False, "error": "name is required for create action"}
            if mode not in ["spoke", "hub"]:
                return {"success": False, "error": "mode must be 'spoke' or 'hub'"}

            if mode == "spoke":
                server = args.get("server")
                members = args.get("members", [])

                if not server:
                    return {"success": False, "error": "server (hub loopback IP) required for spoke mode"}
                if not members:
                    return {"success": False, "error": "members (list of seq-nums) required for spoke mode"}

                latency = args.get("latency", 200)
                jitter = args.get("jitter", 50)
                packetloss = args.get("packetloss", 5)

                create_spoke_health_check(
                    target_ip, api_token, name, server, members,
                    latency, jitter, packetloss, verify_ssl
                )
                result["success"] = True
                result["mode"] = "spoke"
                result["name"] = name
                result["server"] = server
                result["members"] = members
                result["sla"] = {
                    "latency_threshold": latency,
                    "jitter_threshold": jitter,
                    "packetloss_threshold": packetloss
                }
                result["message"] = f"Spoke health check '{name}' created"

            else:  # hub mode
                probe_timeout = args.get("probe_timeout", 2500)
                priority_out_sla = args.get("priority_out_sla", 999)

                create_hub_health_check(
                    target_ip, api_token, name, probe_timeout, priority_out_sla, verify_ssl
                )
                result["success"] = True
                result["mode"] = "hub"
                result["name"] = name
                result["detect_mode"] = "remote"
                result["probe_timeout"] = probe_timeout
                result["priority_out_sla"] = priority_out_sla
                result["message"] = f"Hub health check '{name}' created with remote detection"

        elif action == "delete":
            name = args.get("name")
            if not name:
                return {"success": False, "error": "name is required for delete action"}

            delete_health_check(target_ip, api_token, name, verify_ssl)
            result["success"] = True
            result["name"] = name
            result["message"] = f"Health check '{name}' deleted"

        else:
            return {"success": False, "error": f"Unknown action: {action}. Use 'create', 'list', or 'delete'"}

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:500]
        except:
            pass
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["details"] = error_body

        if e.code == 500 and "already exist" in error_body.lower():
            result["hint"] = f"Health check '{args.get('name')}' may already exist"

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test: List health checks
    print("=== Listing Health Checks ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "list"
    })
    print(json.dumps(result, indent=2))

    # Test: Create spoke health check
    print("\n=== Creating Spoke Health Check ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "create",
        "mode": "spoke",
        "name": "HUB",
        "server": "172.16.255.253",
        "members": [100, 101]
    })
    print(json.dumps(result, indent=2))
