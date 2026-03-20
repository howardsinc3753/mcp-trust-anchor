# FortiGate IPsec

## Purpose
CRUD operations for IPsec Phase1 and Phase2 interfaces on FortiGate devices. Essential for SD-WAN deployments using IPsec overlays.

## When to Use
- Creating IPsec tunnels for SD-WAN spokes connecting to hubs
- Setting up site-to-site VPNs
- Managing ADVPN (Auto-Discovery VPN) configurations
- Updating tunnel parameters (PSK rotation, DPD settings)

## Actions

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `list` | List all Phase1 or Phase2 tunnels | target_ip, phase |
| `get` | Get specific tunnel details | target_ip, phase, name |
| `add` | Create new tunnel | target_ip, phase, name, (type-specific) |
| `update` | Update tunnel settings | target_ip, phase, name, (fields to update) |
| `remove` | Delete tunnel | target_ip, phase, name |

## Parameters

### Common Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | Yes | add, update, remove, list, get |
| phase | string | No | "1" or "2" (default: "1") |
| name | string | For CRUD | Tunnel name |

### Phase1 Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| interface | string | For add | Outbound interface (e.g., "port1") |
| remote_gw | string | No | Remote gateway (0.0.0.0 for dynamic) |
| psksecret | string | For add | Pre-shared key |
| ike_version | integer | No | 1 or 2 (default: 2) |
| type | string | No | "static" or "dynamic" |
| net_device | string | No | "enable"/"disable" for SD-WAN |
| network_overlay | string | No | "enable"/"disable" for overlay |
| network_id | integer | No | Network ID (1-255) |
| localid | string | No | Local ID for IKE negotiation (e.g., "Spoke2-HUB1-VPN1") |
| transport | string | No | IKE transport: "udp", "tcp", "auto" (default: udp) |
| dpd | string | No | "on-idle", "on-demand", "disable" |
| dpd_retrycount | integer | No | DPD retry count |
| dpd_retryinterval | integer | No | DPD retry interval |

### Phase2 Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| phase1name | string | For add | Associated Phase1 name |
| src_subnet | string | No | Source subnet (e.g., "0.0.0.0/0") |
| dst_subnet | string | No | Destination subnet |
| auto_negotiate | string | No | "enable"/"disable" |
| pfs | string | No | Perfect forward secrecy |
| keylifeseconds | integer | No | Key lifetime in seconds |

## Usage Examples

### List All Phase1 Tunnels
```json
{
  "target_ip": "192.168.1.99",
  "action": "list",
  "phase": "1"
}
```

### List All Phase2 Tunnels
```json
{
  "target_ip": "192.168.1.99",
  "action": "list",
  "phase": "2"
}
```

### List Phase2 for Specific Phase1
```json
{
  "target_ip": "192.168.1.99",
  "action": "list",
  "phase": "2",
  "phase1name": "HUB1-VPN1"
}
```

### Create Phase1 (Static Tunnel to Hub)
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "phase": "1",
  "name": "HUB1-VPN1",
  "interface": "port1",
  "remote_gw": "10.0.0.1",
  "psksecret": "MySecretKey123!",
  "ike_version": 2,
  "net_device": "enable",
  "dpd": "on-idle",
  "dpd_retrycount": 3,
  "dpd_retryinterval": 10
}
```

### Create Phase1 (Dynamic Hub)
```json
{
  "target_ip": "10.0.0.1",
  "action": "add",
  "phase": "1",
  "name": "SPOKE-VPN",
  "interface": "port1",
  "remote_gw": "0.0.0.0",
  "psksecret": "MySecretKey123!",
  "type": "dynamic",
  "net_device": "enable",
  "network_overlay": "enable",
  "network_id": 1
}
```

### Create Phase1 for SD-WAN with ADVPN
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "phase": "1",
  "name": "HUB1-VPN1",
  "interface": "port1",
  "remote_gw": "10.0.0.1",
  "psksecret": "MySecretKey123!",
  "ike_version": 2,
  "net_device": "enable",
  "network_overlay": "enable",
  "network_id": 1,
  "auto_discovery_receiver": "enable",
  "exchange_ip_addr4": "172.16.0.3"
}
```

### Create Phase2
```json
{
  "target_ip": "192.168.1.99",
  "action": "add",
  "phase": "2",
  "name": "HUB1-VPN1-P2",
  "phase1name": "HUB1-VPN1",
  "src_subnet": "0.0.0.0/0",
  "dst_subnet": "0.0.0.0/0",
  "auto_negotiate": "enable"
}
```

### Update Phase1 PSK
```json
{
  "target_ip": "192.168.1.99",
  "action": "update",
  "phase": "1",
  "name": "HUB1-VPN1",
  "psksecret": "NewSecretKey456!"
}
```

### Update DPD Settings
```json
{
  "target_ip": "192.168.1.99",
  "action": "update",
  "phase": "1",
  "name": "HUB1-VPN1",
  "dpd": "on-idle",
  "dpd_retrycount": 5,
  "dpd_retryinterval": 15
}
```

### Update LocalID (Important for Hub Authentication)
```json
{
  "target_ip": "192.168.1.99",
  "action": "update",
  "phase": "1",
  "name": "HUB1-VPN1",
  "localid": "Spoke2-HUB1-VPN1"
}
```

**Note:** The `localid` parameter is critical when connecting to a hub that validates spoke identity. If the tunnel shows AUTHENTICATION_FAILED, often the localid is missing or incorrect.

### Delete Phase2 (Must delete before Phase1)
```json
{
  "target_ip": "192.168.1.99",
  "action": "remove",
  "phase": "2",
  "name": "HUB1-VPN1-P2"
}
```

### Delete Phase1
```json
{
  "target_ip": "192.168.1.99",
  "action": "remove",
  "phase": "1",
  "name": "HUB1-VPN1"
}
```

## Response Examples

### List Phase1 Response
```json
{
  "success": true,
  "action": "list",
  "target_ip": "192.168.1.99",
  "phase": "1",
  "count": 2,
  "phase1_interfaces": [
    {"name": "HUB1-VPN1", "type": "static", "interface": "port1", "remote-gw": "10.0.0.1"},
    {"name": "HUB2-VPN2", "type": "static", "interface": "port1", "remote-gw": "10.0.0.2"}
  ],
  "message": "Found 2 Phase1 interfaces"
}
```

### Add Response
```json
{
  "success": true,
  "action": "add",
  "target_ip": "192.168.1.99",
  "phase": "1",
  "name": "HUB1-VPN1",
  "type": "static",
  "message": "Created Phase1 interface 'HUB1-VPN1'"
}
```

## SD-WAN Tunnel Configuration

For SD-WAN with BGP over IPsec overlay:

### Phase1 Settings
```
net-device: enable      # Required for SD-WAN
network-overlay: enable # For ADVPN shortcut
network-id: 1          # Unique per overlay
auto-discovery-receiver: enable  # Spoke receives shortcuts
exchange-ip-addr4: 172.16.0.X    # Loopback IP for BGP
```

### Phase2 Settings
```
src-subnet: 0.0.0.0/0   # All traffic through tunnel
dst-subnet: 0.0.0.0/0
auto-negotiate: enable
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Phase1 already exists | Duplicate name | Use different name or update existing |
| Phase1 not found | Invalid phase1name | Check Phase1 exists before creating Phase2 |
| Cannot delete Phase1 | Phase2 still exists | Delete all associated Phase2 first |
| PSK required | Missing psksecret | Provide pre-shared key for new tunnels |

## Deletion Order

When removing tunnels:
1. First delete all Phase2 interfaces
2. Then delete the Phase1 interface

```
# Delete order
Phase2: HUB1-VPN1-P2 → Phase1: HUB1-VPN1
```

## Related Tools
- `fortigate-interface` - Create loopback for exchange-ip-addr4
- `fortigate-sdwan-member` - Add tunnel to SD-WAN
- `fortigate-sdwan-health-check` - Configure health checks
- `fortigate-firewall-policy` - Create policies for tunnel traffic
- `fortigate-config-push` - Bulk config alternative

## Typical SD-WAN Spoke Workflow

1. **Create loopback** (fortigate-interface):
   ```json
   {"action": "add", "name": "Spoke-Lo", "type": "loopback", "ip": "172.16.0.3/32"}
   ```

2. **Create Phase1** (this tool):
   ```json
   {"action": "add", "phase": "1", "name": "HUB1-VPN1", ...}
   ```

3. **Create Phase2** (this tool):
   ```json
   {"action": "add", "phase": "2", "name": "HUB1-VPN1-P2", "phase1name": "HUB1-VPN1", ...}
   ```

4. **Add SD-WAN member** (fortigate-sdwan-member):
   ```json
   {"action": "add", "interface": "HUB1-VPN1", "source": "172.16.0.3"}
   ```
