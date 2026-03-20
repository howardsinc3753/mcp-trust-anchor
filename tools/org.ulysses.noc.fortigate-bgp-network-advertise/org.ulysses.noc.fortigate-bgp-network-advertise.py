#!/usr/bin/env python3
"""
FortiGate BGP Network Advertise Tool

CRUD operations for BGP network statements on FortiGate devices.
Supports adding, removing, and listing BGP network prefixes.

Canonical ID: org.ulysses.noc.fortigate-bgp-network-advertise/1.0.1
"""

import json
import sys
import os
import urllib3
import ipaddress
from typing import Optional
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
        # urllib fallback
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


def parse_prefix(prefix_str: str) -> tuple:
    """
    Parse prefix string to (network, mask) format.
    Accepts: "10.0.0.0/24" or "10.0.0.0 255.255.255.0"
    Returns: ("10.0.0.0", "255.255.255.0")
    """
    prefix_str = prefix_str.strip()

    if '/' in prefix_str:
        # CIDR format
        try:
            network = ipaddress.ip_network(prefix_str, strict=False)
            return (str(network.network_address), str(network.netmask))
        except ValueError as e:
            raise ValueError(f"Invalid CIDR prefix: {prefix_str} - {e}")
    elif ' ' in prefix_str:
        # Space-separated format
        parts = prefix_str.split()
        if len(parts) != 2:
            raise ValueError(f"Invalid prefix format: {prefix_str}")
        ip_str, mask_str = parts
        # Validate
        try:
            ipaddress.ip_address(ip_str)
            ipaddress.ip_address(mask_str)
        except ValueError as e:
            raise ValueError(f"Invalid IP or mask: {e}")
        return (ip_str, mask_str)
    else:
        raise ValueError(f"Invalid prefix format: {prefix_str}. Use CIDR (10.0.0.0/24) or mask (10.0.0.0 255.255.255.0)")


def prefix_to_display(prefix_str: str) -> str:
    """Convert FortiOS prefix format to CIDR for display."""
    if ' ' in prefix_str:
        parts = prefix_str.split()
        if len(parts) == 2:
            try:
                network = ipaddress.ip_network(f"{parts[0]}/{parts[1]}", strict=False)
                return str(network)
            except:
                pass
    return prefix_str


def get_bgp_config(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """Get current BGP configuration."""
    result = api_request(host, api_token, "GET", "/cmdb/router/bgp", verify_ssl=verify_ssl)
    return result


def get_bgp_networks(host: str, api_token: str, verify_ssl: bool = False) -> list:
    """Get list of BGP network statements."""
    result = get_bgp_config(host, api_token, verify_ssl)

    if not result.get("success"):
        return []

    # Handle different response formats
    # FortiOS returns results as dict for BGP, not a list
    data = result.get("data", {})
    results = data.get("results", data)
    if isinstance(results, list) and len(results) > 0:
        bgp_data = results[0]
    elif isinstance(results, dict):
        bgp_data = results
    else:
        bgp_data = data

    networks = bgp_data.get("network", [])

    return networks


def find_next_network_id(networks: list) -> int:
    """Find next available network ID."""
    if not networks:
        return 1

    used_ids = set()
    for net in networks:
        if 'id' in net:
            used_ids.add(net['id'])

    # Find first available ID
    next_id = 1
    while next_id in used_ids:
        next_id += 1

    return next_id


def find_network_by_prefix(networks: list, prefix: str) -> Optional[dict]:
    """Find network entry by prefix (supports both formats)."""
    try:
        target_net, target_mask = parse_prefix(prefix)
        target_key = f"{target_net} {target_mask}"
    except ValueError:
        return None

    for net in networks:
        net_prefix = net.get("prefix", "")
        if net_prefix == target_key:
            return net
        # Also try normalized comparison
        try:
            net_net, net_mask = parse_prefix(net_prefix)
            if net_net == target_net and net_mask == target_mask:
                return net
        except:
            pass

    return None


def add_bgp_network(host: str, api_token: str, prefix: str,
                    network_id: int = None, route_map: str = None,
                    verify_ssl: bool = False) -> dict:
    """Add a BGP network statement."""
    # Parse and validate prefix
    try:
        net_addr, net_mask = parse_prefix(prefix)
        prefix_formatted = f"{net_addr} {net_mask}"
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Get current networks
    networks = get_bgp_networks(host, api_token, verify_ssl)

    # Check for duplicate
    existing = find_network_by_prefix(networks, prefix)
    if existing:
        return {
            "success": False,
            "error": f"Network {prefix_to_display(prefix_formatted)} already exists with ID {existing.get('id')}"
        }

    # Determine network ID
    if network_id is None:
        network_id = find_next_network_id(networks)

    # Build network entry
    network_entry = {
        "id": network_id,
        "prefix": prefix_formatted
    }

    if route_map:
        network_entry["route-map"] = route_map

    # Add via API - POST to collection endpoint (without ID in URL)
    endpoint = "/cmdb/router/bgp/network"
    result = api_request(host, api_token, "POST", endpoint, data=network_entry, verify_ssl=verify_ssl)

    if result.get("success"):
        return {
            "success": True,
            "network_id": network_id,
            "prefix": prefix_formatted,
            "route_map": route_map or ""
        }
    else:
        # Try PUT to specific entry if POST fails
        endpoint_with_id = f"/cmdb/router/bgp/network/{network_id}"
        result = api_request(host, api_token, "PUT", endpoint_with_id, data=network_entry, verify_ssl=verify_ssl)
        if result.get("success"):
            return {
                "success": True,
                "network_id": network_id,
                "prefix": prefix_formatted,
                "route_map": route_map or ""
            }

        error_msg = result.get("error", "")
        if "data" in result and "cli_error" in str(result.get("data", {})):
            error_msg = result["data"].get("cli_error", error_msg)
        return {"success": False, "error": f"Failed to add network: {error_msg}", "details": result}


def remove_bgp_network(host: str, api_token: str, network_id: int = None,
                       prefix: str = None, verify_ssl: bool = False) -> dict:
    """Remove a BGP network statement by ID or prefix."""
    # Get current networks
    networks = get_bgp_networks(host, api_token, verify_ssl)

    target_id = network_id
    target_prefix = None

    if prefix and not network_id:
        # Find by prefix
        existing = find_network_by_prefix(networks, prefix)
        if not existing:
            return {"success": False, "error": f"Network {prefix} not found"}
        target_id = existing.get("id")
        target_prefix = existing.get("prefix")
    elif network_id:
        # Verify ID exists
        found = False
        for net in networks:
            if net.get("id") == network_id:
                found = True
                target_prefix = net.get("prefix")
                break
        if not found:
            return {"success": False, "error": f"Network ID {network_id} not found"}
    else:
        return {"success": False, "error": "Must specify network_id or prefix"}

    # Delete via API
    endpoint = f"/cmdb/router/bgp/network/{target_id}"
    result = api_request(host, api_token, "DELETE", endpoint, verify_ssl=verify_ssl)

    if result.get("success") or result.get("status_code") == 200:
        return {
            "success": True,
            "network_id": target_id,
            "prefix": target_prefix
        }
    else:
        error_msg = result.get("error", "Unknown error")
        return {"success": False, "error": f"Failed to remove network: {error_msg}", "details": result}


def list_bgp_networks(host: str, api_token: str, verify_ssl: bool = False) -> dict:
    """List all BGP network statements."""
    networks = get_bgp_networks(host, api_token, verify_ssl)

    formatted_networks = []
    for net in networks:
        formatted_networks.append({
            "id": net.get("id"),
            "prefix": prefix_to_display(net.get("prefix", "")),
            "prefix_raw": net.get("prefix", ""),
            "route_map": net.get("route-map", "")
        })

    return {
        "success": True,
        "count": len(formatted_networks),
        "networks": formatted_networks
    }


def main(context) -> dict:
    """Main entry point for the tool."""
    # Handle both ExecutionContext (MCP) and dict (CLI)
    if hasattr(context, 'parameters'):
        params = context.parameters
    else:
        params = context

    # Extract parameters
    target_ip = params.get("target_ip")
    action = params.get("action", "").lower()
    prefix = params.get("prefix")
    network_id = params.get("network_id")
    route_map = params.get("route_map")
    verify_ssl = params.get("verify_ssl", False)

    # Validate required params
    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    if action not in ["add", "remove", "list"]:
        return {"success": False, "error": f"Invalid action: {action}. Must be 'add', 'remove', or 'list'"}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {"success": False, "error": f"No credentials found for {target_ip}"}
    api_token = creds.get("api_token")

    # Verify BGP is configured
    bgp_result = get_bgp_config(target_ip, api_token, verify_ssl)
    if not bgp_result.get("success"):
        return {"success": False, "error": f"Failed to get BGP config: {bgp_result.get('error', 'Unknown error')}"}

    # Handle different response formats
    # FortiOS returns results as dict for BGP, not a list
    data = bgp_result.get("data", {})
    results = data.get("results", data)
    if isinstance(results, list) and len(results) > 0:
        bgp_data = results[0]
    elif isinstance(results, dict):
        bgp_data = results
    else:
        bgp_data = data

    bgp_as = bgp_data.get("as")
    if not bgp_as:
        return {"success": False, "error": "BGP is not configured on this device (no AS number)"}

    # Execute action
    result = {"action": action, "target_ip": target_ip, "bgp_as": bgp_as}

    if action == "list":
        list_result = list_bgp_networks(target_ip, api_token, verify_ssl)
        result.update(list_result)
        if list_result["success"]:
            result["message"] = f"Found {list_result['count']} BGP network statement(s)"

    elif action == "add":
        if not prefix:
            return {"success": False, "error": "prefix is required for 'add' action"}

        add_result = add_bgp_network(target_ip, api_token, prefix, network_id, route_map, verify_ssl)
        result.update(add_result)
        if add_result["success"]:
            result["message"] = f"Added network {prefix_to_display(add_result['prefix'])} with ID {add_result['network_id']}"
            result["networks"] = [{
                "id": add_result["network_id"],
                "prefix": prefix_to_display(add_result["prefix"]),
                "route_map": add_result.get("route_map", "")
            }]

    elif action == "remove":
        if not prefix and not network_id:
            return {"success": False, "error": "prefix or network_id is required for 'remove' action"}

        remove_result = remove_bgp_network(target_ip, api_token, network_id, prefix, verify_ssl)
        result.update(remove_result)
        if remove_result["success"]:
            result["message"] = f"Removed network ID {remove_result['network_id']} ({prefix_to_display(remove_result['prefix'])})"
            result["networks"] = [{
                "id": remove_result["network_id"],
                "prefix": prefix_to_display(remove_result["prefix"]),
                "route_map": ""
            }]

    return result


if __name__ == "__main__":
    # Parse command line arguments or stdin
    if len(sys.argv) > 1:
        # Arguments passed directly
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
                params[key] = val
        result = main(params)
    else:
        # Read from stdin
        try:
            input_data = sys.stdin.read()
            params = json.loads(input_data) if input_data.strip() else {}
            result = main(params)
        except json.JSONDecodeError as e:
            result = {"success": False, "error": f"Invalid JSON input: {e}"}

    print(json.dumps(result, indent=2))
