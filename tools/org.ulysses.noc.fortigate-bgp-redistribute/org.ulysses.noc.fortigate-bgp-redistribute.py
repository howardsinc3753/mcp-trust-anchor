#!/usr/bin/env python3
"""
FortiGate BGP Redistribute Tool

Configure BGP route redistribution settings.

Canonical ID: org.ulysses.noc.fortigate-bgp-redistribute/1.0.0
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
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=data, verify=verify_ssl, timeout=30)
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


def get_redistribute_config(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """Get current BGP redistribution settings."""
    result = api_request(host, api_token, "GET", "/cmdb/router/bgp", verify_ssl=verify_ssl)
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get BGP config")}

    data = result.get("data", {})
    bgp = data.get("results", data)

    redistribute = {
        "redistribute-connected": bgp.get("redistribute", [{}])[0].get("status", "disable") if bgp.get("redistribute") else "disable",
        "redistribute-connected-routemap": "",
        "redistribute-static": "disable",
        "redistribute-static-routemap": "",
        "redistribute-ospf": "disable",
        "redistribute-ospf-routemap": "",
        "redistribute-rip": "disable",
        "redistribute-isis": "disable",
    }

    # Parse redistribute array
    for r in bgp.get("redistribute", []):
        name = r.get("name", "")
        status = r.get("status", "disable")
        routemap = r.get("route-map", "")

        if name == "connected":
            redistribute["redistribute-connected"] = status
            redistribute["redistribute-connected-routemap"] = routemap
        elif name == "static":
            redistribute["redistribute-static"] = status
            redistribute["redistribute-static-routemap"] = routemap
        elif name == "ospf":
            redistribute["redistribute-ospf"] = status
            redistribute["redistribute-ospf-routemap"] = routemap
        elif name == "rip":
            redistribute["redistribute-rip"] = status
        elif name == "isis":
            redistribute["redistribute-isis"] = status

    return {
        "success": True,
        "redistribute": redistribute
    }


def set_redistribute_config(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Set BGP redistribution settings."""
    # Build redistribute array
    redistribute = []
    updated_fields = []

    # Connected routes
    if "redistribute_connected" in params:
        entry = {"name": "connected", "status": params["redistribute_connected"]}
        if "redistribute_connected_routemap" in params:
            entry["route-map"] = params["redistribute_connected_routemap"]
        redistribute.append(entry)
        updated_fields.append("redistribute-connected")

    # Static routes
    if "redistribute_static" in params:
        entry = {"name": "static", "status": params["redistribute_static"]}
        if "redistribute_static_routemap" in params:
            entry["route-map"] = params["redistribute_static_routemap"]
        redistribute.append(entry)
        updated_fields.append("redistribute-static")

    # OSPF routes
    if "redistribute_ospf" in params:
        entry = {"name": "ospf", "status": params["redistribute_ospf"]}
        if "redistribute_ospf_routemap" in params:
            entry["route-map"] = params["redistribute_ospf_routemap"]
        redistribute.append(entry)
        updated_fields.append("redistribute-ospf")

    # RIP routes
    if "redistribute_rip" in params:
        redistribute.append({"name": "rip", "status": params["redistribute_rip"]})
        updated_fields.append("redistribute-rip")

    # ISIS routes
    if "redistribute_isis" in params:
        redistribute.append({"name": "isis", "status": params["redistribute_isis"]})
        updated_fields.append("redistribute-isis")

    if not redistribute:
        return {"success": False, "error": "No redistribution settings specified"}

    update_data = {"redistribute": redistribute}

    result = api_request(host, api_token, "PUT", "/cmdb/router/bgp", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "updated_fields": updated_fields,
            "message": f"Updated redistribution: {', '.join(updated_fields)}"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to update redistribution: {error_msg}"}


def main(context) -> dict[str, Any]:
    """Main entry point."""
    params = context.parameters if hasattr(context, 'parameters') else context

    target_ip = params.get("target_ip")
    action = params.get("action", "get").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["get", "set"]:
        return {"success": False, "error": f"Invalid action: {action}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}

    api_token = creds.get("api_token")
    result = {"action": action, "target_ip": target_ip}

    if action == "get":
        result.update(get_redistribute_config(target_ip, api_token, verify_ssl))
    elif action == "set":
        result.update(set_redistribute_config(target_ip, api_token, params, verify_ssl))

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
