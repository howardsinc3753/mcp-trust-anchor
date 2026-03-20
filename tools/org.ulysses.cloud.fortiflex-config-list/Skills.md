# FortiFlex Config List Skills

## Overview

List all FortiFlex configurations under a program. Each configuration represents a product bundle (FortiGate VM with specific cores, services, etc.) that you can create tokens from.

## When to Use

Use this tool when:
- Looking for existing configurations to create tokens from
- Checking what product bundles are configured
- Verifying configuration details before provisioning

**Example prompts:**
- "What FortiFlex configurations do I have?"
- "List my FortiGate VM configurations"
- "Find the config ID for 2-core FortiGate"

## Prerequisites

1. **FortiFlex Program** - Active program serial number
2. **API Credentials** - ReadWrite or Admin access
3. **Client ID**: `flexvm`

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
program_serial_number: "ELAVMS0000003536"
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_serial_number` | string | No* | Program SN (from config file if not specified) |
| `api_username` | string | No | Override API username |
| `api_password` | string | No | Override API password |

*Required if not in credential file

## Example Usage

### List Configurations (from config file)

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-config-list/1.0.0",
    parameters={}
)
```

### With Explicit Program SN

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-config-list/1.0.0",
    parameters={
        "program_serial_number": "ELAVMS0000003536"
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "program_serial_number": "ELAVMS0000003536",
  "config_count": 3,
  "configs": [
    {
      "config_id": 12345,
      "name": "FGT-VM-2CPU-Bundle",
      "product_type": "FortiGate Virtual Machine",
      "product_id": 1,
      "status": "ACTIVE",
      "parameters": [
        {"name": "cpu", "value": 2},
        {"name": "service", "value": "FC"},
        {"name": "service", "value": "UTP"},
        {"name": "service", "value": "ENT"}
      ]
    },
    {
      "config_id": 12346,
      "name": "FGT-VM-4CPU-Bundle",
      "product_type": "FortiGate Virtual Machine",
      "product_id": 1,
      "status": "ACTIVE",
      "parameters": [
        {"name": "cpu", "value": 4},
        {"name": "service", "value": "FC"},
        {"name": "service", "value": "UTP"}
      ]
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `config_id` | Use this in fortiflex-token-create |
| `name` | Human-readable configuration name |
| `product_type` | Product type (FortiGate VM, FortiManager VM, etc.) |
| `status` | ACTIVE, DISABLED, etc. |
| `parameters` | CPU cores and enabled services |

### Common Service Codes

| Code | Service |
|------|---------|
| FC | FortiCare Support |
| UTP | Unified Threat Protection |
| ENT | Enterprise Bundle |
| ATP | Advanced Threat Protection |
| IPS | Intrusion Prevention |
| AV | AntiVirus |
| WEB | Web Filtering |

## Typical Workflow

```
1. fortiflex-programs-list     -> Get program serial number
2. fortiflex-config-list       -> Find config_id for your product
3. fortiflex-token-create      -> Generate license token
4. Apply token to FortiGate VM
```

If no suitable configuration exists:
```
1. fortiflex-programs-list     -> Get program serial number
2. fortiflex-config-list       -> Verify no existing config
3. fortiflex-config-create     -> Create new configuration
4. fortiflex-token-create      -> Generate license token
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing program_serial_number` | No program SN provided | Use fortiflex-programs-list first |
| `Authentication failed` | Invalid credentials | Check API credentials |
| `No configs found` | Program has no configurations | Use fortiflex-config-create |

## Related Tools

- `fortiflex-programs-list` - List programs (get serial number first)
- `fortiflex-config-create` - Create new configurations
- `fortiflex-token-create` - Create tokens from a configuration

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/fortiflex/v2/configs/list`
- **Method**: POST
- **Client ID**: `flexvm`
- **Required Scope**: Read or higher
