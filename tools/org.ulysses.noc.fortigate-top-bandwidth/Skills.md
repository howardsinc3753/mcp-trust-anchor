# FortiGate Top Bandwidth Analyzer Skills

**THIS TOOL FINDS TOP BANDWIDTH CONSUMERS ON FORTIGATE DEVICES AND CORRELATES APPS WITH SOURCE IPs**

## How to Call

Use this tool when the user mentions ANY of these:
- Top bandwidth users, top talkers, bandwidth hogs
- Who is using the most bandwidth on the FortiGate
- Top source IPs by traffic, highest bandwidth consumers
- FortiView top applications, app bandwidth
- Network capacity analysis, bandwidth triage
- "Who is eating all the bandwidth?"
- "What IPs are using the most data?"
- "Show me top 5 bandwidth users"
- "What app is using the most bandwidth and who is using it?"
- "Drill into YouTube traffic — who's watching?"
- "What is the source IP for that app?"
- "Scan live sessions for apps and source IPs"
- Enable bandwidth tracking on FortiGate

**Example prompts:**
- "Who are the top 5 bandwidth users on the FortiGate?"
- "Show me top talkers on 192.168.209.62"
- "What applications are using the most bandwidth?"
- "Find the IP using the most bandwidth this week"
- "Which IPs are using YouTube?"
- "Drill into Jianguoyun traffic"
- "Scan active sessions — what apps are running and who's using them?"
- "Enable FortiView bandwidth tracking"
- "Top 10 source IPs by upload bandwidth"

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `port` | integer | No | 10443 | HTTPS management port |
| `mode` | string | No | top-sources | Query mode (see Modes below) |
| `top_n` | integer | No | 5 | Number of top consumers (1-50) |
| `time_period` | string | No | hour | For top-apps: hour, day, week |
| `rows` | integer | No | 2000 | Traffic log rows to analyze (max 2000) |
| `sort_by` | string | No | total | Sort by: total, sent, received |
| `view` | string | No | by-app | session-scan: by-app or by-source |
| `enrich_apps` | boolean | No | true | top-sources: add app activity per source IP |
| `enrich_sources` | boolean | No | true | top-apps: add source IPs per application |
| `app_name` | string | No | - | app-drill: application name to investigate |
| `app_id` | integer | No | - | app-drill: FortiGate app ID (alternative to app_name) |
| `timeout` | integer | No | 30 | Total execution timeout budget in seconds |

## Modes

### Mode: session-scan (RECOMMENDED for NOC/SOC triage)
Scans the live session table and aggregates active sessions. This is the ONLY
mode that reliably provides **app_id + source_ip + real bandwidth** in a single
view. Two sub-views available:

- **`view=by-app`** (default): Groups sessions by application, shows which source
  IPs are using each app with actual byte counts.
- **`view=by-source`**: Groups sessions by source IP, shows which apps each IP
  is running with actual byte counts.

Returns: app_name, app_id, total/sent/recv bytes, session_count, source_ips (by-app)
         or source_ip, total/sent/recv bytes, session_count, top_apps (by-source).

**Best for:** "What apps are active and who is using them?" — the definitive triage mode.
**Why this mode exists:** FortiGate's log endpoints have a data gap — no single log type
contains app + source IP + bandwidth together. The live session table is the only
data source that has all three.

### Mode: top-sources
Aggregates traffic logs by source IP and ranks by bandwidth consumption.
When `enrich_apps=true` (default), also queries app-ctrl logs per source IP to show what apps each IP is using.

Returns: source IP, users, total/sent/recv bytes, session count, top destinations, top services, top apps.

**Best for:** "Who is using the most bandwidth?" — historical log-based view.

### Mode: top-apps
Uses native FortiView API to get top applications by bandwidth.
When `enrich_sources=true` (default), also queries app-ctrl logs per app to show which source IPs are using each app.
Resolves app IDs to human-readable names via CMDB lookup.

Returns: app_id, app_name, total_bytes, last upstream/downstream bps, top source IPs.

**Best for:** "What applications are using bandwidth?" — FortiView historical aggregate.
**Requires:** FortiView bandwidth tracking enabled on the device.
**Limitation:** Source IP enrichment uses app-ctrl logs (session counts only, no bytes).
For actual bytes per source per app, use `session-scan` instead.

### Mode: app-drill
Deep investigation of a single application. Queries app-ctrl logs for the named app and aggregates by source IP.

Returns: per-source-IP breakdown with session counts, top destinations, first/last seen timestamps.

**Best for:** "Who is using YouTube?" or "Drill into Jianguoyun traffic" — historical deep-dive.
**Requires:** Either `app_name` or `app_id` parameter.
**Limitation:** app-ctrl logs have session counts but no bandwidth data. For bandwidth per
source IP per app, use `session-scan` with `view=by-app`.

### Mode: enable-tracking
Enables FortiView application bandwidth tracking on the device.
Run this once before using top-apps mode if tracking is not enabled.

**Best for:** One-time setup before using top-apps mode.

## FortiBot Triage Workflow

This tool is the **reference model for FortiBot** single-call triage. The recommended workflow:

1. **Start with `session-scan` (by-app)** — shows every active app with source IPs and real bandwidth
2. **Use `session-scan` (by-source)** — flip the view to see per-IP app breakdown
3. **Use `top-apps`** for historical view — FortiView tracks bandwidth over time periods
4. **Drill into specifics with `app-drill`** — deep-dive into any suspicious app with timestamps

### Which Mode When?

| Question | Best Mode |
|----------|-----------|
| "What apps are active right now and who's using them?" | `session-scan` view=by-app |
| "What is source IP X doing right now?" | `session-scan` view=by-source |
| "Who are the top bandwidth consumers (historical)?" | `top-sources` |
| "What apps used the most bandwidth this week?" | `top-apps` time_period=week |
| "Deep-dive into YouTube — who, when, where?" | `app-drill` app_name=YouTube |
| "I need source IP for an app that only shows in FortiView" | `session-scan` view=by-app |

### Data Source Comparison

| Mode | Data Source | Has App | Has Source IP | Has Bandwidth |
|------|------------|---------|--------------|---------------|
| **session-scan** | Live session table | Yes (app_id) | Yes (saddr) | Yes (sentbyte/rcvdbyte) |
| top-sources | Traffic logs (disk) | Sometimes | Yes | Yes |
| top-apps | FortiView API | Yes (app_id) | No (uses app-ctrl enrichment) | Yes |
| app-drill | App-ctrl logs (disk) | Yes | Yes | No (always 0) |

**session-scan is the only mode with all three columns = Yes.**

### Time Budget Management
All modes share a configurable timeout budget (default 30s). Enrichment calls are best-effort — if the budget runs low, enrichment is skipped gracefully and the core data still returns.

## Interpreting Results

### session-scan by-app Response
```json
{
  "success": true,
  "mode": "session-scan",
  "execution_time_s": 2.01,
  "top_consumers": [
    {
      "rank": 1,
      "app_id": 50610,
      "app_name": "FortiEDR.Core",
      "total_bytes": 1642186290,
      "total_mb": 1566.11,
      "sent_mb": 1217.01,
      "recv_mb": 349.1,
      "session_count": 1,
      "source_ips": [
        {
          "source_ip": "192.168.215.9",
          "total_bytes": 1642186290,
          "total_mb": 1566.11,
          "session_count": 1
        }
      ]
    }
  ],
  "summary": {
    "view": "by-app",
    "total_sessions_scanned": 403,
    "sessions_with_app": 221,
    "unique_apps": 32,
    "data_source": "live_session_table"
  }
}
```

### session-scan by-source Response
```json
{
  "top_consumers": [
    {
      "rank": 1,
      "source_ip": "192.168.215.9",
      "total_mb": 1965.47,
      "session_count": 275,
      "top_apps": [
        {"app_name": "FortiEDR.Core", "total_mb": 1566.4, "session_count": 1},
        {"app_name": "Microsoft.Teams_Video", "total_mb": 275.76, "session_count": 2},
        {"app_name": "QUIC", "total_mb": 14.96, "session_count": 87}
      ]
    }
  ]
}
```

### top-sources Response (enriched)
```json
{
  "top_consumers": [
    {
      "rank": 1,
      "source_ip": "192.168.209.105",
      "total_mb": 50.0,
      "session_count": 245,
      "top_destinations": [{"ip": "216.239.36.223", "bytes": 10000000}],
      "top_services": [{"service": "HTTPS", "bytes": 40000000}],
      "top_apps": [{"app_name": "YouTube", "session_count": 36}]
    }
  ]
}
```

### Key Differences
- **session-scan** gives **real bandwidth per app per source IP** from live sessions
- **top-sources/top-apps** give **historical** data from disk logs with best-effort enrichment
- **app-drill** gives **historical session counts** (no bytes) with timestamps
- **VPN/ESP traffic** (e.g., 192.168.209.30) won't have app signatures in any mode

## Examples

### 1. Session Scan — Apps with Source IPs (RECOMMENDED)
```json
{"target_ip": "192.168.209.62", "mode": "session-scan"}
```
"What apps are active and who is using them?"

### 2. Session Scan — Source IPs with App Breakdown
```json
{"target_ip": "192.168.209.62", "mode": "session-scan", "view": "by-source", "top_n": 10}
```
"Show me what each IP on the network is doing right now"

### 3. Top 5 Bandwidth Users (Historical)
```json
{"target_ip": "192.168.209.62"}
```
"Show me the top bandwidth users from traffic logs"

### 4. Top Applications (FortiView Historical)
```json
{"target_ip": "192.168.209.62", "mode": "top-apps", "time_period": "hour"}
```
"What apps used the most bandwidth in the last hour?"

### 5. Drill Into Specific App
```json
{"target_ip": "192.168.209.62", "mode": "app-drill", "app_name": "YouTube"}
```
"Who is watching YouTube on the network?"

### 6. Enable Bandwidth Tracking
```json
{"target_ip": "192.168.209.62", "mode": "enable-tracking"}
```
"Enable FortiView bandwidth tracking on the firewall"

### 7. Session Scan — Top 3 by Upload
```json
{"target_ip": "192.168.209.62", "mode": "session-scan", "view": "by-app", "top_n": 3, "sort_by": "sent"}
```
"What apps are uploading the most data right now?"

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `target_ip is required` | Missing IP | Provide the FortiGate management IP |
| `Invalid mode` | Wrong mode value | Use: top-sources, top-apps, session-scan, app-drill, enable-tracking |
| `app-drill requires app_name or app_id` | Missing app identifier | Provide app_name or app_id |
| `No API credentials found` | Config missing | Check ~/.config/mcp/fortigate_credentials.yaml |
| `HTTP Error 401` | Auth failed | Verify API token in credential file |
| `HTTP Error 403` | Permission denied | API token needs fwgrp read access for session-scan |
| `HTTP Error 404` | Endpoint not found | FortiOS version may not support this API |
| `Connection failed` | Network issue | Verify IP and port (default 10443) |

## FortiGate API Endpoints Used

| Mode | Method | Endpoint |
|------|--------|----------|
| **session-scan** | **GET** | **`/api/v2/monitor/firewall/sessions`** |
| session-scan (resolve) | GET | `/api/v2/cmdb/application/name?count=10000` |
| top-sources | GET | `/api/v2/log/disk/traffic/forward` |
| top-sources (enrich) | GET | `/api/v2/log/disk/app-ctrl` (per source IP) |
| top-apps | GET | `/api/v2/monitor/system/traffic-history/top-applications` |
| top-apps (resolve) | GET | `/api/v2/cmdb/application/name?count=10000` |
| top-apps (enrich) | GET | `/api/v2/log/disk/app-ctrl` (per app) |
| app-drill | GET | `/api/v2/log/disk/app-ctrl` |
| enable-tracking | POST | `/api/v2/monitor/system/traffic-history/enable-app-bandwidth-tracking` |

## Related Tools

- `fortigate-network-analyzer` - Detailed traffic/event/session logs
- `fortigate-health-check` - Device health metrics (CPU/memory/sessions)
- `fortigate-performance-status` - Performance metrics
- `fortigate-session-table` - Active session table
