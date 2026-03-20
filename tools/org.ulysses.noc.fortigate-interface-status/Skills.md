# FortiGate Interface Status

## Purpose
Monitor interface health and NIC statistics on FortiGate firewalls. Use this tool to:
- Check which interfaces are up/down
- Identify interfaces with errors or packet drops
- **Detect ACTIVE errors** (errors increasing right now vs historical)
- Get deep NIC-level diagnostics for troubleshooting

## When to Use
- **Connectivity issues**: Check if expected interfaces are up
- **Performance problems**: Look for packet drops or errors
- **Network troubleshooting**: Get detailed NIC statistics
- **Active problem detection**: Use `detect_active_errors` to see if errors are happening NOW

## How to Call

### Basic Interface Status
```json
{
  "target_ip": "192.168.1.1"
}
```
Returns all interfaces with basic stats (link status, IP, speed, errors).

### Detect Active Errors (RECOMMENDED for troubleshooting)
```json
{
  "target_ip": "192.168.1.1",
  "detect_active_errors": true
}
```
**Takes ~6 seconds.** Samples error counters 3 times with 3-second intervals.
Determines if errors are ACTIVELY increasing (current problem) vs just historical counts.

### With Deep NIC Diagnostics
```json
{
  "target_ip": "192.168.1.1",
  "include_nic_diag": true
}
```
Adds CLI-based NIC stats including packet drops (requires more API calls).

### Full Diagnostic (Both Features)
```json
{
  "target_ip": "192.168.1.1",
  "detect_active_errors": true,
  "include_nic_diag": true
}
```

### Specific Interfaces Only
```json
{
  "target_ip": "192.168.1.1",
  "interfaces": ["port1", "port2", "wan1"]
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_ip | string | Yes | - | FortiGate management IP |
| detect_active_errors | boolean | No | false | Sample 3x over 6 sec to detect increasing errors |
| interfaces | array | No | all | Specific interfaces to query |
| include_nic_diag | boolean | No | false | Include deep NIC diagnostics |
| timeout | integer | No | 30 | Request timeout in seconds |
| verify_ssl | boolean | No | false | Verify SSL certificate |

## Understanding Error Trends

### The Problem with Error Counters
Error counters are **cumulative** - they count all errors since device boot/reset.
Seeing `rx_errors: 50000` doesn't tell you if:
- Those errors happened months ago (no current problem)
- Those errors are happening RIGHT NOW (active problem)

### How detect_active_errors Works
1. Takes 3 samples, 3 seconds apart (6 seconds total)
2. Compares error counts between first and last sample
3. If errors increased during sampling = **ACTIVE problem**
4. If errors stayed the same = **historical only** (no current issue)

### error_trend Values

| Value | Meaning | Action |
|-------|---------|--------|
| `INCREASING` | Errors actively increasing during sampling | **URGENT**: Active problem, investigate immediately |
| `STABLE` | Errors exist but NOT increasing | Historical errors, may not need immediate action |
| `NONE` | No errors detected | Interface is healthy |
| `UNKNOWN` | detect_active_errors not enabled | Enable for accurate assessment |

## Response Fields

### summary (Quick Reference)
```json
"summary": {
  "total": 13,
  "up": 6,
  "down": 7,
  "with_errors": 2,
  "error_trend": "INCREASING",
  "interfaces_with_active_errors": 1,
  "active_error_interfaces": ["wan1"]
}
```

**Key fields for AI agents:**
- `error_trend`: INCREASING = urgent, STABLE = historical, NONE = healthy
- `interfaces_with_active_errors`: Count of interfaces with active problems
- `active_error_interfaces`: List of interface names needing attention

### error_detection (when detect_active_errors=true)
```json
"error_detection": {
  "samples_taken": 3,
  "interval_seconds": 3,
  "total_sample_time_sec": 6,
  "error_trend": "INCREASING",
  "interfaces_with_active_errors": 1,
  "active_errors": [
    {
      "interface": "wan1",
      "rx_errors_start": 50000,
      "rx_errors_end": 50015,
      "rx_errors_delta": 15,
      "tx_errors_start": 0,
      "tx_errors_end": 0,
      "tx_errors_delta": 0,
      "sample_interval_sec": 6,
      "status": "ACTIVE_ERRORS"
    }
  ]
}
```

### interfaces[]
Each interface includes:
- `name`: Interface name (e.g., "port1", "wan1")
- `ip`: Assigned IP address
- `status`: "up" or "down"
- `link`: Link state (true/false)
- `speed`: Link speed in Mbps
- `duplex`: "full" or "half"
- `mac`: MAC address
- `rx_bytes`, `tx_bytes`: Traffic counters
- `rx_errors`, `tx_errors`: Error counters (cumulative)

### nic_diagnostics[] (when include_nic_diag=true)
- `rx_dropped`, `tx_dropped`: Packet drop counters
- `state`: NIC state
- `speed`: Negotiated speed

## AI Agent Decision Tree

```
1. Check summary.error_trend:
   |
   ├─ "INCREASING" ──► URGENT: Active problem!
   │                   └─ Check summary.active_error_interfaces for which interfaces
   │                   └─ Escalate or investigate physical layer (cable, transceiver)
   │
   ├─ "STABLE" ──► Historical errors only
   │              └─ May indicate past issue that was resolved
   │              └─ Note for maintenance but not urgent
   │
   ├─ "NONE" ──► Healthy, no errors
   │
   └─ "UNKNOWN" ──► Re-run with detect_active_errors=true
```

## Interpreting Active Errors

### What rx_errors_delta Means
- `rx_errors_delta: 15` over 6 seconds = ~2.5 errors/second
- **Typical causes**: Bad cable, failing transceiver, EMI, duplex mismatch

### What tx_errors_delta Means
- Usually indicates driver/hardware issues on FortiGate side
- Or severe congestion causing buffer overruns

### Severity Guidelines
| Errors/Second | Severity | Action |
|---------------|----------|--------|
| 0 | OK | No action |
| 1-10 | Minor | Monitor, schedule maintenance |
| 10-100 | Warning | Investigate soon |
| 100+ | Critical | Immediate action required |

## Common Troubleshooting Scenarios

### Scenario: High error_trend=INCREASING
```
Problem: wan1 showing active errors
Action:
1. Check physical cable connection
2. Verify switch port on other end
3. Check for duplex mismatch
4. Try different cable
5. Check SFP/transceiver if applicable
```

### Scenario: Errors exist but error_trend=STABLE
```
Interpretation: Errors happened in the past, not currently occurring
Action:
1. Note in maintenance log
2. No urgent action needed
3. Consider resetting counters after next maintenance window
```

### Scenario: Interface down unexpectedly
```
Check: interfaces[].link = false for expected interfaces
Action:
1. Physical cable check
2. Remote switch port status
3. Check for admin-down status
```

## Example Response (with active error detection)
```json
{
  "success": true,
  "target_ip": "192.168.209.62",
  "interface_count": 13,
  "interfaces": [...],
  "summary": {
    "total": 13,
    "up": 6,
    "down": 7,
    "with_errors": 0,
    "error_trend": "NONE",
    "interfaces_with_active_errors": 0
  },
  "error_detection": {
    "samples_taken": 3,
    "interval_seconds": 3,
    "total_sample_time_sec": 6,
    "error_trend": "NONE",
    "interfaces_with_active_errors": 0,
    "active_errors": []
  }
}
```

## Related Tools
- `fortigate-health-check`: Overall device health (CPU, memory, 1hr peaks)
- `fortigate-performance-status`: Detailed performance metrics
- `fortigate-running-processes`: Process-level diagnostics
