# FortiGate BGP Neighbor Range

## Purpose

Manage BGP neighbor ranges on FortiGate devices. Neighbor ranges allow dynamic BGP peer acceptance from specified IP prefixes, essential for SD-WAN hub deployments accepting dynamic spoke connections.

## When to Use

- **SD-WAN Hub**: Accept BGP peers from spoke overlay IP ranges
- **ADVPN**: Auto-accept BGP neighbors from discovered spokes
- **Dynamic Scaling**: Add new spokes without manual neighbor config

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | list, get, add, update, remove (default: list) |
| id | integer | Conditional | Range ID (required for get/update/remove) |
| prefix | string | Conditional | IP prefix (required for add) |
| neighbor_group | string | No | Neighbor group to apply |
| max_neighbor_num | integer | No | Max neighbors (0 = unlimited) |

## Example Usage

### Accept Spokes from Overlay Range

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-neighbor-range/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "add",
    "prefix": "10.10.0.0/16",
    "neighbor_group": "DYN_EDGE",
    "max_neighbor_num": 100
  }
}
```

## CLI Equivalent

```
config router bgp
  config neighbor-range
    edit 1
      set prefix 10.10.0.0/16
      set neighbor-group "DYN_EDGE"
      set max-neighbor-num 100
    next
  end
end
```

## Related Tools

- `fortigate-bgp-neighbor-group`: Create neighbor group first
- `fortigate-bgp-config`: Configure BGP global settings
