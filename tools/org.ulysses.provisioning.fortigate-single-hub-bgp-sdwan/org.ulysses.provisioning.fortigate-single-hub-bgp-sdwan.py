#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Single-Hub BGP SD-WAN Template

Provisions a complete SD-WAN topology with BGP routing:
- Hub: Dynamic IPsec tunnel, BGP with neighbor-range for spokes
- Spoke: Static IPsec tunnel to hub, BGP peering with hub loopback

This implements Fortinet's recommended SD-WAN architecture with iBGP
over IPsec overlays for dynamic route exchange.

Reference: Fortinet 4D-Demo SD-WAN configurations
"""

import urllib.request
import urllib.error
import ssl
import json
import gzip
import os
from pathlib import Path
from typing import Any, Optional


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


def decode_response(response) -> str:
    """Decode response handling gzip compression."""
    data = response.read()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return data.decode('utf-8')


def make_api_request(host: str, endpoint: str, api_token: str,
                     method: str = "GET", data: dict = None,
                     verify_ssl: bool = False, timeout: int = 30) -> dict:
    """Make a request to FortiGate REST API using Bearer token auth."""
    url = f"https://{host}{endpoint}"

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    body = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(decode_response(response))


def detect_wan_interface(host: str, api_token: str, verify_ssl: bool = False) -> str:
    """Auto-detect WAN interface (wan1, wan, port1, etc.)."""
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/interface", api_token,
                                  "GET", verify_ssl=verify_ssl)
        interfaces = result.get("results", [])

        for name in ["wan1", "wan", "wan2", "port1"]:
            for iface in interfaces:
                if iface.get("name") == name and iface.get("type") == "physical":
                    ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                    if ip and not ip.startswith("0.0.0.0"):
                        return name

        for iface in interfaces:
            if iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return iface.get("name")

        return "wan1"
    except Exception:
        return "wan1"


def safe_api_call(host: str, api_token: str, endpoint: str, method: str,
                  data: dict, verify_ssl: bool = False) -> tuple:
    """Make API call and return (success, error_msg)."""
    try:
        make_api_request(host, endpoint, api_token, method, data, verify_ssl)
        return True, None
    except urllib.error.HTTPError as e:
        if e.code == 500:
            return False, "may already exist"
        err = e.read().decode()[:200]
        return False, f"HTTP {e.code}: {err}"
    except Exception as ex:
        return False, str(ex)


def provision_hub(target_ip: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Provision hub with IPsec, SD-WAN, and BGP."""
    result = {"components_created": [], "errors": []}

    loopback_ip = params["hub_loopback_ip"]
    loopback_name = params.get("hub_loopback_name", "Hub_Lo")
    tunnel_name = params.get("tunnel_name", "SPOKE_VPN1")
    sdwan_zone = params.get("sdwan_zone", "SDWAN_OVERLAY")
    psk = params["psk"]
    bgp_as = params.get("bgp_as", 65000)
    network_id = params.get("network_id", 1)
    wan_interface = params.get("wan_interface") or detect_wan_interface(target_ip, api_token, verify_ssl)

    # Extract IP without mask
    loopback_ip_only = loopback_ip.split()[0]

    # 1. Create loopback interface
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/interface", "POST", {
        "name": loopback_name,
        "vdom": "root",
        "ip": loopback_ip,
        "allowaccess": "ping",
        "type": "loopback"
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"loopback:{loopback_name}")
    else:
        result["errors"].append(f"loopback:{loopback_name} - {err}")

    # 2. Create IPsec Phase1 (dynamic type for hub)
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/vpn.ipsec/phase1-interface", "POST", {
        "name": tunnel_name,
        "type": "dynamic",
        "interface": wan_interface,
        "ike-version": 2,
        "peertype": "any",
        "net-device": "disable",
        "exchange-ip-addr4": loopback_ip_only,
        "proposal": "aes256-sha256",
        "add-route": "disable",
        "dpd": "on-idle",
        "dpd-retrycount": 3,
        "dpd-retryinterval": 5,
        "network-overlay": "enable",
        "network-id": network_id,
        "psksecret": psk
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"phase1:{tunnel_name}")
    else:
        result["errors"].append(f"phase1:{tunnel_name} - {err}")

    # 3. Create Phase2
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/vpn.ipsec/phase2-interface", "POST", {
        "name": tunnel_name,
        "phase1name": tunnel_name,
        "proposal": "aes256-sha256",
        "auto-negotiate": "enable"
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"phase2:{tunnel_name}")
    else:
        result["errors"].append(f"phase2:{tunnel_name} - {err}")

    # 4. Enable SD-WAN and create zone
    safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan", "PUT",
                  {"status": "enable"}, verify_ssl)
    result["components_created"].append("sdwan:enabled")

    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/zone", "POST",
                            {"name": sdwan_zone}, verify_ssl)
    if ok:
        result["components_created"].append(f"zone:{sdwan_zone}")
    else:
        result["errors"].append(f"zone:{sdwan_zone} - {err}")

    # 5. SD-WAN member (may fail until spoke connects - that's ok)
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/members", "POST", {
        "seq-num": 100,
        "interface": tunnel_name,
        "zone": sdwan_zone,
        "source": loopback_ip_only,
        "priority": 10
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"member:{tunnel_name}")
    else:
        result["errors"].append(f"member:{tunnel_name} - {err}")

    # 6. Static route to spoke loopbacks
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/router/static", "POST", {
        "dst": "172.16.0.0 255.255.255.0",
        "device": tunnel_name,
        "comment": "Route to spoke loopbacks"
    }, verify_ssl)
    if ok:
        result["components_created"].append("route:spoke-loopbacks")
    else:
        result["errors"].append(f"route:spoke-loopbacks - {err}")

    # 6b. SD-WAN health check (4D-Demo hub settings - remote detection mode)
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/health-check", "POST", {
        "name": "From_Edge",
        "detect-mode": "remote",
        "remote-probe-timeout": 2500,
        "failtime": 1,
        "recoverytime": 1,
        "sla-id-redistribute": 1,
        "sla-fail-log-period": 10,
        "sla-pass-log-period": 10,
        "members": [{"seq-num": 0}],  # 0 = all members
        "sla": [{
            "id": 1,
            "link-cost-factor": "remote",
            "priority-out-sla": 999
        }]
    }, verify_ssl)
    if ok:
        result["components_created"].append("health_check:From_Edge")
    else:
        result["errors"].append(f"health_check:From_Edge - {err}")

    # 7. Configure BGP with neighbor-group for spokes (4D-Demo settings)
    bgp_config = {
        "as": bgp_as,
        "router-id": loopback_ip_only,
        "ebgp-multipath": "enable",
        "ibgp-multipath": "enable",
        "recursive-next-hop": "enable",
        "recursive-inherit-priority": "enable",  # 4D-Demo: inherit priority from SD-WAN
        "graceful-restart": "enable",
        "neighbor-group": [{
            "name": "EDGE",
            "advertisement-interval": 1,
            "capability-graceful-restart": "enable",
            "next-hop-self": "enable",
            "soft-reconfiguration": "enable",
            "interface": loopback_name,
            "remote-as": bgp_as,
            "update-source": loopback_name,
            "connect-timer": 5
        }],
        "neighbor-range": [{
            "id": 1,
            "prefix": "172.16.0.0 255.255.0.0",
            "neighbor-group": "EDGE"
        }],
        "network": [{
            "id": 1,
            "prefix": "172.16.0.0 255.255.0.0"
        }],
        "redistribute": {
            "connected": {"status": "enable"}
        }
    }
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/router/bgp", "PUT", bgp_config, verify_ssl)
    if ok:
        result["components_created"].append(f"bgp:as{bgp_as}")
    else:
        result["errors"].append(f"bgp - {err}")

    # 8. Firewall policy for overlay traffic
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/firewall/policy", "POST", {
        "name": "SDWAN_Overlay_Traffic",
        "srcintf": [{"name": loopback_name}, {"name": sdwan_zone}],
        "dstintf": [{"name": loopback_name}, {"name": sdwan_zone}],
        "action": "accept",
        "srcaddr": [{"name": "all"}],
        "dstaddr": [{"name": "all"}],
        "schedule": "always",
        "service": [{"name": "ALL"}],
        "logtraffic": "all"
    }, verify_ssl)
    if ok:
        result["components_created"].append("policy:SDWAN_Overlay_Traffic")
    else:
        result["errors"].append(f"policy - {err}")

    result["wan_interface"] = wan_interface
    return result


def provision_spoke(target_ip: str, api_token: str, params: dict, verify_ssl: bool = False) -> dict:
    """Provision spoke with IPsec, SD-WAN, and BGP."""
    result = {"components_created": [], "errors": []}

    loopback_ip = params["spoke_loopback_ip"]
    loopback_name = params.get("spoke_loopback_name", "Spoke_Lo")
    hub_wan_ip = params["hub_wan_ip"]
    hub_loopback_ip = params["hub_loopback_ip"].split()[0]
    tunnel_name = params.get("tunnel_name", "HUB_VPN1")
    sdwan_zone = params.get("sdwan_zone", "SDWAN_OVERLAY")
    psk = params["psk"]
    bgp_as = params.get("bgp_as", 65000)
    network_id = params.get("network_id", 1)
    wan_interface = params.get("wan_interface") or detect_wan_interface(target_ip, api_token, verify_ssl)

    loopback_ip_only = loopback_ip.split()[0]

    # 1. Create loopback
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/interface", "POST", {
        "name": loopback_name,
        "vdom": "root",
        "ip": loopback_ip,
        "allowaccess": "ping",
        "type": "loopback"
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"loopback:{loopback_name}")
    else:
        result["errors"].append(f"loopback:{loopback_name} - {err}")

    # 2. Create IPsec Phase1 (static to hub)
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/vpn.ipsec/phase1-interface", "POST", {
        "name": tunnel_name,
        "interface": wan_interface,
        "ike-version": 2,
        "peertype": "any",
        "net-device": "enable",
        "exchange-ip-addr4": loopback_ip_only,
        "proposal": "aes256-sha256",
        "add-route": "disable",
        "localid": f"spoke-{tunnel_name}",
        "dpd": "on-idle",
        "dpd-retrycount": 3,
        "dpd-retryinterval": 5,
        "network-overlay": "enable",
        "network-id": network_id,
        "remote-gw": hub_wan_ip,
        "psksecret": psk
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"phase1:{tunnel_name}")
    else:
        result["errors"].append(f"phase1:{tunnel_name} - {err}")

    # 3. Create Phase2
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/vpn.ipsec/phase2-interface", "POST", {
        "name": tunnel_name,
        "phase1name": tunnel_name,
        "proposal": "aes256-sha256",
        "auto-negotiate": "enable"
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"phase2:{tunnel_name}")
    else:
        result["errors"].append(f"phase2:{tunnel_name} - {err}")

    # 4. Enable SD-WAN and create zone
    safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan", "PUT",
                  {"status": "enable"}, verify_ssl)
    result["components_created"].append("sdwan:enabled")

    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/zone", "POST",
                            {"name": sdwan_zone}, verify_ssl)
    if ok:
        result["components_created"].append(f"zone:{sdwan_zone}")
    else:
        result["errors"].append(f"zone:{sdwan_zone} - {err}")

    # 5. SD-WAN member
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/members", "POST", {
        "seq-num": 100,
        "interface": tunnel_name,
        "zone": sdwan_zone,
        "source": loopback_ip_only
    }, verify_ssl)
    if ok:
        result["components_created"].append(f"member:{tunnel_name}")
    else:
        result["errors"].append(f"member:{tunnel_name} - {err}")

    # 6. SD-WAN health check (4D-Demo spoke settings)
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/system/sdwan/health-check", "POST", {
        "name": "HUB",
        "server": hub_loopback_ip,
        "protocol": "ping",
        "update-cascade-interface": "disable",
        "update-static-route": "disable",
        "embed-measured-health": "enable",
        "sla-id-redistribute": 1,
        "sla-fail-log-period": 10,
        "sla-pass-log-period": 10,
        "members": [{"seq-num": 100}],
        "sla": [{"id": 1, "latency-threshold": 200, "jitter-threshold": 50, "packetloss-threshold": 5}]
    }, verify_ssl)
    if ok:
        result["components_created"].append("health_check:HUB")
    else:
        result["errors"].append(f"health_check - {err}")

    # 7. Static route to hub loopbacks
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/router/static", "POST", {
        "dst": "172.16.255.0 255.255.255.0",
        "device": tunnel_name,
        "comment": "Route to hub loopbacks"
    }, verify_ssl)
    if ok:
        result["components_created"].append("route:hub-loopbacks")
    else:
        result["errors"].append(f"route:hub-loopbacks - {err}")

    # 8. Configure BGP to peer with hub (4D-Demo settings)
    bgp_config = {
        "as": bgp_as,
        "router-id": loopback_ip_only,
        "ebgp-multipath": "enable",
        "ibgp-multipath": "enable",
        "recursive-next-hop": "enable",
        "recursive-inherit-priority": "enable",  # 4D-Demo: inherit priority from SD-WAN
        "graceful-restart": "enable",
        "neighbor": [{
            "ip": hub_loopback_ip,
            "advertisement-interval": 1,
            "capability-graceful-restart": "enable",
            "soft-reconfiguration": "enable",
            "interface": loopback_name,
            "remote-as": bgp_as,
            "connect-timer": 1,
            "update-source": loopback_name
        }],
        "redistribute": {
            "connected": {"status": "enable"}
        }
    }
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/router/bgp", "PUT", bgp_config, verify_ssl)
    if ok:
        result["components_created"].append(f"bgp:as{bgp_as}")
    else:
        result["errors"].append(f"bgp - {err}")

    # 9. Firewall policy
    ok, err = safe_api_call(target_ip, api_token, "/api/v2/cmdb/firewall/policy", "POST", {
        "name": "SDWAN_Overlay_Traffic",
        "srcintf": [{"name": loopback_name}, {"name": sdwan_zone}],
        "dstintf": [{"name": loopback_name}, {"name": sdwan_zone}],
        "action": "accept",
        "srcaddr": [{"name": "all"}],
        "dstaddr": [{"name": "all"}],
        "schedule": "always",
        "service": [{"name": "ALL"}],
        "logtraffic": "all"
    }, verify_ssl)
    if ok:
        result["components_created"].append("policy:SDWAN_Overlay_Traffic")
    else:
        result["errors"].append(f"policy - {err}")

    result["wan_interface"] = wan_interface
    return result


def main(context) -> dict[str, Any]:
    """
    FortiGate Single-Hub BGP SD-WAN Template.

    Provisions a complete SD-WAN topology with BGP over IPsec overlay.

    Args:
        context: ExecutionContext with parameters:
            - role: "hub" or "spoke"
            - target_ip: Device management IP
            - hub_wan_ip: Hub's WAN IP (required for spoke)
            - hub_loopback_ip: Hub loopback IP (e.g., "172.16.255.253 255.255.255.255")
            - spoke_loopback_ip: Spoke loopback IP (required for spoke role)
            - psk: Pre-shared key for IPsec
            - bgp_as: BGP AS number (default: 65000)
            - tunnel_name: IPsec tunnel name
            - sdwan_zone: SD-WAN zone name
            - network_id: Overlay network ID (1-255)

    Returns:
        dict: Result with created components and any errors
    """
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    role = args.get("role", "").lower()
    target_ip = args.get("target_ip")
    psk = args.get("psk")

    if not target_ip:
        return {"success": False, "error": "target_ip is required"}
    if not psk:
        return {"success": False, "error": "psk is required"}
    if role not in ["hub", "spoke"]:
        return {"success": False, "error": "role must be 'hub' or 'spoke'"}

    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")
    verify_ssl = creds.get("verify_ssl", False)

    if role == "hub":
        if not args.get("hub_loopback_ip"):
            return {"success": False, "error": "hub_loopback_ip is required for hub role"}

        result = provision_hub(target_ip, api_token, args, verify_ssl)
        result["success"] = True
        result["role"] = "hub"
        result["target_ip"] = target_ip
        result["message"] = f"Hub provisioned with {len(result['components_created'])} components"

    else:  # spoke
        if not args.get("spoke_loopback_ip"):
            return {"success": False, "error": "spoke_loopback_ip is required for spoke role"}
        if not args.get("hub_wan_ip"):
            return {"success": False, "error": "hub_wan_ip is required for spoke role"}
        if not args.get("hub_loopback_ip"):
            return {"success": False, "error": "hub_loopback_ip is required for spoke role"}

        result = provision_spoke(target_ip, api_token, args, verify_ssl)
        result["success"] = True
        result["role"] = "spoke"
        result["target_ip"] = target_ip
        result["message"] = f"Spoke provisioned with {len(result['components_created'])} components"

    return result


if __name__ == "__main__":
    # Example: Provision hub
    hub_result = main({
        "role": "hub",
        "target_ip": "192.168.215.15",
        "hub_loopback_ip": "172.16.255.253 255.255.255.255",
        "psk": "fortinet123",
        "bgp_as": 65000
    })
    print("Hub:", json.dumps(hub_result, indent=2))

    # Example: Provision spoke
    spoke_result = main({
        "role": "spoke",
        "target_ip": "192.168.209.30",
        "hub_wan_ip": "192.168.215.15",
        "hub_loopback_ip": "172.16.255.253 255.255.255.255",
        "spoke_loopback_ip": "172.16.0.2 255.255.255.255",
        "psk": "fortinet123",
        "bgp_as": 65000
    })
    print("Spoke:", json.dumps(spoke_result, indent=2))
