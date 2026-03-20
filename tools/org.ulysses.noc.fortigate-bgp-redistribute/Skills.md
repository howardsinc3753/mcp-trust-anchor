# FortiGate BGP Redistribute

## Purpose

Configure BGP route redistribution on FortiGate devices. Controls which routes are redistributed into BGP from connected networks, static routes, or other routing protocols.

## When to Use

- **Advertise LAN**: Redistribute connected routes for branch LANs
- **Static Route Advertisement**: Share static routes via BGP
- **OSPF to BGP**: Redistribute OSPF routes into BGP backbone
- **Filtered Redistribution**: Apply route-maps to control what's advertised

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | get or set (default: get) |
| redistribute_connected | string | No | Redistribute connected routes |
| redistribute_connected_routemap | string | No | Route-map filter |
| redistribute_static | string | No | Redistribute static routes |
| redistribute_static_routemap | string | No | Route-map filter |
| redistribute_ospf | string | No | Redistribute OSPF routes |

## Example Usage

### Redistribute Connected with Route-Map

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-bgp-redistribute/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "set",
    "redistribute_connected": "enable",
    "redistribute_connected_routemap": "CONNECTED_TO_BGP"
  }
}
```

## CLI Equivalent

```
config router bgp
  config redistribute "connected"
    set status enable
    set route-map "CONNECTED_TO_BGP"
  end
end
```

## Related Tools

- `fortigate-route-map`: Create route-maps for filtering
- `fortigate-bgp-config`: Configure BGP global settings
