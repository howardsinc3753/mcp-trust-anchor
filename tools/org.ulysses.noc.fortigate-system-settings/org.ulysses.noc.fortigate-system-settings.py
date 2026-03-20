#!/usr/bin/env python3
"""FortiGate System Settings Tool - Canonical ID: org.ulysses.noc.fortigate-system-settings/1.0.0

Configure FortiGate system settings including location-id, IKE TCP port,
GUI themes, and other VDOM-level system parameters.
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


def get_system_settings(host: str, token: str, verify: bool = False) -> Dict:
    """Get current system settings."""
    r = api_request(host, token, "GET", "/cmdb/system/settings", verify=verify)
    if not r.get("success"):
        return {"success": False, "error": r.get("error", "Failed to get settings")}

    # Extract commonly used settings
    results = r.get("data", {}).get("results", {})
    if isinstance(results, list) and len(results) > 0:
        results = results[0]

    settings = {
        "location-id": results.get("location-id"),
        "ike-tcp-port": results.get("ike-tcp-port"),
        "opmode": results.get("opmode"),
        "central-nat": results.get("central-nat"),
        "gui-theme": results.get("gui-theme"),
        "gui-default-policy-columns": results.get("gui-default-policy-columns"),
        "allow-subnet-overlap": results.get("allow-subnet-overlap"),
        "http-external-dest": results.get("http-external-dest"),
        "firewall-session-dirty": results.get("firewall-session-dirty"),
    }

    return {"success": True, "settings": settings, "raw": results}


def set_system_settings(host: str, token: str, params: Dict, verify: bool = False) -> Dict:
    """Set system settings."""
    # Map parameter names to API field names
    field_map = {
        "location_id": "location-id",
        "ike_tcp_port": "ike-tcp-port",
        "opmode": "opmode",
        "central_nat": "central-nat",
        "gui_theme": "gui-theme",
        "gui_default_policy_columns": "gui-default-policy-columns",
        "allow_subnet_overlap": "allow-subnet-overlap",
    }

    data = {}
    for param_name, api_name in field_map.items():
        if param_name in params and params[param_name] is not None:
            data[api_name] = params[param_name]

    if not data:
        return {"success": False, "error": "No settings to update"}

    r = api_request(host, token, "PUT", "/cmdb/system/settings", data=data, verify=verify)
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
        result.update(get_system_settings(target_ip, token, verify_ssl))
    elif action == 'set':
        result.update(set_system_settings(target_ip, token, params, verify_ssl))
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
