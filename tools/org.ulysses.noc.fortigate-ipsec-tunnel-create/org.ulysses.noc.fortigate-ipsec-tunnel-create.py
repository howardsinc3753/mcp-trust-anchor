#!/usr/bin/env python3
"""
FortiGate IPsec Tunnel Create Tool

Creates a SINGLE IPsec tunnel (Phase1 + Phase2) on a FortiGate device.
This tool is for adding tunnels to EXISTING configurations, NOT for initial SD-WAN setup.

Key Features:
- Automatic net-device setting based on tunnel type (CRITICAL for SD-WAN)
- Unique network-id validation guidance
- Proper handling of static (spoke) vs dynamic (hub) tunnels

IMPORTANT LESSONS LEARNED:
1. PSK must match exactly on both ends - keep simple during testing
2. network_id MUST be unique per tunnel for SD-WAN
3. net-device=disable is REQUIRED for dynamic/hub tunnels to work with SD-WAN
4. Tunnel won't come up until added to firewall policy or SD-WAN zone
5. SD-WAN member source IP must exist or use 0.0.0.0

FortiOS 7.6+ compatible with REST API Bearer token authentication.
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
    """
    config_paths = [
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

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


def check_tunnel_exists(host: str, api_token: str, tunnel_name: str,
                        verify_ssl: bool = False) -> bool:
    """Check if a tunnel with this name already exists."""
    try:
        make_api_request(host, f"/api/v2/cmdb/vpn.ipsec/phase1-interface/{tunnel_name}",
                        api_token, "GET", verify_ssl=verify_ssl)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def detect_wan_interface(host: str, api_token: str, verify_ssl: bool = False) -> str:
    """Auto-detect the WAN interface."""
    try:
        result = make_api_request(host, "/api/v2/cmdb/system/interface", api_token,
                                  "GET", verify_ssl=verify_ssl)
        interfaces = result.get("results", [])

        # Priority order: wan1, wan, wan2, port1, any physical with IP
        for name in ["wan1", "wan", "wan2"]:
            for iface in interfaces:
                if iface.get("name") == name and iface.get("type") == "physical":
                    ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                    if ip and not ip.startswith("0.0.0.0"):
                        return name

        for iface in interfaces:
            if iface.get("name") == "port1" and iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return "port1"

        for iface in interfaces:
            if iface.get("type") == "physical":
                ip = iface.get("ip", "0.0.0.0 0.0.0.0")
                if ip and not ip.startswith("0.0.0.0"):
                    return iface.get("name")

        return "wan1"
    except Exception:
        return "wan1"


def create_phase1_static(host: str, api_token: str, name: str, interface: str,
                          remote_gw: str, psk: str, network_id: int,
                          localid: str = None, ike_version: int = 2,
                          proposal: str = "aes256-sha256", dhgrp: str = "20 21",
                          exchange_ip: str = None, transport: str = "udp",
                          verify_ssl: bool = False) -> dict:
    """Create IPsec Phase1 for STATIC tunnel (Spoke/Initiator).

    Static tunnels:
    - Initiate connection to a known remote gateway
    - Use net-device=enable (interface available immediately)
    - Require remote-gw parameter

    Key settings from Fortinet 4D-Demo:
    - exchange-ip-addr4: Loopback IP for SD-WAN overlay routing
    - auto-discovery-sender/receiver: Enable ADVPN shortcut discovery
    - dhgrp: DH groups 20 21 for modern security
    - transport: UDP for consistent overlay behavior
    """
    data = {
        "name": name,
        "type": "static",
        "interface": interface,
        "ike-version": ike_version,
        "peertype": "any",
        "net-device": "enable",  # Static tunnels CAN use net-device enable
        "proposal": proposal,
        "dhgrp": dhgrp,
        "add-route": "disable",
        "dpd": "on-idle",
        "dpd-retrycount": 3,
        "dpd-retryinterval": 5,
        "auto-discovery-sender": "enable",  # Spoke sends ADVPN shortcuts
        "auto-discovery-receiver": "enable",  # Spoke receives ADVPN shortcuts
        "network-overlay": "enable",
        "network-id": network_id,
        "transport": transport,
        "remote-gw": remote_gw,
        "psksecret": psk
    }

    if localid:
        data["localid"] = localid

    if exchange_ip:
        data["exchange-ip-addr4"] = exchange_ip

    return make_api_request(host, "/api/v2/cmdb/vpn.ipsec/phase1-interface",
                            api_token, "POST", data, verify_ssl)


def create_phase1_dynamic(host: str, api_token: str, name: str, interface: str,
                           psk: str, network_id: int, ike_version: int = 2,
                           proposal: str = "aes256-sha256", dhgrp: str = "20 21",
                           exchange_ip: str = None, transport: str = "auto",
                           verify_ssl: bool = False) -> dict:
    """Create IPsec Phase1 for DYNAMIC tunnel (Hub/Responder).

    Dynamic tunnels:
    - Accept connections from any spoke (dial-up)
    - MUST use net-device=disable for SD-WAN compatibility
    - No remote-gw (accepts from any source)

    CRITICAL: net-device MUST be "disable" for dynamic tunnels!
    With net-device=enable, the interface won't appear in SD-WAN datasource
    and you'll get "entry not found in datasource" errors.

    Key settings from Fortinet 4D-Demo:
    - exchange-ip-addr4: Loopback IP for SD-WAN overlay routing
    - auto-discovery-sender: Enable ADVPN shortcut discovery (hub sends)
    - dhgrp: DH groups 20 21 for modern security
    - transport: auto for hub flexibility
    """
    data = {
        "name": name,
        "type": "dynamic",  # CRITICAL: Hub must use dynamic type
        "interface": interface,
        "ike-version": ike_version,
        "peertype": "any",
        "net-device": "disable",  # CRITICAL: MUST be disable for dial-up/SD-WAN!
        "proposal": proposal,
        "dhgrp": dhgrp,
        "add-route": "disable",
        "dpd": "on-idle",
        "dpd-retrycount": 3,
        "dpd-retryinterval": 60,
        "auto-discovery-sender": "enable",  # Hub sends ADVPN shortcuts to spokes
        "network-overlay": "enable",
        "network-id": network_id,
        "transport": transport,
        "psksecret": psk
    }

    if exchange_ip:
        data["exchange-ip-addr4"] = exchange_ip

    return make_api_request(host, "/api/v2/cmdb/vpn.ipsec/phase1-interface",
                            api_token, "POST", data, verify_ssl)


def create_phase2(host: str, api_token: str, name: str, phase1name: str,
                  proposal: str = "aes256-sha256", dhgrp: str = "20 21",
                  verify_ssl: bool = False) -> dict:
    """Create IPsec Phase2 interface."""
    data = {
        "name": name,
        "phase1name": phase1name,
        "proposal": proposal,
        "pfs": "enable",
        "dhgrp": dhgrp,
        "auto-negotiate": "enable"
    }
    return make_api_request(host, "/api/v2/cmdb/vpn.ipsec/phase2-interface",
                            api_token, "POST", data, verify_ssl)


def main(context) -> dict[str, Any]:
    """
    Create a single IPsec tunnel (Phase1 + Phase2) on FortiGate.

    This tool creates ONLY the IPsec tunnel - it does NOT:
    - Create SD-WAN zones
    - Create firewall policies
    - Configure BGP

    After creation, you must add the tunnel to an SD-WAN zone or
    firewall policy for it to negotiate and come up.

    Args:
        context: ExecutionContext with parameters:
            Required:
            - target_ip: FortiGate management IP
            - tunnel_name: Name for Phase1 and Phase2
            - tunnel_type: "static" (spoke) or "dynamic" (hub)
            - psk: Pre-shared key (MUST match peer)
            - network_id: Unique overlay ID 1-255

            Conditional:
            - remote_gw: Hub WAN IP (required for static tunnels)

            Optional:
            - interface: WAN interface (auto-detect if not set)
            - localid: Local ID for hub identification (spoke tunnels)
            - exchange_ip: Loopback IP for SD-WAN overlay routing (recommended)
            - transport: Transport mode "udp" or "auto" (default: udp for spoke, auto for hub)
            - ike_version: 1 or 2 (default: 2)
            - proposal: Encryption proposal (default: aes256-sha256)
            - dhgrp: DH groups (default: "20 21")
            - verify_ssl: Verify SSL certificate (default: false)

    Returns:
        dict: Result with tunnel details and next steps
    """
    if hasattr(context, "parameters"):
        args = context.parameters
    else:
        args = context

    # Required parameters
    target_ip = args.get("target_ip")
    tunnel_name = args.get("tunnel_name")
    tunnel_type = args.get("tunnel_type", "").lower()
    psk = args.get("psk")
    network_id = args.get("network_id")

    # Conditional parameters
    remote_gw = args.get("remote_gw")

    # Optional parameters
    interface = args.get("interface")
    localid = args.get("localid")
    exchange_ip = args.get("exchange_ip")  # Loopback IP for SD-WAN overlay
    transport = args.get("transport")  # Defaults set per tunnel type below
    ike_version = args.get("ike_version", 2)
    proposal = args.get("proposal", "aes256-sha256")
    dhgrp = args.get("dhgrp", "20 21")
    verify_ssl = args.get("verify_ssl", False)

    # Set transport default based on tunnel type
    if transport is None:
        transport = "udp" if tunnel_type == "static" else "auto"

    # Validation
    if not target_ip:
        return {
            "success": False,
            "error": "target_ip is required",
            "hint": "Run fortigate-health-check first to verify device connectivity"
        }

    if not tunnel_name:
        return {
            "success": False,
            "error": "tunnel_name is required",
            "hint": "Example: HUB2-VPN2 for spoke, SPOKE_VPN2 for hub"
        }

    if tunnel_type not in ["static", "dynamic"]:
        return {
            "success": False,
            "error": "tunnel_type must be 'static' or 'dynamic'",
            "hint": "Use 'static' for Spoke (initiates to hub), 'dynamic' for Hub (accepts spokes)"
        }

    if not psk:
        return {
            "success": False,
            "error": "psk (pre-shared key) is required",
            "hint": "PSK must be IDENTICAL on both hub and spoke. Keep simple for testing."
        }

    if not network_id:
        return {
            "success": False,
            "error": "network_id is required (1-255)",
            "hint": "MUST be unique per tunnel. Check existing tunnels for used IDs."
        }

    if tunnel_type == "static" and not remote_gw:
        return {
            "success": False,
            "error": "remote_gw is required for static (spoke) tunnels",
            "hint": "Provide the Hub's WAN IP address"
        }

    # Get credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {
            "success": False,
            "error": f"No credentials found for {target_ip}",
            "hint": "Use credential-manager or fortigate-device-register to add credentials first",
            "credential_paths_checked": [
                str(Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml"),
            ]
        }

    api_token = creds.get("api_token")
    if creds.get("verify_ssl") is not None:
        verify_ssl = creds["verify_ssl"]

    # Auto-detect interface if not specified
    if not interface:
        interface = detect_wan_interface(target_ip, api_token, verify_ssl)

    result = {
        "success": False,
        "target_ip": target_ip,
        "tunnel_name": tunnel_name,
        "tunnel_type": tunnel_type,
        "network_id": network_id,
        "interface": interface,
        "phase1_created": False,
        "phase2_created": False
    }

    try:
        # Check if tunnel already exists
        if check_tunnel_exists(target_ip, api_token, tunnel_name, verify_ssl):
            return {
                "success": False,
                "error": f"Tunnel '{tunnel_name}' already exists",
                "hint": "Use a different name or delete the existing tunnel first"
            }

        # Create Phase1 based on tunnel type
        if tunnel_type == "static":
            # Spoke/Initiator tunnel
            if not localid:
                localid = f"spoke-{tunnel_name}"

            create_phase1_static(
                target_ip, api_token, tunnel_name, interface,
                remote_gw, psk, network_id, localid,
                ike_version, proposal, dhgrp, exchange_ip, transport, verify_ssl
            )
            result["net_device"] = "enable"
            result["remote_gw"] = remote_gw
            result["localid"] = localid
            result["transport"] = transport
            if exchange_ip:
                result["exchange_ip"] = exchange_ip

        else:
            # Hub/Responder tunnel (dynamic)
            create_phase1_dynamic(
                target_ip, api_token, tunnel_name, interface,
                psk, network_id, ike_version, proposal, dhgrp, exchange_ip, transport, verify_ssl
            )
            result["net_device"] = "disable"
            result["transport"] = transport
            if exchange_ip:
                result["exchange_ip"] = exchange_ip

        result["phase1_created"] = True

        # Create Phase2
        create_phase2(target_ip, api_token, tunnel_name, tunnel_name,
                     proposal, dhgrp, verify_ssl)
        result["phase2_created"] = True

        result["success"] = True
        result["message"] = f"IPsec tunnel '{tunnel_name}' created successfully"

        # Provide next steps based on tunnel type
        if tunnel_type == "static":
            result["next_steps"] = [
                "Add tunnel interface to SD-WAN zone (member)",
                "Or create firewall policy with tunnel as srcintf/dstintf",
                f"Ensure Hub has matching tunnel with network_id={network_id}",
                f"Verify PSK matches on hub device"
            ]
        else:
            result["next_steps"] = [
                "Add tunnel interface to SD-WAN zone (member)",
                "Or create firewall policy with tunnel as srcintf/dstintf",
                f"Ensure Spoke connects with matching network_id={network_id}",
                "Spoke must use PSK identical to this hub tunnel"
            ]

        result["warnings"] = []
        if tunnel_type == "dynamic":
            result["warnings"].append(
                "net-device is set to 'disable' (required for dynamic tunnels with SD-WAN)"
            )

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:500]
        except:
            pass
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["details"] = error_body

        # Provide helpful hints based on error
        if e.code == 500 and "already exist" in error_body.lower():
            result["hint"] = f"Tunnel '{tunnel_name}' may already exist"
        elif e.code == 401:
            result["hint"] = "Authentication failed - check API token"
        elif e.code == 403:
            result["hint"] = "Permission denied - API user may lack write access"

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test: Create static spoke tunnel
    print("=== Testing Static (Spoke) Tunnel ===")
    result = main({
        "target_ip": "192.168.209.30",
        "tunnel_name": "TEST_VPN",
        "tunnel_type": "static",
        "remote_gw": "192.168.215.15",
        "psk": "password",
        "network_id": 99
    })
    print(json.dumps(result, indent=2))
