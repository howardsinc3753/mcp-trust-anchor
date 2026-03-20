# FortiZTP Device List Skills

## Overview

List all devices registered in FortiZTP with their Zero Touch Provisioning status. This is typically the first step in the ZTP workflow to find device serial numbers before provisioning.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** IAM API Users work with this API.

## When to Use

Use this tool when:
- Finding device serial numbers for ZTP provisioning
- Checking which devices are waiting for provisioning
- Auditing ZTP device inventory
- Filtering devices by type, status, or target

**Example prompts:**
- "List all FortiGate devices in ZTP"
- "Show me unprovisioned devices"
- "Find devices waiting for FortiManager provisioning"
- "What devices are registered in FortiZTP?"

## Prerequisites

1. **FortiCloud Account** - With FortiZTP access
2. **Local IAM API User** - NOT ORG type (FortiZTP limitation)
3. **API Credentials** - Username and password for Local IAM user

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-LOCAL-IAM-USER-ID"
api_password: "your-api-password"
```

**Warning**: ORG IAM API Users will fail authentication with FortiZTP. You must use a Local type IAM API User.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `device_type` | string | No | - | Filter: FortiGate, FortiAP, FortiSwitch, FortiExtender |
| `provision_status` | string | No | - | Filter: provisioned, unprovisioned, hidden, incomplete |
| `provision_target` | string | No | - | Filter: FortiManager, FortiGateCloud, FortiEdgeCloud, ExternalController |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Typical Workflow

### 1. List All Devices

```python
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={}
)
# Find the serial number you need
```

### 2. Filter by Status

```python
# Find devices waiting for provisioning
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={
        "provision_status": "unprovisioned"
    }
)
```

### 3. Provision Device

```python
# Use serial number from step 1/2
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60FXXXXXXXX",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": 67890
    }
)
```

## Example Usage

### List All Devices

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={}
)
```

### List Only FortiGates

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={
        "device_type": "FortiGate"
    }
)
```

### Find Unprovisioned Devices

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={
        "provision_status": "unprovisioned"
    }
)
```

### Find Devices Targeting FortiManager

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-list/1.0.0",
    parameters={
        "provision_target": "FortiManager"
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "device_count": 3,
  "devices": [
    {
      "serial_number": "FGT60F0000000001",
      "device_type": "FortiGate",
      "platform": "FortiGate-60F",
      "provision_status": "unprovisioned",
      "region": "us"
    },
    {
      "serial_number": "FGT60F0000000002",
      "device_type": "FortiGate",
      "platform": "FortiGate-60F",
      "provision_status": "provisioned",
      "provision_target": "FortiManager",
      "fortimanager_oid": 12345,
      "script_oid": 67890
    },
    {
      "serial_number": "FAP221E0000000001",
      "device_type": "FortiAP",
      "platform": "FortiAP-221E",
      "provision_status": "incomplete",
      "provision_sub_status": "waiting"
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `serial_number` | Device serial number (use for provisioning) |
| `device_type` | FortiGate, FortiAP, FortiSwitch, FortiExtender |
| `platform` | Hardware model/platform |
| `provision_status` | provisioned, unprovisioned, hidden, incomplete |
| `provision_sub_status` | waiting, provisioning, provisioningtoolong |
| `provision_target` | FortiManager, FortiGateCloud, FortiEdgeCloud, ExternalController |
| `region` | FortiCloud region |
| `firmware_profile` | Assigned firmware profile |
| `fortimanager_oid` | Associated FortiManager (internal OID) |
| `script_oid` | Associated bootstrap script (internal OID) |

### Provision Status Meanings

| Status | Meaning |
|--------|---------|
| `unprovisioned` | Device registered but not configured for ZTP |
| `provisioned` | Device configured and ready for ZTP |
| `hidden` | Device hidden from ZTP |
| `incomplete` | Provisioning in progress or stalled |

### Sub-Status (when incomplete)

| Sub-Status | Meaning |
|------------|---------|
| `waiting` | Waiting for device to connect |
| `provisioning` | Currently provisioning |
| `provisioningtoolong` | Provisioning taking too long |

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Authentication failed` | Invalid credentials | Check Local IAM user credentials |
| `Missing API credentials` | No credentials configured | Configure forticloud_credentials.yaml |
| `API request failed: 401` | Token expired or invalid | Re-authenticate |
| `API request failed: 403` | Insufficient permissions | Check IAM user permissions |

## Related Tools

- `fortiztp-device-status` - Get detailed status for single device
- `fortiztp-device-provision` - Provision device to target
- `fortiztp-script-list` - List available bootstrap scripts
- `fortiztp-fmg-list` - List registered FortiManagers

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/devices`
- **Method**: GET
- **Client ID**: `fortiztp`
- **Rate Limit**: 2000 calls/hour
