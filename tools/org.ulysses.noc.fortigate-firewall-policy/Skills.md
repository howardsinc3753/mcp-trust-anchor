# FortiGate Firewall Policy - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-firewall-policy/1.0.0`
- **Domain:** noc
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Cases
1. **Create firewall policies** - Allow/deny traffic between zones
2. **Delete policies** - Remove by ID or name
3. **List policies** - View all configured policies
4. **Get policy details** - Retrieve specific policy configuration

### Prerequisites
- Referenced address objects must exist (or use "all")
- Referenced service objects must exist (or use "ALL")
- Referenced UTM profiles must exist (default profiles available)
- API token with read/write access to firewall configuration

## Parameters

### Common Parameters
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| target_ip | Yes | - | FortiGate management IP |
| action | Yes | - | add, remove, list, get |

### Add Action Parameters
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | Yes | - | Policy name |
| srcintf | Yes | - | Source interface/zone list |
| dstintf | Yes | - | Destination interface/zone list |
| srcaddr | No | ["all"] | Source address objects |
| dstaddr | No | ["all"] | Destination address objects or **VIP names** |
| service | No | ["ALL"] | Service objects |
| schedule | No | "always" | Schedule object |
| policy_action | No | "accept" | accept or deny |
| nat | No | false | Enable SNAT |
| logtraffic | No | "all" | all, utm, disable |
| position | No | "top" | top (edit 0) or bottom |

### UTM Parameters (optional)
| Parameter | Description |
|-----------|-------------|
| utm_status | Enable UTM inspection (required for profiles) |
| ips_sensor | IPS sensor profile name |
| av_profile | Antivirus profile name |
| webfilter_profile | Web filter profile name |
| ssl_ssh_profile | SSL/SSH inspection profile |

### Remove/Get Parameters
| Parameter | Required | Description |
|-----------|----------|-------------|
| policy_id | Conditional | Policy ID to remove/get |
| name | Conditional | Policy name (for remove by name) |

## Example Usage

### List All Policies
```json
{
  "target_ip": "192.168.215.15",
  "action": "list"
}
```

### Create Basic Policy (SD-WAN to LAN with NAT)
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "SDWAN_OL_To_Port2",
  "srcintf": ["SDWAN_OVERLAY"],
  "dstintf": ["port2"],
  "srcaddr": ["all"],
  "dstaddr": ["all"],
  "service": ["ALL"],
  "policy_action": "accept",
  "nat": true,
  "logtraffic": "all"
}
```

### Create Policy with UTM (IPS)
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "SDWAN_OL_To_Port2",
  "srcintf": ["SDWAN_OVERLAY"],
  "dstintf": ["port2"],
  "policy_action": "accept",
  "nat": true,
  "logtraffic": "all",
  "utm_status": true,
  "ips_sensor": "all_default_pass"
}
```

### Create Inter-Zone Policy
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "LAN_to_WAN",
  "srcintf": ["port2"],
  "dstintf": ["port1"],
  "srcaddr": ["all"],
  "dstaddr": ["all"],
  "service": ["ALL"],
  "nat": true,
  "position": "bottom"
}
```

### Get Policy by ID
```json
{
  "target_ip": "192.168.215.15",
  "action": "get",
  "policy_id": 1
}
```

### Remove Policy by ID
```json
{
  "target_ip": "192.168.215.15",
  "action": "remove",
  "policy_id": 5
}
```

### Remove Policy by Name
```json
{
  "target_ip": "192.168.215.15",
  "action": "remove",
  "name": "SDWAN_OL_To_Port2"
}
```

### Create Policy with VIP Destination (Port Forwarding)
Use VIP names in `dstaddr` to create policies for inbound NAT/port forwarding:
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "Allow_FMG_541_VIP",
  "srcintf": ["SDWAN_OVERLAY"],
  "dstintf": ["port2"],
  "srcaddr": ["all"],
  "dstaddr": ["VIP_541_FMG"],
  "service": ["ALL"],
  "policy_action": "accept",
  "nat": false,
  "logtraffic": "all"
}
```

### Create Policy with Multiple VIPs
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "Allow_FMG_Services",
  "srcintf": ["SDWAN_OVERLAY"],
  "dstintf": ["port2"],
  "srcaddr": ["all"],
  "dstaddr": ["VIP_541_FMG", "VIP_ICMP_FMG"],
  "service": ["ALL"],
  "policy_action": "accept",
  "logtraffic": "all"
}
```

## Output Examples

### List Output
```json
{
  "success": true,
  "action": "list",
  "target_ip": "192.168.215.15",
  "count": 3,
  "policies": [
    {"policyid": 1, "name": "LAN_to_WAN", "srcintf": ["port2"], "dstintf": ["port1"], "action": "accept", "status": "enable"},
    {"policyid": 2, "name": "SDWAN_Overlay_Traffic", "srcintf": ["Hub_Lo"], "dstintf": ["SDWAN_OVERLAY"], "action": "accept", "status": "enable"}
  ]
}
```

### Add Output
```json
{
  "success": true,
  "action": "add",
  "policy_id": 5,
  "name": "SDWAN_OL_To_Port2",
  "message": "Created policy 'SDWAN_OL_To_Port2' with ID 5 at top of list"
}
```

## Technical Notes

### Policy Order
- Policies are evaluated **top-down** (first match wins)
- `position: "top"` uses `edit 0` to insert at beginning
- `position: "bottom"` appends to end of list
- For precise positioning, use FortiGate GUI or CLI

### Interface Types
Policies can reference:
- Physical interfaces: `port1`, `port2`, `wan1`
- VLAN interfaces: `vlan100`
- Loopback interfaces: `Hub_Lo`, `Spoke_Lo`
- SD-WAN zones: `SDWAN_OVERLAY`, `virtual-wan-link`
- IPsec tunnels: `HUB_VPN1`, `SPOKE_VPN1`

### Default Objects
| Type | Default Name | Matches |
|------|--------------|---------|
| Address | "all" | Any IPv4 |
| Service | "ALL" | Any service/port |
| Schedule | "always" | 24/7 |

### Using VIPs in Policies
Virtual IPs (VIPs) can be referenced in `dstaddr` for inbound NAT/port forwarding:
- **VIP names** work like address objects in policies
- **Port forwarding VIPs** handle DNAT automatically (extip:extport -> mappedip:mappedport)
- **Static NAT VIPs** provide 1:1 IP mapping
- **No SNAT needed** - set `nat: false` when using VIPs (DNAT already applied)
- **Source interface**: Use the interface where external traffic arrives (e.g., SD-WAN overlay)
- **Destination interface**: Use the interface toward the internal server

Use `fortigate-vip` tool to create VIPs before referencing them in policies.

### UTM Default Profiles
Common default profiles available on FortiGate:
- IPS: `all_default_pass`, `all_default`, `default`
- AV: `default`
- Web Filter: `default`
- SSL Inspection: `certificate-inspection`, `deep-inspection`

## Related Tools
- `fortigate-vip` - Create Virtual IPs for port forwarding/static NAT
- `fortigate-address-object` - Create address objects
- `fortigate-service-object` - Create service objects
- `fortigate-health-check` - Verify device connectivity

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Interface not found" | Invalid srcintf/dstintf | Check interface names |
| "Object not found" | Missing address/service | Create object first or use defaults |
| "Profile not found" | Invalid UTM profile | Check profile names |
| "Policy exists" | Duplicate policy name | Use unique name |
