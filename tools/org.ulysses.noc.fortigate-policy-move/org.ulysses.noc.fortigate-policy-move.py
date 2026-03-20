#!/usr/bin/env python3
"""
FortiGate Policy Move Tool

Move firewall policies to reorder them on FortiGate devices.
Supports moving policies before or after a reference policy.

Canonical ID: org.ulysses.noc.fortigate-policy-move/1.0.0
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
        })

    return {"success": True, "policies": policies}


def find_policy_by_name(host: str, api_token: str, name: str, verify_ssl: bool = False) -> Optional[int]:
    """Find policy ID by name."""
    result = list_policies(host, api_token, verify_ssl)
    if not result.get("success"):
        return None

    for p in result.get("policies", []):
        if p.get("name") == name:
            return p.get("policyid")

    return None


def get_policy_name(host: str, api_token: str, policy_id: int, verify_ssl: bool = False) -> Optional[str]:
    """Get policy name by ID."""
    result = api_request(host, api_token, "GET", f"/cmdb/firewall/policy/{policy_id}", verify_ssl=verify_ssl)
    if not result.get("success"):
        return None

    data = result.get("data", {})
    results = data.get("results", [])
    if isinstance(results, list) and len(results) > 0:
        return results[0].get("name", "")
    elif isinstance(results, dict):
        return results.get("name", "")
    return None


def move_policy(host: str, api_token: str, policy_id: int, position: str,
                reference_id: int, verify_ssl: bool = False) -> dict:
    """Move a firewall policy before or after another policy.

    Uses FortiOS API: PUT /cmdb/firewall/policy/{id}?action=move&{before|after}={ref_id}
    """
    if position not in ["before", "after"]:
        return {"success": False, "error": f"Invalid position: {position}. Must be 'before' or 'after'"}

    # Verify source policy exists
    source_name = get_policy_name(host, api_token, policy_id, verify_ssl)
    if source_name is None:
        return {"success": False, "error": f"Policy ID {policy_id} not found"}

    # Verify reference policy exists
    ref_name = get_policy_name(host, api_token, reference_id, verify_ssl)
    if ref_name is None:
        return {"success": False, "error": f"Reference policy ID {reference_id} not found"}

    # Build move endpoint with action=move parameter
    endpoint = f"/cmdb/firewall/policy/{policy_id}?action=move&{position}={reference_id}"

    # FortiOS move uses PUT with empty body
    result = api_request(host, api_token, "PUT", endpoint, data={}, verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "policy_id": policy_id,
            "policy_name": source_name,
            "position": position,
            "reference_id": reference_id,
            "reference_name": ref_name,
            "message": f"Moved policy '{source_name}' (ID: {policy_id}) {position} '{ref_name}' (ID: {reference_id})"
        }
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            cli_error = result["data"].get("cli_error", "")
            if cli_error:
                error_msg = str(cli_error)
        return {"success": False, "error": f"Failed to move policy: {error_msg}", "details": result}


def main(context) -> dict:
    """Main entry point."""
    # Handle both ExecutionContext (MCP) and dict (CLI)
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    target_ip = params.get("target_ip")
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    # Get policy ID (from id or name)
    policy_id = params.get("policy_id")
    policy_name = params.get("policy_name")

    if not policy_id and policy_name:
        policy_id = find_policy_by_name(target_ip, api_token, policy_name, verify_ssl)
        if not policy_id:
            return {"success": False, "error": f"Policy '{policy_name}' not found"}

    if not policy_id:
        return {"success": False, "error": "policy_id or policy_name is required"}

    # Get position
    position = params.get("position", "").lower()
    if position not in ["before", "after"]:
        return {"success": False, "error": "position must be 'before' or 'after'"}

    # Get reference policy ID (from id or name)
    reference_id = params.get("reference_id")
    reference_name = params.get("reference_name")

    if not reference_id and reference_name:
        reference_id = find_policy_by_name(target_ip, api_token, reference_name, verify_ssl)
        if not reference_id:
            return {"success": False, "error": f"Reference policy '{reference_name}' not found"}

    if not reference_id:
        return {"success": False, "error": "reference_id or reference_name is required"}

    # Move the policy
    result = move_policy(target_ip, api_token, policy_id, position, reference_id, verify_ssl)
    result["target_ip"] = target_ip

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
