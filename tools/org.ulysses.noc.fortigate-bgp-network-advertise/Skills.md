# FortiGate BGP Network Advertise - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-bgp-network-advertise/1.0.0`
- **Domain:** noc
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Cases
1. **Add BGP Networks**: Advertise new prefixes via BGP
2. **Remove BGP Networks**: Stop advertising specific prefixes
3. **List BGP Networks**: View currently configured network statements

### Prerequisites
- BGP must already be configured on the FortiGate
- Target networks should exist in routing table (or configure `synchronous disable`)
- API token with read/write access to router configuration

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| target_ip | Yes | - | FortiGate management IP |
| action | Yes | - | Operation: "add", "remove", or "list" |
| prefix | Conditional | - | Network prefix (required for add/remove) |
| network_id | No | auto | Network ID (auto-assigned for add) |
| route_map | No | - | Route-map to apply (optional) |
| verify_ssl | No | false | Verify SSL certificates |

### Prefix Format
Accepts either format:
- CIDR: `10.0.0.0/24`
- Mask: `10.0.0.0 255.255.255.0`

## Example Usage

### List Current BGP Networks
```json
{
  "target_ip": "192.168.215.15",
  "action": "list"
}
```

### Add a Network
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "prefix": "10.100.0.0/24"
}
```

### Add Network with Route-Map
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "prefix": "192.168.50.0/24",
  "route_map": "SET_COMMUNITY_100"
}
```

### Remove a Network
```json
{
  "target_ip": "192.168.215.15",
  "action": "remove",
  "network_id": 3
}
```

Or by prefix:
```json
{
  "target_ip": "192.168.215.15",
  "action": "remove",
  "prefix": "10.100.0.0/24"
}
```

## Output Examples

### List Output
```json
{
  "success": true,
  "action": "list",
  "target_ip": "192.168.215.15",
  "networks": [
    {"id": 1, "prefix": "172.16.0.0/16", "route_map": ""},
    {"id": 2, "prefix": "10.250.250.0/24", "route_map": ""},
    {"id": 3, "prefix": "10.100.0.0/24", "route_map": "SET_COMMUNITY_100"}
  ],
  "message": "Found 3 BGP network statements"
}
```

### Add Output
```json
{
  "success": true,
  "action": "add",
  "target_ip": "192.168.215.15",
  "networks": [
    {"id": 4, "prefix": "192.168.50.0/24", "route_map": ""}
  ],
  "message": "Added network 192.168.50.0/24 with ID 4"
}
```

## Technical Notes

### BGP Synchronization
By default, BGP requires a route to exist in the routing table before advertising:
- Connected networks are in the table automatically
- Static routes must be configured
- Or set `synchronous disable` in BGP config to advertise without underlying route

### Route-Map Usage
Route-maps allow you to:
- Set BGP attributes (community, AS-path, MED, local-preference)
- Filter which routes are advertised
- Modify route attributes before advertisement

### FortiOS CLI Equivalent
```
config router bgp
  config network
    edit 1
      set prefix 10.100.0.0 255.255.255.0
      set route-map "SET_COMMUNITY_100"
    next
  end
end
```

## Related Tools
- `fortigate-single-hub-bgp-sdwan` - Complete SD-WAN + BGP provisioning
- `fortigate-health-check` - Verify device connectivity
- `fortigate-routing-table` - View current routing table

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "BGP not configured" | No BGP AS set | Configure BGP first |
| "Network already exists" | Duplicate prefix | Use list to check existing |
| "Invalid prefix format" | Bad IP/mask | Use CIDR or mask format |
| "Route-map not found" | Missing route-map | Create route-map first |
