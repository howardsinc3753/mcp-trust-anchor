# FortiGate SD-WAN Health Check Tool

## Purpose
Create SD-WAN health checks on FortiGate devices with support for both SPOKE (active ping) and HUB (remote detection) modes. Based on Fortinet 4D-Demo configurations.

## When to Use
- Configuring SD-WAN health monitoring on spoke devices (active ping to hub)
- Setting up hub-side health checks (remote detection from spokes)
- Enabling ADVPN measured health embedding for shortcut routing
- Managing SLA-based health monitoring for overlay tunnels

## Mode Differences (Critical)

### SPOKE Mode (Active Ping)
- Actively pings the hub loopback IP
- Embeds measured health in ADVPN shortcuts
- Uses SLA thresholds (latency, jitter, packet loss)
- CLI: `embed-measured-health enable`

### HUB Mode (Remote Detection)
- Receives embedded health from spokes (passive)
- Uses `detect-mode remote`
- Sets `link-cost-factor remote` in SLA
- Does NOT actively probe

## Parameters

### Required
| Parameter | Type | Description |
|-----------|------|-------------|
| target_ip | string | FortiGate management IP |

### Action (Optional)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| action | string | list | `create`, `list`, or `delete` |

### Mode Selection
| Parameter | Type | Description |
|-----------|------|-------------|
| mode | string | `spoke` (active ping) or `hub` (remote detection) |
| name | string | Health check name (required for create/delete) |

### Spoke Mode Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| server | string | - | Hub loopback IP to ping (required for spoke) |
| members | array[int] | - | SD-WAN member seq-nums (e.g., [100, 200]) |
| latency | integer | 200 | SLA latency threshold in ms |
| jitter | integer | 50 | SLA jitter threshold in ms |
| packetloss | integer | 5 | SLA packet loss threshold % |

### Hub Mode Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| probe_timeout | integer | 2500 | Remote probe timeout in ms |
| priority_out_sla | integer | 999 | Priority when SLA fails |

## Usage Examples

### List All Health Checks
```json
{
  "target_ip": "192.168.209.30",
  "action": "list"
}
```

### Create Spoke Health Check (Active Ping to Hub)
```json
{
  "target_ip": "192.168.209.30",
  "action": "create",
  "mode": "spoke",
  "name": "HUB",
  "server": "172.16.255.253",
  "members": [100],
  "latency": 200,
  "jitter": 50,
  "packetloss": 5
}
```

### Create Hub Health Check (Remote Detection)
```json
{
  "target_ip": "192.168.215.15",
  "action": "create",
  "mode": "hub",
  "name": "From_Edge",
  "probe_timeout": 2500,
  "priority_out_sla": 999
}
```

### Delete Health Check
```json
{
  "target_ip": "192.168.209.30",
  "action": "delete",
  "name": "HUB"
}
```

## FortiOS CLI Equivalent

### SPOKE Health Check (from 4D-Demo)
```
config system sdwan
  config health-check
    edit "HUB"
      set server "172.16.255.253"
      set update-cascade-interface disable
      set update-static-route disable
      set embed-measured-health enable
      set sla-id-redistribute 1
      set sla-fail-log-period 10
      set sla-pass-log-period 10
      set members 100
      config sla
        edit 1
          set latency-threshold 200
          set jitter-threshold 50
          set packetloss-threshold 5
        next
      end
    next
  end
end
```

### HUB Health Check (from 4D-Demo)
```
config system sdwan
  config health-check
    edit "From_Edge"
      set detect-mode remote
      set remote-probe-timeout 2500
      set failtime 1
      set recoverytime 1
      set sla-id-redistribute 1
      set members 0
      config sla
        edit 1
          set link-cost-factor remote
          set priority-out-sla 999
        next
      end
    next
  end
end
```

## Auto-Configured Settings

### Spoke Mode (Auto-Set)
| Setting | Value | Purpose |
|---------|-------|---------|
| update-cascade-interface | disable | Prevent interface cascading |
| update-static-route | disable | Don't modify static routes |
| embed-measured-health | enable | Embed in ADVPN shortcuts |
| sla-id-redistribute | 1 | SLA for redistribution |
| sla-fail-log-period | 10 | Log interval on SLA fail |
| sla-pass-log-period | 10 | Log interval on SLA pass |

### Hub Mode (Auto-Set)
| Setting | Value | Purpose |
|---------|-------|---------|
| detect-mode | remote | Receive health from spokes |
| failtime | 1 | Quick failure detection |
| recoverytime | 1 | Quick recovery detection |
| link-cost-factor | remote | Use remote health metrics |
| members | 0 | All members (wildcard) |

## Output Examples

### List Response
```json
{
  "success": true,
  "action": "list",
  "health_checks": [
    {
      "name": "HUB",
      "server": "172.16.255.253",
      "detect-mode": "active",
      "embed-measured-health": "enable",
      "members": [{"seq-num": 100}]
    }
  ]
}
```

### Create Response
```json
{
  "success": true,
  "action": "create",
  "mode": "spoke",
  "health_check": {
    "name": "HUB",
    "server": "172.16.255.253",
    "sla_thresholds": {
      "latency": 200,
      "jitter": 50,
      "packetloss": 5
    }
  }
}
```

## Troubleshooting

### Health Check Not Working (Spoke)
1. Verify hub loopback IP is correct
2. Check tunnel is UP before health check can work
3. Ensure member seq-nums match SD-WAN member config
4. Verify firewall policy allows ICMP on overlay

### SLA Always Failing (Spoke)
1. Check latency/jitter thresholds are realistic for your WAN
2. Verify overlay tunnel is established
3. Diagnose: `diagnose sys sdwan health-check status`

### Hub Not Receiving Health (Hub)
1. Verify spoke has `embed-measured-health enable`
2. Check ADVPN shortcuts are forming
3. Increase `remote-probe-timeout` if needed

## Related Tools
- `fortigate-sdwan-spoke-template` - Full spoke SD-WAN setup (includes health check)
- `fortigate-sdwan-hub-template` - Full hub SD-WAN setup (includes health check)
- `fortigate-sdwan-member` - Configure SD-WAN members
- `fortigate-sdwan-rule` - Configure SD-WAN rules with SLA

## API Reference
- Endpoint: `/api/v2/cmdb/system/sdwan/health-check`
- Methods: GET, POST, DELETE
- Auth: Bearer token
