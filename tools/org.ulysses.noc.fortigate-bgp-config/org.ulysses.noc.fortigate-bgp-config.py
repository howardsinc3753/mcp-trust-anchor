#!/usr/bin/env python3
"""
FortiGate BGP Config Tool

Configure BGP global settings on FortiGate devices.
Supports AS number, router-id, multipath, graceful-restart, etc.

Canonical ID: org.ulysses.noc.fortigate-bgp-config/1.0.0
"""

import json
import sys
import os
import urllib3
from typing import Optional, Any
from pathlib import Path

# Suppress SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Try to import requests, fall back to urllib if not available
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
    """Make FortiOS API request with Bearer token auth."""
    url = f"https://{host}/api/v2{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

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
                result = {
                    "status_code": resp.status,
                    "success": resp.status in [200, 201]
                }
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


def get_bgp_config(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """Get current BGP global configuration."""
    result = api_request(host, api_token, "GET", "/cmdb/router/bgp", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get BGP config")}

    data = result.get("data", {})
    bgp_raw = data.get("results", data)

    # Extract key BGP settings
    bgp_config = {
        "as": bgp_raw.get("as", 0),
        "router-id": bgp_raw.get("router-id", "0.0.0.0"),
        "ibgp-multipath": bgp_raw.get("ibgp-multipath", "disable"),
        "ibgp-multipath-same-as": bgp_raw.get("ibgp-multipath-same-as", "disable"),
        "recursive-next-hop": bgp_raw.get("recursive-next-hop", "disable"),
        "graceful-restart": bgp_raw.get("graceful-restart", "disable"),
        "graceful-restart-time": bgp_raw.get("graceful-restart-time", 120),
        "graceful-stalepath-time": bgp_raw.get("graceful-stalepath-time", 360),
        "scan-time": bgp_raw.get("scan-time", 60),
        "always-compare-med": bgp_raw.get("always-compare-med", "disable"),
        "deterministic-med": bgp_raw.get("deterministic-med", "disable"),
        "bestpath-as-path-ignore": bgp_raw.get("bestpath-as-path-ignore", "disable"),
        "network-import-check": bgp_raw.get("network-import-check", "enable"),
        "holdtime-timer": bgp_raw.get("holdtime-timer", 180),
        "keepalive-timer": bgp_raw.get("keepalive-timer", 60),
    }

    # Count neighbors if present
    neighbors = bgp_raw.get("neighbor", [])
    bgp_config["neighbor_count"] = len(neighbors) if isinstance(neighbors, list) else 0

    return {
        "success": True,
        "bgp_config": bgp_config
    }


def set_bgp_config(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Set BGP global configuration."""
    # Build update payload
    update_data = {}
    updated_fields = []

    # Map parameter names (underscore to hyphen)
    param_map = {
        "as": "as",
        "router_id": "router-id",
        "ibgp_multipath": "ibgp-multipath",
        "ibgp_multipath_same_as": "ibgp-multipath-same-as",
        "recursive_next_hop": "recursive-next-hop",
        "graceful_restart": "graceful-restart",
        "graceful_restart_time": "graceful-restart-time",
        "graceful_stalepath_time": "graceful-stalepath-time",
        "scan_time": "scan-time",
        "always_compare_med": "always-compare-med",
        "deterministic_med": "deterministic-med",
        "bestpath_as_path_ignore": "bestpath-as-path-ignore",
    }

    for param_name, api_name in param_map.items():
        if param_name in params and params[param_name] is not None:
            value = params[param_name]
            # Convert integers for numeric fields
            if param_name in ["as", "graceful_restart_time", "graceful_stalepath_time", "scan_time"]:
                value = int(value)
            update_data[api_name] = value
            updated_fields.append(api_name)

    if not update_data:
        return {"success": False, "error": "No configuration fields specified"}

    # Apply configuration
    result = api_request(host, api_token, "PUT", "/cmdb/router/bgp", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "updated_fields": updated_fields,
            "message": f"Updated BGP configuration: {', '.join(updated_fields)}"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {
            "success": False,
            "error": f"Failed to update BGP config: {error_msg}",
            "details": result
        }


def main(context) -> dict[str, Any]:
    """Main entry point for the tool."""
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "get").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["get", "set"]:
        return {"success": False, "error": f"Invalid action: {action}. Must be 'get' or 'set'"}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    result = {"action": action, "target_ip": target_ip}

    if action == "get":
        get_result = get_bgp_config(target_ip, api_token, verify_ssl)
        result.update(get_result)
        if get_result["success"]:
            as_num = get_result["bgp_config"].get("as", 0)
            router_id = get_result["bgp_config"].get("router-id", "0.0.0.0")
            result["message"] = f"BGP AS {as_num}, Router-ID {router_id}"

    elif action == "set":
        set_result = set_bgp_config(target_ip, api_token, params, verify_ssl)
        result.update(set_result)

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
