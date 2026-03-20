# FortiZTP Script List Skills

## Overview

List all pre-run CLI scripts available in FortiZTP. These scripts contain FortiGate CLI commands that execute during Zero Touch Provisioning to configure the device during initial setup.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** IAM API Users work with this API.

## When to Use

Use this tool when:
- Finding available bootstrap scripts for device provisioning
- Reviewing existing ZTP configuration scripts
- Getting script OIDs for device provisioning
- Auditing ZTP script inventory

**Example prompts:**
- "List all ZTP scripts"
- "Show me available bootstrap scripts"
- "Find the script OID for site configuration"
- "What scripts are configured in FortiZTP?"

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

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `include_content` | boolean | No | false | Fetch script content (slower) |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Typical Workflow

### 1. List Scripts

```python
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-list/1.0.0",
    parameters={}
)
# Find the script_oid you need
```

### 2. View Script Content

```python
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-list/1.0.0",
    parameters={
        "include_content": true
    }
)
# Review CLI commands in each script
```

### 3. Use Script for Provisioning

```python
# Use script_oid from step 1/2
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60FXXXXXXXX",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": 67890  # From script list
    }
)
```

## Example Usage

### List All Scripts (Metadata Only)

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-list/1.0.0",
    parameters={}
)
```

### List Scripts with Content

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-list/1.0.0",
    parameters={
        "include_content": true
    }
)
```

## Interpreting Results

### Success Response (Metadata Only)

```json
{
  "success": true,
  "script_count": 3,
  "scripts": [
    {
      "oid": 12345,
      "name": "Site-A-Bootstrap",
      "update_time": "2026-01-15T10:30:00Z"
    },
    {
      "oid": 12346,
      "name": "Branch-Default",
      "update_time": "2026-01-10T08:00:00Z"
    },
    {
      "oid": 12347,
      "name": "DC-Core-Config",
      "update_time": "2026-01-20T14:45:00Z"
    }
  ]
}
```

### Success Response (With Content)

```json
{
  "success": true,
  "script_count": 1,
  "scripts": [
    {
      "oid": 12345,
      "name": "Site-A-Bootstrap",
      "update_time": "2026-01-15T10:30:00Z",
      "content": "config system global\n    set hostname Site-A-FW\nend\nconfig system interface\n    edit wan1\n        set ip 10.0.0.1 255.255.255.0\n    next\nend"
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `oid` | Script OID (use this for device provisioning) |
| `name` | Human-readable script name |
| `update_time` | Last modification timestamp |
| `content` | FortiGate CLI commands (only with include_content) |

## Script Content Format

Scripts contain FortiGate CLI configuration commands:

```
config system global
    set hostname Site-A-FW
    set timezone America/New_York
end

config system interface
    edit wan1
        set ip 10.0.0.1 255.255.255.0
        set allowaccess ping https ssh
    next
end

config router static
    edit 1
        set gateway 10.0.0.254
        set device wan1
    next
end
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Authentication failed` | Invalid credentials | Check Local IAM user credentials |
| `Missing API credentials` | No credentials configured | Configure forticloud_credentials.yaml |
| `API request failed: 401` | Token expired or invalid | Re-authenticate |
| `API request failed: 403` | Insufficient permissions | Check IAM user permissions |

## Related Tools

- `fortiztp-script-create` - Create new bootstrap scripts
- `fortiztp-device-list` - List devices for provisioning
- `fortiztp-device-provision` - Provision device with script
- `fortiztp-fmg-list` - List FortiManagers

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/setting/scripts`
- **Content Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/setting/scripts/{oid}/content`
- **Method**: GET
- **Client ID**: `fortiztp`
- **Rate Limit**: 2000 calls/hour
