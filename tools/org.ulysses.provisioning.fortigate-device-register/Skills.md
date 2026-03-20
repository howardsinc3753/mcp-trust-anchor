# FortiGate Device Register - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.provisioning.fortigate-device-register/1.0.0`
- **Domain:** provisioning
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Case
Store FortiGate credentials locally after:
- Creating a new API token
- Receiving credentials from another source
- Migrating from another credential store

### Trigger Phrases
- "register fortigate device"
- "add fortigate to credentials"
- "store fortigate api token"
- "save fortigate credentials"

## Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| device_id | string | Unique device name (e.g., "lab-vm02") |
| host | string | FortiGate management IP |
| api_token | string | REST API token (sensitive) |

## Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| verify_ssl | false | Verify SSL certificates |
| set_default | false | Set as default device |
| model | null | Device model (documentation) |
| firmware | null | Firmware version (documentation) |

## Example Usage

### Basic Registration
```json
{
  "device_id": "lab-vm02",
  "host": "192.168.215.15",
  "api_token": "abc123xyz..."
}
```

### Full Registration with Metadata
```json
{
  "device_id": "lab-vm02",
  "host": "192.168.215.15",
  "api_token": "abc123xyz...",
  "verify_ssl": false,
  "set_default": true,
  "model": "FGT-VM02",
  "firmware": "7.6.5"
}
```

## Output

### Success Response
```json
{
  "success": true,
  "device_id": "lab-vm02",
  "host": "192.168.215.15",
  "credentials_file": "/path/to/fortigate_credentials.yaml",
  "action": "created",
  "is_default": true,
  "total_devices": 3,
  "message": "Device 'lab-vm02' registered successfully"
}
```

## Credentials File Format

After registration, the credentials file contains:

```yaml
# FortiGate Credentials - DO NOT COMMIT
devices:
  lab-71f:
    host: "192.168.209.62"
    api_token: "G5z7ph..."
    verify_ssl: false

  lab-vm02:
    host: "192.168.215.15"
    api_token: "abc123..."
    verify_ssl: false
    _metadata:
      model: FGT-VM02
      firmware: "7.6.5"
      registered_at: "2025-01-15T..."

default_device: "lab-vm02"

default_lookup:
  "192.168.209.62": "lab-71f"
  "192.168.215.15": "lab-vm02"
```

## Workflow Integration

This tool is typically Step 2 of device onboarding:

1. **fortigate-api-token-create** - Create API admin, get token
2. **fortigate-device-register** - Store token locally (this tool)
3. **fortigate-health-check** - Verify connectivity

## Security Notes

- Credentials file should be in `.gitignore`
- Restrict file permissions to authorized users
- Back up credentials securely
- Consider using vault integration for production

## Related Tools

- `fortigate-api-token-create` - Create API token on device
- `fortigate-health-check` - Verify API connectivity
