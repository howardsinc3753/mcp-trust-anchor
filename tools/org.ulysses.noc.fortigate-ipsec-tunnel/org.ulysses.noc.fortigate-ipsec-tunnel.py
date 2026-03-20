#!/usr/bin/env python3
"""
FortiGate IPsec Tunnel Management Tool

Manage IPsec VPN tunnels on FortiGate devices.
Supports listing tunnels, bringing interfaces up/down for failover testing.

Canonical ID: org.ulysses.noc.fortigate-ipsec-tunnel/1.0.0
"""

import json
import sys
import os
import urllib3
from typing import Optional, List
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


def list_ipsec_tunnels(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all IPsec phase1 interfaces (tunnels)."""
    # Get phase1-interface config
    result = api_request(host, api_token, "GET", "/cmdb/vpn.ipsec/phase1-interface", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get IPsec tunnels")}

    data = result.get("data", {}).get("results", [])

    tunnels = []
    for t in data:
        tunnel = {
            "name": t.get("name", ""),
            "interface": t.get("interface", ""),
            "remote_gw": t.get("remote-gw", ""),
            "ike_version": t.get("ike-version", ""),
            "type": t.get("type", ""),
            "psk": "***" if t.get("psksecret") else "",
            "dpd": t.get("dpd", ""),
            "dpd_retry_count": t.get("dpd-retrycount", 0),
            "dpd_retry_interval": t.get("dpd-retryinterval", 0),
            "proposal": t.get("proposal", ""),
            "local_gw": t.get("local-gw", "0.0.0.0"),
            "mode_cfg": t.get("mode-cfg", "disable"),
            "net_device": t.get("net-device", "disable"),
        }
        tunnels.append(tunnel)

    # Get tunnel status from monitor endpoint
    status_result = api_request(host, api_token, "GET", "/monitor/vpn/ipsec", verify_ssl=verify_ssl)
    tunnel_status = {}
    if status_result.get("success"):
        status_data = status_result.get("data", {}).get("results", [])
        for s in status_data:
            name = s.get("name", "")
            if name:
                tunnel_status[name] = {
                    "status": "up" if s.get("proxyid") else "down",
                    "incoming_bytes": s.get("incoming_bytes", 0),
                    "outgoing_bytes": s.get("outgoing_bytes", 0),
                    "rgwy": s.get("rgwy", ""),
                    "creation_time": s.get("creation_time", 0)
                }

    # Merge status into tunnels
    for t in tunnels:
        name = t["name"]
        if name in tunnel_status:
            t["status"] = tunnel_status[name]["status"]
            t["incoming_bytes"] = tunnel_status[name]["incoming_bytes"]
            t["outgoing_bytes"] = tunnel_status[name]["outgoing_bytes"]
        else:
            t["status"] = "unknown"

    return {
        "success": True,
        "tunnels": tunnels,
        "count": len(tunnels)
    }


def get_interface_status(host: str, api_token: str, interface_name: str, verify_ssl: bool = False) -> dict:
    """Get interface admin status."""
    result = api_request(host, api_token, "GET", f"/cmdb/system/interface/{interface_name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", f"Failed to get interface {interface_name}")}

    data = result.get("data", {}).get("results", [])
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    return {
        "success": True,
        "name": data.get("name", interface_name),
        "status": data.get("status", ""),
        "type": data.get("type", ""),
        "ip": data.get("ip", ""),
        "vdom": data.get("vdom", "root")
    }


def set_interface_status(host: str, api_token: str, interface_name: str,
                         status: str, verify_ssl: bool = False) -> dict:
    """Set interface admin status (up/down)."""
    if status not in ["up", "down"]:
        return {"success": False, "error": f"Invalid status: {status}. Must be 'up' or 'down'"}

    # First verify the interface exists
    check = get_interface_status(host, api_token, interface_name, verify_ssl)
    if not check.get("success"):
        return check

    # Set the status
    payload = {"status": status}
    result = api_request(host, api_token, "PUT", f"/cmdb/system/interface/{interface_name}",
                        data=payload, verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "interface": interface_name,
            "status": status,
            "message": f"Interface '{interface_name}' set to {status}"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = str(cli_error)
        return {"success": False, "error": f"Failed to set interface status: {error_msg}", "details": result}


def shutdown_tunnel(host: str, api_token: str, tunnel_name: str, verify_ssl: bool = False) -> dict:
    """Shutdown an IPsec tunnel by disabling its interface."""
    return set_interface_status(host, api_token, tunnel_name, "down", verify_ssl)


def bring_up_tunnel(host: str, api_token: str, tunnel_name: str, verify_ssl: bool = False) -> dict:
    """Bring up an IPsec tunnel by enabling its interface."""
    return set_interface_status(host, api_token, tunnel_name, "up", verify_ssl)


def get_tunnel_status(host: str, api_token: str, tunnel_name: str = None, verify_ssl: bool = False) -> dict:
    """Get IPsec tunnel operational status from monitor API."""
    result = api_request(host, api_token, "GET", "/monitor/vpn/ipsec", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get tunnel status")}

    data = result.get("data", {}).get("results", [])

    tunnels = []
    for t in data:
        tunnel = {
            "name": t.get("name", ""),
            "status": "up" if t.get("proxyid") else "down",
            "phase1_status": "up" if t.get("connection_count", 0) > 0 else "down",
            "incoming_bytes": t.get("incoming_bytes", 0),
            "outgoing_bytes": t.get("outgoing_bytes", 0),
            "rgwy": t.get("rgwy", ""),
            "tun_id": t.get("tun_id", ""),
            "creation_time": t.get("creation_time", 0),
            "proxyid": t.get("proxyid", [])
        }

        # Filter by tunnel name if specified
        if tunnel_name and tunnel["name"] != tunnel_name:
            continue

        tunnels.append(tunnel)

    if tunnel_name and len(tunnels) == 0:
        return {"success": False, "error": f"Tunnel '{tunnel_name}' not found in status"}

    return {
        "success": True,
        "tunnels": tunnels,
        "count": len(tunnels)
    }


def main(context) -> dict:
    """Main entry point for the tool."""
    # Handle both ExecutionContext (MCP) and dict (CLI)
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "list").lower()
    tunnel_name = params.get("tunnel_name")
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    valid_actions = ["list", "status", "shutdown", "up", "down"]
    if action not in valid_actions:
        return {"success": False, "error": f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        action_result = list_ipsec_tunnels(target_ip, api_token, verify_ssl)
        result.update(action_result)

    elif action == "status":
        action_result = get_tunnel_status(target_ip, api_token, tunnel_name, verify_ssl)
        result.update(action_result)

    elif action == "shutdown" or action == "down":
        if not tunnel_name:
            return {"success": False, "error": "tunnel_name is required for shutdown action"}
        action_result = shutdown_tunnel(target_ip, api_token, tunnel_name, verify_ssl)
        result.update(action_result)

    elif action == "up":
        if not tunnel_name:
            return {"success": False, "error": "tunnel_name is required for up action"}
        action_result = bring_up_tunnel(target_ip, api_token, tunnel_name, verify_ssl)
        result.update(action_result)

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
