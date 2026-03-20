# FortiGate Performance Status Skills

**AI Guidance Document for FortiGate Performance Status Tool**

---

## How to Call

Use this tool when:
- User asks for detailed CPU breakdown on FortiGate
- User wants to check memory usage, cached memory, or buffers
- User asks about session rates or maximum sessions
- User mentions performance, uptime, or conserve mode
- User wants more detail than basic health check provides

**Example prompts:**
- "What's the CPU breakdown on the FortiGate?"
- "Show me detailed performance stats for the firewall"
- "Is the FortiGate in conserve mode?"
- "What's the session rate on 192.168.209.62?"
- "How long has the FortiGate been running?"

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `timeout` | integer | No | 30 | Timeout in seconds |
| `verify_ssl` | boolean | No | false | Verify SSL certificate |

---

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "target_ip": "192.168.209.62",
  "cpu": {
    "current": 5,
    "idle": 95,
    "user": 2,
    "system": 3,
    "iowait": 0
  },
  "memory": {
    "total_mb": 1885,
    "used_percent": 53
  },
  "uptime_seconds": 1234567,
  "sessions": {
    "current": 150,
    "rate": 5,
    "max": 100000
  },
  "disk_percent": 1,
  "low_memory": false,
  "conserve_mode": 0
}
```

### Field Meanings

| Field | Description | Thresholds/Actions |
|-------|-------------|-------------------|
| `cpu.current` | Total CPU usage % | >80% = investigate, >95% = critical |
| `cpu.idle` | Idle CPU % | <10% = overloaded |
| `cpu.iowait` | I/O wait % | >20% = disk bottleneck |
| `memory.used_percent` | Memory usage % | >85% = warning, >95% = critical |
| `sessions.current` | Active sessions | Compare to `sessions.max` |
| `sessions.rate` | Sessions/second | Spike may indicate attack |
| `low_memory` | Low memory state | `true` = immediate action needed |
| `conserve_mode` | 0=normal, 1+=degraded | >0 = investigate immediately |
| `uptime_seconds` | Seconds since boot | Use for stability tracking |

### Uptime Conversion
- `uptime_seconds / 86400` = days
- `(uptime_seconds % 86400) / 3600` = hours

---

## Examples

### Example 1: Check Performance

**User:** "What's the detailed performance on the FortiGate?"

**Tool Call:**
```python
fortigate_performance_status(target_ip="192.168.209.62")
```

**Response:**
```json
{
  "success": true,
  "cpu": {"current": 5, "idle": 95},
  "memory": {"used_percent": 53, "total_mb": 1885},
  "uptime_seconds": 864000,
  "sessions": {"current": 150, "rate": 5, "max": 100000}
}
```

**How to explain to user:**
> The FortiGate at 192.168.209.62 is healthy:
> - **CPU:** 5% used (95% idle) - no issues
> - **Memory:** 53% of 1.8GB used - healthy
> - **Uptime:** 10 days
> - **Sessions:** 150 active (0.15% of 100K max), 5/sec rate
>
> No conserve mode or low memory warnings.

### Example 2: Investigate Slow Performance

**User:** "The firewall seems slow, what's going on?"

**Tool Call:**
```python
fortigate_performance_status(target_ip="192.168.209.62")
```

**How to interpret:**
1. Check `cpu.current` - high CPU could cause slowness
2. Check `cpu.iowait` - I/O wait indicates disk issues
3. Check `memory.used_percent` - memory pressure causes slowness
4. Check `conserve_mode` - non-zero means degraded operation
5. Check `low_memory` - true means critical memory state

---

## Error Handling

| Error | Meaning | Suggested Action |
|-------|---------|------------------|
| `target_ip is required` | Missing parameter | Ask user for FortiGate IP |
| `No API credentials found` | Config file missing | Create ~/.config/mcp/fortigate_credentials.yaml |
| `Connection failed` | Network issue | Check connectivity to FortiGate |
| `HTTP Error 401` | Bad API token | Verify API token is valid |
| `HTTP Error 403` | Permission denied | Check API user has monitor access |

---

## Prerequisites

Before using this tool:
1. FortiGate must be reachable on HTTPS (port 443)
2. API token configured in `~/.config/mcp/fortigate_credentials.yaml`
3. API user must have read access to "sysgrp.cfg" permission group

---

## Related Tools

- `org.ulysses.noc.fortigate-health-check` - Basic health summary
- `org.ulysses.noc.fortigate-running-processes` - Process list and usage
- `org.ulysses.noc.fortigate-interface-status` - Network interface status
- `org.ulysses.noc.fortigate-resource-usage` - Historical resource data

---

**Skills Version:** 1.0.0
**Tool Version:** 1.0.0
