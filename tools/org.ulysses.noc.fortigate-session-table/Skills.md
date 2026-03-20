# FortiGate Session Table Skills

## Purpose

View active firewall sessions on a FortiGate device. This is a core NOC troubleshooting tool for:
- Verifying connectivity through the firewall
- Identifying top bandwidth consumers (top talkers)
- Investigating potential security incidents or attacks
- Troubleshooting slow network performance
- Validating that traffic is matching expected policies

## When to Use This Tool

**Use this tool when the user asks:**
- "What sessions are on the firewall?"
- "Show me active connections"
- "Who is using bandwidth on the FortiGate?"
- "Is IP X.X.X.X connected through the firewall?"
- "What traffic is hitting policy 10?"
- "Are there sessions to port 443?"
- "Find connections from 10.0.0.50"
- "What are the top talkers?"
- "Is there a DoS attack?"
- "Why is the network slow?" (after checking health)
- "How many sessions to the internet?"

**Do NOT use this tool for:**
- Historical traffic analysis (use FortiAnalyzer logs)
- Checking overall device health (use fortigate-health-check first)
- Viewing firewall policy configuration
- Modifying or killing sessions
- VPN tunnel status

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `count` | integer | No | 20 | Sessions to return (1-1000) |
| `filter_srcip` | string | No | - | Filter by source IP |
| `filter_dstip` | string | No | - | Filter by destination IP |
| `filter_dport` | integer | No | - | Filter by destination port |
| `filter_policy` | integer | No | - | Filter by policy ID |
| `sort_by` | string | No | bytes | Sort field: bytes, packets, duration, expiry |
| `timeout` | integer | No | 30 | Request timeout in seconds |

## Troubleshooting Workflow

### Step 1: Start with Health Check
Before diving into sessions, verify the firewall is healthy:
```
fortigate-health-check → Check CPU, memory, session count
```

### Step 2: Get Session Overview
If health shows high session count or you need to investigate traffic:
```
fortigate-session-table(count=20, sort_by="bytes")
```
This shows the top 20 bandwidth-consuming sessions.

### Step 3: Drill Down with Filters
Once you identify a pattern, filter to investigate:
```
fortigate-session-table(filter_srcip="10.0.0.50")  # Specific host
fortigate-session-table(filter_dport=443)          # HTTPS traffic
fortigate-session-table(filter_policy=5)           # Specific policy
```

## Interpreting Results

### Session Counts

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Total sessions | < 50% of limit | 50-80% of limit | > 80% of limit |

**Device session limits (approximate):**
- FortiGate 40F: 700K sessions
- FortiGate 60F: 1.5M sessions
- FortiGate 100F: 3M sessions
- FortiGate 200F: 6M sessions

### Session States

| State | Meaning | NOC Action |
|-------|---------|------------|
| `established` | Active bidirectional connection | Normal |
| `syn_sent` | TCP SYN sent, awaiting response | High count = scan or attack |
| `syn_recv` | TCP SYN received, awaiting ACK | High count = SYN flood |
| `fin_wait` | Connection closing | Normal during shutdown |
| `time_wait` | Connection fully closed, waiting | Normal, will expire |
| `close` | Connection closed | Normal |
| `listen` | Server listening (rare in FW) | Usually VIP |

### Protocol Analysis

| Proto | Common Uses | High Count Concern |
|-------|-------------|-------------------|
| TCP (6) | Web, email, apps | Normal dominant protocol |
| UDP (17) | DNS, VoIP, video | Streaming or DNS issues |
| ICMP (1) | Ping, traceroute | Scanning or network testing |
| GRE (47) | VPN tunnels | Tunnel traffic |
| ESP (50) | IPsec encryption | VPN traffic |

### Red Flags to Watch For

1. **Many sessions from single source IP** → Possible compromised host or scan
2. **Many sessions to single destination** → Possible attack target
3. **High syn_sent/syn_recv states** → Port scan or SYN flood attack
4. **Unusual destination ports** → Potential C2 or exfiltration
5. **Sessions with very high duration** → Long-lived tunnel or compromised host
6. **Low policy ID with high traffic** → Check if policy is too permissive

## Example Usage

### Basic: Top Bandwidth Sessions
```json
{
    "target_ip": "192.168.1.1",
    "count": 10,
    "sort_by": "bytes"
}
```

### Investigate Specific Host
```json
{
    "target_ip": "192.168.1.1",
    "filter_srcip": "10.0.0.50",
    "count": 50
}
```

### Check HTTPS Traffic
```json
{
    "target_ip": "192.168.1.1",
    "filter_dport": 443,
    "sort_by": "bytes"
}
```

### Investigate Policy Hits
```json
{
    "target_ip": "192.168.1.1",
    "filter_policy": 5,
    "count": 100
}
```

## Sample Response

```json
{
    "success": true,
    "target_ip": "192.168.209.62",
    "total_sessions": 20,
    "returned_count": 5,
    "sessions": [
        {
            "src_ip": "192.168.215.9",
            "src_port": 56749,
            "dst_ip": "35.186.224.38",
            "dst_port": 443,
            "proto": "TCP",
            "proto_num": 6,
            "policy_id": 7,
            "bytes_in": 290178,
            "bytes_out": 310836,
            "packets_in": 4779,
            "packets_out": 4894,
            "duration": 69803,
            "expiry": 3574,
            "state": "established",
            "src_intf": "_default",
            "dst_intf": "wan1",
            "country": "United States"
        }
    ]
}
```

**Interpretation:**
"The FortiGate has 20 active sessions. The top talker is 192.168.215.9 connecting to a Google server (35.186.224.38) on HTTPS port 443. This session has transferred ~600KB total over 19 hours, matching policy 7. Traffic is flowing from internal (via _default zone) out to wan1. The destination is geolocated to United States."

### Key Fields for NOC Analysis

| Field | NOC Use |
|-------|---------|
| `src_ip` / `dst_ip` | Identify communicating hosts |
| `bytes_in` + `bytes_out` | Total bandwidth consumed |
| `duration` | How long session has been active |
| `policy_id` | Which firewall rule is allowing this |
| `src_intf` / `dst_intf` | Traffic flow direction |
| `country` | Geo-IP for destination (watch for unusual countries) |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `target_ip is required` | Missing parameter | Provide FortiGate IP |
| `No API credentials found` | Missing config | Add device to ~/.config/mcp/fortigate_credentials.yaml |
| `Connection failed` | Network issue | Check network path to FortiGate |
| `HTTP 401 Unauthorized` | Invalid token | Verify API token permissions |
| `HTTP 403 Forbidden` | Insufficient access | Token needs read access to session table |

## Related Tools

- `org.ulysses.noc.fortigate-health-check/1.0.0` - Check device health FIRST
- `org.ulysses.noc.fortigate-routing-table/1.0.0` - View IP routing
- `org.ulysses.noc.fortigate-arp-table/1.0.0` - View ARP cache
- `org.ulysses.noc.fortigate-interface-status/1.0.0` - Check interface status
