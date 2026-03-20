#!/usr/bin/env python3
from __future__ import annotations
"""
FortiGate Interface Status Tool

Retrieves interface status and NIC statistics from a FortiGate device.
Uses REST API for interface list and CLI commands for deep NIC diagnostics.
"""

import urllib.request
import urllib.error
import ssl
import json
import os
import time
from pathlib import Path
from typing import Any, Optional, List, Dict


def load_credentials(target_ip: str) -> Optional[dict]:
    """Load API credentials from local config file.

    MCP credential search order (uses FIRST match):
    1. ~/.config/mcp/ (PRIMARY - MCP server checks this first)
    2. ~/AppData/Local/mcp/ (Windows secondary)
    3. C:/ProgramData/mcp/ or /etc/mcp/ (System-wide)

    Note: We ONLY check MCP paths to ensure consistency with credential-manager.
    Tool-relative and CWD-relative paths are NOT checked to avoid stale credentials.
    """
    config_paths = [
        # PRIMARY: User config (MCP server checks this FIRST)
        Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml",
    ]

    # Platform-specific paths
    if os.name == 'nt':
        # Windows secondary
        config_paths.append(Path.home() / "AppData" / "Local" / "mcp" / "fortigate_credentials.yaml")
        # Windows system-wide
        config_paths.append(Path("C:/ProgramData/mcp/fortigate_credentials.yaml"))
    else:
        # Linux/Mac system-wide
        config_paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                # Check default_lookup first (IP -> device_id mapping)
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    device_name = config["default_lookup"][target_ip]
                    if device_name in config.get("devices", {}):
                        return config["devices"][device_name]

                # Search devices by host
                for device in config.get("devices", {}).values():
                    if device.get("host") == target_ip:
                        return device

            except Exception:
                continue

    return None


def make_api_request(host: str, endpoint: str, api_token: str,
                     verify_ssl: bool = False, timeout: int = 30,
                     method: str = "GET", data: Optional[dict] = None) -> dict:
    """Make a request to FortiGate REST API."""
    url = f"https://{host}{endpoint}?access_token={api_token}"

    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()

    if data:
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, method=method)
    else:
        req = urllib.request.Request(url, method=method)

    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        return json.loads(response.read().decode())


def execute_cli(host: str, command: str, api_token: str,
                verify_ssl: bool = False, timeout: int = 30) -> str:
    """Execute a CLI command via FortiGate API."""
    try:
        response = make_api_request(
            host, "/api/v2/monitor/system/cli",
            api_token, verify_ssl, timeout,
            method="POST", data={"command": command}
        )
        return response.get("results", "")
    except Exception as e:
        return f"CLI Error: {str(e)}"


def parse_nic_stats(output: str, interface_name: str) -> Dict[str, Any]:
    """Parse NIC statistics from CLI output."""
    stats = {
        'interface': interface_name,
        'rx_packets': 0,
        'rx_bytes': 0,
        'rx_dropped': 0,
        'rx_errors': 0,
        'tx_packets': 0,
        'tx_bytes': 0,
        'tx_dropped': 0,
        'tx_errors': 0,
        'speed': 'unknown',
        'state': 'unknown',
        'link': 'unknown',
        'duplex': 'unknown',
    }

    for line in output.split('\n'):
        line = line.strip()

        if 'State:' in line:
            stats['state'] = line.split(':')[1].strip()
        elif 'Link:' in line:
            stats['link'] = line.split(':')[1].strip()
        elif 'Speed:' in line:
            stats['speed'] = line.split(':')[1].strip()
        elif 'Duplex:' in line:
            stats['duplex'] = line.split(':')[1].strip()
        elif 'Rx packets:' in line:
            try:
                stats['rx_packets'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Rx bytes:' in line:
            try:
                stats['rx_bytes'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Rx dropped:' in line:
            try:
                stats['rx_dropped'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Rx errors:' in line:
            try:
                stats['rx_errors'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Tx packets:' in line:
            try:
                stats['tx_packets'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Tx bytes:' in line:
            try:
                stats['tx_bytes'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Tx dropped:' in line:
            try:
                stats['tx_dropped'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Tx errors:' in line:
            try:
                stats['tx_errors'] = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass

    return stats


def get_interface_list(host: str, api_token: str,
                       verify_ssl: bool = False, timeout: int = 30) -> List[Dict[str, Any]]:
    """Get interface list via REST API.

    Note: FortiOS API returns interfaces as a dict keyed by interface name,
    not as a list. We convert to list format for consistency.
    """
    response = make_api_request(
        host, "/api/v2/monitor/system/interface",
        api_token, verify_ssl, timeout
    )

    interfaces = []
    results = response.get("results", {})

    # API returns dict keyed by interface name, iterate over values
    for iface_name, iface in results.items():
        # Convert duplex integer to string (1=full, 0=half)
        duplex_val = iface.get("duplex", 0)
        duplex_str = "full" if duplex_val == 1 else "half" if duplex_val == 0 else str(duplex_val)

        interfaces.append({
            "name": iface.get("name", iface_name),
            "ip": iface.get("ip", "0.0.0.0"),
            "mask": iface.get("mask", 0),
            "status": "up" if iface.get("link") else "down",
            "link": iface.get("link", False),
            "speed": int(iface.get("speed", 0)),
            "duplex": duplex_str,
            "mac": iface.get("mac", "00:00:00:00:00:00"),
            "rx_bytes": iface.get("rx_bytes", 0),
            "tx_bytes": iface.get("tx_bytes", 0),
            "rx_packets": iface.get("rx_packets", 0),
            "tx_packets": iface.get("tx_packets", 0),
            "rx_errors": iface.get("rx_errors", 0),
            "tx_errors": iface.get("tx_errors", 0),
        })

    return interfaces


def detect_active_errors(host: str, api_token: str, verify_ssl: bool = False,
                         timeout: int = 30, samples: int = 3,
                         interval_sec: int = 3) -> Dict[str, Any]:
    """
    Sample interface error counters multiple times to detect ACTIVE errors.

    Takes 3 samples with 3-second intervals. If error counts are increasing
    between samples, the interface has an ACTIVE problem (not just historical).

    Returns:
        dict with:
            - samples: list of sample data
            - active_errors: list of interfaces with increasing errors
            - error_trend: "INCREASING", "STABLE", or "NONE"
    """
    all_samples = []

    for i in range(samples):
        if i > 0:
            time.sleep(interval_sec)

        response = make_api_request(
            host, "/api/v2/monitor/system/interface",
            api_token, verify_ssl, timeout
        )

        sample = {
            "sample_num": i + 1,
            "timestamp": time.time(),
            "interfaces": {}
        }

        for iface_name, iface in response.get("results", {}).items():
            sample["interfaces"][iface_name] = {
                "rx_errors": iface.get("rx_errors", 0),
                "tx_errors": iface.get("tx_errors", 0),
                "rx_packets": iface.get("rx_packets", 0),
                "tx_packets": iface.get("tx_packets", 0),
            }

        all_samples.append(sample)

    # Analyze for increasing errors
    active_errors = []
    if len(all_samples) >= 2:
        first_sample = all_samples[0]["interfaces"]
        last_sample = all_samples[-1]["interfaces"]

        for iface_name in first_sample:
            if iface_name not in last_sample:
                continue

            first = first_sample[iface_name]
            last = last_sample[iface_name]

            rx_delta = last["rx_errors"] - first["rx_errors"]
            tx_delta = last["tx_errors"] - first["tx_errors"]

            if rx_delta > 0 or tx_delta > 0:
                active_errors.append({
                    "interface": iface_name,
                    "rx_errors_start": first["rx_errors"],
                    "rx_errors_end": last["rx_errors"],
                    "rx_errors_delta": rx_delta,
                    "tx_errors_start": first["tx_errors"],
                    "tx_errors_end": last["tx_errors"],
                    "tx_errors_delta": tx_delta,
                    "sample_interval_sec": interval_sec * (samples - 1),
                    "status": "ACTIVE_ERRORS"
                })

    # Determine overall trend
    if active_errors:
        error_trend = "INCREASING"
    elif any(s["interfaces"].get(k, {}).get("rx_errors", 0) > 0 or
             s["interfaces"].get(k, {}).get("tx_errors", 0) > 0
             for s in all_samples for k in s["interfaces"]):
        error_trend = "STABLE"  # Errors exist but not increasing
    else:
        error_trend = "NONE"

    return {
        "samples_taken": samples,
        "interval_seconds": interval_sec,
        "total_sample_time_sec": interval_sec * (samples - 1),
        "active_errors": active_errors,
        "error_trend": error_trend,
        "interfaces_with_active_errors": len(active_errors),
    }


def main(context) -> Dict[str, Any]:
    """
    FortiGate Interface Status - returns interface and NIC statistics.

    Args:
        context: ExecutionContext containing:
            - parameters.target_ip: FortiGate management IP
            - parameters.interfaces: Optional list of specific interfaces to query
            - parameters.include_nic_diag: Include deep NIC diagnostics via CLI
            - parameters.detect_active_errors: Sample 3x over 6 seconds to detect
              if errors are actively increasing (ACTIVE problem vs historical)
            - parameters.timeout: API timeout in seconds
            - parameters.verify_ssl: Verify SSL certificate

    Returns:
        dict: Interface data including:
            - interfaces: List of interface status
            - nic_diagnostics: Deep NIC stats (if include_nic_diag=true)
            - error_detection: Active error analysis (if detect_active_errors=true)
            - summary: Quick health summary with error_trend
    """
    if hasattr(context, "parameters"):
        args = context.parameters
        creds = getattr(context, "credentials", None)
    else:
        args = context
        creds = None

    target_ip = args.get("target_ip")
    timeout = args.get("timeout", 30)
    verify_ssl = args.get("verify_ssl", False)
    specific_interfaces = args.get("interfaces", [])
    include_nic_diag = args.get("include_nic_diag", False)
    detect_errors = args.get("detect_active_errors", False)

    if not target_ip:
        return {"error": "target_ip is required", "success": False}

    # Get credentials
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
        return {
            "error": f"No API credentials found for {target_ip}",
            "success": False,
        }

    try:
        # Get interface list via REST API
        interfaces = get_interface_list(target_ip, api_token, verify_ssl, timeout)

        # Filter if specific interfaces requested
        if specific_interfaces:
            interfaces = [i for i in interfaces if i["name"] in specific_interfaces]

        # Calculate summary
        total_interfaces = len(interfaces)
        up_count = sum(1 for i in interfaces if i.get("link"))
        down_count = total_interfaces - up_count
        error_count = sum(1 for i in interfaces if i.get("rx_errors", 0) > 0 or i.get("tx_errors", 0) > 0)

        result = {
            "success": True,
            "target_ip": target_ip,
            "interface_count": total_interfaces,
            "interfaces": interfaces,
            "summary": {
                "total": total_interfaces,
                "up": up_count,
                "down": down_count,
                "with_errors": error_count,
                "error_trend": "UNKNOWN",  # Will be updated if detect_active_errors=true
            }
        }

        # Detect active errors (samples 3x with 3-second intervals)
        if detect_errors:
            error_detection = detect_active_errors(
                target_ip, api_token, verify_ssl, timeout,
                samples=3, interval_sec=3
            )
            result["error_detection"] = error_detection
            result["summary"]["error_trend"] = error_detection["error_trend"]
            result["summary"]["interfaces_with_active_errors"] = error_detection["interfaces_with_active_errors"]

            # Add active error interfaces to summary for quick reference
            if error_detection["active_errors"]:
                result["summary"]["active_error_interfaces"] = [
                    e["interface"] for e in error_detection["active_errors"]
                ]

        # Deep NIC diagnostics via CLI (optional)
        if include_nic_diag:
            nic_diag = []
            physical_interfaces = [i["name"] for i in interfaces
                                   if not i["name"].startswith(("ssl.", "any", "npu", "virtual"))]

            for iface_name in physical_interfaces[:10]:  # Limit to 10 interfaces
                cli_output = execute_cli(
                    target_ip,
                    f"diagnose hardware deviceinfo nic {iface_name}",
                    api_token, verify_ssl, timeout
                )
                if not cli_output.startswith("CLI Error"):
                    nic_stats = parse_nic_stats(cli_output, iface_name)
                    nic_diag.append(nic_stats)

            result["nic_diagnostics"] = nic_diag

            # Check for drops
            total_rx_drops = sum(n.get("rx_dropped", 0) for n in nic_diag)
            total_tx_drops = sum(n.get("tx_dropped", 0) for n in nic_diag)
            result["summary"]["rx_drops"] = total_rx_drops
            result["summary"]["tx_drops"] = total_tx_drops

            if total_rx_drops > 10000 or total_tx_drops > 10000:
                result["summary"]["drop_status"] = "CRITICAL"
            elif total_rx_drops > 1000 or total_tx_drops > 1000:
                result["summary"]["drop_status"] = "WARNING"
            elif total_rx_drops > 0 or total_tx_drops > 0:
                result["summary"]["drop_status"] = "MINOR"
            else:
                result["summary"]["drop_status"] = "OK"

        return result

    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "target_ip": target_ip,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e.reason}",
            "target_ip": target_ip,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "target_ip": target_ip,
        }


if __name__ == "__main__":
    # Test execution with active error detection
    print("Testing with detect_active_errors=True (takes ~6 seconds)...")
    result = main({
        "target_ip": "192.168.209.62",
        "detect_active_errors": True
    })
    print(json.dumps(result, indent=2))
