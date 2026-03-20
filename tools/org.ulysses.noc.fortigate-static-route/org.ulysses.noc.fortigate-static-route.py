#!/usr/bin/env python3
"""FortiGate Static Route Tool - Canonical ID: org.ulysses.noc.fortigate-static-route/1.0.0"""
import json, sys, os, urllib3
from typing import Optional, Any
from pathlib import Path
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request, urllib.error, ssl

def load_credentials(target_ip):
    paths = [Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml"]
    if os.name == 'nt':
        paths.extend([Path.home() / "AppData/Local/mcp/fortigate_credentials.yaml", Path("C:/ProgramData/mcp/fortigate_credentials.yaml"), Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml")])
    else:
        paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))
    for p in paths:
        if p.exists():
            try:
                import yaml
                config = yaml.safe_load(open(p))
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    name = config["default_lookup"][target_ip]
                    if name in config.get("devices", {}): return config["devices"][name]
                for d in config.get("devices", {}).values():
                    if d.get("host") == target_ip: return d
            except: pass
    return None

def api_request(host, token, method, endpoint, data=None, verify=False):
    url = f"https://{host}/api/v2{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if HAS_REQUESTS:
        try:
            resp = getattr(requests, method.lower())(url, headers=headers, json=data, verify=verify, timeout=30)
            return {"status_code": resp.status_code, "success": resp.status_code in [200,201], "data": resp.json() if resp.text else {}}
        except Exception as e: return {"success": False, "error": str(e)}
    return {"success": False, "error": "requests not available"}

def list_routes(host, token, verify=False):
    r = api_request(host, token, "GET", "/cmdb/router/static", verify_ssl=verify)
    if not r.get("success"): return {"success": False, "error": r.get("error", "Failed")}
    routes = [{"seq-num": x.get("seq-num"), "dst": x.get("dst",""), "gateway": x.get("gateway",""), "device": x.get("device",""), "comment": x.get("comment","")} for x in r.get("data",{}).get("results",[])]
    return {"success": True, "count": len(routes), "routes": routes}

def add_route(host, token, params, verify=False):
    dst = params.get("dst")
    if not dst: return {"success": False, "error": "dst required"}
    data = {"dst": dst}
    for k in ["gateway","device","comment","blackhole","status"]:
        if params.get(k): data[k] = params[k]
    for k in ["distance","weight","priority"]:
        if k in params: data[k] = int(params[k])
    r = api_request(host, token, "POST", "/cmdb/router/static", data=data, verify=verify)
    if r.get("success"): return {"success": True, "dst": dst, "message": f"Created route to {dst}"}
    return {"success": False, "error": r.get("data",{}).get("cli_error", r.get("error",""))}

def remove_route(host, token, seq_num, verify=False):
    r = api_request(host, token, "DELETE", f"/cmdb/router/static/{seq_num}", verify=verify)
    if r.get("success") or r.get("status_code") == 200: return {"success": True, "seq_num": seq_num, "message": f"Deleted {seq_num}"}
    return {"success": False, "error": r.get("error", "Failed")}

def main(context):
    params = context.parameters if hasattr(context, 'parameters') else context
    target_ip, action, verify = params.get("target_ip"), params.get("action", "list").lower(), params.get("verify_ssl", False)
    if not target_ip: return {"success": False, "error": "target_ip required"}
    creds = load_credentials(target_ip)
    if not creds: return {"success": False, "error": f"No credentials for {target_ip}"}
    token = creds.get("api_token")
    result = {"action": action, "target_ip": target_ip}
    if action == "list": result.update(list_routes(target_ip, token, verify))
    elif action == "add": result.update(add_route(target_ip, token, params, verify))
    elif action == "remove": result.update(remove_route(target_ip, token, int(params.get("seq_num",0)), verify))
    return result

if __name__ == "__main__":
    params = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            k,v = arg.split('=',1)
            params[k.lstrip('-')] = int(v) if v.isdigit() else (v.lower()=='true' if v.lower() in ['true','false'] else v)
    print(json.dumps(main(params) if params else main(json.loads(sys.stdin.read() or "{}")), indent=2))
