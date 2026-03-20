# FortiGate BGP Config

## Purpose

Configure BGP global settings on FortiGate devices. This tool manages the BGP process configuration, not individual neighbors (use `fortigate-bgp-neighbor` for that).

Essential for SD-WAN deployments requiring BGP routing between hubs and spokes.

## When to Use

- **Initial BGP Setup**: Configure AS number and router-id before adding neighbors
- **SD-WAN ECMP**: Enable ibgp-multipath for load balancing across multiple overlays
- **Overlay Routing**: Enable recursive-next-hop for SD-WAN tunnel next-hops
- **High Availability**: Configure graceful-restart for hitless failover
- **Tuning**: Adjust scan-time, MED behavior, or path selection

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP address |
| action | string | No | `get` (default) or `set` |
| as | integer | No | BGP Autonomous System number |
| router_id | string | No | BGP router ID (typically loopback IP) |
| ibgp_multipath | string | No | Enable IBGP multipath (`enable`/`disable`) |
| ibgp_multipath_same_as | string | No | Allow multipath for same-AS neighbors |
| recursive_next_hop | string | No | Enable recursive next-hop resolution |
| graceful_restart | string | No | Enable BGP graceful restart |
| graceful_restart_time | integer | No | Restart time in seconds (default 120) |
| graceful_stalepath_time | integer | No | Stalepath time in seconds (default 360) |
| scan_time | integer | No | Route scan interval in seconds |

## Example Usage

### Get Current BGP Config

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-config/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "get"
  }
}
```

### Configure BGP for SD-WAN Hub

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-config/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "as": 65000,
    "router_id": "10.200.99.1",
    "ibgp_multipath": "enable",
    "recursive_next_hop": "enable",
    "graceful_restart": "enable"
  }
}
```

### Configure BGP for SD-WAN Spoke

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-config/1.0.0",
  "parameters": {
    "target_ip": "192.168.1.1",
    "action": "set",
    "as": 65000,
    "router_id": "10.200.99.101",
    "ibgp_multipath": "enable",
    "recursive_next_hop": "enable"
  }
}
```

## Response Format

### Get Response

```json
{
  "success": true,
  "action": "get",
  "target_ip": "192.168.209.35",
  "bgp_config": {
    "as": 65000,
    "router-id": "10.200.99.1",
    "ibgp-multipath": "enable",
    "recursive-next-hop": "enable",
    "graceful-restart": "enable",
    "graceful-restart-time": 120,
    "scan-time": 60,
    "neighbor_count": 4
  },
  "message": "BGP AS 65000, Router-ID 10.200.99.1"
}
```

### Set Response

```json
{
  "success": true,
  "action": "set",
  "target_ip": "192.168.209.35",
  "updated_fields": ["as", "router-id", "ibgp-multipath", "recursive-next-hop"],
  "message": "Updated BGP configuration: as, router-id, ibgp-multipath, recursive-next-hop"
}
```

## SD-WAN Best Practices

For FortiGate SD-WAN deployments:

1. **Use IBGP (same AS)**: All hubs and spokes should use the same AS number
2. **Enable ibgp-multipath**: Required for ECMP across multiple overlay tunnels
3. **Enable recursive-next-hop**: Required when BGP next-hops are reachable via overlay tunnels
4. **Set unique router-id**: Use loopback IP to ensure unique router-id per device
5. **Enable graceful-restart**: Prevents route flapping during tunnel failover

## CLI Equivalent

```
config router bgp
    set as 65000
    set router-id 10.200.99.1
    set ibgp-multipath enable
    set recursive-next-hop enable
    set graceful-restart enable
end
```

## Related Tools

- `fortigate-bgp-neighbor`: Add/remove BGP neighbors
- `fortigate-bgp-troubleshoot`: Diagnose BGP issues
- `fortigate-sdwan-status`: Check SD-WAN overlay status
- `fortigate-ipsec`: Configure IPsec tunnels for overlays

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "No credentials found" | Missing API token | Add device to fortigate_credentials.yaml |
| "Failed to update BGP config" | Invalid parameter value | Check FortiOS documentation for valid values |
| "AS number required" | Setting neighbor without AS | Configure AS number first with this tool |
