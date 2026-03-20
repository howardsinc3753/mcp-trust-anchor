#!/usr/bin/env python3
"""
FortiGate VIP Tool

CRUD operations for Virtual IP (VIP) objects on FortiGate devices.
Configure static NAT, port forwarding, and load balancing VIPs.

Canonical ID: org.ulysses.noc.fortigate-vip/1.0.1
"""

import json
import sys
import os
import urllib3
from typing import Optional
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

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


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


def api_request(host: str, api_token: str, method: str, endpoint: str,
                data: dict = None, verify_ssl: bool = False) -> dict:
    """Make FortiOS API request."""
    url = f"https://{host}/api/v2{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

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


def list_vips(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all VIPs."""
    result = api_request(host, api_token, "GET", "/cmdb/firewall/vip", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get VIPs")}

    data = result.get("data", {})
    vips_raw = data.get("results", [])

    vips = []
    for v in vips_raw:
        vip = {
            "name": v.get("name"),
            "type": v.get("type"),
            "extip": v.get("extip"),
            "mappedip": v.get("mappedip"),
            "extintf": v.get("extintf"),
            "portforward": v.get("portforward"),
            "protocol": v.get("protocol"),
            "extport": v.get("extport"),
            "mappedport": v.get("mappedport"),
            "comment": v.get("comment"),
            "arp_reply": v.get("arp-reply"),
            "color": v.get("color"),
        }
        # Clean up mappedip if it's a list
        if isinstance(vip["mappedip"], list) and len(vip["mappedip"]) > 0:
            vip["mappedip"] = vip["mappedip"][0].get("range", "")
        vips.append(vip)

    return {"success": True, "count": len(vips), "vips": vips}


def get_vip(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get specific VIP."""
    result = api_request(host, api_token, "GET", f"/cmdb/firewall/vip/{name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"VIP '{name}' not found"}

    data = result.get("data", {})
    results = data.get("results", [])
    if isinstance(results, list) and len(results) > 0:
        v = results[0]
    elif isinstance(results, dict):
        v = results
    else:
        return {"success": False, "error": f"VIP '{name}' not found"}

    vip = {
        "name": v.get("name"),
        "type": v.get("type"),
        "extip": v.get("extip"),
        "mappedip": v.get("mappedip"),
        "extintf": v.get("extintf"),
        "portforward": v.get("portforward"),
        "protocol": v.get("protocol"),
        "extport": v.get("extport"),
        "mappedport": v.get("mappedport"),
        "comment": v.get("comment"),
        "arp_reply": v.get("arp-reply"),
        "color": v.get("color"),
    }
    # Clean up mappedip if it's a list
    if isinstance(vip["mappedip"], list) and len(vip["mappedip"]) > 0:
        vip["mappedip"] = vip["mappedip"][0].get("range", "")

    return {"success": True, "vip": vip}


def add_vip(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Add VIP."""
    name = params.get("name")
    extip = params.get("extip")
    mappedip = params.get("mappedip")
    extintf = params.get("extintf")

    if not name:
        return {"success": False, "error": "name is required"}
    if not extip:
        return {"success": False, "error": "extip is required"}
    if not mappedip:
        return {"success": False, "error": "mappedip is required"}
    if not extintf:
        return {"success": False, "error": "extintf is required"}

    vip_data = {
        "name": name,
        "extip": extip,
        "mappedip": [{"range": mappedip}],  # FortiOS expects array of {range: IP}
        "extintf": extintf,
    }

    # Optional fields
    if params.get("type"):
        vip_data["type"] = params["type"]
    if params.get("portforward"):
        vip_data["portforward"] = params["portforward"]
    if params.get("protocol"):
        vip_data["protocol"] = params["protocol"]
    if params.get("extport"):
        vip_data["extport"] = params["extport"]
    if params.get("mappedport"):
        vip_data["mappedport"] = params["mappedport"]
    if params.get("comment"):
        vip_data["comment"] = params["comment"]
    if params.get("arp_reply"):
        vip_data["arp-reply"] = params["arp_reply"]
    if params.get("color") is not None:
        vip_data["color"] = params["color"]

    result = api_request(host, api_token, "POST", "/cmdb/firewall/vip", data=vip_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "message": f"Added VIP '{name}' ({extip} -> {mappedip})"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = str(cli_error)
        return {"success": False, "error": f"Failed to add VIP: {error_msg}", "details": result}


def update_vip(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update VIP."""
    name = params.get("name")

    if not name:
        return {"success": False, "error": "name is required"}

    # Check if exists
    existing = get_vip(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"VIP '{name}' not found"}

    vip_data = {}

    # Update fields
    if params.get("extip"):
        vip_data["extip"] = params["extip"]
    if params.get("mappedip"):
        vip_data["mappedip"] = [{"range": params["mappedip"]}]
    if params.get("extintf"):
        vip_data["extintf"] = params["extintf"]
    if params.get("type"):
        vip_data["type"] = params["type"]
    if params.get("portforward"):
        vip_data["portforward"] = params["portforward"]
    if params.get("protocol"):
        vip_data["protocol"] = params["protocol"]
    if params.get("extport"):
        vip_data["extport"] = params["extport"]
    if params.get("mappedport"):
        vip_data["mappedport"] = params["mappedport"]
    if params.get("comment"):
        vip_data["comment"] = params["comment"]
    if params.get("arp_reply"):
        vip_data["arp-reply"] = params["arp_reply"]
    if params.get("color") is not None:
        vip_data["color"] = params["color"]

    if not vip_data:
        return {"success": False, "error": "No fields to update"}

    result = api_request(host, api_token, "PUT", f"/cmdb/firewall/vip/{name}", data=vip_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "updated_fields": list(vip_data.keys()),
            "message": f"Updated VIP '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        return {"success": False, "error": f"Failed to update VIP: {error_msg}", "details": result}


def remove_vip(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Remove VIP."""
    # Check if exists
    existing = get_vip(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"VIP '{name}' not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/firewall/vip/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "name": name,
            "message": f"Removed VIP '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        # Check if VIP is in use
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = str(cli_error)
        return {"success": False, "error": f"Failed to remove VIP: {error_msg}", "details": result}


def main(context) -> dict:
    """Main entry point."""
    # Handle both ExecutionContext (MCP) and dict (CLI)
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "").lower()
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
        list_result = list_vips(target_ip, api_token, verify_ssl)
        result.update(list_result)
        if list_result["success"]:
            result["message"] = f"Found {list_result['count']} VIPs"

    elif action == "get":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for get"}
        get_result = get_vip(target_ip, api_token, name, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_vip(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "update":
        update_result = update_vip(target_ip, api_token, params, verify_ssl)
        result.update(update_result)

    elif action == "remove":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for remove"}
        remove_result = remove_vip(target_ip, api_token, name, verify_ssl)
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
