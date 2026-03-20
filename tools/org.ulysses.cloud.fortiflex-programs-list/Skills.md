# FortiFlex Programs List Skills

## Overview

List all FortiFlex programs available in your FortiCloud account. This is typically the first step in FortiFlex provisioning workflows - you need the program serial number before you can list or create configurations.

## When to Use

Use this tool when:
- Starting a new FortiFlex provisioning workflow
- Checking available FortiFlex programs
- Verifying program serial numbers
- Checking available points balance

**Example prompts:**
- "What FortiFlex programs do I have?"
- "Show me my FortiFlex point balance"
- "Get my FortiFlex program serial number"

## Prerequisites

1. **FortiCloud Account** - With FortiFlex/FlexVM enabled
2. **API Credentials** - ReadWrite or Admin access to FlexVM portal
3. **Client ID**: `flexvm`

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_username` | string | No | Override API username |
| `api_password` | string | No | Override API password |

## Example Usage

### List All Programs

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-programs-list/1.0.0",
    parameters={}
)
```

### With Explicit Credentials

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiflex-programs-list/1.0.0",
    parameters={
        "api_username": "my-api-user",
        "api_password": "my-api-password"
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "program_count": 1,
  "programs": [
    {
      "serial_number": "ELAVMS0000003536",
      "account_id": 123456,
      "start_date": "2025-01-01",
      "end_date": "2026-12-31",
      "has_support_coverage": true,
      "points": {
        "available": 50000,
        "used": 12500
      }
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `serial_number` | Program SN (use in config-list/config-create) |
| `account_id` | FortiCloud account ID |
| `start_date` | Program start date |
| `end_date` | Program expiration date |
| `has_support_coverage` | Whether FortiCare is included |
| `points.available` | Remaining FortiFlex points |
| `points.used` | Consumed FortiFlex points |

## Typical Workflow

```
1. fortiflex-programs-list     -> Get program serial number
2. fortiflex-config-list       -> List existing configurations
3. fortiflex-config-create     -> Create new configuration (if needed)
4. fortiflex-token-create      -> Generate license token
5. Apply token to FortiGate VM
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `No credentials found` | Missing API credentials | Configure credential file |
| `Authentication failed` | Invalid credentials | Check API username/password |
| `No programs found` | Account has no FortiFlex programs | Contact Fortinet sales |

## Related Tools

- `fortiflex-config-list` - List configurations under a program
- `fortiflex-config-create` - Create new configurations
- `fortiflex-token-create` - Create license tokens

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/fortiflex/v2/programs/list`
- **Method**: POST
- **Client ID**: `flexvm`
- **Required Scope**: Read or higher
