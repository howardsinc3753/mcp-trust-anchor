# FortiGate Route Map

## Purpose

Manage route-maps on FortiGate devices for BGP policy control. Route-maps filter and modify routes during redistribution and neighbor advertisement.

## When to Use

- **Route Filtering**: Permit/deny specific prefixes
- **Attribute Modification**: Set local-pref, MED, AS-path
- **Redistribution Control**: Filter routes entering BGP
- **Neighbor Policy**: Control what's advertised to peers

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| action | string | No | list, get, add, update, remove (default: list) |
| name | string | Conditional | Route-map name |
| comments | string | No | Description |
| rule | object | No | Rule definition with match/set clauses |

### Rule Object

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Rule sequence number |
| action | string | permit or deny |
| match_ip_address | string | Match prefix-list |
| set_local_preference | integer | Set local-pref value |
| set_metric | integer | Set MED value |

## Example Usage

### Create Route-Map with Local-Pref

```json
{
  "canonical_id": "org.ulysses.noc.fortigate-route-map/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "action": "add",
    "name": "PREFER_VPN1",
    "comments": "Prefer VPN1 routes",
    "rule": {
      "id": 10,
      "action": "permit",
      "set_local_preference": 200
    }
  }
}
```

## CLI Equivalent

```
config router route-map
  edit "PREFER_VPN1"
    set comments "Prefer VPN1 routes"
    config rule
      edit 10
        set action permit
        set set-local-preference 200
      next
    end
  next
end
```

## Related Tools

- `fortigate-bgp-redistribute`: Use route-maps for redistribution
- `fortigate-bgp-neighbor`: Apply to neighbor in/out policy
