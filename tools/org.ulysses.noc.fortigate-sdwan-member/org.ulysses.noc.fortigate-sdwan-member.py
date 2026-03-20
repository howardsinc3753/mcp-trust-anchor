#!/usr/bin/env python3
"""
FortiGate SD-WAN Member Tool

CRUD operations for SD-WAN members on FortiGate devices.
Configure overlay members with priority settings.

Canonical ID: org.ulysses.noc.fortigate-sdwan-member/1.0.3
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


def list_members(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all SD-WAN members."""
    result = api_request(host, api_token, "GET", "/cmdb/system/sdwan/members", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get members")}

    data = result.get("data", {})
    members_raw = data.get("results", [])

    members = []
    for m in members_raw:
        members.append({
            "seq_num": m.get("seq-num"),
            "interface": m.get("interface"),
            "zone": m.get("zone"),
            "source": m.get("source"),
            "gateway": m.get("gateway"),
            "priority_in_sla": m.get("priority-in-sla"),
            "priority_out_sla": m.get("priority-out-sla"),
            "cost": m.get("cost"),
            "status": m.get("status")
        })

    return {"success": True, "count": len(members), "members": members}


def get_member(host: str, api_token: str, seq_num: int, verify_ssl: bool = False) -> dict:
    """Get specific SD-WAN member."""
    result = api_request(host, api_token, "GET", f"/cmdb/system/sdwan/members/{seq_num}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Member {seq_num} not found"}

    data = result.get("data", {})
    results = data.get("results", [])
    if isinstance(results, list) and len(results) > 0:
        m = results[0]
    elif isinstance(results, dict):
        m = results
    else:
        return {"success": False, "error": f"Member {seq_num} not found"}

    return {
        "success": True,
        "member": {
            "seq_num": m.get("seq-num"),
            "interface": m.get("interface"),
            "zone": m.get("zone"),
            "source": m.get("source"),
            "gateway": m.get("gateway"),
            "priority_in_sla": m.get("priority-in-sla"),
            "priority_out_sla": m.get("priority-out-sla"),
            "cost": m.get("cost"),
            "status": m.get("status")
        }
    }


def add_member(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Add SD-WAN member."""
    seq_num = params.get("seq_num")
    interface = params.get("interface")

    if not seq_num:
        return {"success": False, "error": "seq_num is required"}
    if not interface:
        return {"success": False, "error": "interface is required for add"}

    member_data = {
        "seq-num": seq_num,
        "interface": interface
    }

    # Optional fields
    if params.get("zone"):
        member_data["zone"] = params["zone"]
    if params.get("source"):
        member_data["source"] = params["source"]
    if params.get("gateway"):
        member_data["gateway"] = params["gateway"]
    if params.get("priority_in_sla") is not None:
        member_data["priority-in-sla"] = params["priority_in_sla"]
    if params.get("priority_out_sla") is not None:
        member_data["priority-out-sla"] = params["priority_out_sla"]
    if params.get("cost") is not None:
        member_data["cost"] = params["cost"]

    result = api_request(host, api_token, "POST", "/cmdb/system/sdwan/members", data=member_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "seq_num": seq_num,
            "interface": interface,
            "message": f"Added member {seq_num} ({interface})"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = str(cli_error)
        return {"success": False, "error": f"Failed to add member: {error_msg}", "details": result}


def update_member(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update SD-WAN member."""
    seq_num = params.get("seq_num")

    if not seq_num:
        return {"success": False, "error": "seq_num is required"}

    # Get existing member first
    existing = get_member(host, api_token, seq_num, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Member {seq_num} not found"}

    member_data = {}

    # Update only provided fields
    if params.get("zone"):
        member_data["zone"] = params["zone"]
    if params.get("source"):
        member_data["source"] = params["source"]
    if params.get("gateway"):
        member_data["gateway"] = params["gateway"]
    if params.get("priority_in_sla") is not None:
        member_data["priority-in-sla"] = params["priority_in_sla"]
    if params.get("priority_out_sla") is not None:
        member_data["priority-out-sla"] = params["priority_out_sla"]
    if params.get("cost") is not None:
        member_data["cost"] = params["cost"]

    if not member_data:
        return {"success": False, "error": "No fields to update"}

    result = api_request(host, api_token, "PUT", f"/cmdb/system/sdwan/members/{seq_num}", data=member_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "seq_num": seq_num,
            "updated_fields": list(member_data.keys()),
            "message": f"Updated member {seq_num}"
        }
    else:
        error_msg = result.get("error", "")
        return {"success": False, "error": f"Failed to update member: {error_msg}", "details": result}


def remove_member(host: str, api_token: str, seq_num: int, verify_ssl: bool = False) -> dict:
    """Remove SD-WAN member."""
    # Check if exists
    existing = get_member(host, api_token, seq_num, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Member {seq_num} not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/system/sdwan/members/{seq_num}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "seq_num": seq_num,
            "message": f"Removed member {seq_num}"
        }
    else:
        return {"success": False, "error": f"Failed to remove member: {result.get('error', '')}", "details": result}


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
        list_result = list_members(target_ip, api_token, verify_ssl)
        result.update(list_result)
        if list_result["success"]:
            result["message"] = f"Found {list_result['count']} SD-WAN members"

    elif action == "get":
        seq_num = params.get("seq_num")
        if not seq_num:
            return {"success": False, "error": "seq_num is required for get"}
        get_result = get_member(target_ip, api_token, seq_num, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_member(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "update":
        update_result = update_member(target_ip, api_token, params, verify_ssl)
        result.update(update_result)

    elif action == "remove":
        seq_num = params.get("seq_num")
        if not seq_num:
            return {"success": False, "error": "seq_num is required for remove"}
        remove_result = remove_member(target_ip, api_token, seq_num, verify_ssl)
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
