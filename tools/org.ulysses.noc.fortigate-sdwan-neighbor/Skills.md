# FortiGate SD-WAN Neighbor Tool

## Purpose
CRUD operations for SD-WAN neighbor statements on FortiGate devices. Configure BGP neighbors for SD-WAN ADVPN with health check bindings and route metric selection.

Based on Fortinet 4D-Demo configurations and FortiOS 7.6+ SD-WAN features.

## When to Use
- Configuring SD-WAN BGP neighbor statements for ADVPN
- Binding BGP neighbors to health checks for SLA-based routing
- Setting up hub-spoke BGP peering with SD-WAN awareness
- Managing neighbor-to-member bindings for overlay traffic steering

## Understanding SD-WAN Neighbors

### What is an SD-WAN Neighbor?
SD-WAN neighbors bind BGP peer IPs to SD-WAN members and health checks. This enables:
- **SLA-based BGP path selection** - BGP uses SD-WAN health metrics
- **Member binding** - Associate a BGP peer with specific overlay tunnels
- **Priority-based routing** - Route metric follows SD-WAN priority

### How It Works
```
BGP Neighbor (172.16.255.253)
    │
    ├── Bound to SD-WAN Members [3, 4]
    │       ├── Member 3 = HUB1_VPN1 tunnel
    │       └── Member 4 = HUB1_VPN2 tunnel
    │
    ├── Health Check: "HUB"
    │       └── Provides SLA metrics (latency, jitter, loss)
    │
    └── Route Metric: priority
            └── BGP uses SD-WAN member priority for path selection
```

## Parameters

### Required
| Parameter | Type | Description |
|-----------|------|-------------|
| target_ip | string | FortiGate management IP |
| action | string | `add`, `update`, `remove`, `list`, `get` |

### Neighbor Settings
| Parameter | Type | Description |
|-----------|------|-------------|
| ip | string | BGP neighbor IP (required for add/update/remove/get) |
| members | array[int] | SD-WAN member seq-nums to bind (e.g., [3, 4]) |
| route_metric | string | Route metric method: `priority`, `latency`, `jitter`, `packetloss`, `bandwidth` |
| health_check | string | Health check name for SLA binding |
| sla_id | integer | SLA ID within health check (optional) |
| minimum_sla_meet_members | integer | Min members meeting SLA (default: 1) |

## Usage Examples

### List All SD-WAN Neighbors
```json
{
  "target_ip": "192.168.209.30",
  "action": "list"
}
```

### Add Neighbor (Spoke → Hub BGP Peer)
Bind hub BGP peer to overlay members with health check:
```json
{
  "target_ip": "192.168.209.30",
  "action": "add",
  "ip": "172.16.255.253",
  "members": [3, 4],
  "route_metric": "priority",
  "health_check": "HUB"
}
```

### Add Neighbor with SLA ID
```json
{
  "target_ip": "192.168.209.30",
  "action": "add",
  "ip": "172.16.255.253",
  "members": [3, 4],
  "route_metric": "priority",
  "health_check": "HUB",
  "sla_id": 1
}
```

### Update Neighbor
```json
{
  "target_ip": "192.168.209.30",
  "action": "update",
  "ip": "172.16.255.253",
  "route_metric": "latency"
}
```

### Remove Neighbor
```json
{
  "target_ip": "192.168.209.30",
  "action": "remove",
  "ip": "172.16.255.253"
}
```

## FortiOS CLI Equivalent

### Spoke SD-WAN Neighbor Configuration (from 4D-Demo)
```
config system sdwan
  config neighbor
    edit "172.16.255.253"
      set member 3 4
      set route-metric priority
      set health-check "HUB"
    next
  end
end
```

### Hub SD-WAN Neighbor Configuration
Hub needs neighbor entries for each spoke:
```
config system sdwan
  config neighbor
    edit "172.16.0.2"
      set member 1 2
      set route-metric priority
      set health-check "From_Edge"
    next
    edit "172.16.0.3"
      set member 1 2
      set route-metric priority
      set health-check "From_Edge"
    next
  end
end
```

## Route Metric Options

| Value | Description | Use Case |
|-------|-------------|----------|
| `priority` | Use SD-WAN member priority | Most common - follows SD-WAN priority-in-sla/priority-out-sla |
| `latency` | Route via lowest latency path | Latency-sensitive applications |
| `jitter` | Route via lowest jitter path | VoIP/video applications |
| `packetloss` | Route via lowest loss path | Critical data transfers |
| `bandwidth` | Route via highest bandwidth path | Bulk transfers |

## Prerequisites

### 1. SD-WAN Members Must Exist
Before adding neighbors, ensure SD-WAN members are configured:
```
config system sdwan
  config members
    edit 3
      set interface "HUB1_VPN1"
      set zone "SDWAN_OVERLAY"
    next
    edit 4
      set interface "HUB1_VPN2"
      set zone "SDWAN_OVERLAY"
    next
  end
end
```

### 2. Health Check Must Exist
The referenced health check must be configured:
```
config system sdwan
  config health-check
    edit "HUB"
      set server "172.16.255.253"
      set members 3 4
      ...
    next
  end
end
```

### 3. BGP Neighbor Must Exist
Configure BGP neighbor with SD-WAN zone:
```
config router bgp
  config neighbor
    edit "172.16.255.253"
      set remote-as 65000
      set interface "Spoke_Lo"
      set update-source "Spoke_Lo"
      set soft-reconfiguration enable
      set connect-timer 1
      set advertisement-interval 1
      set capability-graceful-restart enable
      set additional-path both
    next
  end
end
```

### 4. Firewall Policy for Health Check Probes (CRITICAL)
Health check probes (ICMP ping) MUST be allowed by firewall policy:

**Spoke Policy (allows pings to hub loopback):**
```
config firewall policy
  edit 100
    set name "SDWAN_Health_Probe"
    set srcintf "Spoke_Lo"
    set dstintf "SDWAN_OVERLAY"
    set srcaddr "all"
    set dstaddr "all"
    set action accept
    set schedule "always"
    set service "PING"
  next
end
```

**Hub Policy (allows pings from spokes):**
```
config firewall policy
  edit 100
    set name "SDWAN_Health_Probe"
    set srcintf "SDWAN_OVERLAY"
    set dstintf "Hub_Lo"
    set srcaddr "all"
    set dstaddr "all"
    set action accept
    set schedule "always"
    set service "PING"
  next
end
```

## Output Examples

### List Response
```json
{
  "success": true,
  "action": "list",
  "count": 1,
  "neighbors": [
    {
      "ip": "172.16.255.253",
      "member": [3, 4],
      "route-metric": "priority",
      "health-check": "HUB",
      "sla-id": 0
    }
  ]
}
```

### Add Response
```json
{
  "success": true,
  "action": "add",
  "neighbor": {
    "ip": "172.16.255.253",
    "members": [3, 4],
    "route_metric": "priority",
    "health_check": "HUB"
  },
  "message": "SD-WAN neighbor 172.16.255.253 added with members [3, 4]"
}
```

## Troubleshooting

### Neighbor Not Affecting BGP Routing
1. **Verify SD-WAN member seq-nums** - Must match actual member configuration
2. **Check health check exists** - Name must match exactly
3. **Verify health check members** - Health check must include the same members
4. **Check BGP is configured** - Neighbor must exist in `router bgp` config

### Health Check Failing
1. **Firewall policy** - Ensure ICMP is allowed between loopbacks
2. **Tunnel status** - IPsec tunnel must be UP
3. **Loopback reachability** - Verify routing to peer loopback
4. **Diagnose command**: `diagnose sys sdwan health-check status`

### BGP Not Using SD-WAN Metrics
1. **Check route-metric** - Must be set (default: priority)
2. **Verify SD-WAN neighbor binding** - Run `get system sdwan neighbor`
3. **Check SLA status** - Health check must be passing

## Workflow: Complete SD-WAN Neighbor Setup

### Step 1: Verify Prerequisites
```
fortigate-health-check target_ip=192.168.209.30
```

### Step 2: Check Existing Members
```json
{
  "tool": "fortigate-sdwan-member",
  "action": "list",
  "target_ip": "192.168.209.30"
}
```

### Step 3: Check Health Check
```json
{
  "tool": "fortigate-sdwan-health-check",
  "action": "list",
  "target_ip": "192.168.209.30"
}
```

### Step 4: Add SD-WAN Neighbor
```json
{
  "tool": "fortigate-sdwan-neighbor",
  "action": "add",
  "target_ip": "192.168.209.30",
  "ip": "172.16.255.253",
  "members": [3, 4],
  "route_metric": "priority",
  "health_check": "HUB"
}
```

### Step 5: Verify
```
# On FortiGate CLI:
get router info bgp summary
diagnose sys sdwan neighbor
```

## Related Tools
- `fortigate-sdwan-health-check` - Configure health checks with SLA
- `fortigate-sdwan-member` - Configure SD-WAN members
- `fortigate-sdwan-zone` - Configure SD-WAN zones with ADVPN
- `fortigate-bgp-neighbor` - Configure BGP neighbors
- `fortigate-sdwan-rule` - Configure SD-WAN steering rules

## API Reference
- Endpoint: `/api/v2/cmdb/system/sdwan/neighbor`
- Methods: GET, POST, PUT, DELETE
- Auth: Bearer token

## References
- [Fortinet SD-WAN Remote SLAs](https://community.fortinet.com/t5/FortiGate/Technical-Tip-Fortinet-SD-WAN-Remote-SLAs/ta-p/375338)
- [FortiOS 7.6 Embed SLA Priorities in ICMP Probes](https://docs.fortinet.com/document/fortigate/7.6.0/sd-wan-new-features/640630/embed-sla-priorities-in-icmp-probes)
- [Fortinet 4D-Demo GitHub](https://github.com/fortinet/4D-Demo)
