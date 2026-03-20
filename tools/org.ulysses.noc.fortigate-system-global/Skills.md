# FortiGate System Global

## Purpose

Configure FortiGate system global settings. Manages device-wide parameters like management IP, hostname, admin timeout, REST API options, and SSL/TLS versions.

## When to Use

- **Initial Setup**: Configure hostname, timezone, management IP
- **API Configuration**: Enable `rest-api-key-url-query` for URL-based API auth
- **Security Hardening**: Set admin timeout, SSL versions
- **SD-WAN**: Configure management-ip for overlay identification

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | get or set (default: get) |
| hostname | string | No | Device hostname |
| management_ip | string | No | Management IP (for SD-WAN overlay) |
| rest_api_key_url_query | string | No | enable/disable API key in URL |
| admin_timeout | integer | No | Admin session timeout (minutes) |
| timezone | string | No | System timezone |

## Example Usage

### Get Current Settings
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-global/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "get"
  }
}
```

### Enable REST API Key URL Query
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-global/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "rest_api_key_url_query": "enable"
  }
}
```

### Set Management IP for SD-WAN
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-global/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "management_ip": "192.168.209.35"
  }
}
```

## CLI Equivalent

```
config system global
  set hostname "spoke-02"
  set management-ip 192.168.209.35
  set rest-api-key-url-query enable
  set admin-timeout 60
end
```

## API Endpoint

- GET/PUT `/api/v2/cmdb/system/global`

## Related Tools

- `fortigate-system-settings` - Additional system settings (location-id, ike-tcp-port)
- `fortigate-system-interface` - Interface configuration
