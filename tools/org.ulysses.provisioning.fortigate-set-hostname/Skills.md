# FortiGate Set Hostname - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.provisioning.fortigate-set-hostname/1.0.0`
- **Domain:** provisioning
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Case
Set or change FortiGate device hostname for:
- Initial device setup
- SDWAN topology naming (hub-1, spoke-1, etc.)
- Site identification
- Standardizing device naming conventions

### Trigger Phrases
- "set fortigate hostname"
- "rename fortigate"
- "change device name"
- "configure hostname on fortigate"

## Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| target_ip | string | FortiGate management IP |
| hostname | string | New hostname (max 35 chars) |

## Example Usage

```json
{
  "target_ip": "192.168.215.15",
  "hostname": "howard-sdwan-hub-1"
}
```

## Output

```json
{
  "success": true,
  "target_ip": "192.168.215.15",
  "hostname": "howard-sdwan-hub-1",
  "previous_hostname": "FGVMMLTM26000192",
  "message": "Hostname changed from 'FGVMMLTM26000192' to 'howard-sdwan-hub-1'"
}
```

## Hostname Rules
- Maximum 35 characters
- Must start with alphanumeric character
- Appears in CLI prompt, logs, and SNMP

## Related Tools
- `fortigate-onboard` - Initial device setup
- `fortigate-health-check` - Verify device info
