#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Top Bandwidth Analyzer

Identify top bandwidth consumers on a FortiGate device by source IP, user,
or application. Uses FortiView APIs, traffic log aggregation, live session
table, and app-ctrl log correlation to provide enriched single-call triage.

Modes:
    - top-sources: Aggregate traffic logs by srcip/user, rank by bytes,
                   enrich with app data from app-ctrl logs
    - top-apps: Native FortiView top applications API with app name
                resolution and source IP correlation
    - session-scan: Live session table scan — aggregates active sessions
                    by app, showing source IPs + real bandwidth per app.
                    This is the only mode that reliably correlates
                    app_id + source_ip + bandwidth in a single view.
    - app-drill: Deep investigation of a specific application - who is
                 using it, session counts, destinations
    - enable-tracking: Enable FortiView application bandwidth tracking

Author: Trust-Bot Tool Maker
Version: 1.2.0
Created: 2026-03-08
Updated: 2026-03-09
"""

import urllib.request
import urllib.error
import urllib.parse
import ssl
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional, Dict, List

BLOCKED_PATTERNS = [
    r"[;&|`$]",
    r"\.\.[/\\]",
    r"[<>]",
]

GENERIC_APP_NAMES = {"", "HTTPS", "HTTP", "SSL", "DNS", "tcp", "udp"}


def validate_input(value):
    """Validate input for security."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, str(value)):
            return False, f"Blocked pattern detected: {pattern}"
    return True, None


def validate_ip(ip):
    """Validate IPv4 address format."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False
    return True


def load_credentials(target_ip):
    """Load API credentials from local config file."""
    config_paths = [
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]
    if os.name == "nt":
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
        config_paths.append(Path("C:/ProgramData/mcp/fortigate_credentials.yaml"))
    else:
        config_paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    device_name = config["default_lookup"][target_ip]
                    if device_name in config.get("devices", {}):
                        return config["devices"][device_name]
                for device in config.get("devices", {}).values():
                    if device.get("host") == target_ip:
                        return device
            except Exception:
                continue
    return None


def _remaining_time(start_time, total_timeout):
    """Calculate remaining time budget for API calls."""
    elapsed = time.time() - start_time
    remaining = total_timeout - elapsed
    return max(remaining, 2)


def make_api_request(host, port, endpoint, api_token, method="GET",
                     verify_ssl=False, timeout=30):
    """Make a request to FortiGate REST API with custom port support."""
    url = f"https://{host}:{port}{endpoint}"
    if "?" in url:
        url += f"&access_token={api_token}"
    else:
        url += f"?access_token={api_token}"

    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()

    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(response.read().decode())


def get_device_info(host, port, api_token, verify_ssl, timeout):
    """Get basic device information for context."""
    try:
        response = make_api_request(host, port, "/api/v2/monitor/system/status",
                                    api_token, "GET", verify_ssl, timeout)
        results = response.get("results", {})
        return {
            "serial": response.get("serial", "unknown"),
            "hostname": results.get("hostname", "unknown"),
            "version": response.get("version", "unknown"),
            "model": results.get("model_name", results.get("model", "unknown")),
        }
    except Exception:
        return {"serial": "unknown", "hostname": "unknown",
                "version": "unknown", "model": "unknown"}


def build_app_name_map(host, port, api_token, verify_ssl, timeout):
    """Fetch the full CMDB application name database and return {id: name} map."""
    try:
        endpoint = "/api/v2/cmdb/application/name?count=10000"
        response = make_api_request(host, port, endpoint, api_token,
                                    "GET", verify_ssl, min(timeout, 15))
        return {a["id"]: a["name"] for a in response.get("results", [])
                if "id" in a and "name" in a}
    except Exception:
        return {}


def get_app_activity_for_ip(host, port, api_token, verify_ssl, timeout,
                            srcip, rows=500):
    """Query app-ctrl logs for a specific source IP, return top apps by session count."""
    try:
        safe_ip = urllib.parse.quote(srcip, safe=".")
        endpoint = f"/api/v2/log/disk/app-ctrl?rows={rows}&filter=srcip=={safe_ip}"
        response = make_api_request(host, port, endpoint, api_token,
                                    "GET", verify_ssl, timeout)
        logs = response.get("results", [])

        app_counts = defaultdict(int)
        for log in logs:
            app_name = log.get("app", "")
            if app_name and app_name not in GENERIC_APP_NAMES:
                app_counts[app_name] += 1

        sorted_apps = sorted(app_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"app_name": a[0], "session_count": a[1]} for a in sorted_apps[:5]]
    except Exception:
        return []


def get_source_ips_for_app(host, port, api_token, verify_ssl, timeout,
                           app_name, rows=500):
    """Query app-ctrl logs for a specific app, return top source IPs."""
    try:
        safe_app = urllib.parse.quote(app_name, safe=".")
        endpoint = f"/api/v2/log/disk/app-ctrl?rows={rows}&filter=app=={safe_app}"
        response = make_api_request(host, port, endpoint, api_token,
                                    "GET", verify_ssl, timeout)
        logs = response.get("results", [])

        ip_stats = defaultdict(lambda: {"count": 0, "users": set()})
        for log in logs:
            ip = log.get("srcip", "")
            if ip:
                ip_stats[ip]["count"] += 1
                user = log.get("user", "")
                if user:
                    ip_stats[ip]["users"].add(user)

        sorted_ips = sorted(ip_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        return [{"ip": ip, "user": list(s["users"])[0] if s["users"] else "",
                 "session_count": s["count"]}
                for ip, s in sorted_ips[:5]]
    except Exception:
        return []


def get_top_sources(host, port, api_token, verify_ssl, timeout,
                    rows=2000, top_n=5, sort_by="total", enrich_apps=True,
                    start_time_ref=None):
    """Aggregate traffic logs by source IP/user and rank by bandwidth.

    When enrich_apps=True, also queries app-ctrl logs per top IP to discover
    which applications each source is using.
    """
    call_timeout = min(timeout, 15)
    endpoint = f"/api/v2/log/disk/traffic/forward?rows={min(rows, 2000)}"
    response = make_api_request(host, port, endpoint, api_token,
                                "GET", verify_ssl, call_timeout)
    logs = response.get("results", [])

    ip_stats = defaultdict(lambda: {
        "sent_bytes": 0, "recv_bytes": 0, "total_bytes": 0,
        "session_count": 0, "users": set(),
        "top_destinations": defaultdict(int),
        "top_services": defaultdict(int),
        "top_apps_traffic": defaultdict(int),
    })

    for log in logs:
        srcip = log.get("srcip", "unknown")
        sent = int(log.get("sentbyte", 0))
        recv = int(log.get("rcvdbyte", 0))
        user = log.get("user", "")
        dstip = log.get("dstip", "")
        service = log.get("service", "")
        app = log.get("app", "")

        stats = ip_stats[srcip]
        stats["sent_bytes"] += sent
        stats["recv_bytes"] += recv
        stats["total_bytes"] += sent + recv
        stats["session_count"] += 1
        if user:
            stats["users"].add(user)
        if dstip:
            stats["top_destinations"][dstip] += sent + recv
        if service:
            stats["top_services"][service] += sent + recv
        if app and app not in GENERIC_APP_NAMES:
            stats["top_apps_traffic"][app] += sent + recv

    sort_key = {"total": "total_bytes", "sent": "sent_bytes",
                "received": "recv_bytes"}.get(sort_by, "total_bytes")
    sorted_ips = sorted(ip_stats.items(),
                        key=lambda x: x[1][sort_key], reverse=True)

    enrichment_status = "skipped"
    enriched_count = 0

    top_consumers = []
    for rank, (ip, stats) in enumerate(sorted_ips[:top_n], 1):
        top_dsts = sorted(stats["top_destinations"].items(),
                          key=lambda x: x[1], reverse=True)[:3]
        top_svcs = sorted(stats["top_services"].items(),
                          key=lambda x: x[1], reverse=True)[:3]
        top_apps_from_traffic = sorted(stats["top_apps_traffic"].items(),
                                       key=lambda x: x[1], reverse=True)[:3]

        # App enrichment from app-ctrl logs
        top_apps_enriched = []
        if enrich_apps and start_time_ref and rank <= 5:
            remaining = _remaining_time(start_time_ref, timeout)
            if remaining > 4:
                top_apps_enriched = get_app_activity_for_ip(
                    host, port, api_token, verify_ssl,
                    min(remaining - 2, 8), ip)
                if top_apps_enriched:
                    enriched_count += 1

        # Merge: prefer app-ctrl data, supplement with traffic log apps
        if top_apps_enriched:
            final_apps = top_apps_enriched
        elif top_apps_from_traffic:
            final_apps = [{"app_name": a[0], "bytes": a[1]}
                          for a in top_apps_from_traffic]
        else:
            final_apps = []

        top_consumers.append({
            "rank": rank,
            "source_ip": ip,
            "users": list(stats["users"]) if stats["users"] else [],
            "total_bytes": stats["total_bytes"],
            "total_mb": round(stats["total_bytes"] / (1024 * 1024), 2),
            "sent_bytes": stats["sent_bytes"],
            "sent_mb": round(stats["sent_bytes"] / (1024 * 1024), 2),
            "recv_bytes": stats["recv_bytes"],
            "recv_mb": round(stats["recv_bytes"] / (1024 * 1024), 2),
            "session_count": stats["session_count"],
            "top_destinations": [{"ip": d[0], "bytes": d[1]} for d in top_dsts],
            "top_services": [{"service": s[0], "bytes": s[1]} for s in top_svcs],
            "top_apps": final_apps,
        })

    if enrich_apps:
        if enriched_count == min(top_n, 5):
            enrichment_status = "full"
        elif enriched_count > 0:
            enrichment_status = "partial"
        else:
            enrichment_status = "unavailable"

    total_bandwidth = sum(s["total_bytes"] for s in ip_stats.values())
    return {
        "top_consumers": top_consumers,
        "summary": {
            "logs_analyzed": len(logs),
            "unique_source_ips": len(ip_stats),
            "total_bandwidth_bytes": total_bandwidth,
            "total_bandwidth_mb": round(total_bandwidth / (1024 * 1024), 2),
            "sorted_by": sort_by,
            "app_enrichment": enrichment_status,
            "app_enrichment_ips": enriched_count,
        },
    }


def get_top_apps(host, port, api_token, verify_ssl, timeout,
                 time_period="hour", top_n=5, enrich_sources=True,
                 start_time_ref=None):
    """Get top applications by bandwidth from FortiView API.

    Resolves app_id to human-readable app_name via CMDB lookup.
    When enrich_sources=True, also queries app-ctrl logs per app to find
    which source IPs are using each application.
    """
    if time_period not in ("hour", "day", "week"):
        return {"error": "Invalid time_period. Must be: hour, day, week"}

    # Phase 1: Get FortiView top applications
    endpoint = (f"/api/v2/monitor/system/traffic-history/top-applications"
                f"?time_period={time_period}")
    response = make_api_request(host, port, endpoint, api_token,
                                "GET", verify_ssl, min(timeout, 10))
    results = response.get("results", [])

    # Phase 2: Resolve app names from CMDB
    app_name_map = {}
    if start_time_ref:
        remaining = _remaining_time(start_time_ref, timeout)
        if remaining > 5:
            app_name_map = build_app_name_map(host, port, api_token,
                                              verify_ssl, min(remaining - 3, 10))

    sorted_apps = sorted(results,
                         key=lambda x: x.get("total_bytes", 0), reverse=True)

    enrichment_status = "skipped"
    enriched_count = 0

    top_apps = []
    for rank, app in enumerate(sorted_apps[:top_n], 1):
        aid = app.get("app_id", 0)
        app_name = app_name_map.get(aid, f"unknown(id={aid})")

        # Phase 3: Find source IPs for this app via app-ctrl
        top_source_ips = []
        if enrich_sources and start_time_ref and app_name and rank <= 5:
            remaining = _remaining_time(start_time_ref, timeout)
            if remaining > 4 and not app_name.startswith("unknown("):
                top_source_ips = get_source_ips_for_app(
                    host, port, api_token, verify_ssl,
                    min(remaining - 2, 8), app_name)
                if top_source_ips:
                    enriched_count += 1

        top_apps.append({
            "rank": rank,
            "app_id": aid,
            "app_name": app_name,
            "total_bytes": app.get("total_bytes", 0),
            "total_mb": round(app.get("total_bytes", 0) / (1024 * 1024), 2),
            "last_tx_bps": app.get("last_tx", 0),
            "last_rx_bps": app.get("last_rx", 0),
            "top_source_ips": top_source_ips,
        })

    if enrich_sources:
        if enriched_count == min(top_n, 5):
            enrichment_status = "full"
        elif enriched_count > 0:
            enrichment_status = "partial"
        else:
            enrichment_status = "unavailable"

    total_bandwidth = sum(a.get("total_bytes", 0) for a in results)
    return {
        "top_consumers": top_apps,
        "summary": {
            "total_apps_tracked": len(results),
            "time_period": time_period,
            "total_bandwidth_bytes": total_bandwidth,
            "total_bandwidth_mb": round(total_bandwidth / (1024 * 1024), 2),
            "app_names_resolved": len(app_name_map) > 0,
            "source_enrichment": enrichment_status,
            "source_enrichment_apps": enriched_count,
        },
    }


def get_app_drill(host, port, api_token, verify_ssl, timeout,
                  app_name=None, app_id=None, top_n=10, start_time_ref=None):
    """Deep investigation of a specific application.

    Queries app-ctrl logs for the given app and aggregates by source IP,
    showing session counts, associated users, destinations, and time range.
    Note: app-ctrl logs do not contain bandwidth data, only session counts.
    """
    # Resolve app_id to name if needed
    if not app_name and app_id:
        if start_time_ref:
            remaining = _remaining_time(start_time_ref, timeout)
        else:
            remaining = timeout
        app_map = build_app_name_map(host, port, api_token, verify_ssl,
                                     min(remaining, 10))
        app_name = app_map.get(int(app_id))
        if not app_name:
            return {"error": f"Could not resolve app_id {app_id} to a name"}

    if not app_name:
        return {"error": "app-drill mode requires app_name or app_id parameter"}

    # Query app-ctrl logs for this app
    safe_app = urllib.parse.quote(app_name, safe=".")
    endpoint = f"/api/v2/log/disk/app-ctrl?rows=2000&filter=app=={safe_app}"
    if start_time_ref:
        call_timeout = min(_remaining_time(start_time_ref, timeout) - 2, 15)
    else:
        call_timeout = min(timeout, 15)
    response = make_api_request(host, port, endpoint, api_token,
                                "GET", verify_ssl, max(call_timeout, 3))
    logs = response.get("results", [])

    # Aggregate by source IP
    ip_stats = defaultdict(lambda: {
        "count": 0, "users": set(), "destinations": defaultdict(int),
        "first_seen": "", "last_seen": "",
    })

    for log in logs:
        srcip = log.get("srcip", "")
        if not srcip:
            continue
        s = ip_stats[srcip]
        s["count"] += 1
        user = log.get("user", "")
        if user:
            s["users"].add(user)
        dstip = log.get("dstip", "")
        if dstip:
            s["destinations"][dstip] += 1
        ts = log.get("date", "") + "T" + log.get("time", "")
        if ts and (not s["first_seen"] or ts < s["first_seen"]):
            s["first_seen"] = ts
        if ts and (not s["last_seen"] or ts > s["last_seen"]):
            s["last_seen"] = ts

    sorted_ips = sorted(ip_stats.items(),
                        key=lambda x: x[1]["count"], reverse=True)

    top_source_ips = []
    for rank, (ip, s) in enumerate(sorted_ips[:top_n], 1):
        top_dsts = sorted(s["destinations"].items(),
                          key=lambda x: x[1], reverse=True)[:5]
        top_source_ips.append({
            "rank": rank,
            "source_ip": ip,
            "users": list(s["users"]) if s["users"] else [],
            "session_count": s["count"],
            "top_destinations": [{"ip": d[0], "count": d[1]} for d in top_dsts],
            "first_seen": s["first_seen"],
            "last_seen": s["last_seen"],
        })

    return {
        "app_name": app_name,
        "app_id": int(app_id) if app_id else None,
        "top_source_ips": top_source_ips,
        "summary": {
            "total_sessions": len(logs),
            "unique_source_ips": len(ip_stats),
            "logs_available": response.get("total_lines", len(logs)),
            "note": "Session counts only - app-ctrl logs do not contain bandwidth data",
        },
    }


def get_session_scan(host, port, api_token, verify_ssl, timeout,
                     top_n=10, sort_by="total", view="by-app",
                     start_time_ref=None):
    """Scan the live session table and aggregate by app or source IP.

    This is the key endpoint that provides app_id + source_ip + bandwidth
    in a single data source — solving the FortiGate data fusion gap.

    Endpoint: /api/v2/monitor/firewall/sessions
    Each session contains: saddr, daddr, apps[{id, name}], sentbyte, rcvdbyte

    Args:
        view: 'by-app' aggregates sessions by app_id showing source IPs per app
              'by-source' aggregates sessions by source IP showing apps per source
    """
    # Phase 1: Fetch all live sessions
    call_timeout = min(timeout, 20)
    endpoint = "/api/v2/monitor/firewall/sessions?count=5000"
    response = make_api_request(host, port, endpoint, api_token,
                                "GET", verify_ssl, call_timeout)
    sessions = response.get("results", {}).get("details", [])

    # Phase 2: Resolve app names from CMDB
    app_name_map = {}
    if start_time_ref:
        remaining = _remaining_time(start_time_ref, timeout)
        if remaining > 5:
            app_name_map = build_app_name_map(host, port, api_token,
                                              verify_ssl, min(remaining - 3, 10))

    total_bytes_all = 0

    if view == "by-app":
        # Aggregate by app_id
        app_stats = defaultdict(lambda: {
            "total_sent": 0, "total_recv": 0, "total_bytes": 0,
            "session_count": 0, "sources": defaultdict(lambda: {
                "sent": 0, "recv": 0, "total": 0, "count": 0,
            }),
        })

        for sess in sessions:
            sent = int(sess.get("sentbyte", 0))
            recv = int(sess.get("rcvdbyte", 0))
            srcip = sess.get("saddr", "")
            total_bytes_all += sent + recv

            for app in sess.get("apps", []):
                aid = app.get("id", 0)
                if aid == 0:
                    continue
                s = app_stats[aid]
                s["total_sent"] += sent
                s["total_recv"] += recv
                s["total_bytes"] += sent + recv
                s["session_count"] += 1
                if srcip:
                    src = s["sources"][srcip]
                    src["sent"] += sent
                    src["recv"] += recv
                    src["total"] += sent + recv
                    src["count"] += 1

        sort_key = {"total": "total_bytes", "sent": "total_sent",
                    "received": "total_recv"}.get(sort_by, "total_bytes")
        sorted_apps = sorted(app_stats.items(),
                             key=lambda x: x[1][sort_key], reverse=True)

        top_consumers = []
        for rank, (aid, stats) in enumerate(sorted_apps[:top_n], 1):
            # Sort source IPs by bandwidth within this app
            sorted_srcs = sorted(stats["sources"].items(),
                                 key=lambda x: x[1]["total"], reverse=True)
            top_sources = []
            for ip, src_stats in sorted_srcs[:10]:
                top_sources.append({
                    "source_ip": ip,
                    "sent_bytes": src_stats["sent"],
                    "recv_bytes": src_stats["recv"],
                    "total_bytes": src_stats["total"],
                    "total_mb": round(src_stats["total"] / (1024 * 1024), 2),
                    "session_count": src_stats["count"],
                })

            top_consumers.append({
                "rank": rank,
                "app_id": aid,
                "app_name": app_name_map.get(aid, f"unknown(id={aid})"),
                "total_bytes": stats["total_bytes"],
                "total_mb": round(stats["total_bytes"] / (1024 * 1024), 2),
                "sent_bytes": stats["total_sent"],
                "sent_mb": round(stats["total_sent"] / (1024 * 1024), 2),
                "recv_bytes": stats["total_recv"],
                "recv_mb": round(stats["total_recv"] / (1024 * 1024), 2),
                "session_count": stats["session_count"],
                "source_ips": top_sources,
            })

        return {
            "top_consumers": top_consumers,
            "summary": {
                "view": "by-app",
                "total_sessions_scanned": len(sessions),
                "sessions_with_app": sum(s["session_count"] for s in app_stats.values()),
                "unique_apps": len(app_stats),
                "total_bandwidth_bytes": total_bytes_all,
                "total_bandwidth_mb": round(total_bytes_all / (1024 * 1024), 2),
                "sorted_by": sort_by,
                "app_names_resolved": len(app_name_map) > 0,
                "data_source": "live_session_table",
            },
        }

    else:  # view == "by-source"
        # Aggregate by source IP
        ip_stats = defaultdict(lambda: {
            "total_sent": 0, "total_recv": 0, "total_bytes": 0,
            "session_count": 0, "apps": defaultdict(lambda: {
                "sent": 0, "recv": 0, "total": 0, "count": 0,
            }),
        })

        for sess in sessions:
            sent = int(sess.get("sentbyte", 0))
            recv = int(sess.get("rcvdbyte", 0))
            srcip = sess.get("saddr", "")
            total_bytes_all += sent + recv

            if not srcip:
                continue
            s = ip_stats[srcip]
            s["total_sent"] += sent
            s["total_recv"] += recv
            s["total_bytes"] += sent + recv
            s["session_count"] += 1

            for app in sess.get("apps", []):
                aid = app.get("id", 0)
                if aid == 0:
                    continue
                a = s["apps"][aid]
                a["sent"] += sent
                a["recv"] += recv
                a["total"] += sent + recv
                a["count"] += 1

        sort_key = {"total": "total_bytes", "sent": "total_sent",
                    "received": "total_recv"}.get(sort_by, "total_bytes")
        sorted_ips = sorted(ip_stats.items(),
                            key=lambda x: x[1][sort_key], reverse=True)

        top_consumers = []
        for rank, (ip, stats) in enumerate(sorted_ips[:top_n], 1):
            sorted_apps = sorted(stats["apps"].items(),
                                 key=lambda x: x[1]["total"], reverse=True)
            top_apps = []
            for aid, app_s in sorted_apps[:10]:
                top_apps.append({
                    "app_id": aid,
                    "app_name": app_name_map.get(aid, f"unknown(id={aid})"),
                    "total_bytes": app_s["total"],
                    "total_mb": round(app_s["total"] / (1024 * 1024), 2),
                    "session_count": app_s["count"],
                })

            top_consumers.append({
                "rank": rank,
                "source_ip": ip,
                "total_bytes": stats["total_bytes"],
                "total_mb": round(stats["total_bytes"] / (1024 * 1024), 2),
                "sent_bytes": stats["total_sent"],
                "sent_mb": round(stats["total_sent"] / (1024 * 1024), 2),
                "recv_bytes": stats["total_recv"],
                "recv_mb": round(stats["total_recv"] / (1024 * 1024), 2),
                "session_count": stats["session_count"],
                "top_apps": top_apps,
            })

        return {
            "top_consumers": top_consumers,
            "summary": {
                "view": "by-source",
                "total_sessions_scanned": len(sessions),
                "unique_source_ips": len(ip_stats),
                "total_bandwidth_bytes": total_bytes_all,
                "total_bandwidth_mb": round(total_bytes_all / (1024 * 1024), 2),
                "sorted_by": sort_by,
                "app_names_resolved": len(app_name_map) > 0,
                "data_source": "live_session_table",
            },
        }


def enable_bandwidth_tracking(host, port, api_token, verify_ssl, timeout):
    """Enable FortiView application bandwidth tracking."""
    endpoint = "/api/v2/monitor/system/traffic-history/enable-app-bandwidth-tracking"
    response = make_api_request(host, port, endpoint, api_token,
                                "POST", verify_ssl, timeout)
    return {"tracking_enabled": True, "response": response}


def main(context):
    """FortiGate Top Bandwidth Analyzer - find top bandwidth consumers."""
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    if not target_ip:
        return {"success": False, "error": "target_ip is required"}

    is_ok, reason = validate_input(target_ip)
    if not is_ok:
        return {"success": False, "error": f"Security block: {reason}"}
    if not validate_ip(target_ip):
        return {"success": False, "error": f"Invalid IP address: {target_ip}"}

    port = int(args.get("port", 10443))
    mode = args.get("mode", "top-sources").lower()
    top_n = min(int(args.get("top_n", 5)), 50)
    time_period = args.get("time_period", "hour")
    rows = min(int(args.get("rows", 2000)), 2000)
    sort_by = args.get("sort_by", "total")
    timeout = int(args.get("timeout", 30))
    verify_ssl = args.get("verify_ssl", False)
    enrich_apps = str(args.get("enrich_apps", "true")).lower() == "true"
    enrich_sources = str(args.get("enrich_sources", "true")).lower() == "true"
    app_name = args.get("app_name")
    app_id = args.get("app_id")
    view = args.get("view", "by-app").lower()

    if mode not in ("top-sources", "top-apps", "session-scan", "app-drill", "enable-tracking"):
        return {"success": False,
                "error": "Invalid mode. Must be: top-sources, top-apps, session-scan, app-drill, enable-tracking"}

    api_token = None
    if creds and creds.get("api_token"):
        api_token = creds["api_token"]
        if creds.get("verify_ssl") is not None:
            verify_ssl = creds["verify_ssl"]
    else:
        local_creds = load_credentials(target_ip)
        if local_creds:
            api_token = local_creds.get("api_token")
            if local_creds.get("verify_ssl") is not None:
                verify_ssl = local_creds["verify_ssl"]

    if not api_token:
        return {"success": False,
                "error": f"No API credentials found for {target_ip}. "
                         "Configure in ~/.config/mcp/fortigate_credentials.yaml"}

    start_time_ref = time.time()

    try:
        device_info = get_device_info(target_ip, port, api_token,
                                      verify_ssl, timeout)

        if mode == "top-sources":
            result = get_top_sources(target_ip, port, api_token,
                                     verify_ssl, timeout,
                                     rows=rows, top_n=top_n,
                                     sort_by=sort_by,
                                     enrich_apps=enrich_apps,
                                     start_time_ref=start_time_ref)
        elif mode == "top-apps":
            result = get_top_apps(target_ip, port, api_token,
                                  verify_ssl, timeout,
                                  time_period=time_period,
                                  top_n=top_n,
                                  enrich_sources=enrich_sources,
                                  start_time_ref=start_time_ref)
        elif mode == "session-scan":
            result = get_session_scan(target_ip, port, api_token,
                                      verify_ssl, timeout,
                                      top_n=top_n, sort_by=sort_by,
                                      view=view,
                                      start_time_ref=start_time_ref)
        elif mode == "app-drill":
            if not app_name and not app_id:
                return {"success": False,
                        "error": "app-drill mode requires app_name or app_id parameter",
                        "target_ip": target_ip, "mode": mode}
            result = get_app_drill(target_ip, port, api_token,
                                   verify_ssl, timeout,
                                   app_name=app_name, app_id=app_id,
                                   top_n=top_n,
                                   start_time_ref=start_time_ref)
        elif mode == "enable-tracking":
            result = enable_bandwidth_tracking(target_ip, port, api_token,
                                               verify_ssl, timeout)

        if "error" in result and not result.get("top_consumers") and not result.get("top_source_ips"):
            return {"success": False, "error": result["error"],
                    "target_ip": target_ip, "mode": mode}

        elapsed = round(time.time() - start_time_ref, 2)
        return {
            "success": True,
            "target_ip": target_ip,
            "port": port,
            "mode": mode,
            "device": device_info,
            "execution_time_s": elapsed,
            **result,
        }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        return {"success": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "detail": error_body,
                "target_ip": target_ip, "port": port, "mode": mode}
    except urllib.error.URLError as e:
        return {"success": False,
                "error": f"Connection failed: {e.reason}",
                "target_ip": target_ip, "port": port, "mode": mode}
    except json.JSONDecodeError as e:
        return {"success": False,
                "error": f"Invalid JSON response: {e}",
                "target_ip": target_ip, "port": port, "mode": mode}
    except Exception as e:
        return {"success": False,
                "error": f"Unexpected error: {str(e)}",
                "target_ip": target_ip, "port": port, "mode": mode}


if __name__ == "__main__":
    import sys
    test_args = {"target_ip": "192.168.209.62", "port": 10443,
                 "mode": "top-sources", "top_n": 5}
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                if key in ("port", "rows", "top_n", "app_id"):
                    value = int(value)
                test_args[key] = value
    result = main(test_args)
    print(json.dumps(result, indent=2, default=str))
