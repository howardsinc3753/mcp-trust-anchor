# FortiGate Config Backup - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-config-backup/1.0.2`
- **Domain:** noc
- **Intent:** audit
- **Vendor:** fortinet
- **Tested:** FortiOS 7.6.5 (FortiWiFi-50G-5G hardware)

## When to Use This Tool

### Primary Use Cases

1. **Cadence Backups** - Scheduled configuration backups (daily, weekly)
2. **Pre-Change Backup** - Before applying configuration changes
3. **Disaster Recovery** - Export config for DR purposes
4. **Configuration Audit** - Review current device configuration
5. **Migration Preparation** - Export config before hardware replacement

### Trigger Phrases

- "backup fortigate configuration"
- "export fortigate config"
- "save firewall configuration"
- "download fortigate settings"
- "create config backup for disaster recovery"

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP |
| `scope` | string | No | `global` | Backup scope (global or vdom) |
| `vdom` | string | No | `root` | VDOM name (only when scope=vdom) |
| `file_format` | string | No | `fos` | Output format: `fos` (CLI text) or `yaml` |
| `password_mask` | boolean | No | `false` | Mask secrets/passwords in backup |
| `save_to_file` | boolean | No | `false` | Save backup to local file |
| `backup_path` | string | No | `C:/ProgramData/Ulysses/backups/fortigate` | Directory for backups |
| `timeout` | integer | No | `60` | Request timeout in seconds |
| `verify_ssl` | boolean | No | `false` | Verify SSL certificate |

## Example Usage

### Basic Backup (Return Content)

```python
execute_certified_tool(
    canonical_id="org.ulysses.noc.fortigate-config-backup/1.0.2",
    parameters={
        "target_ip": "192.168.209.30"
    }
)
```

### Save to File (Recommended for Large Configs)

```python
execute_certified_tool(
    canonical_id="org.ulysses.noc.fortigate-config-backup/1.0.2",
    parameters={
        "target_ip": "192.168.209.30",
        "save_to_file": true,
        "backup_path": "C:/ProgramData/Ulysses/backups/fortigate"
    }
)
```

### VDOM-Specific Backup

```python
execute_certified_tool(
    canonical_id="org.ulysses.noc.fortigate-config-backup/1.0.2",
    parameters={
        "target_ip": "192.168.209.30",
        "scope": "vdom",
        "vdom": "customer-a",
        "save_to_file": true
    }
)
```

### Masked Backup (Hide Secrets)

```python
execute_certified_tool(
    canonical_id="org.ulysses.noc.fortigate-config-backup/1.0.2",
    parameters={
        "target_ip": "192.168.209.30",
        "password_mask": true,
        "save_to_file": true
    }
)
```

## Output

### Success Response (Inline Content)

```json
{
  "success": true,
  "target_ip": "192.168.209.30",
  "hostname": "howard-sdwan-spoke-1",
  "serial_number": "FW50G5TK25000404",
  "firmware_version": "v7.6.5",
  "scope": "global",
  "backup_size_bytes": 45678,
  "backup_timestamp": "2026-02-07T10:30:00",
  "config_content": "#config-version=FW50G5-7.6.5-FW-build3651..."
}
```

### Success Response (Saved to File)

```json
{
  "success": true,
  "target_ip": "192.168.209.30",
  "hostname": "howard-sdwan-spoke-1",
  "serial_number": "FW50G5TK25000404",
  "firmware_version": "v7.6.5",
  "scope": "global",
  "backup_size_bytes": 45678,
  "backup_timestamp": "2026-02-07T10:30:00",
  "saved_to": "C:/ProgramData/Ulysses/backups/fortigate/howard-sdwan-spoke-1_FW50G5TK25000404_20260207_103000.conf",
  "config_content": "[Saved to C:/ProgramData/Ulysses/backups/fortigate/...]"
}
```

### Error Response

```json
{
  "success": false,
  "error": "HTTP Error 401: Unauthorized",
  "target_ip": "192.168.209.30",
  "hostname": "howard-sdwan-spoke-1"
}
```

## Backup File Naming Convention

Files are saved with this format:
```
{hostname}_{serial}_{YYYYMMDD}_{HHMMSS}.conf
```

Example:
```
howard-sdwan-spoke-1_FW50G5TK25000404_20260207_103000.conf
```

## Cadence Backup Integration

For scheduled backups in FortiBot.AI:

```python
# Daily backup workflow
def daily_backup(devices: list[str]):
    results = []
    for device_ip in devices:
        result = execute_certified_tool(
            canonical_id="org.ulysses.noc.fortigate-config-backup/1.0.0",
            parameters={
                "target_ip": device_ip,
                "save_to_file": True,
                "backup_path": f"C:/ProgramData/Ulysses/backups/fortigate/{datetime.now().strftime('%Y-%m')}"
            }
        )
        results.append(result)
    return results
```

## Workflow Integration

Typical use in change management:

```
1. fortigate-config-backup      → Pre-change backup
2. fortigate-config-push        → Apply changes
3. fortigate-health-check       → Verify device healthy
4. fortigate-config-backup      → Post-change backup (optional)
```

## REST API Details

**IMPORTANT:** FortiOS 7.6+ requires POST method with JSON body (not GET with query params).

```
POST /api/v2/monitor/system/config/backup
Authorization: Bearer {api_token}
Content-Type: application/json

{
    "destination": "file",
    "scope": "global",
    "file_format": "fos",
    "password_mask": false
}
```

Returns: Plain text FortiOS CLI configuration

**Note:** Earlier FortiOS versions used GET with query parameters. This tool automatically uses the correct POST method for 7.6+ compatibility.

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTP 401` | Invalid or expired token | Regenerate API token |
| `HTTP 403` | Insufficient permissions | Use super_admin profile |
| `Connection failed` | Network issue | Check connectivity to FortiGate |
| `No API credentials` | Missing config | Add device to fortigate_credentials.yaml |

## Security Notes

- API token is never stored in backup files
- Backups may contain sensitive data (PSK, passwords)
- Restrict backup directory permissions
- Consider encrypting backup files at rest
- Regularly rotate backup retention

## Related Tools

- `fortigate-health-check` - Verify device connectivity
- `fortigate-config-push` - Apply configuration changes
- `fortigate-device-register` - Register new devices
- `fortigate-onboard` - Complete device onboarding

## FortiBot.AI Integration

This tool is designed for integration with FortiBot.AI for:
- **Cadence backups**: Scheduled daily/weekly backups
- **Pre-change protection**: Automatic backup before any config push
- **Compliance auditing**: Regular config exports for review
- **Disaster recovery**: Maintain backup library for all managed devices
