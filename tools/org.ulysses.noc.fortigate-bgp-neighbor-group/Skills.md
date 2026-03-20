# FortiGate BGP Neighbor Group

## Purpose

Manage BGP neighbor groups on FortiGate devices. Neighbor groups define common settings for dynamic BGP neighbors, essential for SD-WAN/ADVPN deployments where spokes connect dynamically to hubs.

## When to Use

- **SD-WAN Hub Setup**: Create neighbor groups before configuring neighbor ranges
- **ADVPN Deployments**: Define settings for dynamically discovered spokes
- **Common Policy**: Apply consistent settings to multiple dynamic neighbors

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | list, get, add, update, remove (default: list) |
| name | string | Conditional | Group name (required for get/add/update/remove) |
| remote_as | integer | No | Remote AS number |
| update_source | string | No | Source interface for BGP updates |
| soft_reconfiguration | string | No | Enable soft reconfiguration |
| next_hop_self | string | No | Set self as next-hop |
| route_reflector_client | string | No | Configure as RR client |

## Example Usage

### Create Neighbor Group for Dynamic Spokes

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-neighbor-group/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "add",
    "name": "DYN_EDGE",
    "remote_as": 65000,
    "update_source": "loopback0",
    "soft_reconfiguration": "enable",
    "next_hop_self": "enable",
    "route_reflector_client": "enable"
  }
}
```

## CLI Equivalent

```
config router bgp
  config neighbor-group
    edit "DYN_EDGE"
      set remote-as 65000
      set update-source "loopback0"
      set soft-reconfiguration enable
      set next-hop-self enable
      set route-reflector-client enable
    next
  end
end
```

## Related Tools

- `fortigate-bgp-neighbor-range`: Accept neighbors from prefix using this group
- `fortigate-bgp-config`: Configure BGP global settings first
