# FortiGate SD-WAN Member - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-sdwan-member/1.0.0`
- **Domain:** noc
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Cases
1. **Configure overlay members** - Add IPsec tunnels to SD-WAN with priorities
2. **Set SLA priorities** - Configure priority-in-sla and priority-out-sla
3. **Update member settings** - Modify existing member configuration
4. **List/Get members** - View current SD-WAN member configuration

### Prerequisites
- SD-WAN must be enabled on the device
- Interface must exist before adding as member
- Zone must exist (or will be created)

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| target_ip | Yes | - | FortiGate management IP |
| action | Yes | - | add, update, remove, list, get |
| seq_num | Conditional | - | Member sequence number |
| interface | Conditional | - | Interface name (required for add) |
| zone | No | - | SD-WAN zone name |
| source | No | - | Source IP (loopback for overlay) |
| priority_in_sla | No | - | Priority when SLA met (lower=better) |
| priority_out_sla | No | - | Priority when SLA not met |
| cost | No | - | Interface cost |

## Example Usage

### List All Members
```json
{
  "target_ip": "192.168.209.30",
  "action": "list"
}
```

### Add Overlay Member with Priorities (Spoke)
```json
{
  "target_ip": "192.168.209.30",
  "action": "add",
  "seq_num": 100,
  "interface": "HUB1-VPN1",
  "zone": "SDWAN-HUB",
  "source": "172.16.0.2",
  "priority_in_sla": 10,
  "priority_out_sla": 100
}
```

### Update Member Priorities
```json
{
  "target_ip": "192.168.209.30",
  "action": "update",
  "seq_num": 100,
  "priority_in_sla": 5,
  "priority_out_sla": 50
}
```

### Get Specific Member
```json
{
  "target_ip": "192.168.209.30",
  "action": "get",
  "seq_num": 100
}
```

### Remove Member
```json
{
  "target_ip": "192.168.209.30",
  "action": "remove",
  "seq_num": 100
}
```

## Priority Guidelines

### Spoke Configuration
| Setting | Typical Value | Purpose |
|---------|---------------|---------|
| `priority_in_sla` | 10 | Lower = preferred when SLA met |
| `priority_out_sla` | 100 | Higher = less preferred when SLA fails |

### Multiple Overlays (Staggered)
```
Overlay 1 (seq 100): priority_in_sla=10, priority_out_sla=100
Overlay 2 (seq 101): priority_in_sla=15, priority_out_sla=105
```

## Technical Notes

### Source IP
- For overlay members, set `source` to spoke's loopback IP
- This ensures health checks use the overlay path

### Zone Assignment
- Members can be assigned to zones for policy routing
- Common zones: `SDWAN_OVERLAY`, `SDWAN-HUB`, `virtual-wan-link`

### CLI Equivalent
```
config system sdwan
  config members
    edit 100
      set interface "HUB1-VPN1"
      set zone "SDWAN-HUB"
      set source 172.16.0.2
      set priority-in-sla 10
      set priority-out-sla 100
    next
  end
end
```

## Related Tools
- `fortigate-sdwan-health-check` - Configure health checks
- `fortigate-sdwan-neighbor` - Configure SD-WAN neighbors
- `fortigate-sdwan-spoke-template` - Full spoke provisioning
