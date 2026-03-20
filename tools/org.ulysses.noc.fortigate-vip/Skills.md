# FortiGate VIP Tool

## Purpose
CRUD operations for Virtual IP (VIP) objects on FortiGate devices. Configure static NAT, port forwarding, and load balancing VIPs.

## When to Use
- Creating destination NAT rules for inbound traffic
- Port forwarding external ports to internal servers
- Setting up 1:1 NAT mappings
- Creating VIPs to reference in firewall policies

## Parameters

### Required
| Parameter | Type | Description |
|-----------|------|-------------|
| target_ip | string | FortiGate management IP |
| action | string | add, update, remove, list, get |

### VIP Settings
| Parameter | Type | Description |
|-----------|------|-------------|
| name | string | VIP name (required for add/update/remove/get) |
| extip | string | External IP address (required for add) |
| mappedip | string | Internal/mapped IP address (required for add) |
| extintf | string | External interface receiving traffic (required for add) |

### Port Forwarding
| Parameter | Type | Description |
|-----------|------|-------------|
| portforward | string | enable/disable port forwarding |
| protocol | string | tcp, udp, sctp, icmp |
| extport | string | External port or range (e.g., "541" or "80-443") |
| mappedport | string | Mapped port or range |

### Optional
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | static-nat (default), load-balance, server-load-balance |
| comment | string | VIP description |
| arp_reply | string | enable/disable ARP reply |
| color | integer | Icon color (0-32) |

## Usage Examples

### List VIPs
```json
{
  "target_ip": "192.168.215.15",
  "action": "list"
}
```

### Add Static NAT VIP (No Port Forwarding)
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "VIP_WebServer",
  "extip": "192.168.215.100",
  "mappedip": "10.10.10.50",
  "extintf": "wan1"
}
```

### Add Port Forwarding VIP
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "VIP_541_FMG",
  "extip": "192.168.215.17",
  "mappedip": "10.250.250.100",
  "extintf": "SPOKE_VPN1",
  "portforward": "enable",
  "protocol": "tcp",
  "extport": "541",
  "mappedport": "541"
}
```

### Add ICMP VIP (for ping forwarding)
```json
{
  "target_ip": "192.168.215.15",
  "action": "add",
  "name": "VIP_ICMP_Server",
  "extip": "192.168.215.17",
  "mappedip": "10.250.250.100",
  "extintf": "SPOKE_VPN1",
  "portforward": "enable",
  "protocol": "icmp"
}
```

### Update VIP
```json
{
  "target_ip": "192.168.215.15",
  "action": "update",
  "name": "VIP_541_FMG",
  "comment": "FortiManager access via SD-WAN"
}
```

### Remove VIP
```json
{
  "target_ip": "192.168.215.15",
  "action": "remove",
  "name": "VIP_541_FMG"
}
```

## FortiOS CLI Equivalent

```
config firewall vip
  edit "VIP_541_FMG"
    set extip 192.168.215.17
    set mappedip "10.250.250.100"
    set extintf "SPOKE_VPN1"
    set portforward enable
    set protocol tcp
    set extport 541
    set mappedport 541
  next
end
```

## Using VIPs in Firewall Policies

VIPs are referenced as destination addresses in firewall policies:

```
config firewall policy
  edit 100
    set srcintf "wan1"
    set dstintf "internal"
    set srcaddr "all"
    set dstaddr "VIP_541_FMG"    <-- VIP reference
    set action accept
    set schedule "always"
    set service "TCP_541"
  next
end
```

## Output Examples

### List Response
```json
{
  "success": true,
  "action": "list",
  "count": 2,
  "vips": [
    {
      "name": "VIP_541_FMG",
      "extip": "192.168.215.17",
      "mappedip": "10.250.250.100",
      "extintf": "SPOKE_VPN1",
      "portforward": "enable",
      "protocol": "tcp",
      "extport": "541",
      "mappedport": "541"
    }
  ]
}
```

## Troubleshooting

### VIP Not Working
1. Verify external interface is correct
2. Check firewall policy references the VIP in dstaddr
3. Ensure ARP reply is enabled if needed
4. Verify no IP conflicts with extip

### Port Forwarding Issues
1. Check protocol matches traffic type
2. Verify extport/mappedport are correct
3. Ensure service in firewall policy matches ports

## Related Tools
- `fortigate-firewall-policy` - Create policies referencing VIPs
- `fortigate-address` - Create address objects

## API Reference
- Endpoint: `/api/v2/cmdb/firewall/vip`
- Methods: GET, POST, PUT, DELETE
- Auth: Bearer token
