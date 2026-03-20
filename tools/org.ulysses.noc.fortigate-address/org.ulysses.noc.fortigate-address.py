#!/usr/bin/env python3
"""
FortiGate Address Tool

CRUD operations for firewall address objects on FortiGate devices.

Canonical ID: org.ulysses.noc.fortigate-address/1.0.0
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
        Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"),
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

    if os.name == 'nt':
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
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


def list_addresses(host: str, api_token: str, verify_ssl: bool = False,
                   addr_type: str = None) -> dict:
    """List all firewall address objects."""
    result = api_request(host, api_token, "GET", "/cmdb/firewall/address", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get addresses")}

    data = result.get("data", {})
    addresses_raw = data.get("results", [])

    addresses = []
    for a in addresses_raw:
        a_type = a.get("type", "ipmask")

        # Filter by type if specified
        if addr_type and a_type != addr_type:
            continue

        addr = {
            "name": a.get("name"),
            "type": a_type,
            "comment": a.get("comment", ""),
        }

        # Add type-specific fields
        if a_type == "ipmask":
            addr["subnet"] = a.get("subnet", "")
        elif a_type == "iprange":
            addr["start-ip"] = a.get("start-ip", "")
            addr["end-ip"] = a.get("end-ip", "")
        elif a_type == "fqdn":
            addr["fqdn"] = a.get("fqdn", "")
        elif a_type == "geography":
            addr["country"] = a.get("country", "")

        addresses.append(addr)

    return {
        "success": True,
        "count": len(addresses),
        "addresses": addresses
    }


def get_address(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get a specific firewall address by name."""
    from urllib.parse import quote
    encoded_name = quote(name, safe="")

    result = api_request(host, api_token, "GET", f"/cmdb/firewall/address/{encoded_name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Address '{name}' not found"}

    data = result.get("data", {})
    if "results" in data:
        if isinstance(data["results"], list) and len(data["results"]) > 0:
            addr = data["results"][0]
        elif isinstance(data["results"], dict):
            addr = data["results"]
        else:
            return {"success": False, "error": f"Address '{name}' not found"}
    else:
        addr = data

    return {
        "success": True,
        "address": {
            "name": addr.get("name"),
            "type": addr.get("type", "ipmask"),
            "subnet": addr.get("subnet", ""),
            "start-ip": addr.get("start-ip", ""),
            "end-ip": addr.get("end-ip", ""),
            "fqdn": addr.get("fqdn", ""),
            "country": addr.get("country", ""),
            "comment": addr.get("comment", ""),
            "associated-interface": addr.get("associated-interface", ""),
            "allow-routing": addr.get("allow-routing", "disable"),
        }
    }


def add_address(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create a new firewall address object."""
    name = params.get("name")
    addr_type = params.get("type", "ipmask")

    if not name:
        return {"success": False, "error": "name is required"}

    # Check if exists
    existing = get_address(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Address '{name}' already exists"}

    addr_data = {
        "name": name,
        "type": addr_type,
    }

    # Type-specific required fields
    if addr_type == "ipmask":
        subnet = params.get("subnet")
        if not subnet:
            return {"success": False, "error": "subnet is required for ipmask type"}
        addr_data["subnet"] = subnet

    elif addr_type == "iprange":
        start_ip = params.get("start_ip")
        end_ip = params.get("end_ip")
        if not start_ip or not end_ip:
            return {"success": False, "error": "start_ip and end_ip required for iprange type"}
        addr_data["start-ip"] = start_ip
        addr_data["end-ip"] = end_ip

    elif addr_type == "fqdn":
        fqdn = params.get("fqdn")
        if not fqdn:
            return {"success": False, "error": "fqdn is required for fqdn type"}
        addr_data["fqdn"] = fqdn

    elif addr_type == "geography":
        country = params.get("country")
        if not country:
            return {"success": False, "error": "country is required for geography type"}
        addr_data["country"] = country

    # Optional fields
    if "comment" in params:
        addr_data["comment"] = params["comment"]

    if "associated_interface" in params:
        addr_data["associated-interface"] = params["associated_interface"]

    if "allow_routing" in params:
        addr_data["allow-routing"] = params["allow_routing"]

    result = api_request(host, api_token, "POST", "/cmdb/firewall/address", data=addr_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "type": addr_type,
            "message": f"Created {addr_type} address '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to create address: {error_msg}", "details": result}


def update_address(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update an existing firewall address."""
    name = params.get("name")

    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_address(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Address '{name}' not found"}

    update_data = {}

    param_map = {
        "start_ip": "start-ip",
        "end_ip": "end-ip",
        "associated_interface": "associated-interface",
        "allow_routing": "allow-routing",
    }

    for param_name, api_name in param_map.items():
        if param_name in params:
            update_data[api_name] = params[param_name]

    for key in ["subnet", "fqdn", "country", "comment"]:
        if key in params:
            update_data[key] = params[key]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    from urllib.parse import quote
    encoded_name = quote(name, safe="")

    result = api_request(host, api_token, "PUT", f"/cmdb/firewall/address/{encoded_name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "updated_fields": list(update_data.keys()),
            "message": f"Updated address '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to update address: {error_msg}", "details": result}


def remove_address(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete a firewall address object."""
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_address(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Address '{name}' not found"}

    from urllib.parse import quote
    encoded_name = quote(name, safe="")

    result = api_request(host, api_token, "DELETE", f"/cmdb/firewall/address/{encoded_name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "name": name,
            "message": f"Deleted address '{name}'"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        # Check if in use
        if "entry is used" in str(result.get("data", {})):
            error_msg = f"Address '{name}' is in use by a policy. Remove from policies first."
        return {"success": False, "error": f"Failed to delete address: {error_msg}", "details": result}


def main(context) -> dict[str, Any]:
    """Main entry point for the tool."""
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    valid_actions = ["add", "update", "remove", "list", "get"]
    if action not in valid_actions:
        return {"success": False, "error": f"Invalid action: {action}. Must be one of: {valid_actions}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        addr_type = params.get("type")
        list_result = list_addresses(target_ip, api_token, verify_ssl, addr_type)
        result.update(list_result)
        if list_result["success"]:
            type_filter = f" (type={addr_type})" if addr_type else ""
            result["message"] = f"Found {list_result['count']} addresses{type_filter}"

    elif action == "get":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for 'get' action"}
        get_result = get_address(target_ip, api_token, name, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_address(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "update":
        update_result = update_address(target_ip, api_token, params, verify_ssl)
        result.update(update_result)

    elif action == "remove":
        name = params.get("name")
        remove_result = remove_address(target_ip, api_token, name, verify_ssl)
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
