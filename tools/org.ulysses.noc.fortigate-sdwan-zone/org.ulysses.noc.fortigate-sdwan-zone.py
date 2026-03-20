#!/usr/bin/env python3
"""
FortiGate SD-WAN Zone Tool

CRUD operations for SD-WAN zones on FortiGate devices.
Configure zones with ADVPN shortcut selection support.

Based on Fortinet 4D-Demo configurations:
- Zone naming
- ADVPN shortcut selection (advpn-select)
- ADVPN health check binding (advpn-health-check)

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


def get_zones(host: str, api_token: str, verify_ssl: bool = False) -> list:
    """Get all SD-WAN zones."""
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/sdwan/zone",
                                 api_token, "GET", verify_ssl=verify_ssl)
        return result.get("results", [])
    except:
        return []


def get_zone(host: str, api_token: str, name: str, verify_ssl: bool = False) -> Optional[dict]:
    """Get a specific SD-WAN zone by name."""
    try:
        result = make_api_request(host, f"/api/v2/cmdb/system/sdwan/zone/{name}",
                                 api_token, "GET", verify_ssl=verify_ssl)
        results = result.get("results", [])
        return results[0] if results else None
    except:
        return None


def add_zone(host: str, api_token: str, name: str,
             advpn_select: bool = None, advpn_health_check: str = None,
             minimum_sla_meet_members: int = None, service_access: str = None,
             verify_ssl: bool = False) -> dict:
    """Add an SD-WAN zone.

    Args:
        name: Zone name
        advpn_select: Enable ADVPN shortcut selection
        advpn_health_check: Health check for ADVPN evaluation
        minimum_sla_meet_members: Min members meeting SLA for ADVPN
        service_access: Service access (allow/deny)
    """
    data = {"name": name}

    if advpn_select is not None:
        data["advpn-select"] = "enable" if advpn_select else "disable"

    if advpn_health_check:
        data["advpn-health-check"] = advpn_health_check

    if minimum_sla_meet_members is not None:
        data["minimum-sla-meet-members"] = minimum_sla_meet_members

    if service_access:
        data["service-access"] = service_access

    return make_api_request(host, "/api/v2/cmdb/system/sdwan/zone",
                            api_token, "POST", data, verify_ssl)


def update_zone(host: str, api_token: str, name: str,
                advpn_select: bool = None, advpn_health_check: str = None,
                minimum_sla_meet_members: int = None, service_access: str = None,
                verify_ssl: bool = False) -> dict:
    """Update an existing SD-WAN zone."""
    data = {}

    if advpn_select is not None:
        data["advpn-select"] = "enable" if advpn_select else "disable"

    if advpn_health_check:
        data["advpn-health-check"] = advpn_health_check

    if minimum_sla_meet_members is not None:
        data["minimum-sla-meet-members"] = minimum_sla_meet_members

    if service_access:
        data["service-access"] = service_access

    return make_api_request(host, f"/api/v2/cmdb/system/sdwan/zone/{name}",
                            api_token, "PUT", data, verify_ssl)


def remove_zone(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Remove an SD-WAN zone."""
    return make_api_request(host, f"/api/v2/cmdb/system/sdwan/zone/{name}",
                            api_token, "DELETE", verify_ssl=verify_ssl)


def main(context) -> dict[str, Any]:
    """
    CRUD operations for SD-WAN zones on FortiGate.

    Args:
        context: ExecutionContext with parameters:
            Required:
            - target_ip: FortiGate management IP

            Optional:
            - action: "add", "update", "remove", "list", or "get" (default: list)

            For add/update:
            - name: Zone name
            - advpn_select: Enable ADVPN shortcut selection (true/false)
            - advpn_health_check: Health check for ADVPN evaluation
            - minimum_sla_meet_members: Min members meeting SLA
            - service_access: allow or deny

            For remove/get:
            - name: Zone name

    Returns:
        dict: Result with zone details
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
            zones = get_zones(target_ip, api_token, verify_ssl)
            result["success"] = True
            result["zones"] = [{
                "name": z.get("name"),
                "advpn-select": z.get("advpn-select", "disable"),
                "advpn-health-check": z.get("advpn-health-check", ""),
                "minimum-sla-meet-members": z.get("minimum-sla-meet-members", 0)
            } for z in zones]
            result["count"] = len(zones)

        elif action == "get":
            name = args.get("name")
            if not name:
                return {"success": False, "error": "name is required for get action"}

            zone = get_zone(target_ip, api_token, name, verify_ssl)
            if zone:
                result["success"] = True
                result["zone"] = {
                    "name": zone.get("name"),
                    "advpn-select": zone.get("advpn-select", "disable"),
                    "advpn-health-check": zone.get("advpn-health-check", ""),
                    "minimum-sla-meet-members": zone.get("minimum-sla-meet-members", 0)
                }
            else:
                result["error"] = f"Zone {name} not found"

        elif action == "add":
            name = args.get("name")
            if not name:
                return {"success": False, "error": "name is required for add action"}

            advpn_select = args.get("advpn_select")
            advpn_health_check = args.get("advpn_health_check")
            minimum_sla_meet_members = args.get("minimum_sla_meet_members")
            service_access = args.get("service_access")

            add_zone(target_ip, api_token, name, advpn_select, advpn_health_check,
                    minimum_sla_meet_members, service_access, verify_ssl)

            result["success"] = True
            result["zone"] = {
                "name": name,
                "advpn_select": advpn_select,
                "advpn_health_check": advpn_health_check
            }

            if advpn_select:
                result["message"] = f"SD-WAN zone {name} created with ADVPN enabled"
            else:
                result["message"] = f"SD-WAN zone {name} created"

        elif action == "update":
            name = args.get("name")
            if not name:
                return {"success": False, "error": "name is required for update action"}

            advpn_select = args.get("advpn_select")
            advpn_health_check = args.get("advpn_health_check")
            minimum_sla_meet_members = args.get("minimum_sla_meet_members")
            service_access = args.get("service_access")

            update_zone(target_ip, api_token, name, advpn_select, advpn_health_check,
                       minimum_sla_meet_members, service_access, verify_ssl)

            result["success"] = True
            result["name"] = name
            result["message"] = f"SD-WAN zone {name} updated"

        elif action == "remove":
            name = args.get("name")
            if not name:
                return {"success": False, "error": "name is required for remove action"}

            remove_zone(target_ip, api_token, name, verify_ssl)
            result["success"] = True
            result["name"] = name
            result["message"] = f"SD-WAN zone {name} removed"

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
            result["hint"] = f"Zone '{args.get('name')}' may already exist"
        elif e.code == 500 and "in use" in error_body.lower():
            result["hint"] = f"Zone '{args.get('name')}' is in use by members or policies"

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test: List zones
    print("=== Listing SD-WAN Zones ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "list"
    })
    print(json.dumps(result, indent=2))

    # Test: Add zone with ADVPN
    print("\n=== Adding SD-WAN Zone with ADVPN ===")
    result = main({
        "target_ip": "192.168.209.30",
        "action": "add",
        "name": "HUB1",
        "advpn_select": True,
        "advpn_health_check": "HUB"
    })
    print(json.dumps(result, indent=2))
