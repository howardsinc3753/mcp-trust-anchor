#!/usr/bin/env python3
"""
FortiGate BGP Neighbor Group Tool

Manage BGP neighbor groups for dynamic peer acceptance in SD-WAN/ADVPN.

Canonical ID: org.ulysses.noc.fortigate-bgp-neighbor-group/1.0.0
"""

import json
import sys
import os
import urllib3
from typing import Optional, Any
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import ssl


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from local config file."""
    config_paths = [
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]
    if os.name == 'nt':
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
        config_paths.append(Path("C:/ProgramData/mcp/fortigate_credentials.yaml"))
        config_paths.append(Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"))
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


def api_request(host: str, api_token: str, method: str, endpoint: str,
                data: dict = None, verify_ssl: bool = False) -> dict:
    """Make FortiOS API request."""
    url = f"https://{host}/api/v2{endpoint}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    if HAS_REQUESTS:
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, verify=verify_ssl, timeout=30)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=data, verify=verify_ssl, timeout=30)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=data, verify=verify_ssl, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, verify=verify_ssl, timeout=30)
            else:
                return {"success": False, "error": f"Unknown method: {method}"}
            result = {"status_code": resp.status_code, "success": resp.status_code in [200, 201]}
            try:
                result["data"] = resp.json()
            except:
                result["data"] = {"raw": resp.text}
            return result
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    else:
        ctx = ssl.create_default_context()
        if not verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            if data:
                req.data = json.dumps(data).encode('utf-8')
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                result = {"status_code": resp.status, "success": resp.status in [200, 201]}
                try:
                    result["data"] = json.loads(resp.read().decode('utf-8'))
                except:
                    result["data"] = {}
                return result
        except urllib.error.HTTPError as e:
            result = {"success": False, "status_code": e.code, "error": str(e)}
            try:
                result["data"] = json.loads(e.read().decode('utf-8'))
            except:
                pass
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


def list_neighbor_groups(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all BGP neighbor groups."""
    result = api_request(host, api_token, "GET", "/cmdb/router/bgp/neighbor-group", verify_ssl=verify_ssl)
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get neighbor groups")}

    data = result.get("data", {})
    groups = data.get("results", [])

    return {
        "success": True,
        "count": len(groups),
        "neighbor_groups": [{
            "name": g.get("name"),
            "remote-as": g.get("remote-as", 0),
            "update-source": g.get("update-source", ""),
            "next-hop-self": g.get("next-hop-self", "disable"),
            "soft-reconfiguration": g.get("soft-reconfiguration", "disable"),
            "route-reflector-client": g.get("route-reflector-client", "disable"),
        } for g in groups]
    }


def get_neighbor_group(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get specific neighbor group."""
    result = api_request(host, api_token, "GET", f"/cmdb/router/bgp/neighbor-group/{name}", verify_ssl=verify_ssl)
    if not result.get("success"):
        return {"success": False, "error": f"Neighbor group '{name}' not found"}

    data = result.get("data", {})
    group = data.get("results", [data])[0] if isinstance(data.get("results"), list) else data

    return {
        "success": True,
        "neighbor_group": {
            "name": group.get("name"),
            "remote-as": group.get("remote-as", 0),
            "update-source": group.get("update-source", ""),
            "next-hop-self": group.get("next-hop-self", "disable"),
            "soft-reconfiguration": group.get("soft-reconfiguration", "disable"),
            "capability-graceful-restart": group.get("capability-graceful-restart", "enable"),
            "capability-route-refresh": group.get("capability-route-refresh", "enable"),
            "route-reflector-client": group.get("route-reflector-client", "disable"),
            "link-down-failover": group.get("link-down-failover", "disable"),
        }
    }


def add_neighbor_group(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create new neighbor group."""
    name = params.get("name")
    if not name:
        return {"success": False, "error": "name is required"}

    # Check if exists
    existing = get_neighbor_group(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Neighbor group '{name}' already exists"}

    group_data = {"name": name}

    param_map = {
        "remote_as": "remote-as",
        "update_source": "update-source",
        "soft_reconfiguration": "soft-reconfiguration",
        "capability_graceful_restart": "capability-graceful-restart",
        "capability_route_refresh": "capability-route-refresh",
        "next_hop_self": "next-hop-self",
        "route_reflector_client": "route-reflector-client",
        "link_down_failover": "link-down-failover",
    }

    for param_name, api_name in param_map.items():
        if param_name in params and params[param_name] is not None:
            group_data[api_name] = params[param_name]

    result = api_request(host, api_token, "POST", "/cmdb/router/bgp/neighbor-group", data=group_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {"success": True, "name": name, "message": f"Created neighbor group '{name}'"}
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to create neighbor group: {error_msg}"}


def update_neighbor_group(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update existing neighbor group."""
    name = params.get("name")
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_neighbor_group(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Neighbor group '{name}' not found"}

    update_data = {}
    param_map = {
        "remote_as": "remote-as",
        "update_source": "update-source",
        "soft_reconfiguration": "soft-reconfiguration",
        "capability_graceful_restart": "capability-graceful-restart",
        "capability_route_refresh": "capability-route-refresh",
        "next_hop_self": "next-hop-self",
        "route_reflector_client": "route-reflector-client",
        "link_down_failover": "link-down-failover",
    }

    for param_name, api_name in param_map.items():
        if param_name in params and params[param_name] is not None:
            update_data[api_name] = params[param_name]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    result = api_request(host, api_token, "PUT", f"/cmdb/router/bgp/neighbor-group/{name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {"success": True, "name": name, "updated_fields": list(update_data.keys()), "message": f"Updated neighbor group '{name}'"}
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to update neighbor group: {error_msg}"}


def remove_neighbor_group(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete neighbor group."""
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_neighbor_group(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Neighbor group '{name}' not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/router/bgp/neighbor-group/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {"success": True, "name": name, "message": f"Deleted neighbor group '{name}'"}
    else:
        return {"success": False, "error": f"Failed to delete neighbor group: {result.get('error', 'Unknown error')}"}


def main(context) -> dict[str, Any]:
    """Main entry point."""
    params = context.parameters if hasattr(context, 'parameters') else context

    target_ip = params.get("target_ip")
    action = params.get("action", "list").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["list", "get", "add", "update", "remove"]:
        return {"success": False, "error": f"Invalid action: {action}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}

    api_token = creds.get("api_token")
    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        result.update(list_neighbor_groups(target_ip, api_token, verify_ssl))
    elif action == "get":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for 'get' action"}
        result.update(get_neighbor_group(target_ip, api_token, name, verify_ssl))
    elif action == "add":
        result.update(add_neighbor_group(target_ip, api_token, params, verify_ssl))
    elif action == "update":
        result.update(update_neighbor_group(target_ip, api_token, params, verify_ssl))
    elif action == "remove":
        name = params.get("name")
        result.update(remove_neighbor_group(target_ip, api_token, name, verify_ssl))

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
            result = {"success": False, "error": f"Invalid JSON input: {e}"}
    print(json.dumps(result, indent=2))
