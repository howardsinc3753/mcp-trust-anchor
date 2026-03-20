# FortiZTP Device Provision Skills

## Overview

Provision or unprovision a device for Zero Touch Provisioning. When provisioned, the device connects to its assigned target (FortiManager, FortiGateCloud, etc.) on boot and pulls configuration including any bootstrap scripts.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** IAM API Users work with this API.

## When to Use

Use this tool when:
- Provisioning a new device for automatic configuration
- Assigning a device to FortiManager with bootstrap script
- Re-provisioning a device to trigger ZTP
- Unprovisioning a device to reset ZTP status

**Example prompts:**
- "Provision FGT60F000001 to FortiManager with script 12345"
- "Set up ZTP for the new FortiGate"
- "Unprovision and reprovision device to trigger ZTP"
- "Assign device to FortiManager OID 67890"

## Prerequisites

1. **FortiCloud Account** - With FortiZTP access
2. **Local IAM API User** - NOT ORG type (FortiZTP limitation)
3. **Device Serial Number** - From fortiztp-device-list
4. **FortiManager OID** - From fortiztp-fmg-list (for FortiManager target)
5. **Script OID** - From fortiztp-script-list (optional)

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-LOCAL-IAM-USER-ID"
api_password: "your-api-password"
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `device_sn` | string | **Yes** | - | Device serial number |
| `provision_status` | string | No | provisioned | 'provisioned' or 'unprovisioned' |
| `provision_target` | string | No | - | FortiManager, FortiGateCloud, etc. |
| `region` | string | No | - | FortiCloud region (for cloud targets) |
| `fortimanager_oid` | integer | No | - | FortiManager OID |
| `script_oid` | integer | No | - | Bootstrap script OID |
| `use_default_script` | boolean | No | - | Use default script |
| `external_controller_sn` | string | No | - | External controller SN |
| `external_controller_ip` | string | No | - | External controller IP |
| `firmware_profile` | string | No | - | Firmware profile name |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Complete Workflow

### 1. Find Device Serial Number

```python
devices = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={"provision_status": "unprovisioned"}
)
# Get device_sn from results
```

### 2. Find FortiManager OID

```python
fmgs = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-fmg-list/1.0.0",
    parameters={}
)
# Get fortimanager_oid from results
```

### 3. Find or Create Script

```python
# List existing scripts
scripts = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-list/1.0.0",
    parameters={}
)

# Or create new script
script = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-create/1.0.0",
    parameters={
        "name": "Site-A-Bootstrap",
        "content": "config system global\n    set hostname Site-A\nend"
    }
)
# Get script_oid from results
```

### 4. Provision Device

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": 67890
    }
)
```

## Example Usage

### Provision to FortiManager

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_status": "provisioned",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": 67890
    }
)
```

### Provision to FortiGateCloud

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_target": "FortiGateCloud",
        "region": "us"
    }
)
```

### Unprovision Device

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_status": "unprovisioned"
    }
)
```

### Re-Provision (Trigger ZTP)

```python
# Step 1: Unprovision
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_status": "unprovisioned"
    }
)

# Step 2: Re-provision with new settings
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001",
        "provision_status": "provisioned",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": 99999  # New script
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "message": "Device FGT60F0000000001 provisioned successfully",
  "device": {
    "serial_number": "FGT60F0000000001",
    "provision_status": "provisioned",
    "provision_target": "FortiManager",
    "fortimanager_oid": 12345,
    "script_oid": 67890
  }
}
```

## Provision Target Requirements

| Target | Required Fields |
|--------|-----------------|
| FortiManager | `fortimanager_oid` OR (`external_controller_sn` + `external_controller_ip`) |
| FortiGateCloud | `region` |
| FortiEdgeCloud | `region` |
| ExternalController | `external_controller_ip` |

## What Happens After Provisioning

1. Device boots and contacts FortiCloud
2. FortiCloud returns ZTP configuration
3. Device connects to assigned target (FortiManager)
4. Bootstrap script runs (if script_oid provided)
5. Device pulls full configuration from FortiManager

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing required parameter: device_sn` | No serial number | Provide device_sn |
| `Invalid provision_status` | Wrong status value | Use 'provisioned' or 'unprovisioned' |
| `Authentication failed` | Invalid credentials | Check Local IAM user credentials |
| `Device not found` | Serial number not registered | Verify device is in FortiZTP |
| `Invalid fortimanager_oid` | FMG not registered | Use fortiztp-fmg-list to find valid OID |

## Related Tools

- `fortiztp-device-list` - Find device serial numbers
- `fortiztp-device-status` - Check device status
- `fortiztp-script-list` - Find script OIDs
- `fortiztp-script-create` - Create bootstrap scripts
- `fortiztp-fmg-list` - Find FortiManager OIDs

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/devices/{deviceSN}`
- **Method**: PUT
- **Client ID**: `fortiztp`
- **Rate Limit**: 2000 calls/hour
