# FortiFlex Config Create Skills

## Overview

Create new FortiFlex configurations for FortiGate VMs and other Fortinet products. A configuration defines the product bundle (CPU cores, services) that license tokens are generated from.

**IMPORTANT**: This tool creates configurations that consume FortiFlex points when tokens are generated. Verify your settings before executing.

## When to Use

Use this tool when:
- Setting up a new product bundle (e.g., FortiGate VM with 2 CPUs and full services)
- No existing configuration matches your requirements
- Deploying SD-WAN sites with specific resource needs

**Example prompts:**
- "Create a FortiFlex config for FortiGate VM with 2 cores and all services"
- "Set up a new 4-CPU FortiGate configuration"
- "Create sdwan-spoke-config with UTP bundle"

## Prerequisites

1. **FortiFlex Program** - Active program with available points
2. **API Credentials** - ReadWrite or Admin access
3. **Program SN** - From fortiflex-programs-list
4. **Client ID**: `flexvm`

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
program_serial_number: "ELAVMS0000003536"
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | **Yes** | - | Configuration name |
| `product_type` | string | No | fortigate-vm | Product type |
| `cpu` | integer | No | 2 | CPU cores (1, 2, 4, 8, 16, 32, 96) |
| `services` | array | No | ["FC", "UTP", "ENT"] | Service codes |
| `program_serial_number` | string | No* | from config | Program SN |
| `api_username` | string | No | from config | API username |
| `api_password` | string | No | from config | API password |

*Required if not in credential file

## Service Codes

| Code | Service | Description |
|------|---------|-------------|
| FC | FortiCare Premium | 24x7 support |
| UTP | Unified Threat Protection | AV, IPS, Web Filter, App Control |
| ENT | Enterprise Bundle | Full security + SD-WAN |
| ATP | Advanced Threat Protection | FortiSandbox integration |
| IPS | Intrusion Prevention | IPS only |
| AV | AntiVirus | AV only |
| WEB | Web Filtering | Web filter only |
| SWNM | SD-WAN Orchestrator | FortiManager SD-WAN |

## Example Usage

### Create FortiGate VM with 2 CPUs and All Services

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-config-create/1.0.0",
    parameters={
        "name": "sdwan-spoke-2cpu-ent",
        "product_type": "fortigate-vm",
        "cpu": 2,
        "services": ["FC", "UTP", "ENT"]
    }
)
```

### Create 4-CPU FortiGate with Basic Services

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-config-create/1.0.0",
    parameters={
        "name": "hub-fgt-4cpu-utp",
        "cpu": 4,
        "services": ["FC", "UTP"]
    }
)
```

### Create FortiManager VM

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-config-create/1.0.0",
    parameters={
        "name": "fmg-vm-config",
        "product_type": "fortimanager-vm",
        "cpu": 4,
        "services": ["FC"]
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "config_id": 98765,
  "name": "sdwan-spoke-2cpu-ent",
  "product_type": "fortigate-vm",
  "cpu": 2,
  "services": ["FC", "UTP", "ENT"],
  "program_serial_number": "ELAVMS0000003536",
  "status": "ACTIVE",
  "message": "Configuration created. Use config_id=98765 with fortiflex-token-create"
}
```

### Next Step

Use the returned `config_id` to create tokens:

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-token-create/1.0.1",
    parameters={
        "config_id": 98765,
        "count": 1
    }
)
```

## Complete SD-WAN Site Workflow

```
1. fortiflex-programs-list        -> Get program SN, check points
2. fortiflex-config-create        -> Create "sdwan-spoke-2cpu-ent"
3. fortiflex-token-create         -> Generate token from config
4. Deploy FortiGate VM            -> Apply token during bootstrap
5. fortigate-sdwan-blueprint      -> Generate SD-WAN config
6. fortigate-config-push          -> Push to device
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing name` | No configuration name | Provide unique name |
| `Invalid CPU value` | CPU not supported | Use 1, 2, 4, 8, 16, 32, or 96 |
| `Unknown product type` | Invalid product type | Check supported types |
| `Insufficient points` | Not enough points | Check program balance |
| `Configuration exists` | Duplicate name | Use unique name |

## Related Tools

- `fortiflex-programs-list` - Get program SN and point balance
- `fortiflex-config-list` - List existing configurations
- `fortiflex-token-create` - Create tokens from configuration
- `fortiflex-entitlements-list` - List all entitlements/licenses

## Entitlement Endpoint Reference

After creating a config, use the appropriate entitlement endpoint:

| Product Type | API Endpoint | Notes |
|--------------|--------------|-------|
| FortiGate-VM, FMG-VM, FAZ-VM | `entitlements/vm/create` | Use `fortiflex-token-create` |
| Physical hardware (FGT HW, FSW, FAP) | `entitlements/hardware/create` | Requires device serial numbers |
| Cloud services (FortiEDR) | `entitlements/cloud/create` | For SaaS products |

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/fortiflex/v2/configs/create`
- **Method**: POST
- **Client ID**: `flexvm`
- **Required Scope**: ReadWrite or Admin
