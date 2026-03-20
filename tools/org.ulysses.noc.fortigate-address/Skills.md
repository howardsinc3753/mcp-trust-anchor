# FortiGate Address

## Purpose
CRUD operations for firewall address objects. Create address objects before using them in firewall policies.

## Address Types

| Type | Description | Required Field |
|------|-------------|----------------|
| `ipmask` | Subnet/host | subnet |
| `iprange` | IP range | start_ip, end_ip |
| `fqdn` | Domain name | fqdn |
| `geography` | Country | country |

## Usage Examples

### List All Addresses
```json
{"target_ip": "192.168.1.99", "action": "list"}
```

### Create Subnet Address
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "LAN_Network",
  "type": "ipmask",
  "subnet": "10.3.1.0/24",
  "comment": "Local LAN subnet"
}
```

### Create Host Address
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "Server01",
  "type": "ipmask",
  "subnet": "10.3.1.100/32"
}
```

### Create IP Range
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "DHCP_Range",
  "type": "iprange",
  "start_ip": "10.3.1.100",
  "end_ip": "10.3.1.200"
}
```

### Create FQDN Address
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "name": "Google_DNS",
  "type": "fqdn",
  "fqdn": "dns.google.com"
}
```

### Delete Address
```json
{
  "target_ip": "192.168.1.99",
  "action": "remove",
  "name": "LAN_Network"
}
```

## Built-in Addresses
FortiGate has built-in addresses you can use without creating:
- `all` - Any address (0.0.0.0/0)
- `none` - No address
- Various predefined objects

## Related Tools
- `fortigate-firewall-policy` - Use addresses in policies
- `fortigate-address-group` - Group multiple addresses
