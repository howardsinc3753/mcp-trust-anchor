# FortiGate SD-WAN Zone Tool

## Purpose
CRUD operations for SD-WAN zones on FortiGate devices. Configure zones for SD-WAN traffic steering with ADVPN shortcut selection support.

Based on Fortinet 4D-Demo configurations and FortiOS 7.6+ SD-WAN features.

## When to Use
- Creating SD-WAN zones for overlay traffic
- Enabling ADVPN shortcut selection on zones
- Binding health checks for ADVPN path selection
- Managing zone-based firewall policies for SD-WAN

## Understanding SD-WAN Zones

### What is an SD-WAN Zone?
SD-WAN zones group interfaces (tunnels) for:
- **Firewall policy targeting** - Apply policies to zone instead of individual interfaces
- **Traffic steering** - Route traffic through zone members
- **ADVPN shortcut selection** - Enable dynamic shortcut path selection

### ADVPN Shortcut Selection
When enabled on a zone:
```
Zone: HUB1
    │
    ├── advpn-select: enable
    │       └── Enables ADVPN shortcut consideration
    │
    └── advpn-health-check: "HUB"
            └── Uses this health check for shortcut SLA evaluation
```

## Parameters

### Required
| Parameter | Type | Description |
|-----------|------|-------------|
| target_ip | string | FortiGate management IP |

### Action (Optional)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| action | string | list | `add`, `update`, `remove`, `list`, `get` |

### Zone Settings
| Parameter | Type | Description |
|-----------|------|-------------|
| name | string | Zone name (required for add/update/remove/get) |
| advpn_select | boolean | Enable ADVPN shortcut selection |
| advpn_health_check | string | Health check for ADVPN shortcut evaluation |
| minimum_sla_meet_members | integer | Min members meeting SLA for ADVPN (default: 1) |
| service_access | string | Service access: `allow` or `deny` |

## Usage Examples

### List All SD-WAN Zones
```json
{
  "target_ip": "192.168.209.30",
  "action": "list"
}
```

### Add Basic Zone
```json
{
  "target_ip": "192.168.209.30",
  "action": "add",
  "name": "SDWAN_OVERLAY"
}
```

### Add Zone with ADVPN Settings (4D-Demo Style)
```json
{
  "target_ip": "192.168.209.30",
  "action": "add",
  "name": "HUB1",
  "advpn_select": true,
  "advpn_health_check": "HUB"
}
```

### Update Zone to Enable ADVPN
```json
{
  "target_ip": "192.168.209.30",
  "action": "update",
  "name": "HUB1",
  "advpn_select": true,
  "advpn_health_check": "HUB"
}
```

### Remove Zone
```json
{
  "target_ip": "192.168.209.30",
  "action": "remove",
  "name": "OLD_ZONE"
}
```

## FortiOS CLI Equivalent

### Basic Zone
```
config system sdwan
  config zone
    edit "SDWAN_OVERLAY"
    next
  end
end
```

### Zone with ADVPN Settings (from 4D-Demo)
```
config system sdwan
  config zone
    edit "HUB1"
      set advpn-select enable
      set advpn-health-check "HUB"
    next
  end
end
```

### Multiple Zones Example
```
config system sdwan
  config zone
    edit "virtual-wan-link"
    next
    edit "WAN1"
    next
    edit "WAN2"
    next
    edit "HUB1"
      set advpn-select enable
      set advpn-health-check "HUB"
    next
  end
end
```

## ADVPN Shortcut Selection Explained

### What It Does
When `advpn-select enable` is set:
1. SD-WAN evaluates ADVPN shortcuts for traffic
2. Uses `advpn-health-check` SLA metrics to select best shortcut
3. Enables spoke-to-spoke shortcuts when SLA is met

### Requirements for ADVPN
1. **IPsec tunnels** must have `auto-discovery-sender/receiver enable`
2. **Health check** must exist with proper SLA thresholds
3. **Zone** must have ADVPN settings enabled
4. **Firewall policy** must allow traffic on zone

### Workflow
```
Traffic Flow: Spoke1 → Spoke2

1. SD-WAN checks if ADVPN shortcut exists
2. Evaluates shortcut against advpn-health-check SLA
3. If SLA met: Use direct spoke-to-spoke shortcut
4. If SLA not met: Route through hub
```

## Prerequisites

### 1. SD-WAN Must Be Enabled
```
config system sdwan
  set status enable
end
```

### 2. Health Check Must Exist (for ADVPN)
```json
{
  "tool": "fortigate-sdwan-health-check",
  "action": "create",
  "mode": "spoke",
  "name": "HUB",
  "server": "172.16.255.253",
  "members": [3, 4]
}
```

### 3. Members Should Be Assigned to Zone
After creating zone, add members:
```
config system sdwan
  config members
    edit 3
      set interface "HUB1_VPN1"
      set zone "HUB1"
    next
  end
end
```

## Output Examples

### List Response
```json
{
  "success": true,
  "action": "list",
  "count": 3,
  "zones": [
    {
      "name": "virtual-wan-link",
      "advpn-select": "disable"
    },
    {
      "name": "HUB1",
      "advpn-select": "enable",
      "advpn-health-check": "HUB"
    }
  ]
}
```

### Add Response
```json
{
  "success": true,
  "action": "add",
  "zone": {
    "name": "HUB1",
    "advpn_select": true,
    "advpn_health_check": "HUB"
  },
  "message": "SD-WAN zone HUB1 created with ADVPN enabled"
}
```

## Troubleshooting

### Zone Not Appearing in Firewall Policy
1. Verify zone was created: `get system sdwan zone`
2. Check SD-WAN is enabled: `get system sdwan`
3. Ensure at least one member is assigned to zone

### ADVPN Shortcuts Not Working
1. **Check advpn-select** - Must be `enable` on zone
2. **Check health check** - Must exist and be passing
3. **Check tunnel settings** - `auto-discovery-sender/receiver enable`
4. **Diagnose**: `diagnose sys sdwan advpn-session list`

### Zone Cannot Be Deleted
1. Remove all members from zone first
2. Remove zone from all firewall policies
3. Then delete zone

## Common Zone Configurations

### Hub Overlay Zone
```json
{
  "name": "SDWAN_OVERLAY",
  "advpn_select": false
}
```

### Spoke ADVPN Zone
```json
{
  "name": "HUB1",
  "advpn_select": true,
  "advpn_health_check": "HUB"
}
```

### WAN Underlay Zone
```json
{
  "name": "WAN1"
}
```

## Related Tools
- `fortigate-sdwan-member` - Add interfaces to zones
- `fortigate-sdwan-health-check` - Configure health checks for ADVPN
- `fortigate-sdwan-neighbor` - Configure BGP neighbor bindings
- `fortigate-sdwan-rule` - Configure SD-WAN steering rules
- `fortigate-firewall-policy` - Create policies targeting zones

## API Reference
- Endpoint: `/api/v2/cmdb/system/sdwan/zone`
- Methods: GET, POST, PUT, DELETE
- Auth: Bearer token

## References
- [Fortinet 4D-Demo GitHub](https://github.com/fortinet/4D-Demo)
- [FortiOS SD-WAN Zone Configuration](https://docs.fortinet.com/document/fortigate/7.6.0/administration-guide/939310/zones)
