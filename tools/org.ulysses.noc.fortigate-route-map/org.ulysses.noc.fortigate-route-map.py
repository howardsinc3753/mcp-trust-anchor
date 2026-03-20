#!/usr/bin/env python3
"""
FortiGate Route Map Tool

Manage route-maps for BGP policy control.

Canonical ID: org.ulysses.noc.fortigate-route-map/1.0.0
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


def list_route_maps(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all route-maps."""
    result = api_request(host, api_token, "GET", "/cmdb/router/route-map", verify_ssl=verify_ssl)
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Failed to get route-maps")}

    data = result.get("data", {})
    maps = data.get("results", [])

    return {
        "success": True,
        "count": len(maps),
        "route_maps": [{
            "name": m.get("name"),
            "comments": m.get("comments", ""),
            "rule_count": len(m.get("rule", [])),
        } for m in maps]
    }


def get_route_map(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Get specific route-map with rules."""
    result = api_request(host, api_token, "GET", f"/cmdb/router/route-map/{name}", verify_ssl=verify_ssl)
    if not result.get("success"):
        return {"success": False, "error": f"Route-map '{name}' not found"}

    data = result.get("data", {})
    rmap = data.get("results", [data])[0] if isinstance(data.get("results"), list) else data

    rules = []
    for r in rmap.get("rule", []):
        rules.append({
            "id": r.get("id"),
            "action": r.get("action", "permit"),
            "match-ip-address": r.get("match-ip-address", ""),
            "match-ip-nexthop": r.get("match-ip-nexthop", ""),
            "match-as-path": r.get("match-as-path", ""),
            "match-community": r.get("match-community", ""),
            "match-tag": r.get("match-tag", 0),
            "set-local-preference": r.get("set-local-preference", 0),
            "set-metric": r.get("set-metric", 0),
            "set-aspath": r.get("set-aspath", []),
            "set-community": r.get("set-community", []),
            "set-tag": r.get("set-tag", 0),
        })

    return {
        "success": True,
        "route_map": {
            "name": rmap.get("name"),
            "comments": rmap.get("comments", ""),
            "rules": rules,
        }
    }


def add_route_map(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Create new route-map."""
    name = params.get("name")
    if not name:
        return {"success": False, "error": "name is required"}

    # Check if exists
    existing = get_route_map(host, api_token, name, verify_ssl)
    if existing.get("success"):
        return {"success": False, "error": f"Route-map '{name}' already exists"}

    rmap_data = {"name": name}

    if "comments" in params:
        rmap_data["comments"] = params["comments"]

    # Add initial rule if provided
    if "rule" in params:
        rule = params["rule"]
        rule_data = {"id": rule.get("id", 1)}

        if "action" in rule:
            rule_data["action"] = rule["action"]

        # Match clauses
        if "match_ip_address" in rule:
            rule_data["match-ip-address"] = rule["match_ip_address"]
        if "match_ip_nexthop" in rule:
            rule_data["match-ip-nexthop"] = rule["match_ip_nexthop"]
        if "match_as_path" in rule:
            rule_data["match-as-path"] = rule["match_as_path"]
        if "match_community" in rule:
            rule_data["match-community"] = rule["match_community"]
        if "match_tag" in rule:
            rule_data["match-tag"] = int(rule["match_tag"])

        # Set clauses
        if "set_local_preference" in rule:
            rule_data["set-local-preference"] = int(rule["set_local_preference"])
        if "set_metric" in rule:
            rule_data["set-metric"] = int(rule["set_metric"])
        if "set_aspath" in rule:
            rule_data["set-aspath"] = rule["set_aspath"]
        if "set_community" in rule:
            rule_data["set-community"] = rule["set_community"]
        if "set_tag" in rule:
            rule_data["set-tag"] = int(rule["set_tag"])

        rmap_data["rule"] = [rule_data]

    result = api_request(host, api_token, "POST", "/cmdb/router/route-map", data=rmap_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {"success": True, "name": name, "message": f"Created route-map '{name}'"}
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to create route-map: {error_msg}"}


def update_route_map(host: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Update route-map (add/modify rules)."""
    name = params.get("name")
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_route_map(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Route-map '{name}' not found"}

    update_data = {}

    if "comments" in params:
        update_data["comments"] = params["comments"]

    # Update rule if provided
    if "rule" in params:
        rule = params["rule"]
        rule_data = {"id": rule.get("id", 1)}

        if "action" in rule:
            rule_data["action"] = rule["action"]

        # Match clauses
        if "match_ip_address" in rule:
            rule_data["match-ip-address"] = rule["match_ip_address"]
        if "match_ip_nexthop" in rule:
            rule_data["match-ip-nexthop"] = rule["match_ip_nexthop"]
        if "match_as_path" in rule:
            rule_data["match-as-path"] = rule["match_as_path"]
        if "match_community" in rule:
            rule_data["match-community"] = rule["match_community"]
        if "match_tag" in rule:
            rule_data["match-tag"] = int(rule["match_tag"])

        # Set clauses
        if "set_local_preference" in rule:
            rule_data["set-local-preference"] = int(rule["set_local_preference"])
        if "set_metric" in rule:
            rule_data["set-metric"] = int(rule["set_metric"])
        if "set_aspath" in rule:
            rule_data["set-aspath"] = rule["set_aspath"]
        if "set_community" in rule:
            rule_data["set-community"] = rule["set_community"]
        if "set_tag" in rule:
            rule_data["set-tag"] = int(rule["set_tag"])

        update_data["rule"] = [rule_data]

    if not update_data:
        return {"success": False, "error": "No update fields specified"}

    result = api_request(host, api_token, "PUT", f"/cmdb/router/route-map/{name}", data=update_data, verify_ssl=verify_ssl)

    if result.get("success"):
        return {"success": True, "name": name, "message": f"Updated route-map '{name}'"}
    else:
        error_msg = result.get("error", "")
        if "data" in result:
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to update route-map: {error_msg}"}


def remove_route_map(host: str, api_token: str, name: str, verify_ssl: bool = False) -> dict:
    """Delete route-map."""
    if not name:
        return {"success": False, "error": "name is required"}

    existing = get_route_map(host, api_token, name, verify_ssl)
    if not existing.get("success"):
        return {"success": False, "error": f"Route-map '{name}' not found"}

    result = api_request(host, api_token, "DELETE", f"/cmdb/router/route-map/{name}", verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {"success": True, "name": name, "message": f"Deleted route-map '{name}'"}
    else:
        return {"success": False, "error": f"Failed to delete route-map: {result.get('error', 'Unknown error')}"}


def main(context) -> dict[str, Any]:
    """Main entry point."""
    params = context.parameters if hasattr(context, 'parameters') else context

    target_ip = params.get("target_ip")
    action = params.get("action", "list").lower()
    verify_ssl = params.get("verify_ssl", False)

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["list", "get", "add", "update", "remove"]:
        return {"success": False, "error": f"Invalid action: {action}"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}

    api_token = creds.get("api_token")
    result = {"action": action, "target_ip": target_ip}

    if action == "list":
        result.update(list_route_maps(target_ip, api_token, verify_ssl))
    elif action == "get":
        name = params.get("name")
        if not name:
            return {"success": False, "error": "name is required for 'get' action"}
        result.update(get_route_map(target_ip, api_token, name, verify_ssl))
    elif action == "add":
        result.update(add_route_map(target_ip, api_token, params, verify_ssl))
    elif action == "update":
        result.update(update_route_map(target_ip, api_token, params, verify_ssl))
    elif action == "remove":
        name = params.get("name")
        result.update(remove_route_map(target_ip, api_token, name, verify_ssl))

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
