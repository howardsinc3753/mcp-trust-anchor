# SD-WAN IP Collision Check

## Purpose
Validates proposed IP allocations against existing SD-WAN network inventory to prevent subnet overlap across sites.

## When to Use
- **Before provisioning** a new SD-WAN site
- **During BLOCK_0** wizard validation
- **When adding VLANs** to existing sites
- **During capacity planning** to find next available site_id

## Actions

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `check` | Validate proposed IPs against existing | site_id OR proposed_subnets |
| `list-allocations` | Show all allocated IPs/subnets | (none) |
| `suggest-next` | Get next available site_id | (none) |

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| action | string | Yes | check, list-allocations, suggest-next |
| site_id | integer | For check | Site ID to validate (1-254) |
| proposed_subnets | array | For check | List of CIDR subnets to validate |
| proposed_management_ip | string | No | Management IP to check |
| include_hub | boolean | No | Include hub in collision check (default: true) |

## Usage Examples

### Check Site ID 4 for Collisions
```json
{
  "action": "check",
  "site_id": 4
}
```

Response when VALID:
```json
{
  "success": true,
  "action": "check",
  "valid": true,
  "checked_site_id": 4,
  "derived_allocations": {
    "loopback": "172.16.0.4/32",
    "lan_subnet": "10.4.1.0/24",
    "site_name": "spoke-04",
    "hostname": "FG-Spoke-04"
  },
  "message": "No IP collisions detected - safe to proceed"
}
```

Response when COLLISION:
```json
{
  "success": true,
  "action": "check",
  "valid": false,
  "collisions": [
    {
      "proposed": "172.16.0.4/32",
      "conflicts_with": "172.16.0.4/32",
      "site": "spoke-04",
      "collision_type": "subnet_overlap"
    }
  ],
  "message": "Found 1 collision(s) - resolve before provisioning"
}
```

### Check Explicit Subnets
```json
{
  "action": "check",
  "proposed_subnets": ["10.100.1.0/24", "172.16.0.10/32"],
  "proposed_management_ip": "192.168.209.50"
}
```

### List All Current Allocations
```json
{
  "action": "list-allocations"
}
```

Response:
```json
{
  "success": true,
  "action": "list-allocations",
  "allocations": {
    "loopbacks": [
      {"subnet": "172.16.0.2/32", "site": "spoke-01", "interface": "Spoke-Lo"},
      {"subnet": "172.16.0.3/32", "site": "spoke-02", "interface": "Spoke-Lo"}
    ],
    "lan_subnets": [
      {"subnet": "192.168.1.0/24", "site": "spoke-01", "interface": "lan"},
      {"subnet": "10.3.1.0/24", "site": "spoke-02", "interface": "port2"}
    ],
    "management_ips": [
      {"ip": "192.168.209.30", "site": "spoke-01"},
      {"ip": "192.168.209.35", "site": "spoke-02"}
    ]
  },
  "summary": {
    "total_loopbacks": 2,
    "total_lan_subnets": 2,
    "total_sites": 2
  }
}
```

### Get Next Available Site ID
```json
{
  "action": "suggest-next"
}
```

Response:
```json
{
  "success": true,
  "action": "suggest-next",
  "suggestion": {
    "next_available_site_id": 4,
    "derived": {
      "site_id": 4,
      "loopback": "172.16.0.4/32",
      "lan_subnet": "10.4.1.0/24",
      "site_name": "spoke-04",
      "hostname": "FG-Spoke-04",
      "router_id": "172.16.0.4",
      "location_id": "172.16.0.4"
    },
    "used_site_ids": [1, 2, 3]
  },
  "message": "Next available site_id is 4"
}
```

## IP Schema (Derivation from site_id)

| Component | Formula | Example (site_id=4) |
|-----------|---------|---------------------|
| Loopback | `172.16.0.{site_id}/32` | 172.16.0.4/32 |
| LAN Subnet | `10.{site_id}.1.0/24` | 10.4.1.0/24 |
| VLAN Subnet | `10.{site_id}.{vlan_id}.0/24` | 10.4.10.0/24 |
| Site Name | `spoke-{site_id:02d}` | spoke-04 |
| Hostname | `FG-Spoke-{site_id:02d}` | FG-Spoke-04 |
| Router ID | `172.16.0.{site_id}` | 172.16.0.4 |

## Collision Types

| Type | Description |
|------|-------------|
| `subnet_overlap` | Proposed subnet overlaps with existing |
| `duplicate_management_ip` | Management IP already in use |
| `invalid_format` | Proposed subnet is malformed |
| `invalid_ip` | Proposed IP address is invalid |

## Integration with BLOCK_0 Wizard

```yaml
# In BLOCK_0 validation:
validation:
  - tool: org.ulysses.noc.sdwan-ip-collision-check/1.0.0
    params:
      action: check
      site_id: "{{ site_id }}"
    expect:
      valid: true
```

## Data Source

Reads from: `C:/ProgramData/Ulysses/config/sdwan-manifest.yaml`

This file is managed by `fortigate-sdwan-manifest-tracker` tool.

## Related Tools
- `fortigate-sdwan-manifest-tracker` - Maintains the SD-WAN inventory
- `fortigate-interface` - Creates loopback/VLAN interfaces
- `fortigate-sdwan-member` - Configures SD-WAN members
