#!/usr/bin/env python3
"""
FortiGate Interface Tool

CRUD operations for interfaces on FortiGate devices.
Supports creating, updating, listing, getting, and deleting interfaces.

Canonical ID: org.ulysses.noc.fortigate-interface/1.0.0
"""

import json
import sys
import os
import urllib3
from typing import Optional, List, Any
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

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Valid interface types that can be created
CREATABLE_TYPES = ["loopback", "vlan", "aggregate", "redundant", "tunnel"]

# Valid allowaccess options
VALID_ALLOWACCESS = [
    "ping", "https", "ssh", "http", "fgfm", "fabric", "snmp",
    "telnet", "radius-acct", "probe-response", "ftm", "speed-test"
]


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from local config file."""
    config_paths = [
        # PRIMARY: Production path
        Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml"),
        # User config (MCP server checks this)
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

    # Platform-specific paths
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


def list_interfaces(host: str, api_token: str, verify_ssl: bool = False,
                    interface_type: str = None) -> dict:
    """List all interfaces, optionally filtered by type."""
    result = api_request(host, api_token, "GET", "/cmdb/system/interface", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get interfaces")}

    data = result.get("data", {})
    interfaces_raw = data.get("results", [])

    interfaces = []
    for iface in interfaces_raw:
        iface_type = iface.get("type", "")

        # Filter by type if specified
        if interface_type and iface_type != interface_type:
            continue

        interfaces.append({
            "name": iface.get("name"),
            "type": iface_type,
            "ip": iface.get("ip", "0.0.0.0 0.0.0.0"),
            "status": iface.get("status", ""),
            "alias": iface.get("alias", ""),
            "role": iface.get("role", ""),
            "vlanid": iface.get("vlanid", 0) if iface_type == "vlan" else None,
            "interface": iface.get("interface", "") if iface_type == "vlan" else None,
            "allowaccess": iface.get("allowaccess", ""),
            "vdom": iface.get("vdom", "root"),
            "mode": iface.get("mode", "static"),
        })

    return {
        "success": True,
        "count": len(interfaces),
        "interfaces": interfaces
    }


def get_interface(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get a specific interface by name."""
    result = api_request(host, api_token, "GET", f"/cmdb/system/interface/{name}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Interface '{name}' not found"}

    data = result.get("data", {})
    # Handle both list and dict responses
    if "results" in data:
        if isinstance(data["results"], list) and len(data["results"]) > 0:
            iface = data["results"][0]
        elif isinstance(data["results"], dict):
            iface = data["results"]
        else:
            return {"success": False, "error": f"Interface '{name}' not found"}
    else:
        iface = data

    return {
        "success": True,
        "interface": {
            "name": iface.get("name"),
            "type": iface.get("type", ""),
            "ip": iface.get("ip", "0.0.0.0 0.0.0.0"),
            "status": iface.get("status", "up"),
            "alias": iface.get("alias", ""),
            "description": iface.get("description", ""),
            "role": iface.get("role", ""),
            "vlanid": iface.get("vlanid", 0),
            "interface": iface.get("interface", ""),
            "allowaccess": iface.get("allowaccess", ""),
            "vdom": iface.get("vdom", "root"),
            "mode": iface.get("mode", "static"),
            "mtu": iface.get("mtu", 1500),
            "speed": iface.get("speed", "auto"),
            "mac-addr": iface.get("macaddr", ""),
        }
    }


def add_interface(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create a new interface (loopback, VLAN, aggregate, etc.)."""
    name = params.get("name")
    iface_type = params.get("type", "loopback")
    ip = params.get("ip")
    vlanid = params.get("vlanid")
    parent_interface = params.get("interface")  # For VLAN
    alias = params.get("alias", "")
    allowaccess = params.get("allowaccess", "")
    vdom = params.get("vdom", "root")
    role = params.get("role", "undefined")
    status = params.get("status", "up")

    # Validation
    if not name:
        return {"success": False, "error": "name is required"}

    if iface_type not in CREATABLE_TYPES:
        return {"success": False, "error": f"Cannot create interface type '{iface_type}'. Creatable types: {CREATABLE_TYPES}"}

    if iface_type == "vlan":
        if not vlanid:
            return {"success": False, "error": "vlanid is required for VLAN interfaces"}
        if not parent_interface:
            return {"success": False, "error": "interface (parent) is required for VLAN interfaces"}

    # Check if interface already exists
    existing = get_interface(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Interface '{name}' already exists"}

    # Build interface data
    interface_data = {
        "name": name,
        "type": iface_type,
        "vdom": vdom,
        "status": status,
        "role": role,
    }

    # Add IP if provided
    if ip:
        interface_data["ip"] = ip
        interface_data["mode"] = "static"

    # Add alias if provided
    if alias:
        interface_data["alias"] = alias

    # Add allowaccess if provided
    if allowaccess:
        # Validate allowaccess values
        if isinstance(allowaccess, list):
            allowaccess = " ".join(allowaccess)
        access_list = allowaccess.split()
        invalid = [a for a in access_list if a not in VALID_ALLOWACCESS]
        if invalid:
            return {"success": False, "error": f"Invalid allowaccess values: {invalid}. Valid: {VALID_ALLOWACCESS}"}
        interface_data["allowaccess"] = allowaccess

    # VLAN-specific settings
    if iface_type == "vlan":
        interface_data["vlanid"] = int(vlanid)
        interface_data["interface"] = parent_interface

    # Aggregate-specific settings
    if iface_type == "aggregate":
        member_interfaces = params.get("member", [])
        if isinstance(member_interfaces, str):
            member_interfaces = [m.strip() for m in member_interfaces.split(",")]
        if member_interfaces:
            interface_data["member"] = [{"interface-name": m} for m in member_interfaces]

    # Create interface
    result = api_request(host, api_token, "POST", "/cmdb/system/interface", data=interface_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "type": iface_type,
            "message": f"Created {iface_type} interface '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to create interface: {error_msg}", "details": result}


def update_interface(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update an existing interface."""
    name = params.get("name")

    if not name:
        return {"success": False, "error": "name is required"}

    # Verify interface exists
    existing = get_interface(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Interface '{name}' not found"}

    # Build update data - only include fields that are specified
    update_data = {}

    if "ip" in params:
        update_data["ip"] = params["ip"]
        update_data["mode"] = "static"

    if "alias" in params:
        update_data["alias"] = params["alias"]

    if "allowaccess" in params:
        allowaccess = params["allowaccess"]
        if isinstance(allowaccess, list):
            allowaccess = " ".join(allowaccess)
        # Validate allowaccess values
        access_list = allowaccess.split()
        invalid = [a for a in access_list if a not in VALID_ALLOWACCESS]
        if invalid:
            return {"success": False, "error": f"Invalid allowaccess values: {invalid}. Valid: {VALID_ALLOWACCESS}"}
        update_data["allowaccess"] = allowaccess

    if "status" in params:
        update_data["status"] = params["status"]

    if "role" in params:
        update_data["role"] = params["role"]

    if "mtu" in params:
        update_data["mtu"] = int(params["mtu"])

    if "description" in params:
        update_data["description"] = params["description"]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    # Update interface
    result = api_request(host, api_token, "PUT", f"/cmdb/system/interface/{name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "name": name,
            "updated_fields": list(update_data.keys()),
            "message": f"Updated interface '{name}'"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to update interface: {error_msg}", "details": result}


def remove_interface(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete an interface (only loopback, VLAN, aggregate types can be deleted)."""
    if not name:
        return {"success": False, "error": "name is required"}

    # Check if interface exists and get its type
    existing = get_interface(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Interface '{name}' not found"}

    iface_type = existing["interface"].get("type", "")

    # Prevent deletion of physical interfaces
    if iface_type in ["physical", "hard-switch"]:
        return {"success": False, "error": f"Cannot delete physical interface '{name}'. Physical interfaces cannot be removed."}

    # Delete interface
    result = api_request(host, api_token, "DELETE", f"/cmdb/system/interface/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "name": name,
            "type": iface_type,
            "message": f"Deleted {iface_type} interface '{name}'"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to delete interface: {error_msg}", "details": result}


def main(context) -> dict[str, Any]:
    """Main entry point for the tool."""
    # Handle both ExecutionContext (MCP) and dict (CLI)
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    action = params.get("action", "").lower()
    verify_ssl = params.get("verify_ssl", False)

    # Validate required params
    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["add", "update", "remove", "list", "get"]:
        return {"success": False, "error": f"Invalid action: {action}. Must be 'add', 'update', 'remove', 'list', or 'get'"}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    # Execute action
    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        interface_type = params.get("type")  # Optional filter
        list_result = list_interfaces(target_ip, api_token, verify_ssl, interface_type)
        result.update(list_result)
        if list_result["success"]:
            type_filter = f" (type={interface_type})" if interface_type else ""
            result["message"] = f"Found {list_result['count']} interfaces{type_filter}"

    elif action == "get":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for 'get' action"}
        get_result = get_interface(target_ip, api_token, name, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_interface(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "update":
        update_result = update_interface(target_ip, api_token, params, verify_ssl)
        result.update(update_result)

    elif action == "remove":
        name = params.get("name")
        remove_result = remove_interface(target_ip, api_token, name, verify_ssl)
        result.update(remove_result)

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        params = {}
        for arg in sys.argv[1:]:
            if '=' in arg:
                key, val = arg.split('=', 1)
                key = key.lstrip('-')
                # Handle boolean
                if val.lower() in ['true', 'false']:
                    val = val.lower() == 'true'
                # Handle integer
                elif val.isdigit():
                    val = int(val)
                # Handle lists (comma-separated)
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
