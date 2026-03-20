# FortiGate Single-Hub BGP SD-WAN Template - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.provisioning.fortigate-single-hub-bgp-sdwan/1.0.0`
- **Domain:** provisioning
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Case
Provision a complete SD-WAN topology with BGP routing over IPsec overlay.
Use this when you need:
- Hub-spoke SD-WAN with dynamic routing
- iBGP for route exchange over the overlay
- Automated provisioning of both hub and spoke roles

### Architecture
```
                    ┌─────────────────────┐
                    │   HUB (AS 65000)    │
                    │  Lo: 172.16.255.253 │
                    │  BGP neighbor-range │
                    │   (172.16.0.0/16)   │
                    └─────────┬───────────┘
                              │ IPsec (dynamic)
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
        │  Spoke 1  │   │  Spoke 2  │   │  Spoke N  │
        │ 172.16.0.1│   │ 172.16.0.2│   │ 172.16.0.N│
        │  AS 65000 │   │  AS 65000 │   │  AS 65000 │
        └───────────┘   └───────────┘   └───────────┘
```

## Parameters

### Hub Role
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| role | Yes | - | Set to "hub" |
| target_ip | Yes | - | Hub management IP |
| hub_loopback_ip | Yes | - | Hub loopback (e.g., "172.16.255.253 255.255.255.255") |
| psk | Yes | - | Pre-shared key |
| bgp_as | No | 65000 | BGP AS number |
| tunnel_name | No | SPOKE_VPN1 | IPsec tunnel name |
| sdwan_zone | No | SDWAN_OVERLAY | SD-WAN zone |
| network_id | No | 1 | Overlay network ID |

### Spoke Role
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| role | Yes | - | Set to "spoke" |
| target_ip | Yes | - | Spoke management IP |
| hub_wan_ip | Yes | - | Hub's WAN IP |
| hub_loopback_ip | Yes | - | Hub's loopback IP |
| spoke_loopback_ip | Yes | - | Spoke loopback (e.g., "172.16.0.2 255.255.255.255") |
| psk | Yes | - | Pre-shared key (must match hub) |
| bgp_as | No | 65000 | BGP AS number (must match hub) |

## Example Usage

### Provision Hub
```json
{
  "role": "hub",
  "target_ip": "192.168.215.15",
  "hub_loopback_ip": "172.16.255.253 255.255.255.255",
  "psk": "fortinet123",
  "bgp_as": 65000,
  "tunnel_name": "SPOKE_VPN1",
  "sdwan_zone": "SDWAN_OVERLAY"
}
```

### Provision Spoke
```json
{
  "role": "spoke",
  "target_ip": "192.168.209.30",
  "hub_wan_ip": "192.168.215.15",
  "hub_loopback_ip": "172.16.255.253 255.255.255.255",
  "spoke_loopback_ip": "172.16.0.2 255.255.255.255",
  "psk": "fortinet123",
  "bgp_as": 65000,
  "tunnel_name": "HUB_VPN1"
}
```

## Components Created

### Hub
| Component | Details |
|-----------|---------|
| Loopback | Hub_Lo with loopback IP |
| Phase1 | Dynamic IPsec (type=dynamic, net-device=disable) |
| Phase2 | Quick mode config |
| SD-WAN Zone | SDWAN_OVERLAY |
| SD-WAN Member | Tunnel -> zone |
| Static Route | 172.16.0.0/24 via tunnel |
| BGP | AS 65000, neighbor-group EDGE, neighbor-range 172.16.0.0/16 |
| Firewall Policy | Loopback <-> SD-WAN zone |

### Spoke
| Component | Details |
|-----------|---------|
| Loopback | Spoke_Lo with loopback IP |
| Phase1 | Static IPsec to hub WAN IP |
| Phase2 | Quick mode config |
| SD-WAN Zone | SDWAN_OVERLAY |
| SD-WAN Member | Tunnel -> zone |
| Health Check | HUB_Health -> hub loopback |
| Static Route | 172.16.255.0/24 via tunnel |
| BGP | AS 65000, neighbor 172.16.255.253 |
| Firewall Policy | Loopback <-> SD-WAN zone |

## BGP Configuration Details

### Hub BGP
- Uses **neighbor-range** to accept any peer from 172.16.0.0/16
- Uses **neighbor-group** EDGE with:
  - next-hop-self enabled
  - graceful-restart enabled
  - soft-reconfiguration enabled
  - update-source: Hub loopback

### Spoke BGP
- Static neighbor to hub loopback (172.16.255.253)
- Uses spoke loopback as update-source
- Redistributes connected networks

## Key Technical Notes

1. **IPsec exchange-ip-addr4**: Both hub and spoke advertise their loopback IP via IKE extension
2. **net-device disable**: Hub Phase1 requires `net-device disable` for SD-WAN integration
3. **Static routes**: Required for initial BGP peering before routes are learned
4. **iBGP**: Same AS (65000) on hub and spokes for internal BGP peering

## Related Tools
- `fortigate-sdwan-hub-template` - Hub-only provisioning
- `fortigate-sdwan-spoke-template` - Spoke-only provisioning
- `fortigate-health-check` - Verify device connectivity
