#!/usr/bin/env python3
"""
FortiGate IPsec Tool

CRUD operations for IPsec Phase1 and Phase2 interfaces on FortiGate devices.
Supports creating, updating, listing, getting, and deleting IPsec tunnels.

Canonical ID: org.ulysses.noc.fortigate-ipsec/1.0.0
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
        Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"),
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


# ============== PHASE1 FUNCTIONS ==============

def list_phase1(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all Phase1 interfaces."""
    result = api_request(host, api_token, "GET", "/cmdb/vpn.ipsec/phase1-interface", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get Phase1 interfaces")}

    data = result.get("data", {})
    tunnels_raw = data.get("results", [])

    tunnels = []
    for t in tunnels_raw:
        tunnels.append({
            "name": t.get("name"),
            "type": t.get("type", "static"),
            "interface": t.get("interface", ""),
            "remote-gw": t.get("remote-gw", "0.0.0.0"),
            "ike-version": t.get("ike-version", 2),
            "mode-cfg": t.get("mode-cfg", "disable"),
            "net-device": t.get("net-device", "disable"),
            "add-route": t.get("add-route", "enable"),
            "dpd": t.get("dpd", "on-demand"),
            "network-overlay": t.get("network-overlay", "disable"),
            "network-id": t.get("network-id", 0),
        })

    return {
        "success": True,
        "count": len(tunnels),
        "phase1_interfaces": tunnels
    }


def get_phase1(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get a specific Phase1 interface by name."""
    result = api_request(host, api_token, "GET", f"/cmdb/vpn.ipsec/phase1-interface/{name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Phase1 interface '{name}' not found"}

    data = result.get("data", {})
    if "results" in data:
        if isinstance(data["results"], list) and len(data["results"]) > 0:
            tunnel = data["results"][0]
        elif isinstance(data["results"], dict):
            tunnel = data["results"]
        else:
            return {"success": False, "error": f"Phase1 interface '{name}' not found"}
    else:
        tunnel = data

    return {
        "success": True,
        "phase1": {
            "name": tunnel.get("name"),
            "type": tunnel.get("type", "static"),
            "interface": tunnel.get("interface", ""),
            "remote-gw": tunnel.get("remote-gw", "0.0.0.0"),
            "ike-version": tunnel.get("ike-version", 2),
            "mode-cfg": tunnel.get("mode-cfg", "disable"),
            "net-device": tunnel.get("net-device", "disable"),
            "add-route": tunnel.get("add-route", "enable"),
            "dpd": tunnel.get("dpd", "on-demand"),
            "dpd-retrycount": tunnel.get("dpd-retrycount", 3),
            "dpd-retryinterval": tunnel.get("dpd-retryinterval", 20),
            "network-overlay": tunnel.get("network-overlay", "disable"),
            "network-id": tunnel.get("network-id", 0),
            "exchange-ip-addr4": tunnel.get("exchange-ip-addr4", "0.0.0.0"),
            "auto-discovery-receiver": tunnel.get("auto-discovery-receiver", "disable"),
            "auto-discovery-sender": tunnel.get("auto-discovery-sender", "disable"),
            "proposal": tunnel.get("proposal", []),
            "dhgrp": tunnel.get("dhgrp", ""),
            "localid": tunnel.get("localid", ""),
            "transport": tunnel.get("transport", ""),
        }
    }


def add_phase1(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create a new Phase1 interface."""
    name = params.get("name")
    interface = params.get("interface")
    remote_gw = params.get("remote_gw", "0.0.0.0")
    psksecret = params.get("psksecret")

    # Validation
    if not name:
        return {"success": False, "error": "name is required"}
    if not interface:
        return {"success": False, "error": "interface is required"}
    if not psksecret:
        return {"success": False, "error": "psksecret is required"}

    # Check if exists
    existing = get_phase1(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Phase1 interface '{name}' already exists"}

    # Build Phase1 data
    phase1_data = {
        "name": name,
        "interface": interface,
        "remote-gw": remote_gw,
        "psksecret": psksecret,
        "ike-version": params.get("ike_version", 2),
    }

    # Optional parameters
    if "type" in params:
        phase1_data["type"] = params["type"]  # static or dynamic

    if "mode_cfg" in params:
        phase1_data["mode-cfg"] = params["mode_cfg"]

    if "net_device" in params:
        phase1_data["net-device"] = params["net_device"]

    if "add_route" in params:
        phase1_data["add-route"] = params["add_route"]

    if "dpd" in params:
        phase1_data["dpd"] = params["dpd"]

    if "dpd_retrycount" in params:
        phase1_data["dpd-retrycount"] = int(params["dpd_retrycount"])

    if "dpd_retryinterval" in params:
        phase1_data["dpd-retryinterval"] = int(params["dpd_retryinterval"])

    # SD-WAN/ADVPN parameters
    if "network_overlay" in params:
        phase1_data["network-overlay"] = params["network_overlay"]

    if "network_id" in params:
        phase1_data["network-id"] = int(params["network_id"])

    if "exchange_ip_addr4" in params:
        phase1_data["exchange-ip-addr4"] = params["exchange_ip_addr4"]

    if "auto_discovery_receiver" in params:
        phase1_data["auto-discovery-receiver"] = params["auto_discovery_receiver"]

    if "auto_discovery_sender" in params:
        phase1_data["auto-discovery-sender"] = params["auto_discovery_sender"]

    # Local ID for IKE identification
    if "localid" in params:
        phase1_data["localid"] = params["localid"]

    # Transport protocol - CRITICAL: default to UDP to avoid conflict with HTTPS port 443
    # When set to "auto", FortiGate defaults to TCP which blocks the management API
    transport = params.get("transport", "udp")
    phase1_data["transport"] = transport

    # Encryption proposals
    if "proposal" in params:
        proposals = params["proposal"]
        if isinstance(proposals, str):
            proposals = [p.strip() for p in proposals.split(",")]
        phase1_data["proposal"] = proposals

    if "dhgrp" in params:
        phase1_data["dhgrp"] = params["dhgrp"]

    # Create Phase1
    result = api_request(host, api_token, "POST", "/cmdb/vpn.ipsec/phase1-interface", data=phase1_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "type": params.get("type", "static"),
            "message": f"Created Phase1 interface '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to create Phase1: {error_msg}", "details": result}


def update_phase1(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update an existing Phase1 interface."""
    name = params.get("name")

    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_phase1(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Phase1 interface '{name}' not found"}

    update_data = {}

    # Map parameter names (underscore to hyphen)
    param_map = {
        "remote_gw": "remote-gw",
        "ike_version": "ike-version",
        "mode_cfg": "mode-cfg",
        "net_device": "net-device",
        "add_route": "add-route",
        "dpd_retrycount": "dpd-retrycount",
        "dpd_retryinterval": "dpd-retryinterval",
        "network_overlay": "network-overlay",
        "network_id": "network-id",
        "exchange_ip_addr4": "exchange-ip-addr4",
        "auto_discovery_receiver": "auto-discovery-receiver",
        "auto_discovery_sender": "auto-discovery-sender",
        "localid": "localid",
        "transport": "transport",
    }

    for param_name, api_name in param_map.items():
        if param_name in params:
            update_data[api_name] = params[param_name]

    # Direct mappings
    for key in ["interface", "psksecret", "dpd", "proposal", "dhgrp", "type"]:
        if key in params:
            update_data[key] = params[key]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    result = api_request(host, api_token, "PUT", f"/cmdb/vpn.ipsec/phase1-interface/{name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "updated_fields": list(update_data.keys()),
            "message": f"Updated Phase1 interface '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to update Phase1: {error_msg}", "details": result}


def remove_phase1(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete a Phase1 interface."""
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_phase1(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Phase1 interface '{name}' not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/vpn.ipsec/phase1-interface/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "name": name,
            "message": f"Deleted Phase1 interface '{name}'"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        return {"success": False, "error": f"Failed to delete Phase1: {error_msg}", "details": result}


# ============== PHASE2 FUNCTIONS ==============

def list_phase2(host: str, api_token: str, phase1_name: str = None, verify_ssl: bool = False) -> dict:
    """List all Phase2 interfaces, optionally filtered by Phase1 name."""
    result = api_request(host, api_token, "GET", "/cmdb/vpn.ipsec/phase2-interface", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get Phase2 interfaces")}

    data = result.get("data", {})
    tunnels_raw = data.get("results", [])

    tunnels = []
    for t in tunnels_raw:
        if phase1_name and t.get("phase1name") != phase1_name:
            continue
        tunnels.append({
            "name": t.get("name"),
            "phase1name": t.get("phase1name", ""),
            "src-addr-type": t.get("src-addr-type", "subnet"),
            "dst-addr-type": t.get("dst-addr-type", "subnet"),
            "src-subnet": t.get("src-subnet", ""),
            "dst-subnet": t.get("dst-subnet", ""),
            "auto-negotiate": t.get("auto-negotiate", "enable"),
        })

    return {
        "success": True,
        "count": len(tunnels),
        "phase2_interfaces": tunnels
    }


def get_phase2(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get a specific Phase2 interface by name."""
    result = api_request(host, api_token, "GET", f"/cmdb/vpn.ipsec/phase2-interface/{name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Phase2 interface '{name}' not found"}

    data = result.get("data", {})
    if "results" in data:
        if isinstance(data["results"], list) and len(data["results"]) > 0:
            tunnel = data["results"][0]
        elif isinstance(data["results"], dict):
            tunnel = data["results"]
        else:
            return {"success": False, "error": f"Phase2 interface '{name}' not found"}
    else:
        tunnel = data

    return {
        "success": True,
        "phase2": {
            "name": tunnel.get("name"),
            "phase1name": tunnel.get("phase1name", ""),
            "src-addr-type": tunnel.get("src-addr-type", "subnet"),
            "dst-addr-type": tunnel.get("dst-addr-type", "subnet"),
            "src-subnet": tunnel.get("src-subnet", ""),
            "dst-subnet": tunnel.get("dst-subnet", ""),
            "auto-negotiate": tunnel.get("auto-negotiate", "enable"),
            "proposal": tunnel.get("proposal", []),
            "dhgrp": tunnel.get("dhgrp", ""),
            "pfs": tunnel.get("pfs", "enable"),
            "keylifeseconds": tunnel.get("keylifeseconds", 43200),
        }
    }


def add_phase2(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create a new Phase2 interface."""
    name = params.get("name")
    phase1name = params.get("phase1name")

    if not name:
        return {"success": False, "error": "name is required"}
    if not phase1name:
        return {"success": False, "error": "phase1name is required"}

    # Verify Phase1 exists
    phase1_check = get_phase1(host, api_token, phase1name, verify_ssl)
    if not phase1_check.get("success"):
        return {"success": False, "error": f"Phase1 interface '{phase1name}' not found"}

    # Check if Phase2 exists
    existing = get_phase2(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Phase2 interface '{name}' already exists"}

    # Build Phase2 data
    phase2_data = {
        "name": name,
        "phase1name": phase1name,
    }

    # Traffic selectors
    if "src_subnet" in params:
        phase2_data["src-subnet"] = params["src_subnet"]
        phase2_data["src-addr-type"] = "subnet"

    if "dst_subnet" in params:
        phase2_data["dst-subnet"] = params["dst_subnet"]
        phase2_data["dst-addr-type"] = "subnet"

    # Optional parameters
    if "auto_negotiate" in params:
        phase2_data["auto-negotiate"] = params["auto_negotiate"]

    if "proposal" in params:
        proposals = params["proposal"]
        if isinstance(proposals, str):
            proposals = [p.strip() for p in proposals.split(",")]
        phase2_data["proposal"] = proposals

    if "dhgrp" in params:
        phase2_data["dhgrp"] = params["dhgrp"]

    if "pfs" in params:
        phase2_data["pfs"] = params["pfs"]

    if "keylifeseconds" in params:
        phase2_data["keylifeseconds"] = int(params["keylifeseconds"])

    # Create Phase2
    result = api_request(host, api_token, "POST", "/cmdb/vpn.ipsec/phase2-interface", data=phase2_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "phase1name": phase1name,
            "message": f"Created Phase2 interface '{name}' for Phase1 '{phase1name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to create Phase2: {error_msg}", "details": result}


def update_phase2(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update an existing Phase2 interface."""
    name = params.get("name")

    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_phase2(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Phase2 interface '{name}' not found"}

    update_data = {}

    param_map = {
        "src_subnet": "src-subnet",
        "dst_subnet": "dst-subnet",
        "auto_negotiate": "auto-negotiate",
    }

    for param_name, api_name in param_map.items():
        if param_name in params:
            update_data[api_name] = params[param_name]

    for key in ["proposal", "dhgrp", "pfs", "keylifeseconds"]:
        if key in params:
            update_data[key] = params[key]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    result = api_request(host, api_token, "PUT", f"/cmdb/vpn.ipsec/phase2-interface/{name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "updated_fields": list(update_data.keys()),
            "message": f"Updated Phase2 interface '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to update Phase2: {error_msg}", "details": result}


def remove_phase2(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete a Phase2 interface."""
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_phase2(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Phase2 interface '{name}' not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/vpn.ipsec/phase2-interface/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "name": name,
            "message": f"Deleted Phase2 interface '{name}'"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        return {"success": False, "error": f"Failed to delete Phase2: {error_msg}", "details": result}


# ============== MAIN ==============

def main(context) -> dict[str, Any]:
    """Main entry point for the tool."""
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "").lower()
    phase = params.get("phase", "1")  # Default to Phase1
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    valid_actions = ["add", "update", "remove", "list", "get"]
    if action not in valid_actions:
        return {"success": False, "error": f"Invalid action: {action}. Must be one of: {valid_actions}"}

    # Normalize phase
    phase = str(phase)
    if phase not in ["1", "2"]:
        return {"success": False, "error": "phase must be '1' or '2'"}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    result = {"action": action, "target_ip": target_ip, "phase": phase}

    if phase == "1":
        if action == "list":
            list_result = list_phase1(target_ip, api_token, verify_ssl)
            result.update(list_result)
            if list_result["success"]:
                result["message"] = f"Found {list_result['count']} Phase1 interfaces"

        elif action == "get":
            name = params.get("name")
            if not name:
                return {"success": False, "error": "name is required for 'get' action"}
            get_result = get_phase1(target_ip, api_token, name, verify_ssl)
            result.update(get_result)

        elif action == "add":
            add_result = add_phase1(target_ip, api_token, params, verify_ssl)
            result.update(add_result)

        elif action == "update":
            update_result = update_phase1(target_ip, api_token, params, verify_ssl)
            result.update(update_result)

        elif action == "remove":
            name = params.get("name")
            remove_result = remove_phase1(target_ip, api_token, name, verify_ssl)
            result.update(remove_result)

    else:  # Phase 2
        if action == "list":
            phase1_filter = params.get("phase1name")
            list_result = list_phase2(target_ip, api_token, phase1_filter, verify_ssl)
            result.update(list_result)
            if list_result["success"]:
                filter_msg = f" for Phase1 '{phase1_filter}'" if phase1_filter else ""
                result["message"] = f"Found {list_result['count']} Phase2 interfaces{filter_msg}"

        elif action == "get":
            name = params.get("name")
            if not name:
                return {"success": False, "error": "name is required for 'get' action"}
            get_result = get_phase2(target_ip, api_token, name, verify_ssl)
            result.update(get_result)

        elif action == "add":
            add_result = add_phase2(target_ip, api_token, params, verify_ssl)
            result.update(add_result)

        elif action == "update":
            update_result = update_phase2(target_ip, api_token, params, verify_ssl)
            result.update(update_result)

        elif action == "remove":
            name = params.get("name")
            remove_result = remove_phase2(target_ip, api_token, name, verify_ssl)
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
                elif ',' in val:
                    val = [v.strip() for v in val.split(',')]
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
