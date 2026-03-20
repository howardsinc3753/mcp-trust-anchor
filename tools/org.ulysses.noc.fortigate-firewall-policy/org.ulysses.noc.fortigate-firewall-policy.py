#!/usr/bin/env python3
"""
FortiGate Firewall Policy Tool

CRUD operations for firewall policies on FortiGate devices.
Supports creating, deleting, listing, and getting policy details.

Canonical ID: org.ulysses.noc.fortigate-firewall-policy/1.0.2
"""

import json
import sys
import os
import urllib3
from typing import Optional, List
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


def list_policies(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all firewall policies."""
    result = api_request(host, api_token, "GET", "/cmdb/firewall/policy", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get policies")}

    data = result.get("data", {})
    policies_raw = data.get("results", [])

    policies = []
    for p in policies_raw:
        policies.append({
            "policyid": p.get("policyid"),
            "name": p.get("name", ""),
            "srcintf": [i.get("name") for i in p.get("srcintf", [])],
            "dstintf": [i.get("name") for i in p.get("dstintf", [])],
            "srcaddr": [a.get("name") for a in p.get("srcaddr", [])],
            "dstaddr": [a.get("name") for a in p.get("dstaddr", [])],
            "service": [s.get("name") for s in p.get("service", [])],
            "action": p.get("action", ""),
            "status": p.get("status", ""),
            "nat": p.get("nat", "disable"),
            "logtraffic": p.get("logtraffic", "")
        })

    return {
        "success": True,
        "count": len(policies),
        "policies": policies
    }


def get_policy(host: str, api_token: str, policy_id: int, verify_ssl: bool = False) -> dict:
    """Get a specific firewall policy by ID."""
    result = api_request(host, api_token, "GET", f"/cmdb/firewall/policy/{policy_id}", verify_ssl=verify_ssl)

    if not result.get("success"):
        return {"success": False, "error": f"Policy ID {policy_id} not found"}

    data = result.get("data", {})
    # Handle both list and dict responses
    if "results" in data:
        if isinstance(data["results"], list) and len(data["results"]) > 0:
            policy = data["results"][0]
        elif isinstance(data["results"], dict):
            policy = data["results"]
        else:
            return {"success": False, "error": f"Policy ID {policy_id} not found"}
    else:
        policy = data

    return {
        "success": True,
        "policy": {
            "policyid": policy.get("policyid"),
            "name": policy.get("name", ""),
            "srcintf": [i.get("name") for i in policy.get("srcintf", [])],
            "dstintf": [i.get("name") for i in policy.get("dstintf", [])],
            "srcaddr": [a.get("name") for a in policy.get("srcaddr", [])],
            "dstaddr": [a.get("name") for a in policy.get("dstaddr", [])],
            "service": [s.get("name") for s in policy.get("service", [])],
            "action": policy.get("action", ""),
            "status": policy.get("status", ""),
            "nat": policy.get("nat", "disable"),
            "logtraffic": policy.get("logtraffic", ""),
            "utm-status": policy.get("utm-status", "disable"),
            "ips-sensor": policy.get("ips-sensor", ""),
            "av-profile": policy.get("av-profile", ""),
            "webfilter-profile": policy.get("webfilter-profile", ""),
            "ssl-ssh-profile": policy.get("ssl-ssh-profile", "")
        }
    }


def find_policy_by_name(host: str, api_token: str, name: str, verify_ssl: bool = False) -> Optional[int]:
    """Find policy ID by name."""
    result = list_policies(host, api_token, verify_ssl)
    if not result.get("success"):
        return None

    for p in result.get("policies", []):
        if p.get("name") == name:
            return p.get("policyid")

    return None


def ensure_list(val, default=None):
    """Ensure value is a list. Convert string to single-item list."""
    if val is None:
        return default if default else []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return [val]


def add_policy(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Add a new firewall policy."""
    name = params.get("name")
    srcintf = ensure_list(params.get("srcintf"))
    dstintf = ensure_list(params.get("dstintf"))
    srcaddr = ensure_list(params.get("srcaddr"), ["all"])
    dstaddr = ensure_list(params.get("dstaddr"), ["all"])
    service = ensure_list(params.get("service"), ["ALL"])
    schedule = params.get("schedule", "always")
    action = params.get("policy_action", "accept")
    nat = params.get("nat", False)
    logtraffic = params.get("logtraffic", "all")
    position = params.get("position", "top")

    # UTM options
    utm_status = params.get("utm_status", False)
    ips_sensor = params.get("ips_sensor")
    av_profile = params.get("av_profile")
    webfilter_profile = params.get("webfilter_profile")
    ssl_ssh_profile = params.get("ssl_ssh_profile")

    # Validation
    if not name:
        return {"success": False, "error": "name is required"}
    if not srcintf:
        return {"success": False, "error": "srcintf is required"}
    if not dstintf:
        return {"success": False, "error": "dstintf is required"}

    # Check if policy name already exists
    existing_id = find_policy_by_name(host, api_token, name, verify_ssl)
    if existing_id:
        return {"success": False, "error": f"Policy '{name}' already exists with ID {existing_id}"}

    # Build policy data
    policy_data = {
        "name": name,
        "srcintf": [{"name": i} for i in srcintf],
        "dstintf": [{"name": i} for i in dstintf],
        "srcaddr": [{"name": a} for a in srcaddr],
        "dstaddr": [{"name": a} for a in dstaddr],
        "service": [{"name": s} for s in service],
        "schedule": schedule,
        "action": action,
        "nat": "enable" if nat else "disable",
        "logtraffic": logtraffic,
        "status": "enable"
    }

    # Position: edit 0 for top, no policyid for bottom (append)
    if position == "top":
        policy_data["policyid"] = 0

    # UTM profiles
    if utm_status:
        policy_data["utm-status"] = "enable"
        if ips_sensor:
            policy_data["ips-sensor"] = ips_sensor
        if av_profile:
            policy_data["av-profile"] = av_profile
        if webfilter_profile:
            policy_data["webfilter-profile"] = webfilter_profile
        if ssl_ssh_profile:
            policy_data["ssl-ssh-profile"] = ssl_ssh_profile

    # Create policy
    result = api_request(host, api_token, "POST", "/cmdb/firewall/policy", data=policy_data, verify_ssl=verify_ssl)

    if result.get("success"):
        # Get the created policy ID from response
        resp_data = result.get("data", {})
        new_id = resp_data.get("mkey")

        # If mkey not in response, find by name
        if not new_id:
            new_id = find_policy_by_name(host, api_token, name, verify_ssl)

        position_text = "top" if position == "top" else "bottom"
        return {
            "success": True,
            "policy_id": new_id,
            "name": name,
            "message": f"Created policy '{name}' with ID {new_id} at {position_text} of list"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = cli_error
        return {"success": False, "error": f"Failed to create policy: {error_msg}", "details": result}


def remove_policy(host: str, api_token: str, policy_id: int = None, name: str = None, verify_ssl: bool = False) -> dict:
    """Remove a firewall policy by ID or name."""
    target_id = policy_id
    target_name = name

    if not target_id and name:
        target_id = find_policy_by_name(host, api_token, name, verify_ssl)
        if not target_id:
            return {"success": False, "error": f"Policy '{name}' not found"}
        target_name = name
    elif target_id and not target_name:
        # Get name for reporting
        policy_result = get_policy(host, api_token, target_id, verify_ssl)
        if policy_result.get("success"):
            target_name = policy_result["policy"].get("name", f"ID:{target_id}")
    elif not target_id and not name:
        return {"success": False, "error": "Must specify policy_id or name"}

    # Delete policy
    result = api_request(host, api_token, "DELETE", f"/cmdb/firewall/policy/{target_id}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "policy_id": target_id,
            "name": target_name,
            "message": f"Deleted policy '{target_name}' (ID: {target_id})"
        }
    else:
        error_msg = result.get("error", "Unknown error")
        return {"success": False, "error": f"Failed to delete policy: {error_msg}", "details": result}


def main(context) -> dict:
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

    if action not in ["add", "remove", "list", "get"]:
        return {"success": False, "error": f"Invalid action: {action}. Must be 'add', 'remove', 'list', or 'get'"}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    # Execute action
    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        list_result = list_policies(target_ip, api_token, verify_ssl)
        result.update(list_result)
        if list_result["success"]:
            result["message"] = f"Found {list_result['count']} firewall policies"

    elif action == "get":
        policy_id = params.get("policy_id")
        if not policy_id:
            return {"success": False, "error": "policy_id is required for 'get' action"}
        get_result = get_policy(target_ip, api_token, policy_id, verify_ssl)
        result.update(get_result)

    elif action == "add":
        add_result = add_policy(target_ip, api_token, params, verify_ssl)
        result.update(add_result)

    elif action == "remove":
        policy_id = params.get("policy_id")
        name = params.get("name")
        remove_result = remove_policy(target_ip, api_token, policy_id, name, verify_ssl)
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
