# FortiZTP Script Create Skills

## Overview

Create pre-run CLI scripts for Zero Touch Provisioning. These bootstrap scripts contain FortiGate CLI commands that execute during initial device setup to configure hostname, interfaces, routing, and policies.

**CRITICAL**: FortiZTP does NOT support ORG IAM API Users. Only **Local type** IAM API Users work with this API.

## When to Use

Use this tool when:
- Creating new bootstrap scripts for site deployments
- Automating FortiGate initial configuration
- Setting up SD-WAN spoke site templates
- Creating standardized configuration scripts

**Example prompts:**
- "Create a ZTP script for Site-A"
- "Create a bootstrap script to set hostname and WAN interface"
- "Create a new FortiGate provisioning script"

## Prerequisites

1. **FortiCloud Account** - With FortiZTP access
2. **Local IAM API User** - NOT ORG type (FortiZTP limitation)
3. **API Credentials** - Username and password with write access

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-LOCAL-IAM-USER-ID"
api_password: "your-api-password"
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | **Yes** | - | Script name (e.g., "Site-A-Bootstrap") |
| `content` | string | **Yes** | - | FortiGate CLI commands |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Typical Workflow

### 1. Create Bootstrap Script

```python
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-create/1.0.0",
    parameters={
        "name": "Site-A-Bootstrap",
        "content": """config system global
    set hostname Site-A-FW
end
config system interface
    edit wan1
        set ip 10.0.0.1 255.255.255.0
    next
end"""
    }
)
# Save the script_oid for provisioning
```

### 2. Provision Device with Script

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-device-provision/1.0.0",
    parameters={
        "device_sn": "FGT60FXXXXXXXX",
        "provision_target": "FortiManager",
        "fortimanager_oid": 12345,
        "script_oid": result["script"]["oid"]
    }
)
```

## Example Usage

### Basic Script

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-create/1.0.0",
    parameters={
        "name": "Basic-Bootstrap",
        "content": "config system global\n    set hostname Branch-FW\nend"
    }
)
```

### Complete Site Configuration

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-create/1.0.0",
    parameters={
        "name": "Site-A-Full-Config",
        "content": """config system global
    set hostname Site-A-FW
    set timezone America/New_York
end

config system interface
    edit wan1
        set ip 10.1.1.1 255.255.255.0
        set allowaccess ping https ssh
    next
    edit internal
        set ip 192.168.1.1 255.255.255.0
    next
end

config router static
    edit 1
        set gateway 10.1.1.254
        set device wan1
    next
end

config system dns
    set primary 8.8.8.8
    set secondary 8.8.4.4
end"""
    }
)
```

### SD-WAN Spoke Template

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortiztp-script-create/1.0.0",
    parameters={
        "name": "SDWAN-Spoke-Template",
        "content": """config system global
    set hostname SDWAN-Spoke
end

config system sdwan
    set status enable
    config zone
        edit virtual-wan-link
        next
    end
    config members
        edit 1
            set interface wan1
            set gateway 10.0.0.254
        next
    end
end"""
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "message": "Script 'Site-A-Bootstrap' created successfully",
  "script": {
    "oid": 12345,
    "name": "Site-A-Bootstrap",
    "content_length": 256
  }
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `oid` | Script OID (use this for device provisioning) |
| `name` | Script name as provided |
| `content_length` | Number of characters in script |

## Script Content Guidelines

### Valid CLI Commands

Scripts should contain valid FortiGate CLI configuration:

```
config system global
    set hostname <name>
    set timezone <timezone>
end

config system interface
    edit <interface>
        set ip <ip> <mask>
        set allowaccess <access>
    next
end

config router static
    edit <id>
        set gateway <ip>
        set device <interface>
    next
end
```

### Common Configuration Blocks

| Block | Purpose |
|-------|---------|
| `config system global` | Hostname, timezone, settings |
| `config system interface` | Interface IP/access |
| `config router static` | Default routes |
| `config system dns` | DNS servers |
| `config system sdwan` | SD-WAN configuration |
| `config firewall policy` | Security policies |

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing required parameter: name` | No script name | Provide name parameter |
| `Missing required parameter: content` | No CLI commands | Provide content parameter |
| `Authentication failed` | Invalid credentials | Check Local IAM user credentials |
| `Failed to create script metadata` | API error | Check permissions and name uniqueness |
| `Failed to set script content` | Content error | Verify CLI syntax |

## Related Tools

- `fortiztp-script-list` - List existing scripts
- `fortiztp-device-list` - Find devices to provision
- `fortiztp-device-provision` - Assign script to device
- `fortiztp-fmg-list` - List FortiManagers

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **Create Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/setting/scripts`
- **Content Endpoint**: `https://fortiztp.forticloud.com/public/api/v2/setting/scripts/{oid}/content`
- **Methods**: POST (create), PUT (content)
- **Client ID**: `fortiztp`
- **Rate Limit**: 2000 calls/hour

## Two-Step Creation Process

The API requires two calls:
1. **POST /setting/scripts** - Creates script metadata, returns OID
2. **PUT /setting/scripts/{oid}/content** - Sets CLI content

This tool handles both steps automatically.
