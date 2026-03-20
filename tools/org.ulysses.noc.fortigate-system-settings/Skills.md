# FortiGate System Settings

## Purpose

Configure FortiGate system settings (config system settings). Manages VDOM-level parameters like location-id for SD-WAN ADVPN, IKE over TCP port, and GUI preferences.

## When to Use

- **SD-WAN ADVPN**: Set `location-id` (overlay IP) for spoke identification
- **IKE over TCP**: Configure `ike-tcp-port` (e.g., 11443) for environments blocking UDP 500/4500
- **Operation Mode**: Switch between NAT and transparent mode
- **GUI Customization**: Set theme, default policy columns

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | get or set (default: get) |
| location_id | string | No | Location ID (overlay IP for ADVPN) |
| ike_tcp_port | integer | No | IKE over TCP port (default 443) |
| opmode | string | No | nat or transparent |
| central_nat | string | No | enable/disable central NAT |
| gui_theme | string | No | GUI theme name |

## Example Usage

### Get Current Settings
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-settings/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "get"
  }
}
```

### Set Location ID for SD-WAN ADVPN
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-settings/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "location_id": "172.16.0.3"
  }
}
```

### Configure IKE over TCP Port
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-system-settings/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "ike_tcp_port": 11443
  }
}
```

## CLI Equivalent

```
config system settings
  set location-id 172.16.0.3
  set ike-tcp-port 11443
end
```

## API Endpoint

- GET/PUT `/api/v2/cmdb/system/settings`

## SD-WAN ADVPN Notes

The `location-id` is critical for SD-WAN ADVPN:
- Used as the spoke's overlay IP in the ADVPN mesh
- Must be unique per spoke
- Typically matches `exchange-ip-addr4` in Phase1 config
- Hub uses this to identify and route to spokes

## Related Tools

- `fortigate-system-global` - Global system settings (hostname, management-ip)
- `fortigate-ipsec` - IPsec Phase1/Phase2 configuration
