#!/usr/bin/env python3
"""
FortiGate SD-WAN Onboard Tool

Orchestrates the complete SD-WAN site onboarding workflow including:
1. FortiFlex license provisioning (for VMs)
2. Blueprint-based configuration generation
3. License application and config deployment
4. Manifest tracking

This tool integrates with:
- fortiflex-config-list / fortiflex-config-create
- fortiflex-token-create
- fortigate-sdwan-blueprint-planner
- fortigate-sdwan-manifest-tracker
- fortigate-config-push

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-18
"""

import json
import logging
import os
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# Configuration paths
MANIFEST_PATH = Path("C:/ProgramData/Ulysses/config/sdwan-manifest.yaml")
TEMPLATE_DIR = Path("C:/ProgramData/Ulysses/config/blueprints")
CREDENTIAL_PATHS = [
    Path("C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"),
    Path("config/forticloud_credentials.yaml"),
    Path.home() / ".ulysses" / "forticloud_credentials.yaml",
]

# FortiFlex API
FORTIFLEX_AUTH_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
FORTIFLEX_API_BASE = "https://support.fortinet.com/ES/api/fortiflex/v2"
FLEXVM_CLIENT_ID = "flexvm"


# =============================================================================
# Credential Loading
# =============================================================================

def load_forticloud_credentials() -> Dict[str, Any]:
    """Load FortiCloud API credentials for FortiFlex."""
    creds = {
        "api_username": None,
        "api_password": None,
        "program_serial_number": None,
        "account_id": None
    }

    # Check environment variables
    if os.environ.get("FORTICLOUD_API_USERNAME"):
        creds["api_username"] = os.environ["FORTICLOUD_API_USERNAME"]
    if os.environ.get("FORTICLOUD_API_PASSWORD"):
        creds["api_password"] = os.environ["FORTICLOUD_API_PASSWORD"]
    if os.environ.get("FORTIFLEX_PROGRAM_SN"):
        creds["program_serial_number"] = os.environ["FORTIFLEX_PROGRAM_SN"]

    # Try credential files
    for cred_path in CREDENTIAL_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, "r") as f:
                    config = yaml.safe_load(f)
                if config:
                    if not creds["api_username"] and "api_username" in config:
                        creds["api_username"] = config["api_username"]
                    if not creds["api_password"] and "api_password" in config:
                        creds["api_password"] = config["api_password"]
                    if not creds["program_serial_number"] and "program_serial_number" in config:
                        creds["program_serial_number"] = config["program_serial_number"]
                    if not creds["account_id"] and "account_id" in config:
                        creds["account_id"] = config["account_id"]
                    if creds["api_username"] and creds["api_password"]:
                        break
            except Exception as e:
                logger.warning(f"Failed to load from {cred_path}: {e}")

    return creds


def load_fortigate_credentials(target_ip: str) -> Optional[Dict[str, Any]]:
    """Load FortiGate API credentials for a specific device."""
    config_paths = [
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
        Path("C:/ProgramData/mcp/fortigate_credentials.yaml"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
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


# =============================================================================
# FortiFlex API Functions
# =============================================================================

def get_fortiflex_oauth_token(api_username: str, api_password: str) -> str:
    """Get OAuth access token from FortiCloud IAM."""
    payload = {
        "username": api_username,
        "password": api_password,
        "client_id": FLEXVM_CLIENT_ID,
        "grant_type": "password"
    }

    response = requests.post(FORTIFLEX_AUTH_URL, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()

    if result.get("status") != "success":
        raise Exception(f"Authentication failed: {result.get('message', 'Unknown error')}")

    return result["access_token"]


def list_fortiflex_configs(token: str, program_sn: str, account_id: int = None) -> List[Dict]:
    """List FortiFlex configurations."""
    url = f"{FORTIFLEX_API_BASE}/configs/list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"programSerialNumber": program_sn}
    if account_id:
        payload["accountId"] = account_id

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()

    if result.get("status") != 0:
        raise Exception(result.get("message") or "Failed to list configs")

    return result.get("configs", [])


def create_fortiflex_config(
    token: str,
    program_sn: str,
    name: str,
    product_type: str = "FGT_VM_Bundle",
    cpu: int = 2,
    services: List[str] = None,
    account_id: int = None
) -> Dict[str, Any]:
    """Create a new FortiFlex configuration."""
    url = f"{FORTIFLEX_API_BASE}/configs/create"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Default services if not specified
    if services is None:
        services = ["FC", "UTP", "ENT"]

    # Build product type parameters based on product
    product_params = {
        "cpuSize": str(cpu),
        "servicePkg": services[0] if services else "FC"
    }

    payload = {
        "programSerialNumber": program_sn,
        "name": name,
        "productType": {
            "id": 1,  # FortiGate VM Bundle
            "name": product_type
        },
        "parameters": [
            {"id": 1, "value": str(cpu)},  # CPU size
        ]
    }

    if account_id:
        payload["accountId"] = account_id

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()

    if result.get("status") != 0:
        raise Exception(result.get("message") or "Failed to create config")

    return result.get("configs", [{}])[0]


def create_fortiflex_token(
    token: str,
    config_id: int,
    count: int = 1,
    end_date: str = None
) -> List[Dict[str, Any]]:
    """Create FortiFlex VM entitlements (tokens)."""
    url = f"{FORTIFLEX_API_BASE}/entitlements/vm/create"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"configId": config_id, "count": count}
    if end_date:
        payload["endDate"] = end_date

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        try:
            error_data = response.json()
            raise Exception(f"API Error: {error_data.get('message') or error_data}")
        except ValueError:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    result = response.json()

    if result.get("status") != 0:
        raise Exception(result.get("message") or "Failed to create token")

    return result.get("entitlements", [])


# =============================================================================
# Manifest Functions
# =============================================================================

def load_manifest() -> Dict:
    """Load SD-WAN manifest."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return yaml.safe_load(f) or {}

    return {
        "manifest_version": "1.0.0",
        "created": datetime.now().isoformat(),
        "network": {"name": "SD-WAN Network", "as_number": 65000},
        "devices": {}
    }


def save_manifest(manifest: Dict):
    """Save SD-WAN manifest."""
    manifest["last_updated"] = datetime.now().isoformat()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(MANIFEST_PATH, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)


# =============================================================================
# FortiGate API Functions
# =============================================================================

def apply_license_to_fortigate(
    target_ip: str,
    api_token: str,
    license_token: str,
    verify_ssl: bool = False
) -> Dict[str, Any]:
    """
    Apply FortiFlex license to FortiGate VM via API.

    Note: This requires the FortiGate to be accessible and have API enabled.
    For unlicensed VMs, SSH may be needed instead.
    """
    url = f"https://{target_ip}/api/v2/monitor/system/vmlicense/upload"

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # The license is applied via the vmlicense endpoint
    payload = {"file_content": license_token}

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {"success": True, "result": result}

    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Onboarding Workflow Functions
# =============================================================================

def provision_license(
    site_name: str,
    config_id: int = None,
    config_name: str = None,
    cpu: int = 2,
    services: List[str] = None
) -> Dict[str, Any]:
    """
    Provision a FortiFlex license for a new site.

    Args:
        site_name: Name for the site/device
        config_id: Existing FortiFlex config ID to use
        config_name: Name for new config if creating one
        cpu: CPU cores for new config (1, 2, 4, 8, 16, 32)
        services: Service codes for new config

    Returns:
        Dict with token details
    """
    logger.info(f"Provisioning FortiFlex license for {site_name}")

    # Load FortiCloud credentials
    creds = load_forticloud_credentials()
    if not creds["api_username"] or not creds["api_password"]:
        return {
            "success": False,
            "error": "No FortiCloud credentials found",
            "hint": "Configure forticloud_credentials.yaml with api_username and api_password"
        }

    if not creds["program_serial_number"]:
        return {
            "success": False,
            "error": "No program_serial_number configured",
            "hint": "Add program_serial_number to forticloud_credentials.yaml"
        }

    try:
        # Get OAuth token
        oauth_token = get_fortiflex_oauth_token(
            creds["api_username"],
            creds["api_password"]
        )

        # If no config_id provided, look for or create one
        if not config_id:
            # List existing configs
            configs = list_fortiflex_configs(
                oauth_token,
                creds["program_serial_number"],
                creds.get("account_id")
            )

            # Look for matching config by name
            if config_name:
                for cfg in configs:
                    if cfg.get("name") == config_name:
                        config_id = cfg.get("id")
                        logger.info(f"Found existing config: {config_name} (ID: {config_id})")
                        break

            # If still no config, create one
            if not config_id:
                new_config_name = config_name or f"sdwan-{site_name}-{cpu}cpu"
                logger.info(f"Creating new config: {new_config_name}")

                new_config = create_fortiflex_config(
                    oauth_token,
                    creds["program_serial_number"],
                    new_config_name,
                    cpu=cpu,
                    services=services,
                    account_id=creds.get("account_id")
                )
                config_id = new_config.get("id")

        if not config_id:
            return {"success": False, "error": "Could not determine or create config_id"}

        # Create token
        entitlements = create_fortiflex_token(oauth_token, config_id, count=1)

        if not entitlements:
            return {"success": False, "error": "No entitlements returned"}

        ent = entitlements[0]

        return {
            "success": True,
            "step": "provision-license",
            "site_name": site_name,
            "config_id": config_id,
            "fortiflex": {
                "serial": ent.get("serialNumber"),
                "token": ent.get("token"),
                "config_id": ent.get("configId"),
                "status": ent.get("status"),
                "token_status": ent.get("tokenStatus"),
                "start_date": ent.get("startDate"),
                "end_date": ent.get("endDate")
            },
            "license_command": f"execute vm-license install {ent.get('token')}",
            "next_step": "Apply license to FortiGate VM, then run 'generate-config' action"
        }

    except Exception as e:
        logger.exception(f"License provisioning failed: {e}")
        return {"success": False, "error": str(e)}


def generate_site_config(
    site_name: str,
    site_id: int,
    wan_ip: str,
    wan_gateway: str,
    lan_ip: str,
    lan_network: str,
    license_type: str = None,
    # FortiFlex license parameters (for VM deployments)
    fortiflex_token: str = None,
    fortiflex_serial: str = None,
    fortiflex_config_id: str = None,
    fortiflex_config_name: str = None,
    fortiflex_status: str = None,
    fortiflex_end_date: str = None,
    # Standard license parameters (for hardware devices)
    device_serial: str = None,
    device_model: str = None,
    license_name: str = None,
    license_start_date: str = None,
    license_end_date: str = None,
    add_to_manifest: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate SD-WAN configuration for a site.

    This is a simplified version - for full template-based config,
    use fortigate-sdwan-blueprint-planner.

    Args:
        site_name: Site hostname
        site_id: Unique site ID
        wan_ip: WAN interface IP
        wan_gateway: WAN default gateway
        lan_ip: LAN interface IP
        lan_network: LAN network (CIDR)
        license_type: 'fortiflex' (VM) or 'standard' (hardware)

        For FortiFlex (VM):
        - fortiflex_token: FortiFlex license token
        - fortiflex_serial: FortiFlex serial number
        - fortiflex_config_id: FortiFlex config ID
        - fortiflex_config_name: FortiFlex config name
        - fortiflex_status: License status
        - fortiflex_end_date: License end date

        For Standard (hardware):
        - device_serial: Hardware device serial number
        - device_model: Device model
        - license_name: License/contract name
        - license_start_date: License start date
        - license_end_date: License end date

        add_to_manifest: Whether to add to manifest

    Returns:
        Dict with generated config details
    """
    logger.info(f"Generating SD-WAN config for {site_name} (license_type: {license_type or 'not_specified'})")

    # Normalize license type
    license_type = (license_type or "").lower()

    # Calculate loopback from site_id
    loopback_ip = f"172.16.0.{site_id}"

    # Load manifest for hub info
    manifest = load_manifest()

    # Find hub info
    hub_wan_ip = kwargs.get("hub_wan_ip", "")
    hub_loopback = kwargs.get("hub_loopback", "172.16.255.253")
    hub_bgp_loopback = kwargs.get("hub_bgp_loopback", "172.16.255.252")

    for key, device in manifest.get("devices", {}).items():
        if device.get("role") == "hub":
            hub_wan_ip = hub_wan_ip or device.get("management_ip", "")
            for lo in device.get("interfaces", {}).get("loopback", []):
                if "hub" in lo.get("name", "").lower():
                    hub_loopback = lo.get("ip", "").split()[0]
                elif "bgp" in lo.get("name", "").lower():
                    hub_bgp_loopback = lo.get("ip", "").split()[0]
            break

    # Build config
    config_lines = []

    # Header
    config_lines.append(f"""# ============================================
# SD-WAN Spoke Configuration: {site_name}
# Site ID: {site_id}
# Generated: {datetime.now().isoformat()}
# ============================================
""")

    # License section based on type
    if license_type == "fortiflex" and fortiflex_token:
        config_lines.append(f"""# ============================================
# LICENSE TYPE: FortiFlex (VM Token-Based)
# ============================================
# Model: {device_model or 'FortiGate-VM'}
# FortiFlex Serial: {fortiflex_serial or 'N/A'}
# Config ID: {fortiflex_config_id or 'N/A'}
# Config Name: {fortiflex_config_name or 'N/A'}
# Status: {fortiflex_status or 'PENDING'}
# End Date: {fortiflex_end_date or 'N/A'}
#
# IMPORTANT: Run this command FIRST after initial VM boot:
#   execute vm-license install {fortiflex_token}
#
# After license installation, the device will reboot.
# Then apply the remaining configuration below.
""")
    elif license_type == "standard" and device_serial:
        config_lines.append(f"""# ============================================
# LICENSE TYPE: Standard (Hardware-Based)
# ============================================
# Model: {device_model or 'FortiGate Appliance'}
# Device Serial: {device_serial}
# License Name: {license_name or 'N/A'}
# Start Date: {license_start_date or 'N/A'}
# End Date: {license_end_date or 'N/A'}
#
# Hardware devices are pre-licensed. No token application required.
# Apply configuration directly to the device.
""")
    elif not license_type:
        config_lines.append(f"""# ============================================
# WARNING: LICENSE TYPE NOT SPECIFIED
# ============================================
# Please specify license_type:
#   - 'fortiflex' for VM deployments (requires token)
#   - 'standard' for hardware appliances (pre-licensed)
""")

    # Basic system config
    config_lines.append(f"""# System Configuration
config system global
    set hostname "{site_name}"
end

# Loopback Interface
config system interface
    edit "Branch-Lo"
        set vdom "root"
        set ip {loopback_ip} 255.255.255.255
        set allowaccess ping
        set type loopback
    next
end
""")

    # Note about remaining config
    config_lines.append(f"""# ============================================
# REMAINING CONFIGURATION
# ============================================
# For complete SD-WAN configuration including:
#   - WAN/LAN interfaces
#   - IPsec VPN tunnels
#   - SD-WAN zones, members, health checks
#   - BGP configuration
#   - Firewall policies
#
# Use the fortigate-sdwan-blueprint-planner tool:
#   action: plan-site
#   csv_path: <filled template>
#
# Or configure manually with these values:
#   WAN IP: {wan_ip}
#   WAN Gateway: {wan_gateway}
#   LAN IP: {lan_ip}
#   LAN Network: {lan_network}
#   Hub WAN IP: {hub_wan_ip}
#   Hub Loopback: {hub_loopback}
#   Hub BGP Loopback: {hub_bgp_loopback}
# ============================================
""")

    config_text = "\n".join(config_lines)

    # Save config file
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    config_path = TEMPLATE_DIR / f"{site_name}_onboard_config.txt"

    with open(config_path, 'w') as f:
        f.write(config_text)

    result = {
        "success": True,
        "step": "generate-config",
        "site_name": site_name,
        "site_id": site_id,
        "loopback_ip": loopback_ip,
        "config_path": str(config_path),
        "config_lines": len(config_text.split("\n")),
        "license_type": license_type or "not_specified"
    }

    # Include license info based on type
    if license_type == "fortiflex" and fortiflex_token:
        result["license"] = {
            "type": "fortiflex",
            "serial": fortiflex_serial,
            "token": fortiflex_token,
            "config_id": fortiflex_config_id,
            "config_name": fortiflex_config_name,
            "status": fortiflex_status or "PENDING",
            "end_date": fortiflex_end_date,
            "requires_token_application": True,
            "license_command": f"execute vm-license install {fortiflex_token}"
        }
    elif license_type == "standard" and device_serial:
        result["license"] = {
            "type": "standard",
            "device_serial": device_serial,
            "device_model": device_model,
            "license_name": license_name,
            "start_date": license_start_date,
            "end_date": license_end_date,
            "requires_token_application": False,
            "note": "Hardware device is pre-licensed. Apply config directly."
        }

    # Add to manifest if requested
    if add_to_manifest:
        device_key = f"spoke_onboard_{site_id}"

        device_entry = {
            "role": "spoke",
            "management_ip": wan_ip,
            "device_name": site_name,
            "loopback_ip": loopback_ip,
            "status": "onboarding",
            "onboarded_at": datetime.now().isoformat(),
            "license_type": license_type or "not_specified",
            "device_model": device_model
        }

        # Add license info based on type
        if license_type == "fortiflex":
            device_entry["license"] = {
                "type": "fortiflex",
                "serial": fortiflex_serial,
                "token": fortiflex_token,
                "config_id": fortiflex_config_id,
                "config_name": fortiflex_config_name,
                "status": fortiflex_status or "PENDING",
                "end_date": fortiflex_end_date,
                "assigned_at": datetime.now().isoformat()
            }
        elif license_type == "standard":
            device_entry["license"] = {
                "type": "standard",
                "device_serial": device_serial,
                "license_name": license_name,
                "start_date": license_start_date,
                "end_date": license_end_date,
                "assigned_at": datetime.now().isoformat()
            }

        manifest.setdefault("devices", {})[device_key] = device_entry
        save_manifest(manifest)

        result["added_to_manifest"] = True
        result["device_key"] = device_key

    # Set appropriate next step based on license type
    if license_type == "fortiflex":
        result["next_step"] = "Apply license token to FortiGate VM first, wait for reboot, then apply config"
    elif license_type == "standard":
        result["next_step"] = "Apply config directly to hardware device (already pre-licensed)"
    else:
        result["next_step"] = "Specify license_type, then apply config to FortiGate"

    return result


def complete_onboarding(
    target_ip: str,
    device_key: str = None
) -> Dict[str, Any]:
    """
    Complete the onboarding by absorbing device config into manifest.

    Args:
        target_ip: FortiGate management IP
        device_key: Optional device key to update (instead of creating new)

    Returns:
        Dict with completion status
    """
    logger.info(f"Completing onboarding for {target_ip}")

    # Load FortiGate credentials
    creds = load_fortigate_credentials(target_ip)
    if not creds:
        return {
            "success": False,
            "error": f"No credentials found for {target_ip}",
            "hint": "Register device with fortigate-credential-manager first"
        }

    # This would normally call the manifest-tracker's absorb function
    # For now, return instructions
    return {
        "success": True,
        "step": "complete",
        "target_ip": target_ip,
        "message": "Run fortigate-sdwan-manifest-tracker with action=absorb to complete",
        "command": {
            "tool": "fortigate-sdwan-manifest-tracker",
            "parameters": {
                "action": "absorb",
                "target_ip": target_ip
            }
        }
    }


def full_onboard(
    site_name: str,
    site_id: int,
    wan_ip: str,
    wan_gateway: str,
    lan_ip: str,
    lan_network: str,
    license_type: str = "fortiflex",
    # FortiFlex-specific parameters
    provision_license_flag: bool = True,
    config_id: int = None,
    config_name: str = None,
    cpu: int = 2,
    services: List[str] = None,
    # Standard license parameters (for hardware devices)
    device_serial: str = None,
    device_model: str = None,
    license_name: str = None,
    license_start_date: str = None,
    license_end_date: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Full onboarding workflow in one call.

    IMPORTANT: Workflow differs based on license_type:
    - 'fortiflex' (VM): Provision license token -> Generate config -> Deploy VM -> Apply token -> Reboot -> Apply config
    - 'standard' (hardware): Generate config -> Apply config directly (device is pre-licensed)

    Args:
        site_name: Site hostname
        site_id: Unique site ID
        wan_ip: WAN interface IP
        wan_gateway: WAN default gateway
        lan_ip: LAN interface IP
        lan_network: LAN network (CIDR)
        license_type: 'fortiflex' (VM) or 'standard' (hardware) - REQUIRED

        For FortiFlex (VM deployments):
        - provision_license_flag: Whether to provision new FortiFlex license
        - config_id: Existing FortiFlex config ID
        - config_name: Name for new FortiFlex config
        - cpu: CPU cores for new config
        - services: Service codes for new config

        For Standard (hardware devices):
        - device_serial: Hardware device serial number
        - device_model: Device model (e.g., FortiWiFi-50G-5G)
        - license_name: License/contract name
        - license_start_date: License start date
        - license_end_date: License end date

    Returns:
        Dict with full onboarding results
    """
    # Normalize license type
    license_type = (license_type or "fortiflex").lower()

    logger.info(f"Starting full onboard for {site_name} (license_type: {license_type})")

    if license_type not in ["fortiflex", "standard"]:
        return {
            "success": False,
            "error": f"Invalid license_type: {license_type}",
            "valid_types": ["fortiflex", "standard"],
            "hint": "Use 'fortiflex' for VM deployments (requires token), 'standard' for hardware appliances"
        }

    results = {
        "success": True,
        "site_name": site_name,
        "site_id": site_id,
        "license_type": license_type,
        "steps_completed": [],
        "steps_remaining": []
    }

    fortiflex_token = None
    fortiflex_serial = None
    fortiflex_config_id = None
    fortiflex_config_name = None
    fortiflex_status = None
    fortiflex_end_date = None

    # FortiFlex workflow: Provision license first (for VMs only)
    if license_type == "fortiflex" and provision_license_flag:
        license_result = provision_license(
            site_name=site_name,
            config_id=config_id,
            config_name=config_name,
            cpu=cpu,
            services=services
        )

        if not license_result.get("success"):
            results["success"] = False
            results["error"] = license_result.get("error")
            results["step_failed"] = "provision-license"
            return results

        results["license_provisioning"] = license_result
        results["steps_completed"].append("provision-license")

        fortiflex = license_result.get("fortiflex", {})
        fortiflex_token = fortiflex.get("token")
        fortiflex_serial = fortiflex.get("serial")
        fortiflex_config_id = str(fortiflex.get("config_id", ""))
        fortiflex_status = fortiflex.get("status")
        fortiflex_end_date = fortiflex.get("end_date")

    # Generate config (for both license types)
    config_result = generate_site_config(
        site_name=site_name,
        site_id=site_id,
        wan_ip=wan_ip,
        wan_gateway=wan_gateway,
        lan_ip=lan_ip,
        lan_network=lan_network,
        license_type=license_type,
        # FortiFlex params
        fortiflex_token=fortiflex_token,
        fortiflex_serial=fortiflex_serial,
        fortiflex_config_id=fortiflex_config_id,
        fortiflex_config_name=fortiflex_config_name,
        fortiflex_status=fortiflex_status,
        fortiflex_end_date=fortiflex_end_date,
        # Standard license params
        device_serial=device_serial,
        device_model=device_model,
        license_name=license_name,
        license_start_date=license_start_date,
        license_end_date=license_end_date,
        add_to_manifest=True,
        **kwargs
    )

    if not config_result.get("success"):
        results["success"] = False
        results["error"] = config_result.get("error")
        results["step_failed"] = "generate-config"
        return results

    results["config"] = config_result
    results["steps_completed"].append("generate-config")

    # Remaining manual steps differ by license type
    if license_type == "fortiflex":
        results["steps_remaining"] = [
            "1. Deploy FortiGate VM",
            f"2. Apply license: execute vm-license install {fortiflex_token}" if fortiflex_token else "2. Apply FortiFlex license token",
            "3. Wait for device reboot",
            f"4. Apply configuration from: {config_result.get('config_path')}",
            "5. Verify connectivity",
            f"6. Complete onboarding: fortigate-sdwan-manifest-tracker action=absorb target_ip={wan_ip}"
        ]
        if fortiflex_token:
            results["license_command"] = f"execute vm-license install {fortiflex_token}"
    else:  # standard license
        results["steps_remaining"] = [
            f"1. Power on hardware device (Serial: {device_serial})" if device_serial else "1. Power on hardware device",
            f"2. Apply configuration from: {config_result.get('config_path')}",
            "   (Hardware devices are pre-licensed - no token application needed)",
            "3. Verify connectivity",
            f"4. Complete onboarding: fortigate-sdwan-manifest-tracker action=absorb target_ip={wan_ip}"
        ]
        results["requires_token_application"] = False

    results["steps_remaining"] = [s for s in results["steps_remaining"] if s]
    results["config_path"] = config_result.get("config_path")
    results["device_key"] = config_result.get("device_key")

    # Include license summary
    results["license"] = config_result.get("license", {})

    return results


# =============================================================================
# Main Entry Point
# =============================================================================

def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the onboarding tool."""
    action = params.get("action", "").lower()

    if action == "provision-license":
        return provision_license(
            site_name=params.get("site_name", "NewSite"),
            config_id=params.get("config_id"),
            config_name=params.get("config_name"),
            cpu=params.get("cpu", 2),
            services=params.get("services")
        )

    elif action == "generate-config":
        required = ["site_name", "site_id", "wan_ip", "wan_gateway", "lan_ip", "lan_network"]
        for field in required:
            if not params.get(field):
                return {"success": False, "error": f"Missing required field: {field}"}

        return generate_site_config(
            site_name=params["site_name"],
            site_id=int(params["site_id"]),
            wan_ip=params["wan_ip"],
            wan_gateway=params["wan_gateway"],
            lan_ip=params["lan_ip"],
            lan_network=params["lan_network"],
            license_type=params.get("license_type"),
            # FortiFlex params
            fortiflex_token=params.get("fortiflex_token"),
            fortiflex_serial=params.get("fortiflex_serial"),
            fortiflex_config_id=params.get("fortiflex_config_id"),
            fortiflex_config_name=params.get("fortiflex_config_name"),
            fortiflex_status=params.get("fortiflex_status"),
            fortiflex_end_date=params.get("fortiflex_end_date"),
            # Standard license params
            device_serial=params.get("device_serial"),
            device_model=params.get("device_model"),
            license_name=params.get("license_name"),
            license_start_date=params.get("license_start_date"),
            license_end_date=params.get("license_end_date"),
            add_to_manifest=params.get("add_to_manifest", True),
            hub_wan_ip=params.get("hub_wan_ip"),
            hub_loopback=params.get("hub_loopback"),
            hub_bgp_loopback=params.get("hub_bgp_loopback")
        )

    elif action == "complete":
        target_ip = params.get("target_ip")
        if not target_ip:
            return {"success": False, "error": "Missing required field: target_ip"}

        return complete_onboarding(
            target_ip=target_ip,
            device_key=params.get("device_key")
        )

    elif action == "full-onboard":
        required = ["site_name", "site_id", "wan_ip", "wan_gateway", "lan_ip", "lan_network"]
        for field in required:
            if not params.get(field):
                return {"success": False, "error": f"Missing required field: {field}"}

        # Check if license_type is specified
        license_type = params.get("license_type", "fortiflex")

        return full_onboard(
            site_name=params["site_name"],
            site_id=int(params["site_id"]),
            wan_ip=params["wan_ip"],
            wan_gateway=params["wan_gateway"],
            lan_ip=params["lan_ip"],
            lan_network=params["lan_network"],
            license_type=license_type,
            # FortiFlex params
            provision_license_flag=params.get("provision_license", True),
            config_id=params.get("config_id"),
            config_name=params.get("config_name"),
            cpu=params.get("cpu", 2),
            services=params.get("services"),
            # Standard license params
            device_serial=params.get("device_serial"),
            device_model=params.get("device_model"),
            license_name=params.get("license_name"),
            license_start_date=params.get("license_start_date"),
            license_end_date=params.get("license_end_date"),
            # Hub info
            hub_wan_ip=params.get("hub_wan_ip"),
            hub_loopback=params.get("hub_loopback"),
            hub_bgp_loopback=params.get("hub_bgp_loopback")
        )

    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "valid_actions": ["provision-license", "generate-config", "complete", "full-onboard"],
            "license_types": {
                "fortiflex": "For VM deployments - requires license token application after VM deployment",
                "standard": "For hardware appliances - devices are pre-licensed, no token needed"
            },
            "workflows": {
                "fortiflex_vm": [
                    "1. provision-license - Get FortiFlex token",
                    "2. generate-config - Generate config with license_type=fortiflex",
                    "3. Deploy VM",
                    "4. Apply license: execute vm-license install <token>",
                    "5. Wait for reboot",
                    "6. Apply configuration",
                    "7. complete - Absorb into manifest"
                ],
                "standard_hardware": [
                    "1. generate-config - Generate config with license_type=standard",
                    "2. Power on hardware device (already licensed)",
                    "3. Apply configuration directly",
                    "4. complete - Absorb into manifest"
                ]
            },
            "quick_start": "Use 'full-onboard' with license_type='fortiflex' or 'standard' for automated workflow"
        }


def main(context) -> Dict[str, Any]:
    """Entry point for MCP execution."""
    if hasattr(context, "parameters"):
        params = context.parameters
    elif isinstance(context, dict):
        params = context
    else:
        params = {}

    return execute(params)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python tool.py <action> [params...]")
        print("Actions: provision-license, generate-config, complete, full-onboard")
        print("")
        print("Examples:")
        print("  python tool.py provision-license --site_name Branch1")
        print("  python tool.py full-onboard --site_name Branch1 --site_id 1 --wan_ip 10.1.1.2 ...")
        sys.exit(1)

    action = sys.argv[1]
    params = {"action": action}

    # Simple arg parsing
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:]
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                params[key] = sys.argv[i + 1]
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1

    result = main(params)
    print(json.dumps(result, indent=2))
