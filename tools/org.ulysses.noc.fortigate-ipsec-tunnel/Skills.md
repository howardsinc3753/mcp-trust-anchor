# FortiGate IPsec Tunnel - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-ipsec-tunnel/1.0.0`
- **Domain:** noc
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Cases
1. **Failover testing** - Shutdown tunnel to test BGP/routing failover
2. **Inventory IPsec tunnels** - List all phase1 interfaces
3. **Monitor tunnel status** - Check if tunnels are up/down
4. **Maintenance windows** - Gracefully bring tunnels up/down

### SD-WAN Failover Testing Workflow
1. List tunnels to find tunnel name
2. Shutdown tunnel on Spoke
3. Verify BGP session drops (use fortigate-bgp-troubleshoot)
4. Verify traffic fails over to alternate path
5. Bring tunnel back up
6. Verify BGP re-establishes

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| target_ip | Yes | - | FortiGate management IP |
| action | No | list | Action to perform (see below) |
| tunnel_name | Conditional | - | Required for shutdown/up actions |
| verify_ssl | No | false | Verify SSL certificates |

### Actions

| Action | Description | Requires tunnel_name |
|--------|-------------|---------------------|
| list | List all IPsec phase1 interfaces | No |
| status | Get tunnel operational status | Optional (filters) |
| shutdown | Admin down the tunnel interface | Yes |
| down | Alias for shutdown | Yes |
| up | Admin up the tunnel interface | Yes |

## Example Usage

### List All IPsec Tunnels
```json
{
  "target_ip": "192.168.209.30",
  "action": "list"
}
```
**Output:**
```json
{
  "success": true,
  "action": "list",
  "target_ip": "192.168.209.30",
  "tunnels": [
    {
      "name": "SDWAN_OL_HUB",
      "interface": "wan",
      "remote_gw": "192.168.215.15",
      "type": "dynamic",
      "status": "up"
    }
  ],
  "count": 1
}
```

### Check Tunnel Status
```json
{
  "target_ip": "192.168.209.30",
  "action": "status"
}
```

### Shutdown Tunnel (Failover Test)
```json
{
  "target_ip": "192.168.209.30",
  "action": "shutdown",
  "tunnel_name": "SDWAN_OL_HUB"
}
```
**Output:**
```json
{
  "success": true,
  "action": "shutdown",
  "target_ip": "192.168.209.30",
  "interface": "SDWAN_OL_HUB",
  "status": "down",
  "message": "Interface 'SDWAN_OL_HUB' set to down"
}
```

### Bring Tunnel Back Up
```json
{
  "target_ip": "192.168.209.30",
  "action": "up",
  "tunnel_name": "SDWAN_OL_HUB"
}
```

## Failover Testing Workflow

### Step 1: List Tunnels
```json
{"target_ip": "192.168.209.30", "action": "list"}
```
Note the tunnel name(s).

### Step 2: Check Initial BGP State
Use `fortigate-bgp-troubleshoot`:
```json
{"target_ip": "192.168.209.30", "action": "summary"}
```
Verify BGP neighbor is established.

### Step 3: Shutdown Tunnel
```json
{"target_ip": "192.168.209.30", "action": "shutdown", "tunnel_name": "SDWAN_OL_HUB"}
```

### Step 4: Verify BGP Drops
Wait a few seconds for DPD/keepalive timeout, then:
```json
{"target_ip": "192.168.209.30", "action": "summary"}
```
BGP should show neighbor as Idle or not established.

### Step 5: Verify Failover
Test connectivity through alternate path (WAN).

### Step 6: Restore Tunnel
```json
{"target_ip": "192.168.209.30", "action": "up", "tunnel_name": "SDWAN_OL_HUB"}
```

### Step 7: Verify Recovery
```json
{"target_ip": "192.168.209.30", "action": "summary"}
```
BGP should re-establish.

## CLI Equivalents

| Tool Action | FortiOS CLI Command |
|-------------|---------------------|
| list | `get vpn ipsec tunnel summary` |
| status | `diagnose vpn tunnel list` |
| shutdown | `config system interface; edit <name>; set status down; end` |
| up | `config system interface; edit <name>; set status up; end` |

## Technical Notes

### Interface vs Phase1
- IPsec tunnels create virtual interfaces with the same name as phase1-interface
- Admin up/down is controlled via `/cmdb/system/interface/{name}`
- Phase1 config is at `/cmdb/vpn.ipsec/phase1-interface`

### Tunnel Status
- Status comes from `/monitor/vpn/ipsec`
- Shows incoming/outgoing bytes, remote gateway, etc.
- "proxyid" array indicates phase2 SAs are established

### DPD (Dead Peer Detection)
- After admin down, DPD on the remote end will eventually timeout
- Default DPD retry: 3 attempts, 20 second intervals = ~60 seconds
- BGP hold timer typically 90-180 seconds

## Related Tools
- `fortigate-bgp-troubleshoot` - Verify BGP state before/after failover
- `fortigate-sdwan-health-check` - Check SD-WAN member health
- `fortigate-health-check` - Device connectivity test

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "tunnel_name is required" | Missing parameter | Specify tunnel_name for shutdown/up |
| "Interface not found" | Wrong tunnel name | Use list action to find correct name |
| "Failed to set interface status" | API error | Check permissions, verify interface exists |
| "401 Unauthorized" | Invalid/expired token | Regenerate API token |
