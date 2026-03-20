#!/usr/bin/env python3
"""
SD-WAN IP Collision Check Tool
Validates proposed IP allocations against existing SD-WAN network inventory.
Prevents subnet overlap across sites.
"""

import ipaddress
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


def get_manifest_path() -> Path:
    """Get path to sdwan-manifest.yaml."""
    # Check environment variable first
    if "ULYSSES_CONFIG_PATH" in os.environ:
        return Path(os.environ["ULYSSES_CONFIG_PATH"]) / "sdwan-manifest.yaml"

    # Default paths
    if sys.platform == "win32":
        return Path("C:/ProgramData/Ulysses/config/sdwan-manifest.yaml")
    return Path("/etc/ulysses/config/sdwan-manifest.yaml")


def load_manifest() -> dict:
    """Load the SD-WAN manifest file."""
    manifest_path = get_manifest_path()

    if not manifest_path.exists():
        return {"devices": {}, "hub_registry": {}}

    with open(manifest_path, "r") as f:
        return yaml.safe_load(f) or {"devices": {}, "hub_registry": {}}


def parse_ip_to_network(ip_str: str):
    """Parse IP string (CIDR or 'IP MASK') to ipaddress.ip_network."""
    if not ip_str or ip_str.startswith("0.0.0.0"):
        return None

    try:
        if "/" in ip_str:
            return ipaddress.ip_network(ip_str, strict=False)
        elif " " in ip_str:
            # "IP MASK" format
            parts = ip_str.split()
            addr = parts[0]
            if addr == "0.0.0.0":
                return None
            mask = parts[1] if len(parts) > 1 else "255.255.255.255"
            return ipaddress.ip_network(f"{addr}/{mask}", strict=False)
        else:
            return ipaddress.ip_network(f"{ip_str}/32", strict=False)
    except ValueError:
        return None


def extract_allocations(manifest: dict, include_hub: bool = True) -> dict:
    """Extract all IP allocations from the manifest.

    Handles manifest structure where interfaces are grouped by type:
    interfaces:
      physical: [...]
      loopback: [...]
      tunnel: [...]
      vlan: [...]
    """
    allocations = {
        "loopbacks": [],
        "lan_subnets": [],
        "vlan_subnets": [],
        "management_ips": [],
        "by_site": {}
    }

    devices = manifest.get("devices", {})

    for device_key, device in devices.items():
        role = device.get("role", "unknown")

        # Skip hub if not included
        if role == "hub" and not include_hub:
            continue

        site_allocs = {
            "loopbacks": [],
            "lan_subnets": [],
            "vlan_subnets": [],
            "management_ip": None
        }

        # Management IP
        mgmt_ip = device.get("management_ip")
        if mgmt_ip:
            allocations["management_ips"].append({
                "ip": mgmt_ip,
                "site": device_key
            })
            site_allocs["management_ip"] = mgmt_ip

        # Interfaces - grouped by type (physical, loopback, tunnel, vlan)
        interfaces = device.get("interfaces", {})

        # Process loopback interfaces
        for iface in interfaces.get("loopback", []):
            ip = iface.get("ip", "")
            network = parse_ip_to_network(ip)
            if network:
                entry = {
                    "subnet": str(network),
                    "interface": iface.get("name", ""),
                    "site": device_key,
                    "network": network
                }
                allocations["loopbacks"].append(entry)
                site_allocs["loopbacks"].append(str(network))

        # Process VLAN interfaces
        for iface in interfaces.get("vlan", []):
            ip = iface.get("ip", "")
            network = parse_ip_to_network(ip)
            if network:
                entry = {
                    "subnet": str(network),
                    "interface": iface.get("name", ""),
                    "site": device_key,
                    "network": network,
                    "vlanid": iface.get("vlanid")
                }
                allocations["vlan_subnets"].append(entry)
                site_allocs["vlan_subnets"].append(str(network))

        # Process physical interfaces (check for LAN role)
        for iface in interfaces.get("physical", []):
            ip = iface.get("ip", "")
            network = parse_ip_to_network(ip)
            if network:
                iface_role = iface.get("role", "")
                iface_name = iface.get("name", "")

                # Check if this is a LAN interface
                if iface_role == "lan" or "lan" in iface_name.lower():
                    entry = {
                        "subnet": str(network),
                        "interface": iface_name,
                        "site": device_key,
                        "network": network
                    }
                    allocations["lan_subnets"].append(entry)
                    site_allocs["lan_subnets"].append(str(network))

        allocations["by_site"][device_key] = site_allocs

    return allocations


def check_overlap(proposed: list, existing: list) -> list:
    """Check if proposed subnets overlap with existing allocations."""
    collisions = []

    for prop_str in proposed:
        try:
            prop_net = ipaddress.ip_network(prop_str, strict=False)
        except ValueError as e:
            collisions.append({
                "proposed": prop_str,
                "error": f"Invalid subnet: {e}",
                "collision_type": "invalid_format"
            })
            continue

        for exist in existing:
            exist_net = exist.get("network")
            if exist_net is None:
                continue

            if prop_net.overlaps(exist_net):
                collisions.append({
                    "proposed": prop_str,
                    "conflicts_with": exist["subnet"],
                    "site": exist["site"],
                    "interface": exist.get("interface", ""),
                    "collision_type": "subnet_overlap"
                })

    return collisions


def check_management_ip(proposed_ip: str, existing: list) -> list:
    """Check if proposed management IP conflicts."""
    collisions = []

    try:
        prop_addr = ipaddress.ip_address(proposed_ip)
    except ValueError as e:
        return [{"proposed": proposed_ip, "error": str(e), "collision_type": "invalid_ip"}]

    for exist in existing:
        if exist["ip"] == proposed_ip:
            collisions.append({
                "proposed": proposed_ip,
                "conflicts_with": exist["ip"],
                "site": exist["site"],
                "collision_type": "duplicate_management_ip"
            })

    return collisions


def derive_from_site_id(site_id: int) -> dict:
    """Derive standard IP allocations from site_id."""
    return {
        "site_id": site_id,
        "loopback": f"172.16.0.{site_id}/32",
        "lan_subnet": f"10.{site_id}.1.0/24",
        "site_name": f"spoke-{site_id:02d}",
        "hostname": f"FG-Spoke-{site_id:02d}",
        "router_id": f"172.16.0.{site_id}",
        "location_id": f"172.16.0.{site_id}"
    }


def suggest_next_site_id(allocations: dict) -> dict:
    """Suggest the next available site_id."""
    used_ids = set()

    # Extract used site_ids from loopbacks (172.16.0.x pattern)
    for loopback in allocations.get("loopbacks", []):
        subnet = loopback.get("subnet", "")
        if subnet.startswith("172.16.0."):
            try:
                # Extract the last octet
                parts = subnet.split("/")[0].split(".")
                site_id = int(parts[3])
                used_ids.add(site_id)
            except (IndexError, ValueError):
                continue

    # Find next available
    for candidate in range(1, 255):
        if candidate not in used_ids:
            derived = derive_from_site_id(candidate)
            return {
                "next_available_site_id": candidate,
                "derived": derived,
                "used_site_ids": sorted(used_ids)
            }

    return {
        "error": "No site_ids available (1-254 exhausted)",
        "used_site_ids": sorted(used_ids)
    }


def action_check(params: dict) -> dict:
    """Check proposed allocations for collisions."""
    manifest = load_manifest()
    include_hub = params.get("include_hub", True)
    allocations = extract_allocations(manifest, include_hub)

    all_collisions = []

    # Check site_id derived subnets
    site_id = params.get("site_id")
    if site_id:
        derived = derive_from_site_id(site_id)
        proposed = [derived["loopback"], derived["lan_subnet"]]

        # Check loopback
        loopback_collisions = check_overlap(
            [derived["loopback"]],
            allocations["loopbacks"]
        )
        all_collisions.extend(loopback_collisions)

        # Check LAN
        lan_collisions = check_overlap(
            [derived["lan_subnet"]],
            allocations["lan_subnets"] + allocations["vlan_subnets"]
        )
        all_collisions.extend(lan_collisions)

    # Check explicit proposed subnets
    proposed_subnets = params.get("proposed_subnets", [])
    if proposed_subnets:
        all_existing = (
            allocations["loopbacks"] +
            allocations["lan_subnets"] +
            allocations["vlan_subnets"]
        )
        subnet_collisions = check_overlap(proposed_subnets, all_existing)
        all_collisions.extend(subnet_collisions)

    # Check management IP
    proposed_mgmt = params.get("proposed_management_ip")
    if proposed_mgmt:
        mgmt_collisions = check_management_ip(
            proposed_mgmt,
            allocations["management_ips"]
        )
        all_collisions.extend(mgmt_collisions)

    valid = len(all_collisions) == 0

    result = {
        "success": True,
        "action": "check",
        "valid": valid,
        "collisions": all_collisions
    }

    if site_id:
        result["checked_site_id"] = site_id
        result["derived_allocations"] = derive_from_site_id(site_id)

    if valid:
        result["message"] = "No IP collisions detected - safe to proceed"
    else:
        result["message"] = f"Found {len(all_collisions)} collision(s) - resolve before provisioning"

    return result


def action_list_allocations(params: dict) -> dict:
    """List all current IP allocations."""
    manifest = load_manifest()
    include_hub = params.get("include_hub", True)
    allocations = extract_allocations(manifest, include_hub)

    # Clean up network objects for JSON serialization
    clean_allocations = {
        "loopbacks": [
            {"subnet": a["subnet"], "site": a["site"], "interface": a.get("interface", "")}
            for a in allocations["loopbacks"]
        ],
        "lan_subnets": [
            {"subnet": a["subnet"], "site": a["site"], "interface": a.get("interface", "")}
            for a in allocations["lan_subnets"]
        ],
        "vlan_subnets": [
            {"subnet": a["subnet"], "site": a["site"], "interface": a.get("interface", "")}
            for a in allocations["vlan_subnets"]
        ],
        "management_ips": allocations["management_ips"],
        "by_site": allocations["by_site"]
    }

    return {
        "success": True,
        "action": "list-allocations",
        "allocations": clean_allocations,
        "summary": {
            "total_loopbacks": len(allocations["loopbacks"]),
            "total_lan_subnets": len(allocations["lan_subnets"]),
            "total_vlan_subnets": len(allocations["vlan_subnets"]),
            "total_sites": len(allocations["by_site"])
        },
        "message": f"Found {len(allocations['by_site'])} tracked sites"
    }


def action_suggest_next(params: dict) -> dict:
    """Suggest next available site_id with derived IPs."""
    manifest = load_manifest()
    allocations = extract_allocations(manifest, include_hub=False)  # Exclude hub for site_id

    suggestion = suggest_next_site_id(allocations)

    if "error" in suggestion:
        return {
            "success": False,
            "action": "suggest-next",
            "message": suggestion["error"],
            "used_site_ids": suggestion["used_site_ids"]
        }

    return {
        "success": True,
        "action": "suggest-next",
        "suggestion": suggestion,
        "message": f"Next available site_id is {suggestion['next_available_site_id']}"
    }


def main(context) -> dict:
    """Main entry point.

    Args:
        context: ExecutionContext containing:
            - parameters: Tool parameters (action, site_id, etc.)
            - credentials: Credential vault data (optional)
            - metadata: Tool manifest and execution metadata

    Returns:
        dict with success status and results
    """
    # Extract parameters from context
    params = context.parameters if hasattr(context, 'parameters') else context

    action = params.get("action")

    if action == "check":
        return action_check(params)
    elif action == "list-allocations":
        return action_list_allocations(params)
    elif action == "suggest-next":
        return action_suggest_next(params)
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "valid_actions": ["check", "list-allocations", "suggest-next"]
        }


if __name__ == "__main__":
    # CLI mode for testing
    if len(sys.argv) > 1:
        params = json.loads(sys.argv[1])
    else:
        # Default test
        params = {"action": "suggest-next"}

    # Create mock context for CLI testing
    class MockContext:
        def __init__(self, params):
            self.parameters = params

    result = main(MockContext(params))
    print(json.dumps(result, indent=2))
