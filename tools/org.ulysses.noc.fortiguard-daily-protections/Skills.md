# FortiGuard Daily Protections Report - Skills Guide

## Purpose

This tool generates a partner-friendly HTML report showing the latest protections customers receive from FortiGuard Labs. Perfect for partner briefings, customer demonstrations, and showcasing the value of FortiGuard subscriptions.

## When to Use

- **Partner meetings**: Show customers what protections they're receiving today
- **Daily security updates**: Start your day knowing what new signatures are deployed
- **Customer demos**: Demonstrate FortiGuard's real-time threat intelligence
- **Value justification**: Quantify the protection FortiGuard provides
- **Outbreak response**: Check for active outbreak alerts affecting customers

## Example Prompts

- "Show me today's FortiGuard protections"
- "What new signatures did FortiGuard release today?"
- "Generate a partner protection report"
- "Are there any active FortiGuard outbreak alerts?"
- "Run the FortiGuard daily report"

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_dir` | string | `C:\Temp` | Directory to save HTML report |
| `open_browser` | boolean | `true` | Auto-open report in browser |
| `include_av` | boolean | `true` | Include Antivirus updates |
| `include_ips` | boolean | `true` | Include IPS rule updates |
| `include_web` | boolean | `true` | Include Web Filter updates |
| `include_app` | boolean | `true` | Include App Control updates |
| `include_outbreak` | boolean | `true` | Include Outbreak alerts |
| `max_items` | integer | `25` | Max items per category |

## Data Sources

### FortiGuard Feeds
- **Outbreak Alerts**: Emergency response to active global threats (ransomware, zero-days)
- **PSIRT Advisories**: Fortinet product security incident response
- **Threat Research Blog**: Deep-dive analysis from FortiGuard Labs
- **Virus Encyclopedia**: Latest malware signatures and technical analysis

### Protection Statistics
- **Antivirus**: Signature count and daily additions
- **IPS/IDS**: Rule count and daily updates
- **Web Filter**: URLs rated and categorized
- **App Control**: Application signatures

## Output Structure

```json
{
  "success": true,
  "report_path": "C:\\Temp\\fortiguard-protections-2026-01-20.html",
  "summary": {
    "total_updates": 45,
    "av_signatures": 62,
    "av_total": 1254567,
    "av_db_version": "93.06488",
    "ips_rules": 19,
    "ips_total": 23656,
    "ips_db_version": "35.154",
    "sandbox_zerodays": 847,
    "sandbox_zerodays_today": 12,
    "sandbox_samples": 2345678,
    "outbreak_alerts": 0,
    "last_update": "2026-01-20 14:30 UTC",
    "critical_items": 3,
    "high_items": 8
  },
  "database_details": {
    "av": {
      "name": "Antivirus Database",
      "version": "93.06488",
      "total": 1254567,
      "today": 62,
      "last_update": "2026-01-20 14:30 UTC"
    },
    "ips": {
      "name": "IPS Rules Database",
      "version": "35.154",
      "total": 23656,
      "today": 19,
      "last_update": "2026-01-20 14:30 UTC"
    },
    "sandbox": {
      "name": "FortiSandbox Cloud",
      "version": "Cloud Service",
      "zerodays_caught": 847,
      "zerodays_today": 12,
      "samples_analyzed": 2345678
    }
  },
  "highlights": [...],
  "browser_opened": true,
  "message": "FortiGuard Daily Protections report generated..."
}
```

## Claude Interpretation Guidelines

When this tool runs, Claude should:

1. **Highlight outbreak alerts first**: If any active outbreaks, emphasize them immediately.

2. **Summarize protection stats with DB versions**: "Your customers received X new AV signatures (DB v93.06488) and Y IPS rules (DB v35.154) today."

3. **Emphasize sandbox zero-day protection**: "FortiSandbox has caught X zero-days through inline analysis."

4. **Note PSIRT advisories**: Call out any product security updates partners should be aware of.

5. **Contextualize for partners**: Explain how the protections help their customers.

6. **Suggest follow-up**: "Would you like me to check if any of these affect your FortiGate lab?"

## Example Claude Response

> "I've generated today's FortiGuard Daily Protections report and opened it in your browser.
>
> **Key Highlights:**
> - 62 new antivirus signatures deployed today (DB v93.06488)
> - 19 IPS rules updated for exploit protection (DB v35.154)
> - FortiSandbox caught 12 new zero-days today (847 total)
> - No active outbreak alerts
>
> **Database Versions:**
> - AV Database: v93.06488 (1,254,567 total signatures)
> - IPS Database: v35.154 (23,656 total rules)
> - FortiSandbox: Cloud inline analysis active
>
> The FortiGuard network blocked 987,654 malware instances and 123,456 exploits in the last 24 hours.
>
> Partners should be aware of the PSIRT advisory for FortiOS 7.4 - customers should verify they're on a patched version.
>
> Would you like me to email this report to your partner distribution list?"

## Report Sections

The HTML report includes:

1. **Protection Statistics Cards**: Visual display of daily/total signature counts
2. **Active Protections Summary**: Grid showing AV, IPS, Web Filter, App Control status
3. **Outbreak Alerts**: Critical section for active global threats
4. **PSIRT Advisories**: Security advisories for Fortinet products
5. **Threat Research**: Deep-dive analysis articles
6. **Malware Analysis**: Latest virus encyclopedia entries

## Partner Value Points

Use this report to demonstrate:
- **Real-time protection**: "FortiGuard updated your protection X times today"
- **Global visibility**: "FortiGuard blocked Y million threats across our network"
- **Expert analysis**: "FortiGuard Labs researchers identified these new threats"
- **Proactive defense**: "Your customers were protected before they even knew about this threat"

## Notes

- Report is timestamped and saved for historical reference
- Statistics refresh throughout the day as FortiGuard releases updates
- Outbreak alerts have highest priority and appear first
- HTML report can be shared with customers via email or presentations
