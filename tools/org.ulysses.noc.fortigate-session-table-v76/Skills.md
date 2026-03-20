# FortiGate Session Table (FortiOS 7.6+) Skills

## Purpose

View active firewall sessions on FortiGate devices running **FortiOS 7.6 and later**.

This tool uses the updated `/api/v2/monitor/firewall/sessions` endpoint (plural) introduced in FortiOS 7.6.

**IMPORTANT:** For FortiOS 7.4 and earlier, use `org.ulysses.noc.fortigate-session-table` instead.

## When to Use This Tool

**Use this tool when:**
- FortiGate is running FortiOS 7.6.x or later
- User asks about active sessions, connections, or traffic
- Troubleshooting connectivity through the firewall
- Identifying top bandwidth consumers
- Investigating security incidents
- Validating traffic is matching expected policies

**Do NOT use this tool for:**
- FortiGate running FortiOS 7.4 or earlier (use fortigate-session-table)
- Historical traffic analysis (use FortiAnalyzer logs or network-analyzer)
- Checking overall device health (use fortigate-health-check first)
- Viewing firewall policy configuration

## Firmware Version Detection

Before using session tools, check the FortiGate firmware version:

```
fortigate-health-check → Check firmware_version field
```

| Firmware | Tool to Use |
|----------|-------------|
| 7.6.x+ | `fortigate-session-table-v76` (this tool) |
| 7.4.x and earlier | `fortigate-session-table` |

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `count` | integer | No | 100 | Sessions to return (20-1000) |
| `filter_srcip` | string | No | - | Filter by source IP |
| `filter_dstip` | string | No | - | Filter by destination IP |
| `filter_srcport` | integer | No | - | Filter by source port |
| `filter_dstport` | integer | No | - | Filter by destination port |
| `filter_policy` | integer | No | - | Filter by policy ID |
| `filter_protocol` | string | No | - | Filter by protocol (tcp/udp/icmp) |
| `filter_srcintf` | string | No | - | Filter by source interface |
| `filter_dstintf` | string | No | - | Filter by destination interface |
| `filter_country` | string | No | - | Filter by destination country |
| `filter_username` | string | No | - | Filter by authenticated user |
| `ip_version` | string | No | ipv4 | IP version (ipv4/ipv6/ipboth) |
| `include_summary` | boolean | No | true | Include session statistics |
| `timeout` | integer | No | 30 | Request timeout in seconds |

## API Differences: 7.6 vs 7.4

| Feature | FortiOS 7.4 | FortiOS 7.6 |
|---------|-------------|-------------|
| Endpoint | `/firewall/session` | `/firewall/sessions` (plural) |
| Count param | Optional | **Required** (20-1000) |
| IP fields | `srcaddr/dstaddr` | `saddr/daddr` |
| Summary | Limited | Full stats with NPU/nTurbo counts |
| Shaper drops | Not available | `tx_shaper_drops/rx_shaper_drops` |

## Example Usage

### Basic: Get Top Sessions
```json
{
    "target_ip": "192.168.1.1",
    "count": 50
}
```

### Investigate Specific Host
```json
{
    "target_ip": "192.168.1.1",
    "filter_srcip": "10.0.0.50",
    "count": 100
}
```

### Check HTTPS Traffic
```json
{
    "target_ip": "192.168.1.1",
    "filter_dstport": 443,
    "filter_protocol": "tcp"
}
```

### Check Policy Hits
```json
{
    "target_ip": "192.168.1.1",
    "filter_policy": 5,
    "count": 200
}
```

### IPv6 Sessions
```json
{
    "target_ip": "192.168.1.1",
    "ip_version": "ipv6",
    "count": 50
}
```

## Sample Response (FortiOS 7.6)

```json
{
    "success": true,
    "target_ip": "192.168.209.62",
    "firmware_version": "7.6+",
    "total_sessions": 536,
    "matched_sessions": 50,
    "returned_count": 50,
    "summary": {
        "session_count": 536,
        "matched_count": 50,
        "setup_rate": 12,
        "npu_session_count": 0,
        "nturbo_session_count": 0
    },
    "sessions": [
        {
            "src_ip": "192.168.215.9",
            "src_port": 56749,
            "dst_ip": "35.186.224.38",
            "dst_port": 443,
            "proto": "TCP",
            "proto_num": 6,
            "policy_id": 7,
            "policy_type": "policy",
            "bytes_in": 290178,
            "bytes_out": 310836,
            "packets_in": 4779,
            "packets_out": 4894,
            "duration": 69803,
            "expiry": 3574,
            "src_intf": "_default",
            "dst_intf": "wan1",
            "country": "United States",
            "username": "",
            "vdom": "root",
            "nat_src_ip": "66.110.253.68",
            "nat_src_port": 56749,
            "shaper": "",
            "tx_shaper_drops": 0,
            "rx_shaper_drops": 0,
            "fortiasic": ""
        }
    ]
}
```

## FortiOS 7.6 Specific Fields

| Field | Description |
|-------|-------------|
| `policy_type` | "policy", "policy6", or "security-policy" |
| `nat_src_ip` | Source NAT IP address |
| `nat_dst_ip` | Destination NAT IP address |
| `tx_shaper_drops` | Bytes dropped by traffic shaper (outbound) |
| `rx_shaper_drops` | Bytes dropped by traffic shaper (inbound) |
| `fortiasic` | NPU acceleration type (NP7, NP6, etc.) |
| `vdom` | VDOM name (from `vf` field) |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `HTTP 404` | Wrong endpoint or old firmware | Use fortigate-session-table for 7.4 |
| `target_ip is required` | Missing parameter | Provide FortiGate IP |
| `No API credentials found` | Missing config | Add device credentials |
| `HTTP 401 Unauthorized` | Invalid token | Verify API token |
| `HTTP 403 Forbidden` | Insufficient access | Token needs sysgrp.cfg access |

## Related Tools

- `org.ulysses.noc.fortigate-session-table/1.0.x` - For FortiOS 7.4 and earlier
- `org.ulysses.noc.fortigate-health-check/1.0.x` - Check device health FIRST
- `org.ulysses.noc.fortigate-network-analyzer/1.0.x` - Traffic logs (works on all versions)
