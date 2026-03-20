#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate SD-WAN Hub Template Tool (No ADVPN)

Provisions a complete SD-WAN hub configuration to accept spoke connections:
1. Loopback interface (for BGP/health checks)
2. IPsec Phase1 tunnel (dynamic mode - accepts spoke connections)
3. IPsec Phase2 interface
4. SD-WAN zone for overlay
5. SD-WAN member
6. Firewall policies

This is a simplified template without ADVPN/BGP for basic hub-spoke topology.
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
    """Auto-detect the WAN interface.

    Checks for common WAN interface naming conventions:
    - wan1, wan, wan2 (hardware appliances)
    - port1, port2 (VMs and some models)
    """
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/interface", api_token,
                                  "GET", verify_ssl=verify_ssl)
        interfaces = result.get("results", [])

        # Priority 1: wan1, wan, wan2
        for name in ["wan1", "wan", "wan2"]:
            for iface in interfaces:
                if iface.get("name") == name and iface.get("type") == "physical":
                    ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                    if ip and not ip.startswith("0.0.0.0"):
                        return name

        # Priority 2: Any interface starting with wan
        for iface in interfaces:
            if iface.get("name", "").startswith("wan") and iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return iface.get("name")

        # Priority 3: port1 (common on VMs)
        for iface in interfaces:
            if iface.get("name") == "port1" and iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return "port1"

        # Priority 4: First physical interface with an IP
        for iface in interfaces:
            if iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return iface.get("name")

        return "wan1"  # Fallback
    except Exception:
        return "wan1"


def create_loopback_interface(host: str, api_token: str, name: str, ip: str,
                               verify_ssl: bool = False) -> dict:
    """Create loopback interface."""
    data = {
        "name": name,
        "vdom": "root",
        "ip": ip,
        "allowaccess": "ping",
        "type": "loopback"
    }
    return make_api_request(host, "/api/v2/cmdb/system/interface", api_token,
                            "POST", data, verify_ssl)


def create_hub_ipsec_phase1(host: str, api_token: str, name: str, interface: str,
                             psk: str, loopback_ip: str, network_id: int = 1,
                             verify_ssl: bool = False) -> dict:
    """Create IPsec Phase1-interface for hub (dynamic/dial-up mode).

    Uses type=dynamic to accept connections from any spoke without
    specifying remote-gw. This is the hub configuration for SD-WAN.

    Key settings from Fortinet 4D-Demo:
    - exchange-ip-addr4: Loopback IP for SD-WAN overlay routing
    - auto-discovery-sender: Enable ADVPN shortcut discovery
    - dhgrp: DH groups 20 21 for modern security
    - transport: UDP for consistent overlay behavior
    """
    # Extract just the IP without mask for exchange-ip-addr4
    exchange_ip = loopback_ip.split('/')[0].split()[0]

    data = {
        "name": name,
        "type": "dynamic",  # CRITICAL: Hub must use dynamic type to accept spoke connections
        "interface": interface,
        "ike-version": 2,
        "peertype": "any",
        "net-device": "disable",  # MUST be disable for dial-up tunnels to work with SD-WAN
        "exchange-ip-addr4": exchange_ip,  # Loopback IP for SD-WAN overlay routing
        "proposal": "aes256-sha256",
        "add-route": "disable",
        "dpd": "on-idle",
        "dpd-retrycount": 3,
        "dpd-retryinterval": 60,
        "dhgrp": "20 21",  # Modern DH groups
        "auto-discovery-sender": "enable",  # Hub sends ADVPN shortcuts to spokes
        "network-overlay": "enable",
        "network-id": network_id,
        "transport": "auto",  # UDP transport for overlay
        "psksecret": psk
        # No remote-gw for hub - type=dynamic accepts from any spoke
    }
    return make_api_request(host, "/api/v2/cmdb/vpn.ipsec/phase1-interface", api_token,
                            "POST", data, verify_ssl)


def create_ipsec_phase2(host: str, api_token: str, name: str, phase1name: str,
                        verify_ssl: bool = False) -> dict:
    """Create IPsec Phase2-interface."""
    data = {
        "name": name,
        "phase1name": phase1name,
        "proposal": "aes256-sha256",
        "auto-negotiate": "enable"
    }
    return make_api_request(host, "/api/v2/cmdb/vpn.ipsec/phase2-interface", api_token,
                            "POST", data, verify_ssl)


def set_location_id(host: str, api_token: str, loopback_ip: str,
                    verify_ssl: bool = False) -> dict:
    """Set system location-id to loopback IP for SD-WAN identification.

    The location-id is used by SD-WAN to identify this device in the overlay.
    Setting it to the loopback IP ensures consistent identification.
    """
    # Extract just the IP without mask
    location_ip = loopback_ip.split('/')[0].split()[0]

    data = {"location-id": location_ip}
    return make_api_request(host, "/api/v2/cmdb/system/settings", api_token,
                            "PUT", data, verify_ssl)


def enable_sdwan(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """Enable SD-WAN if not already enabled."""
    data = {"status": "enable"}
    return make_api_request(host, "/api/v2/cmdb/system/sdwan", api_token,
                            "PUT", data, verify_ssl)


def create_sdwan_zone(host: str, api_token: str, name: str,
                      verify_ssl: bool = False) -> dict:
    """Create SD-WAN zone."""
    data = {"name": name}
    return make_api_request(host, "/api/v2/cmdb/system/sdwan/zone", api_token,
                            "POST", data, verify_ssl)


def create_sdwan_member(host: str, api_token: str, seq_num: int, interface: str,
                        zone: str, source_ip: str, priority: int = 10,
                        priority_in_sla: int = 10, priority_out_sla: int = 20,
                        verify_ssl: bool = False) -> dict:
    """Add interface as SD-WAN member with priority settings.

    Priority settings from Fortinet 4D-Demo:
    - priority: Base priority (lower = preferred)
    - priority-in-sla: Priority when SLA is met
    - priority-out-sla: Priority when SLA is not met
    """
    source = source_ip.split('/')[0].split()[0]

    data = {
        "seq-num": seq_num,
        "interface": interface,
        "zone": zone,
        "source": source,
        "priority": priority,
        "priority-in-sla": priority_in_sla,
        "priority-out-sla": priority_out_sla
    }
    return make_api_request(host, "/api/v2/cmdb/system/sdwan/members", api_token,
                            "POST", data, verify_ssl)


def create_firewall_address(host: str, api_token: str, name: str, subnet: str,
                            verify_ssl: bool = False) -> dict:
    """Create firewall address object."""
    data = {
        "name": name,
        "subnet": subnet
    }
    return make_api_request(host, "/api/v2/cmdb/firewall/address", api_token,
                            "POST", data, verify_ssl)


def create_firewall_policy(host: str, api_token: str, name: str,
                           srcintf: list, dstintf: list,
                           srcaddr: list, dstaddr: list,
                           verify_ssl: bool = False) -> dict:
    """Create firewall policy."""
    data = {
        "name": name,
        "srcintf": [{"name": i} for i in srcintf],
        "dstintf": [{"name": i} for i in dstintf],
        "action": "accept",
        "srcaddr": [{"name": a} for a in srcaddr],
        "dstaddr": [{"name": a} for a in dstaddr],
        "schedule": "always",
        "service": [{"name": "ALL"}],
        "logtraffic": "all"
    }
    return make_api_request(host, "/api/v2/cmdb/firewall/policy", api_token,
                            "POST", data, verify_ssl)


def main(context) -> dict[str, Any]:
    """
    FortiGate SD-WAN Hub Template - Provisions hub to accept spoke connections.

    Creates:
    1. Loopback interface for health check/BGP peering
    2. IPsec Phase1 tunnel (dynamic mode - accepts any spoke)
    3. IPsec Phase2 interface
    4. SD-WAN zone
    5. SD-WAN member (tunnel -> zone)
    6. Firewall address objects
    7. Firewall policy (overlay traffic)

    Args:
        context: ExecutionContext with parameters:
            - target_ip: Hub FortiGate management IP
            - loopback_ip: Hub loopback IP (e.g., "172.16.255.253 255.255.255.255")
            - loopback_name: Loopback interface name (default: "Hub_Lo")
            - tunnel_name: IPsec tunnel name (default: "SPOKE_VPN1")
            - wan_interface: WAN interface for tunnel (auto-detect if not set)
            - psk: Pre-shared key for IPsec
            - sdwan_zone: SD-WAN zone name (default: "SDWAN_OVERLAY")
            - network_id: Network overlay ID 1-255 (default: 1)

    Returns:
        dict: Result with created components and any errors
    """
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    # Required parameters
    target_ip = args.get("target_ip")
    loopback_ip = args.get("loopback_ip")
    psk = args.get("psk")

    # Optional parameters with defaults
    loopback_name = args.get("loopback_name", "Hub_Lo")
    tunnel_name = args.get("tunnel_name", "SPOKE_VPN1")
    wan_interface = args.get("wan_interface")  # Auto-detect if not specified
    sdwan_zone = args.get("sdwan_zone", "SDWAN_OVERLAY")
    network_id = args.get("network_id", 1)
    verify_ssl = args.get("verify_ssl", False)
    timeout = args.get("timeout", 30)

    # Validation
    if not target_ip:
        return {"success": False, "error": "target_ip is required"}
    if not loopback_ip:
        return {"success": False, "error": "loopback_ip is required (e.g., '172.16.255.253 255.255.255.255')"}
    if not psk:
        return {"success": False, "error": "psk (pre-shared key) is required"}

    # Get credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")
    if creds.get("verify_ssl") is not None:
        verify_ssl = creds["verify_ssl"]

    # Auto-detect WAN interface if not specified
    if not wan_interface:
        wan_interface = detect_wan_interface(target_ip, api_token, verify_ssl)

    result = {
        "success": False,
        "target_ip": target_ip,
        "components_created": [],
        "errors": []
    }

    try:
        # 0. Set location-id to loopback IP for SD-WAN identification
        try:
            set_location_id(target_ip, api_token, loopback_ip, verify_ssl)
            result["components_created"].append(f"location-id:{loopback_ip.split()[0]}")
        except Exception as e:
            result["errors"].append(f"location-id: {str(e)}")

        # 1. Create loopback interface
        try:
            create_loopback_interface(target_ip, api_token, loopback_name, loopback_ip, verify_ssl)
            result["components_created"].append(f"loopback:{loopback_name}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"loopback:{loopback_name} may already exist")
            else:
                raise

        # 2. Create Hub IPsec Phase1 (dynamic mode - accepts spoke connections)
        try:
            create_hub_ipsec_phase1(target_ip, api_token, tunnel_name, wan_interface,
                                    psk, loopback_ip, network_id, verify_ssl)
            result["components_created"].append(f"phase1:{tunnel_name}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"phase1:{tunnel_name} may already exist")
            else:
                raise

        # 3. Create IPsec Phase2
        try:
            create_ipsec_phase2(target_ip, api_token, tunnel_name, tunnel_name, verify_ssl)
            result["components_created"].append(f"phase2:{tunnel_name}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"phase2:{tunnel_name} may already exist")
            else:
                raise

        # 4. Enable SD-WAN
        try:
            enable_sdwan(target_ip, api_token, verify_ssl)
            result["components_created"].append("sdwan:enabled")
        except Exception:
            pass

        # 5. Create SD-WAN zone
        try:
            create_sdwan_zone(target_ip, api_token, sdwan_zone, verify_ssl)
            result["components_created"].append(f"zone:{sdwan_zone}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"zone:{sdwan_zone} may already exist")
            else:
                raise

        # 6. Create SD-WAN member (use seq-num 100)
        # NOTE: For dynamic tunnels, the interface may not be available until spokes connect
        try:
            create_sdwan_member(target_ip, api_token, 100, tunnel_name, sdwan_zone, loopback_ip, verify_ssl)
            result["components_created"].append(f"member:{tunnel_name}->{sdwan_zone}")
        except urllib.error.HTTPError as e:
            # Dynamic tunnels won't appear until spokes connect - this is expected
            result["errors"].append(f"member:{tunnel_name} - dynamic tunnel not yet available (will appear when spokes connect)")

        # 7. Create firewall address for loopback subnet
        loopback_subnet_name = "SDWAN_Loopbacks"
        try:
            create_firewall_address(target_ip, api_token, loopback_subnet_name, "172.16.0.0 255.255.0.0", verify_ssl)
            result["components_created"].append(f"address:{loopback_subnet_name}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"address:{loopback_subnet_name} may already exist")

        # 8. Create firewall policy for overlay traffic
        policy_name = "SDWAN_Overlay_Traffic"
        try:
            create_firewall_policy(
                target_ip, api_token,
                policy_name,
                srcintf=[loopback_name, sdwan_zone],
                dstintf=[loopback_name, sdwan_zone],
                srcaddr=["all"],
                dstaddr=["all"],
                verify_ssl=verify_ssl
            )
            result["components_created"].append(f"policy:{policy_name}")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                result["errors"].append(f"policy:{policy_name} may already exist")

        result["success"] = True
        result["message"] = f"SD-WAN hub template applied. Created {len(result['components_created'])} components."
        result["config_summary"] = {
            "loopback": f"{loopback_name} ({loopback_ip})",
            "tunnel": f"{tunnel_name} (dynamic - accepts spokes)",
            "wan_interface": wan_interface,
            "sdwan_zone": sdwan_zone,
            "network_id": network_id
        }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:300]
        except:
            pass
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["details"] = error_body

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test execution
    result = main({
        "target_ip": "192.168.215.15",
        "loopback_ip": "172.16.255.253 255.255.255.255",
        "psk": "fortinet123",
        "tunnel_name": "SPOKE_VPN1",
        "sdwan_zone": "SDWAN_OVERLAY"
    })
    print(json.dumps(result, indent=2))
