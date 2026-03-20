#!/usr/bin/env python3
"""
FortiGate SD-WAN Neighbor Tool

CRUD operations for SD-WAN neighbor statements on FortiGate devices.
Configure BGP neighbors with SD-WAN member bindings and health checks.

Based on Fortinet 4D-Demo configurations:
- Bind BGP peers to SD-WAN members
- Associate health checks for SLA-based routing
- Set route-metric for path selection

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


def get_neighbors(host: str, api_token: str, verify_ssl: bool = False) -> list:
    """Get all SD-WAN neighbors."""
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/sdwan/neighbor",
                                 api_token, "GET", verify_ssl=verify_ssl)
        return result.get("results", [])
    except:
        return []


def get_neighbor(host: str, api_token: str, ip: str, verify_ssl: bool = False) -> Optional[dict]:
    """Get a specific SD-WAN neighbor by IP."""
    try:
        result = make_api_request(host, f"/api/v2/cmdb/system/sdwan/neighbor/{ip}",
                                 api_token, "GET", verify_ssl=verify_ssl)
        results = result.get("results", [])
        return results[0] if results else None
    except:
        return None


def add_neighbor(host: str, api_token: str, ip: str, members: list,
                 route_metric: str = "priority", health_check: str = None,
                 sla_id: int = None, minimum_sla_meet_members: int = None,
                 mode: str = None, verify_ssl: bool = False) -> dict:
    """Add an SD-WAN neighbor.

    Args:
        ip: BGP neighbor IP address
        members: List of SD-WAN member seq-nums to bind
        route_metric: Route metric method (priority, latency, jitter, packetloss, bandwidth)
        health_check: Health check name for SLA binding
        sla_id: SLA ID within health check
        minimum_sla_meet_members: Minimum members that must meet SLA
        mode: Neighbor mode (sla, speedtest)
    """
    data = {
        "ip": ip,
        "member": [{"seq-num": m} for m in members],
        "route-metric": route_metric
    }

    if health_check:
        data["health-check"] = health_check

    if sla_id is not None:
        data["sla-id"] = sla_id

    if minimum_sla_meet_members is not None:
        data["minimum-sla-meet-members"] = minimum_sla_meet_members

    if mode:
        data["mode"] = mode

    return make_api_request(host, "/api/v2/cmdb/system/sdwan/neighbor",
                            api_token, "POST", data, verify_ssl)


def update_neighbor(host: str, api_token: str, ip: str, members: list = None,
                    route_metric: str = None, health_check: str = None,
                    sla_id: int = None, minimum_sla_meet_members: int = None,
                    mode: str = None, verify_ssl: bool = False) -> dict:
    """Update an existing SD-WAN neighbor."""
    data = {}

    if members is not None:
        data["member"] = [{"seq-num": m} for m in members]

    if route_metric:
        data["route-metric"] = route_metric

    if health_check:
        data["health-check"] = health_check

    if sla_id is not None:
        data["sla-id"] = sla_id

    if minimum_sla_meet_members is not None:
        data["minimum-sla-meet-members"] = minimum_sla_meet_members

    if mode:
        data["mode"] = mode

    return make_api_request(host, f"/api/v2/cmdb/system/sdwan/neighbor/{ip}",
                            api_token, "PUT", data, verify_ssl)


def remove_neighbor(host: str, api_token: str, ip: str, verify_ssl: bool = False) -> dict:
    """Remove an SD-WAN neighbor."""
    return make_api_request(host, f"/api/v2/cmdb/system/sdwan/neighbor/{ip}",
                            api_token, "DELETE", verify_ssl=verify_ssl)


def main(context) -> dict[str, Any]:
    """
    CRUD operations for SD-WAN neighbors on FortiGate.

    Args:
        context: ExecutionContext with parameters:
            Required:
            - target_ip: FortiGate management IP
            - action: "add", "update", "remove", "list", or "get"

            For add/update:
            - ip: BGP neighbor IP address
            - members: List of SD-WAN member seq-nums (e.g., [3, 4])
            - route_metric: priority, latency, jitter, packetloss, bandwidth
            - health_check: Health check name
            - sla_id: SLA ID within health check (optional)

            For remove/get:
            - ip: Neighbor IP to remove/get

    Returns:
        dict: Result with neighbor details
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
            neighbors = get_neighbors(target_ip, api_token, verify_ssl)
            result["success"] = True
            result["neighbors"] = [{
                "ip": n.get("ip"),
                "member": [m.get("seq-num") for m in n.get("member", [])],
                "route-metric": n.get("route-metric"),
                "health-check": n.get("health-check"),
                "sla-id": n.get("sla-id", 0)
            } for n in neighbors]
            result["count"] = len(neighbors)

        elif action == "get":
            ip = args.get("ip")
            if not ip:
                return {"success": False, "error": "ip is required for get action"}

            neighbor = get_neighbor(target_ip, api_token, ip, verify_ssl)
            if neighbor:
                result["success"] = True
                result["neighbor"] = {
                    "ip": neighbor.get("ip"),
                    "member": [m.get("seq-num") for m in neighbor.get("member", [])],
                    "route-metric": neighbor.get("route-metric"),
                    "health-check": neighbor.get("health-check"),
                    "sla-id": neighbor.get("sla-id", 0)
                }
            else:
                result["error"] = f"Neighbor {ip} not found"

        elif action == "add":
            ip = args.get("ip")
            members = args.get("members", [])

            if not ip:
                return {"success": False, "error": "ip is required for add action"}
            if not members:
                return {"success": False, "error": "members is required for add action"}

            route_metric = args.get("route_metric", "priority")
            health_check = args.get("health_check")
            sla_id = args.get("sla_id")
            minimum_sla_meet_members = args.get("minimum_sla_meet_members")
            mode = args.get("mode")

            add_neighbor(target_ip, api_token, ip, members, route_metric,
                        health_check, sla_id, minimum_sla_meet_members, mode, verify_ssl)

            result["success"] = True
            result["neighbor"] = {
                "ip": ip,
                "members": members,
                "route_metric": route_metric,
                "health_check": health_check
            }
            result["message"] = f"SD-WAN neighbor {ip} added with members {members}"

        elif action == "update":
            ip = args.get("ip")
            if not ip:
                return {"success": False, "error": "ip is required for update action"}

            members = args.get("members")
            route_metric = args.get("route_metric")
            health_check = args.get("health_check")
            sla_id = args.get("sla_id")
            minimum_sla_meet_members = args.get("minimum_sla_meet_members")
            mode = args.get("mode")

            update_neighbor(target_ip, api_token, ip, members, route_metric,
                           health_check, sla_id, minimum_sla_meet_members, mode, verify_ssl)

            result["success"] = True
            result["ip"] = ip
            result["message"] = f"SD-WAN neighbor {ip} updated"

        elif action == "remove":
            ip = args.get("ip")
            if not ip:
                return {"success": False, "error": "ip is required for remove action"}

            remove_neighbor(target_ip, api_token, ip, verify_ssl)
            result["success"] = True
            result["ip"] = ip
            result["message"] = f"SD-WAN neighbor {ip} removed"

        else:
            return {"success": False, "error": f"Unknown action: {action}. Use 'add', 'update', 'remove', 'list', or 'get'"}

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:500]
        except:
            pass
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["details"] = error_body

        if e.code == 500 and "already exist" in error_body.lower():
            result["hint"] = f"Neighbor '{args.get('ip')}' may already exist"

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test: List neighbors
    print("=== Listing SD-WAN Neighbors ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "list"
    })
    print(json.dumps(result, indent=2))

    # Test: Add neighbor
    print("\n=== Adding SD-WAN Neighbor ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "add",
        "ip": "172.16.255.253",
        "members": [3, 4],
        "route_metric": "priority",
        "health_check": "HUB"
    })
    print(json.dumps(result, indent=2))
