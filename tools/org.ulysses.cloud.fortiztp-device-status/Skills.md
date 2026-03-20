# FortiZTP Device Status Skills

## Overview

Get detailed ZTP status for a specific device by serial number. Returns complete provisioning details.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** works.

## When to Use

- Checking device provisioning status after configuration
- Verifying device assignment to FortiManager
- Troubleshooting ZTP issues for specific device

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_sn` | string | **Yes** | Device serial number |

## Example Usage

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-status/1.0.0",
    parameters={
        "device_sn": "FGT60F0000000001"
    }
)
```

## Response

```json
{
  "success": true,
  "device": {
    "serial_number": "FGT60F0000000001",
    "device_type": "FortiGate",
    "platform": "FortiGate-60F",
    "provision_status": "provisioned",
    "provision_target": "FortiManager",
    "fortimanager_oid": 12345,
    "script_oid": 67890
  }
}
```

## Related Tools

- `fortiztp-device-list` - List all devices
- `fortiztp-device-provision` - Change device provisioning

## API Reference

- **Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/devices/{deviceSN}`
- **Method**: GET
- **Client ID**: `fortiztp`
