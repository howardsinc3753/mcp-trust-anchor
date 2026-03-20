#!/usr/bin/env python3
"""FortiGate System Global Tool - Canonical ID: org.ulysses.noc.fortigate-system-global/1.0.0

Configure FortiGate system global settings including management IP,
hostname, admin timeout, REST API options, and other global parameters.
"""
import json, sys, os, urllib3
from typing import Optional, Dict, Any
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def load_credentials(target_ip: str) -> Optional[Dict]:
    """Load credentials from config files."""
    paths = [Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml"]
    if os.name == 'nt':
        paths.extend([
            Path.home() / "AppData/Local/mcp/fortigate_credentials.yaml",
            Path("C:/ProgramData/mcp/fortigate_credentials.yaml"),
            Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml")
        ])
    else:
        paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for p in paths:
        if p.exists():
            try:
                import yaml
                config = yaml.safe_load(open(p))
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    name = config["default_lookup"][target_ip]
                    if name in config.get("devices", {}):
                        return config["devices"][name]
                for d in config.get("devices", {}).values():
                    if d.get("host") == target_ip:
                        return d
            except Exception:
                pass
    return None


def api_request(host: str, token: str, method: str, endpoint: str, data=None, verify=False) -> Dict:
    """Make FortiGate REST API request."""
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not available"}

    url = f"https://{host}/api/v2{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        resp = getattr(requests, method.lower())(url, headers=headers, json=data, verify=verify, timeout=30)
        return {
            "status_code": resp.status_code,
            "success": resp.status_code in [200, 201],
            "data": resp.json() if resp.text else {}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_global_settings(host: str, token: str, verify: bool = False) -> Dict:
    """Get current system global settings."""
    r = api_request(host, token, "GET", "/cmdb/system/global", verify=verify)
    if not r.get("success"):
        return {"success": False, "error": r.get("error", "Failed to get settings")}

    # Extract commonly used settings
    results = r.get("data", {}).get("results", {})
    if isinstance(results, list) and len(results) > 0:
        results = results[0]

    settings = {
        "hostname": results.get("hostname"),
        "timezone": results.get("timezone"),
        "admin-timeout": results.get("admin-timeout"),
        "admintimeout": results.get("admintimeout"),
        "management-ip": results.get("management-ip"),
        "rest-api-key-url-query": results.get("rest-api-key-url-query"),
        "admin-https-ssl-versions": results.get("admin-https-ssl-versions"),
        "gui-allow-incompatible-fabric-fgt": results.get("gui-allow-incompatible-fabric-fgt"),
    }

    return {"success": True, "settings": settings, "raw": results}


def set_global_settings(host: str, token: str, params: Dict, verify: bool = False) -> Dict:
    """Set system global settings."""
    # Map parameter names to API field names
    field_map = {
        "hostname": "hostname",
        "management_ip": "management-ip",
        "admin_timeout": "admin-timeout",
        "admintimeout": "admintimeout",
        "timezone": "timezone",
        "rest_api_key_url_query": "rest-api-key-url-query",
        "admin_https_ssl_versions": "admin-https-ssl-versions",
        "gui_allow_incompatible_fabric_fgt": "gui-allow-incompatible-fabric-fgt",
    }

    data = {}
    for param_name, api_name in field_map.items():
        if param_name in params and params[param_name] is not None:
            data[api_name] = params[param_name]

    if not data:
        return {"success": False, "error": "No settings to update"}

    r = api_request(host, token, "PUT", "/cmdb/system/global", data=data, verify=verify)
    if r.get("success"):
        return {"success": True, "message": f"Updated settings: {list(data.keys())}", "updated": data}

    error = r.get("data", {}).get("cli_error", r.get("error", "Failed"))
    return {"success": False, "error": error}


def main(context) -> Dict[str, Any]:
    """Main entry point."""
    params = context.parameters if hasattr(context, 'parameters') else context

    target_ip = params.get('target_ip')
    action = params.get('action', 'get').lower()
    verify_ssl = params.get('verify_ssl', False)

    if not target_ip:
        return {'success': False, 'error': 'target_ip required'}

    creds = load_credentials(target_ip)
    if not creds:
        return {'success': False, 'error': f'No credentials for {target_ip}'}

    token = creds.get('api_token')
    if not token:
        return {'success': False, 'error': 'No API token in credentials'}

    result = {'action': action, 'target_ip': target_ip}

    if action == 'get':
        result.update(get_global_settings(target_ip, token, verify_ssl))
    elif action == 'set':
        result.update(set_global_settings(target_ip, token, params, verify_ssl))
    else:
        return {'success': False, 'error': f'Unknown action: {action}'}

    return result


if __name__ == "__main__":
    params = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            k, v = arg.split('=', 1)
            k = k.lstrip('-')
            if v.isdigit():
                params[k] = int(v)
            elif v.lower() in ['true', 'false']:
                params[k] = v.lower() == 'true'
            else:
                params[k] = v

    if params:
        print(json.dumps(main(params), indent=2, default=str))
    else:
        print(json.dumps(main(json.loads(sys.stdin.read() or "{}")), indent=2, default=str))
