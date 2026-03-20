# FortiGate Network Analyzer Skills

**THIS IS THE PRIMARY TOOL FOR FORTIGATE LOGS AND EVENTS**

## How to Call

Use this tool when user mentions ANY of these:
- FortiGate logs, traffic logs, event logs, system events
- FortiGate 71F, FGT71F, LAB-71F, 192.168.209.62
- Firewall logs, firewall events, firewall traffic
- VPN events, admin events, system events on FortiGate
- Network sessions, connections, traffic analysis
- "What has IP X connected to?"
- Troubleshooting FortiGate connectivity

**DO NOT** use log-analyzer for FortiGate - use THIS tool instead.

**Example prompts:**
- "Show me traffic logs from the FortiGate"
- "Show me system events from the FortiGate"
- "Show me system events from the FortiGate 71F"
- "Get FortiGate event logs"
- "What connections has 192.168.1.100 made?"
- "Get the last 50 VPN events"
- "Show traffic to policy 21"
- "Find all denied connections"
- "Show me logs from 192.168.209.62"

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `mode` | string | No | traffic | Query mode: `traffic`, `event`, `session` |
| `rows` | integer | No | 100 | Number of log entries (max 2000) |
| `srcip` | string | No | - | Filter by source IP |
| `dstip` | string | No | - | Filter by destination IP |
| `policyid` | integer | No | - | Filter by policy ID |
| `action` | string | No | - | Filter: accept, close, timeout, deny |
| `service` | string | No | - | Filter: DNS, HTTPS, SSH, etc. |
| `filter` | string | No | - | Custom filter syntax |
| `event_subtype` | string | No | system | Event subtype: system, vpn, user |
| `start_time` | string | No | - | ISO format start time |
| `end_time` | string | No | - | ISO format end time |

## Modes

### Mode: traffic
Retrieves forward traffic logs. Use for:
- Analyzing network flows
- Troubleshooting connectivity
- Bandwidth investigation
- Policy utilization

### Mode: event
Retrieves event logs. Use for:
- System events (reboots, config changes)
- VPN tunnel status
- Admin login activity
- Security rating changes

### Mode: session
Convenience mode to find all sessions for a specific IP. Requires `srcip` or `dstip`.
- Searches IP as both source and destination
- Combines and sorts results
- Perfect for host troubleshooting

## Interpreting Results

### Traffic Log Fields

| Field | Description |
|-------|-------------|
| `srcip/dstip` | Source and destination IP |
| `srcport/dstport` | Source and destination ports |
| `action` | accept, close, timeout, deny |
| `policyid` | Matching firewall policy |
| `service` | Protocol/service name |
| `app` | Application identified by DPI |
| `sentbyte/rcvdbyte` | Bytes transferred |
| `duration` | Session duration in seconds |
| `srcintf/dstintf` | Input/output interfaces |

### Actions Explained
- **accept**: Session allowed, still active
- **close**: Session completed normally
- **timeout**: Session timed out (idle)
- **deny**: Session blocked by policy

### Pagination
Large queries may have `has_more: true`. Use `session_id` for continuation (future feature).

## Good Use Cases

### 1. General Traffic Analysis
```json
{"target_ip": "192.168.209.62", "mode": "traffic", "rows": 100}
```
"Show me recent traffic on the FortiGate"

### 2. Host Troubleshooting
```json
{"target_ip": "192.168.209.62", "mode": "session", "srcip": "192.168.1.100", "rows": 50}
```
"What has 192.168.1.100 been connecting to?"

### 3. Policy Investigation
```json
{"target_ip": "192.168.209.62", "mode": "traffic", "policyid": 21, "rows": 100}
```
"Show me traffic hitting policy 21"

### 4. Denied Connections
```json
{"target_ip": "192.168.209.62", "mode": "traffic", "action": "deny", "rows": 50}
```
"Show blocked traffic"

### 5. System Events
```json
{"target_ip": "192.168.209.62", "mode": "event", "event_subtype": "system", "rows": 50}
```
"Show system events from the firewall"

### 6. VPN Events
```json
{"target_ip": "192.168.209.62", "mode": "event", "event_subtype": "vpn", "rows": 50}
```
"Show VPN tunnel events"

## Bad Use Cases

- Don't use for configuration changes (read-only tool)
- Don't use for real-time threat detection (use security tools)
- Don't use for firmware management
- Don't use for backup/restore operations

## Example Interaction

**User:** "What connections has 192.168.209.105 made in the last hour?"

**Tool Call:**
```python
fortigate_network_analyzer(
    target_ip="192.168.209.62",
    mode="session",
    srcip="192.168.209.105",
    rows=100
)
```

**Response:**
```json
{
  "success": true,
  "target_ip": "192.168.209.62",
  "mode": "session",
  "device": {
    "serial": "FGT71FTK22004117",
    "hostname": "LAB-71F-FortiGate",
    "version": "v7.4.9"
  },
  "query": {
    "rows_requested": 100,
    "rows_returned": 45,
    "total_available": 9049
  },
  "results": [
    {
      "timestamp": "2025-12-17T12:57:05",
      "srcip": "192.168.209.105",
      "dstip": "216.239.36.223",
      "dstport": 443,
      "action": "close",
      "service": "HTTPS",
      "app": "Google.Services",
      "sentbyte": 10065,
      "rcvdbyte": 2085
    }
  ]
}
```

**Interpretation:**
"Found 45 sessions for 192.168.209.105. Most traffic is HTTPS to Google services and Microsoft. Total 9049 matching logs available. Device is LAB-71F-FortiGate running v7.4.9."

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `target_ip is required` | Missing IP | Ask user for FortiGate IP |
| `Invalid mode` | Wrong mode value | Use: traffic, event, session |
| `session mode requires srcip or dstip` | Missing IP filter | Provide srcip or dstip |
| `No API credentials found` | Config missing | Check ~/.config/mcp/fortigate_credentials.yaml |
| `HTTP Error 401` | Auth failed | Verify API token |
| `HTTP Error 403` | Permission denied | Check API token permissions |
| `Connection failed` | Network issue | Verify connectivity |

## Filter Syntax Reference

FortiGate supports advanced filtering:

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equals | `srcip==192.168.1.1` |
| `!=` | Not equals | `action!=accept` |
| `=@` | Contains | `app=@Microsoft` |
| `>=` | Greater than | `sentbyte>=1000000` |
| `<=` | Less than | `duration<=60` |
| `,` | OR | `action==deny,action==timeout` |
| `&` | AND | `srcip==10.0.0.1&dstport==443` |

Use the `filter` parameter for complex queries:
```json
{"target_ip": "192.168.209.62", "filter": "srcip==10.0.0.1&sentbyte>=1000000"}
```

## Related Tools

- `fortigate-health-check` - Device health metrics
- `fortigate-interface-status` - Interface statistics
- `fortigate-performance-status` - CPU/memory/session metrics
- `fortigate-running-processes` - Running processes

## API Reference

Base URL: `https://{fortigate_ip}/api/v2/log`

| Endpoint | Description |
|----------|-------------|
| `/disk/traffic/forward` | Forward traffic logs |
| `/disk/event/system` | System events |
| `/disk/event/vpn` | VPN events |
| `/disk/event/user` | User events |
