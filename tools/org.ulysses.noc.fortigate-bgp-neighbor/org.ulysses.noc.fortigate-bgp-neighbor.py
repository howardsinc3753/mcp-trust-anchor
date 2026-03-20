#!/usr/bin/env python3
"""
FortiGate BGP Neighbor Tool

CRUD operations for BGP neighbors on FortiGate devices.
Configure iBGP/eBGP neighbors with graceful restart, soft-reconfiguration, etc.

Canonical ID: org.ulysses.noc.fortigate-bgp-neighbor/1.0.0
"""

import json
import sys
import os
from typing import Optional, Any
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    import ssl
except ImportError:
    pass

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from MCP config paths."""
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
                     method: str = "GET", data: dict = None,
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """Make FortiGate REST API request."""
    url = f"https://{host}{endpoint}"

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    body = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            result = response.read().decode('utf-8')
            return {"success": True, "status_code": response.status, "data": json.loads(result) if result else {}}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        return {
            "success": False,
            "status_code": e.code,
            "error": f"HTTP {e.code}: {e.reason}",
            "details": error_body
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_bgp_neighbors(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all BGP neighbors."""
    result = make_api_request(host, "/api/v2/cmdb/router/bgp/neighbor", api_token, "GET", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get neighbors")}

    neighbors = result.get("data", {}).get("results", [])
    return {
        "success": True,
        "count": len(neighbors),
        "neighbors": [{
            "ip": n.get("ip"),
            "remote_as": n.get("remote-as"),
            "interface": n.get("interface"),
            "update_source": n.get("update-source"),
            "soft_reconfiguration": n.get("soft-reconfiguration"),
            "capability_graceful_restart": n.get("capability-graceful-restart"),
            "advertisement_interval": n.get("advertisement-interval")
        } for n in neighbors]
    }


def get_bgp_neighbor(host: str, api_token: str, ip: str, verify_ssl: bool = False) -> dict:
    """Get specific BGP neighbor."""
    result = make_api_request(host, f"/api/v2/cmdb/router/bgp/neighbor/{ip}", api_token, "GET", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Neighbor {ip} not found"}

    results = result.get("data", {}).get("results", [])
    if not results:
        return {"success": False, "error": f"Neighbor {ip} not found"}

    n = results[0] if isinstance(results, list) else results
    return {
        "success": True,
        "neighbor": {
            "ip": n.get("ip"),
            "remote_as": n.get("remote-as"),
            "interface": n.get("interface"),
            "update_source": n.get("update-source"),
            "soft_reconfiguration": n.get("soft-reconfiguration"),
            "capability_graceful_restart": n.get("capability-graceful-restart"),
            "advertisement_interval": n.get("advertisement-interval"),
            "connect_timer": n.get("connect-timer")
        }
    }


def add_bgp_neighbor(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Add a BGP neighbor."""
    ip = params.get("ip")
    remote_as = params.get("remote_as")

    if not ip:
        return {"success": False, "error": "ip is required"}
    if not remote_as:
        return {"success": False, "error": "remote_as is required"}

    neighbor_data = {
        "ip": ip,
        "remote-as": remote_as
    }

    # Optional fields
    if params.get("interface"):
        neighbor_data["interface"] = params["interface"]
    if params.get("update_source"):
        neighbor_data["update-source"] = params["update_source"]
    if params.get("soft_reconfiguration"):
        neighbor_data["soft-reconfiguration"] = params["soft_reconfiguration"]
    if params.get("capability_graceful_restart"):
        neighbor_data["capability-graceful-restart"] = params["capability_graceful_restart"]
    if params.get("advertisement_interval") is not None:
        neighbor_data["advertisement-interval"] = params["advertisement_interval"]
    if params.get("connect_timer") is not None:
        neighbor_data["connect-timer"] = params["connect_timer"]
    if params.get("next_hop_self"):
        neighbor_data["next-hop-self"] = params["next_hop_self"]

    result = make_api_request(host, "/api/v2/cmdb/router/bgp/neighbor", api_token, "POST", neighbor_data, verify_ssl)

    if result.get("success") or result.get("status_code") in [200, 201]:
        return {
            "success": True,
            "ip": ip,
            "remote_as": remote_as,
            "message": f"Added BGP neighbor {ip} (AS {remote_as})"
        }
    else:
        return {"success": False, "error": f"Failed to add neighbor: {result.get('error', '')}", "details": result.get("details")}


def update_bgp_neighbor(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update a BGP neighbor."""
    ip = params.get("ip")

    if not ip:
        return {"success": False, "error": "ip is required"}

    neighbor_data = {}

    if params.get("remote_as"):
        neighbor_data["remote-as"] = params["remote_as"]
    if params.get("interface"):
        neighbor_data["interface"] = params["interface"]
    if params.get("update_source"):
        neighbor_data["update-source"] = params["update_source"]
    if params.get("soft_reconfiguration"):
        neighbor_data["soft-reconfiguration"] = params["soft_reconfiguration"]
    if params.get("capability_graceful_restart"):
        neighbor_data["capability-graceful-restart"] = params["capability_graceful_restart"]
    if params.get("advertisement_interval") is not None:
        neighbor_data["advertisement-interval"] = params["advertisement_interval"]
    if params.get("connect_timer") is not None:
        neighbor_data["connect-timer"] = params["connect_timer"]

    if not neighbor_data:
        return {"success": False, "error": "No fields to update"}

    result = make_api_request(host, f"/api/v2/cmdb/router/bgp/neighbor/{ip}", api_token, "PUT", neighbor_data, verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "ip": ip,
            "updated_fields": list(neighbor_data.keys()),
            "message": f"Updated BGP neighbor {ip}"
        }
    else:
        return {"success": False, "error": f"Failed to update neighbor: {result.get('error', '')}", "details": result.get("details")}


def remove_bgp_neighbor(host: str, api_token: str, ip: str, verify_ssl: bool = False) -> dict:
    """Remove a BGP neighbor."""
    result = make_api_request(host, f"/api/v2/cmdb/router/bgp/neighbor/{ip}", api_token, "DELETE", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "ip": ip,
            "message": f"Removed BGP neighbor {ip}"
        }
    else:
        return {"success": False, "error": f"Failed to remove neighbor: {result.get('error', '')}", "details": result.get("details")}


def main(context) -> dict[str, Any]:
    """Main entry point for BGP neighbor CRUD operations."""
    if hasattr(context, "parameters"):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "list").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["add", "update", "remove", "list", "get"]:
        return {"success": False, "error": f"Invalid action: {action}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}

    api_token = creds.get("api_token")
    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        list_result = list_bgp_neighbors(target_ip, api_token, verify_ssl)
        result.update(list_result)

    elif action == "get":
        ip = params.get("ip")
        if not ip:
            return {"success": False, "error": "ip is required for get"}
        get_result = get_bgp_neighbor(target_ip, api_token, ip, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_bgp_neighbor(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "update":
        update_result = update_bgp_neighbor(target_ip, api_token, params, verify_ssl)
        result.update(update_result)

    elif action == "remove":
        ip = params.get("ip")
        if not ip:
            return {"success": False, "error": "ip is required for remove"}
        remove_result = remove_bgp_neighbor(target_ip, api_token, ip, verify_ssl)
        result.update(remove_result)

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        params = {}
        for arg in sys.argv[1:]:
            if '=' in arg:
                key, val = arg.split('=', 1)
                key = key.lstrip('-')
                if val.lower() in ['true', 'false']:
                    val = val.lower() == 'true'
                elif val.isdigit():
                    val = int(val)
                params[key] = val
        result = main(params)
    else:
        try:
            input_data = sys.stdin.read()
            params = json.loads(input_data) if input_data.strip() else {}
            result = main(params)
        except json.JSONDecodeError as e:
            result = {"success": False, "error": f"Invalid JSON: {e}"}

    print(json.dumps(result, indent=2))
