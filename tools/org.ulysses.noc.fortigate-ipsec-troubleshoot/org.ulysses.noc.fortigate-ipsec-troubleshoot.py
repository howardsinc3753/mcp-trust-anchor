#!/usr/bin/env python3
"""FortiGate IPsec Troubleshoot Tool - Canonical ID: org.ulysses.noc.fortigate-ipsec-troubleshoot/1.0.0

In-depth IPsec VPN tunnel troubleshooting with:
- Phase1/Phase2 status analysis
- IKE error counter analysis with delta comparison
- NPU offload verification
- Optional packet capture (IKE/ESP) with analysis
"""
import json, sys, os, re, time, urllib3
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

# Default thresholds for warnings
DEFAULT_THRESHOLDS = {
    'dpd_fail_old_hit': 100,
    'dpd_fail_old_ignore': 100,
    'isakmp_timeout_initiator': 100,
    'isakmp_timeout_responder': 100,
    'isakmp_retrans_send': 100,
    'quick_retrans_send': 100,
    'out_fail': 50,
}


def load_credentials(target_ip: str) -> Optional[Dict]:
    """Load credentials from config files. Supports both API and SSH."""
    paths = [Path.home() / ".config" / "mcp" / "fortigate_credentials.yaml"]
    if os.name == 'nt':
        paths.extend([
            Path.home() / "AppData/Local/mcp/fortigate_credentials.yaml",
            Path("C:/ProgramData/mcp/fortigate_credentials.yaml"),
            Path("C:/ProgramData/Ulysses/config/fortigate_credentials.yaml")
        ])
    else:
        paths.append(Path("/etc/mcp/fortigate_credentials.yaml"))

    for p in paths:
        if p.exists():
            try:
                import yaml
                config = yaml.safe_load(open(p))
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    name = config["default_lookup"][target_ip]
                    if name in config.get("devices", {}):
                        return config["devices"][name]
                for d in config.get("devices", {}).values():
                    if d.get("host") == target_ip:
                        return d
            except Exception:
                pass
    return None


def api_request(host: str, token: str, method: str, endpoint: str, data=None, verify=False) -> Dict:
    """Make FortiGate REST API request."""
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not available"}

    url = f"https://{host}/api/v2{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        resp = getattr(requests, method.lower())(url, headers=headers, json=data, verify=verify, timeout=30)
        return {
            "status_code": resp.status_code,
            "success": resp.status_code in [200, 201],
            "data": resp.json() if resp.text else {}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ssh_command(host: str, username: str, password: str, command: str, timeout: int = 30) -> Tuple[bool, str]:
    """Execute SSH command on FortiGate."""
    if not HAS_PARAMIKO:
        return False, "paramiko library not available"

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)

        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        output = stdout.read().decode('utf-8', errors='ignore')
        client.close()
        return True, output
    except Exception as e:
        return False, str(e)


def parse_ike_errors(output: str) -> Dict[str, int]:
    """Parse 'diagnose vpn ike errors' output into counter dict."""
    counters = {}
    for line in output.splitlines():
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            parts = line.split(':')
            if len(parts) >= 2:
                key = parts[0].strip().replace('.', '_').replace('-', '_')
                try:
                    # Handle "mem.fail: 0 0 0" format
                    val = parts[1].strip().split()[0]
                    counters[key] = int(val)
                except (ValueError, IndexError):
                    pass
    return counters


def parse_tunnel_list(output: str, tunnel_name: str) -> Dict[str, Any]:
    """Parse 'diagnose vpn tunnel list name <tunnel>' output."""
    result = {
        'found': False,
        'npu_flag': None,
        'inbound_spi': None,
        'outbound_spi': None,
        'enc_packets': 0,
        'dec_packets': 0,
        'sa_count': 0,
        'remote_gw': None,
        'interface': None,
    }

    if tunnel_name.lower() not in output.lower():
        return result

    result['found'] = True

    # Extract npu_flag
    npu_match = re.search(r'npu_flag=(\d+)', output)
    if npu_match:
        result['npu_flag'] = npu_match.group(1).zfill(2)

    # Extract SPIs
    spi_in = re.search(r'inbound.*spi[:\s]+([0-9a-fA-F]+)', output, re.IGNORECASE)
    spi_out = re.search(r'outbound.*spi[:\s]+([0-9a-fA-F]+)', output, re.IGNORECASE)
    if spi_in:
        result['inbound_spi'] = spi_in.group(1)
    if spi_out:
        result['outbound_spi'] = spi_out.group(1)

    # Extract packet counters
    enc_match = re.search(r'enc[:\s]+(\d+)', output, re.IGNORECASE)
    dec_match = re.search(r'dec[:\s]+(\d+)', output, re.IGNORECASE)
    if enc_match:
        result['enc_packets'] = int(enc_match.group(1))
    if dec_match:
        result['dec_packets'] = int(dec_match.group(1))

    # Extract SA count (sa=N)
    sa_match = re.search(r'\bsa[=:](\d+)', output)
    if sa_match:
        result['sa_count'] = int(sa_match.group(1))

    # Extract remote gateway
    rgw_match = re.search(r'remote[_\-]?(?:gw|gateway|addr)[:\s]+(\d+\.\d+\.\d+\.\d+)', output, re.IGNORECASE)
    if rgw_match:
        result['remote_gw'] = rgw_match.group(1)

    return result


def parse_gateway_list(output: str, tunnel_name: str) -> Dict[str, Any]:
    """Parse 'diagnose vpn ike gateway list name <tunnel>' output."""
    result = {
        'found': False,
        'status': 'unknown',
        'phase1_established': False,
        'remote_ip': None,
        'local_ip': None,
        'nat_traversal': False,
    }

    if tunnel_name.lower() not in output.lower():
        return result

    result['found'] = True

    # Check status
    if 'established' in output.lower():
        result['status'] = 'established'
        result['phase1_established'] = True
    elif 'connecting' in output.lower():
        result['status'] = 'connecting'
    elif 'dead' in output.lower():
        result['status'] = 'dead'

    # NAT-T detection
    if 'nat-t' in output.lower() or 'port 4500' in output.lower():
        result['nat_traversal'] = True

    # Extract IPs
    remote_match = re.search(r'remote[:\s]+(\d+\.\d+\.\d+\.\d+)', output, re.IGNORECASE)
    local_match = re.search(r'local[:\s]+(\d+\.\d+\.\d+\.\d+)', output, re.IGNORECASE)
    if remote_match:
        result['remote_ip'] = remote_match.group(1)
    if local_match:
        result['local_ip'] = local_match.group(1)

    return result


def analyze_issues(gateway_info: Dict, tunnel_info: Dict, counters: Dict,
                   thresholds: Dict, delta_counters: Optional[Dict] = None) -> List[Dict]:
    """Analyze collected data and generate issue findings."""
    issues = []

    # Phase1 issues
    if not gateway_info.get('phase1_established'):
        issues.append({
            'category': 'connectivity',
            'severity': 'critical',
            'finding': f"Phase1 not established (status: {gateway_info.get('status', 'unknown')})",
            'remediation': 'Verify PSK, peer IP, proposals match. Check firewall allows UDP 500/4500.'
        })

    # Phase2/SA issues
    if tunnel_info.get('found'):
        sa_count = tunnel_info.get('sa_count', 0)
        if sa_count == 0:
            issues.append({
                'category': 'selector',
                'severity': 'warning',
                'finding': 'No active SA (sa=0)',
                'remediation': 'Verify proxy-id/selector match on both sides. Initiate interesting traffic.'
            })

        # One-way traffic
        enc = tunnel_info.get('enc_packets', 0)
        dec = tunnel_info.get('dec_packets', 0)
        if enc > 100 and dec == 0:
            issues.append({
                'category': 'traffic',
                'severity': 'critical',
                'finding': f'One-way traffic detected (enc={enc}, dec={dec})',
                'remediation': 'Remote peer not sending return traffic. Check remote config, routing, firewall.'
            })

        # NPU offload
        npu_flag = tunnel_info.get('npu_flag')
        if npu_flag and npu_flag != '03':
            npu_desc = {
                '00': 'No offload (ingress+egress in kernel)',
                '01': 'Egress only offloaded',
                '02': 'Ingress only offloaded',
            }.get(npu_flag, f'Partial offload ({npu_flag})')
            issues.append({
                'category': 'performance',
                'severity': 'warning',
                'finding': f'NPU offload incomplete: npu_flag={npu_flag} - {npu_desc}',
                'remediation': 'Verify NPU config, interface binding. Check: diag npu np6 port-list'
            })

    # Counter-based issues (use delta if available, otherwise absolute)
    check_counters = delta_counters if delta_counters else counters
    counter_checks = [
        ('dpd_fail_old_hit', 'DPD probe timestamp too old - FGT under heavy CPU load'),
        ('dpd_fail_old_ignore', 'DPD probes ignored due to load'),
        ('isakmp_timeout_initiator', 'Phase1 initiator timeouts'),
        ('isakmp_timeout_responder', 'Phase1 responder timeouts'),
        ('isakmp_retrans_send', 'IKE retransmissions - peer not responding'),
        ('quick_retrans_send', 'Phase2 retransmissions'),
        ('out_fail', 'Outbound packet failures'),
    ]

    for counter_key, description in counter_checks:
        value = check_counters.get(counter_key, 0)
        threshold = thresholds.get(counter_key, DEFAULT_THRESHOLDS.get(counter_key, 100))
        if value > threshold:
            severity = 'critical' if value > threshold * 10 else 'warning'
            issues.append({
                'category': 'counter',
                'severity': severity,
                'finding': f'{counter_key}={value} (threshold: {threshold}) - {description}',
                'remediation': 'Review IKE debug logs, check peer health, verify network path.'
            })

    return issues


def build_capture_command(tunnel_info: Dict, gateway_info: Dict, capture_type: str,
                          count: int, interface: str = 'any') -> str:
    """Build appropriate sniffer command based on tunnel characteristics."""
    peer_ip = gateway_info.get('remote_ip') or tunnel_info.get('remote_gw')
    nat_t = gateway_info.get('nat_traversal', False)
    spi_in = tunnel_info.get('inbound_spi', '')
    spi_out = tunnel_info.get('outbound_spi', '')

    if not peer_ip:
        return f'diagnose sniffer packet {interface} "udp port 500 or udp port 4500" 6 {count} l'

    if capture_type == 'ike':
        if nat_t:
            return f'diagnose sniffer packet {interface} "host {peer_ip} and (udp port 500 or (udp port 4500 and udp[8:4]==0x00000000))" 6 {count} l'
        else:
            return f'diagnose sniffer packet {interface} "host {peer_ip} and udp port 500" 6 {count} l'
    else:  # esp
        if nat_t and spi_in and spi_out:
            return f'diagnose sniffer packet {interface} "host {peer_ip} and udp port 4500 and (udp[8:4]==0x{spi_in} or udp[8:4]==0x{spi_out})" 6 {count} l'
        elif spi_in and spi_out:
            return f'diagnose sniffer packet {interface} "host {peer_ip} and esp and (ip[20:4]==0x{spi_in} or ip[20:4]==0x{spi_out})" 6 {count} l'
        else:
            if nat_t:
                return f'diagnose sniffer packet {interface} "host {peer_ip} and udp port 4500" 6 {count} l'
            return f'diagnose sniffer packet {interface} "host {peer_ip} and esp" 6 {count} l'


def analyze_capture(output: str, capture_type: str) -> Dict[str, Any]:
    """Analyze packet capture output."""
    analysis = {
        'packets_captured': 0,
        'findings': [],
        'raw_sample': '',
    }

    # Count packets (lines starting with timestamp or containing packet data)
    packet_lines = [l for l in output.splitlines() if re.match(r'\d+\.\d+\.\d+', l) or 'length' in l.lower()]
    analysis['packets_captured'] = len(packet_lines)

    if analysis['packets_captured'] == 0:
        analysis['findings'].append('No packets captured - tunnel may be idle or filter too restrictive')
        return analysis

    # Sample first few packets
    analysis['raw_sample'] = '\n'.join(output.splitlines()[:20])

    if capture_type == 'ike':
        # Look for IKE patterns
        if 'isakmp' in output.lower() or 'port 500' in output.lower():
            analysis['findings'].append('IKE traffic detected')
        if 'notify' in output.lower():
            analysis['findings'].append('IKE NOTIFY messages present - may indicate errors')
        if '4500' in output:
            analysis['findings'].append('NAT-T traffic on port 4500 detected')
    else:
        # ESP analysis
        spis = re.findall(r'spi[:\s]*(?:0x)?([0-9a-fA-F]+)', output, re.IGNORECASE)
        if spis:
            unique_spis = list(set(spis))
            analysis['spis_seen'] = unique_spis
            if len(unique_spis) >= 2:
                analysis['findings'].append(f'Bidirectional traffic: {len(unique_spis)} unique SPIs')
            else:
                analysis['findings'].append(f'Unidirectional traffic: only {len(unique_spis)} SPI(s)')

    return analysis


def run_diagnose(ssh_func, tunnel_name: str, thresholds: Dict) -> Dict[str, Any]:
    """Run diagnostic mode - read-only analysis."""
    result = {
        'action': 'diagnose',
        'phase1': {},
        'phase2': {},
        'counters': {},
        'issues': [],
    }

    # Get gateway info (Phase1)
    ok, output = ssh_func(f'diagnose vpn ike gateway list name {tunnel_name}')
    if ok:
        result['phase1'] = parse_gateway_list(output, tunnel_name)
        result['phase1']['raw'] = output[:500]

    # Get tunnel info (Phase2)
    ok, output = ssh_func(f'diagnose vpn tunnel list name {tunnel_name}')
    if ok:
        result['phase2'] = parse_tunnel_list(output, tunnel_name)
        result['phase2']['raw'] = output[:500]

    # Get error counters
    ok, output = ssh_func('diagnose vpn ike errors')
    if ok:
        result['counters'] = parse_ike_errors(output)

    # Analyze
    result['issues'] = analyze_issues(
        result['phase1'], result['phase2'], result['counters'], thresholds
    )

    return result


def run_delta(ssh_func, tunnel_name: str, thresholds: Dict, wait_seconds: int = 60) -> Dict[str, Any]:
    """Run delta mode - compare counters over time."""
    result = {
        'action': 'delta',
        'wait_seconds': wait_seconds,
        'counters_before': {},
        'counters_after': {},
        'delta': {},
        'issues': [],
    }

    # First sample
    ok, output = ssh_func('diagnose vpn ike errors')
    if ok:
        result['counters_before'] = parse_ike_errors(output)

    # Wait
    time.sleep(wait_seconds)

    # Second sample
    ok, output = ssh_func('diagnose vpn ike errors')
    if ok:
        result['counters_after'] = parse_ike_errors(output)

    # Calculate delta
    for key in result['counters_after']:
        before = result['counters_before'].get(key, 0)
        after = result['counters_after'].get(key, 0)
        if after > before:
            result['delta'][key] = after - before

    # Also get current tunnel state
    diagnose_result = run_diagnose(ssh_func, tunnel_name, thresholds)
    result['phase1'] = diagnose_result['phase1']
    result['phase2'] = diagnose_result['phase2']

    # Analyze with delta
    result['issues'] = analyze_issues(
        result['phase1'], result['phase2'], result['counters_after'],
        thresholds, delta_counters=result['delta']
    )

    return result


def run_capture(ssh_func, tunnel_name: str, capture_type: str,
                count: int, timeout: int, thresholds: Dict) -> Dict[str, Any]:
    """Run capture mode - packet capture and analysis."""
    result = {
        'action': 'capture',
        'capture_type': capture_type,
        'capture_count': count,
        'capture_analysis': {},
        'issues': [],
    }

    # First get tunnel info to build proper filter
    diagnose_result = run_diagnose(ssh_func, tunnel_name, thresholds)
    result['phase1'] = diagnose_result['phase1']
    result['phase2'] = diagnose_result['phase2']
    result['issues'] = diagnose_result['issues']

    # Build capture command
    capture_cmd = build_capture_command(
        result['phase2'], result['phase1'], capture_type, count
    )
    result['capture_command'] = capture_cmd

    # Run capture (with extended timeout)
    ok, output = ssh_func(capture_cmd)
    if ok:
        result['capture_analysis'] = analyze_capture(output, capture_type)
    else:
        result['capture_analysis'] = {'error': output}

    return result


def main(context) -> Dict[str, Any]:
    """Main entry point."""
    params = context.parameters if hasattr(context, 'parameters') else context

    target_ip = params.get('target_ip')
    tunnel_name = params.get('tunnel_name')
    action = params.get('action', 'diagnose').lower()
    capture_type = params.get('capture_type', 'ike')
    capture_count = min(params.get('capture_count', 10), 50)
    capture_timeout = params.get('capture_timeout', 30)
    thresholds = {**DEFAULT_THRESHOLDS, **params.get('thresholds', {})}
    verify_ssl = params.get('verify_ssl', False)

    if not target_ip:
        return {'success': False, 'error': 'target_ip required'}
    if not tunnel_name:
        return {'success': False, 'error': 'tunnel_name required'}

    # Load credentials
    creds = load_credentials(target_ip)
    if not creds:
        return {'success': False, 'error': f'No credentials for {target_ip}'}

    # Need SSH credentials
    ssh_user = creds.get('ssh_username') or creds.get('username')
    ssh_pass = creds.get('ssh_password') or creds.get('password')
    if not ssh_user or not ssh_pass:
        return {'success': False, 'error': 'SSH credentials (ssh_username/ssh_password) required'}

    # Create SSH helper
    def ssh_func(cmd: str, timeout: int = 30) -> Tuple[bool, str]:
        return ssh_command(target_ip, ssh_user, ssh_pass, cmd, timeout)

    # Build result
    result = {
        'success': True,
        'tunnel_name': tunnel_name,
        'target_ip': target_ip,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'health': 'unknown',
    }

    try:
        if action == 'diagnose':
            action_result = run_diagnose(ssh_func, tunnel_name, thresholds)
        elif action == 'delta':
            action_result = run_delta(ssh_func, tunnel_name, thresholds, wait_seconds=60)
        elif action == 'capture':
            # Extend SSH timeout for capture
            def ssh_func_capture(cmd: str, timeout: int = capture_timeout + 10) -> Tuple[bool, str]:
                return ssh_command(target_ip, ssh_user, ssh_pass, cmd, timeout)
            action_result = run_capture(ssh_func_capture, tunnel_name, capture_type,
                                        capture_count, capture_timeout, thresholds)
        else:
            return {'success': False, 'error': f'Unknown action: {action}'}

        result.update(action_result)

        # Determine overall health
        issues = result.get('issues', [])
        if any(i['severity'] == 'critical' for i in issues):
            result['health'] = 'critical'
        elif any(i['severity'] == 'warning' for i in issues):
            result['health'] = 'degraded'
        elif result.get('phase1', {}).get('phase1_established'):
            result['health'] = 'healthy'

        # Add recommended commands
        phase1 = result.get('phase1', {})
        phase2 = result.get('phase2', {})
        result['recommended_commands'] = {
            'ike_debug': f'diagnose vpn ike log filter name {tunnel_name}; diagnose debug app ike -1; diagnose debug enable',
            'capture_ike': build_capture_command(phase2, phase1, 'ike', 10),
            'capture_esp': build_capture_command(phase2, phase1, 'esp', 10),
            'flush_tunnel': f'diagnose vpn tunnel flush {tunnel_name}',
        }

    except Exception as e:
        result['success'] = False
        result['error'] = str(e)

    return result


if __name__ == "__main__":
    params = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            k, v = arg.split('=', 1)
            k = k.lstrip('-')
            if v.isdigit():
                params[k] = int(v)
            elif v.lower() in ['true', 'false']:
                params[k] = v.lower() == 'true'
            else:
                params[k] = v

    if params:
        print(json.dumps(main(params), indent=2, default=str))
    else:
        print(json.dumps(main(json.loads(sys.stdin.read() or "{}")), indent=2, default=str))
