# FortiZTP FortiManager List Skills

## Overview

List FortiManagers registered in FortiZTP. Returns OIDs needed for device provisioning to FortiManager targets.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** works.

## When to Use

- Finding FortiManager OIDs for device provisioning
- Auditing registered FortiManagers
- Checking FortiManager-script associations

## Example Usage

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-fmg-list/1.0.0",
    parameters={}
)
```

## Response

```json
{
  "success": true,
  "fortimanager_count": 2,
  "fortimanagers": [
    {
      "oid": 12345,
      "serial_number": "FMG-VM0000000001",
      "ip_address": "10.0.0.100",
      "script_oid": 67890,
      "update_time": "2026-01-15T10:00:00Z"
    }
  ]
}
```

## Related Tools

- `fortiztp-device-provision` - Use OID to provision devices
- `fortiztp-script-list` - Find script OIDs

## API Reference

- **Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/setting/fortimanagers`
- **Method**: GET
- **Client ID**: `fortiztp`
