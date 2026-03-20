# FortiGate Interface

## Purpose
CRUD operations for interfaces on FortiGate devices. Create loopbacks, VLANs, aggregates, or update existing interface settings consistently.

## When to Use
- Creating loopback interfaces for SD-WAN overlays
- Creating VLAN interfaces for network segmentation
- Updating interface IP addresses or allowaccess settings
- Listing all interfaces or filtering by type
- Deleting unused loopback/VLAN interfaces

## Actions

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `list` | List all interfaces | target_ip |
| `get` | Get specific interface | target_ip, name |
| `add` | Create new interface | target_ip, name, type |
| `update` | Update interface settings | target_ip, name, (fields to update) |
| `remove` | Delete interface | target_ip, name |

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | Yes | add, update, remove, list, get |
| name | string | For CRUD | Interface name |
| type | string | For add | loopback, vlan, aggregate, redundant |
| ip | string | No | IP address (e.g., "172.16.0.1/32") |
| allowaccess | string | No | Access methods: "ping https ssh http fgfm" |
| alias | string | No | Interface description |
| vlanid | integer | For VLAN | VLAN ID (1-4094) |
| interface | string | For VLAN | Parent physical interface |
| status | string | No | up or down |
| role | string | No | lan, wan, dmz, undefined |

## Usage Examples

### List All Interfaces
```json
{
  "target_ip": "192.168.1.99",
  "action": "list"
}
```

### List Only Loopback Interfaces
```json
{
  "target_ip": "192.168.1.99",
  "action": "list",
  "type": "loopback"
}
```

### Get Specific Interface
```json
{
  "target_ip": "192.168.1.99",
  "action": "get",
  "name": "port1"
}
```

### Create Loopback Interface
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "Spoke-Lo",
  "type": "loopback",
  "ip": "172.16.0.3/32",
  "allowaccess": "ping",
  "alias": "SD-WAN Overlay Source"
}
```

### Create VLAN Interface
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "VLAN100",
  "type": "vlan",
  "vlanid": 100,
  "interface": "port3",
  "ip": "10.100.1.1/24",
  "allowaccess": "ping https ssh",
  "role": "lan"
}
```

### Update Interface (Add HTTPS Access)
```json
{
  "target_ip": "192.168.1.99",
  "action": "update",
  "name": "port1",
  "allowaccess": "ping https ssh http fgfm"
}
```

### Update Interface IP
```json
{
  "target_ip": "192.168.1.99",
  "action": "update",
  "name": "Spoke-Lo",
  "ip": "172.16.0.5/32"
}
```

### Delete Loopback Interface
```json
{
  "target_ip": "192.168.1.99",
  "action": "remove",
  "name": "Spoke-Lo"
}
```

## Response Examples

### List Response
```json
{
  "success": true,
  "action": "list",
  "target_ip": "192.168.1.99",
  "count": 5,
  "interfaces": [
    {"name": "port1", "type": "physical", "ip": "192.168.1.99 255.255.255.0", "status": "up"},
    {"name": "port2", "type": "physical", "ip": "10.3.1.1 255.255.255.0", "status": "up"},
    {"name": "Spoke-Lo", "type": "loopback", "ip": "172.16.0.3 255.255.255.255", "status": "up"}
  ],
  "message": "Found 5 interfaces"
}
```

### Add Response
```json
{
  "success": true,
  "action": "add",
  "target_ip": "192.168.1.99",
  "name": "Spoke-Lo",
  "type": "loopback",
  "message": "Created loopback interface 'Spoke-Lo'"
}
```

### Update Response
```json
{
  "success": true,
  "action": "update",
  "target_ip": "192.168.1.99",
  "name": "port1",
  "updated_fields": ["allowaccess"],
  "message": "Updated interface 'port1'"
}
```

## Interface Types

| Type | Can Create | Can Delete | Notes |
|------|------------|------------|-------|
| physical | No | No | Hardware ports (port1, port2, etc.) |
| loopback | Yes | Yes | Virtual interfaces for overlays |
| vlan | Yes | Yes | Requires parent interface and VLAN ID |
| aggregate | Yes | Yes | Link aggregation (requires member interfaces) |
| redundant | Yes | Yes | Redundant interfaces |
| tunnel | No | No | Created via IPsec config |

## Valid allowaccess Values
- `ping` - ICMP ping
- `https` - HTTPS management
- `ssh` - SSH access
- `http` - HTTP management
- `fgfm` - FortiManager
- `fabric` - Security Fabric
- `snmp` - SNMP
- `telnet` - Telnet (not recommended)
- `radius-acct` - RADIUS accounting
- `probe-response` - Probe response
- `ftm` - FortiToken Mobile
- `speed-test` - Speed test

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Interface already exists | Name conflict | Use different name or update existing |
| Cannot create type | Invalid type | Use: loopback, vlan, aggregate, redundant |
| Cannot delete physical | Trying to delete hardware port | Physical interfaces cannot be removed |
| vlanid required | Missing for VLAN type | Provide vlanid parameter |
| interface required | Missing parent for VLAN | Provide parent interface name |
| Invalid allowaccess | Unknown access method | Use only valid allowaccess values |

## Related Tools
- `fortigate-interface-status` - Monitor interface health and errors
- `fortigate-config-push` - Push bulk CLI config
- `fortigate-sdwan-member` - Configure SD-WAN members using interfaces
- `fortigate-firewall-policy` - Create policies using interfaces

## SD-WAN Workflow Example

1. **Create loopback** (this tool):
   ```json
   {"action": "add", "name": "Spoke-Lo", "type": "loopback", "ip": "172.16.0.3/32"}
   ```

2. **Create IPsec tunnel** (fortigate-ipsec tool):
   ```json
   {"action": "add", "name": "HUB1-VPN1", ...}
   ```

3. **Add SD-WAN member** (fortigate-sdwan-member):
   ```json
   {"action": "add", "interface": "HUB1-VPN1", "source": "172.16.0.3"}
   ```

4. **Create firewall policy** (fortigate-firewall-policy):
   ```json
   {"action": "add", "srcintf": "port2", "dstintf": "HUB1-VPN1", ...}
   ```
