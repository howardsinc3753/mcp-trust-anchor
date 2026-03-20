# FortiGate IPsec Troubleshoot

## Purpose

In-depth IPsec VPN tunnel troubleshooting for FortiGate devices. Performs comprehensive diagnostics including Phase1/Phase2 status analysis, IKE error counter tracking, NPU offload verification, and optional packet capture with automated analysis.

## When to Use

- **Tunnel Down**: Phase1 won't establish, peer unreachable
- **Intermittent Issues**: Tunnel flaps, packet loss, performance degradation
- **One-Way Traffic**: Traffic flows out but nothing returns
- **Performance Problems**: High latency, ESP not offloaded to NPU
- **Counter Investigation**: DPD failures, IKE retransmissions, timeouts

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_ip | string | Yes | - | FortiGate management IP |
| tunnel_name | string | Yes | - | Phase1 tunnel name |
| action | string | No | diagnose | diagnose, capture, or delta |
| capture_type | string | No | ike | ike or esp |
| capture_count | integer | No | 10 | Packets to capture (max 50) |
| capture_timeout | integer | No | 30 | Capture timeout seconds |

## Actions

### diagnose (default)
Read-only analysis of tunnel health:
- Phase1 status (established/connecting/dead)
- Phase2 SA status (sa=0/1/2)
- NPU offload flag (npu_flag=00/01/02/03)
- IKE error counters
- Traffic counters (enc/dec)

### delta
Compare IKE error counters over 1 minute:
- Takes baseline counter snapshot
- Waits 60 seconds
- Takes second snapshot
- Reports delta (new errors during window)
- Useful for detecting active issues vs historical

### capture
Run limited packet capture (10 packets default):
- Auto-builds appropriate BPF filter based on tunnel config
- Supports NAT-T detection (port 4500 vs 500)
- Filters by SPI for multi-tunnel scenarios
- Returns packet analysis summary

## Example Usage

### Basic Diagnosis
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-ipsec-troubleshoot/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "tunnel_name": "HUB1-VPN1"
  }
}
```

### Delta Counter Analysis
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-ipsec-troubleshoot/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "tunnel_name": "HUB1-VPN1",
    "action": "delta"
  }
}
```

### Capture IKE Negotiation
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-ipsec-troubleshoot/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "tunnel_name": "HUB1-VPN1",
    "action": "capture",
    "capture_type": "ike",
    "capture_count": 20
  }
}
```

### Capture ESP Traffic
```json
{
  "canonical_id": "org.ulysses.noc.fortigate-ipsec-troubleshoot/1.0.0",
  "parameters": {
    "target_ip": "192.168.209.35",
    "tunnel_name": "HUB1-VPN1",
    "action": "capture",
    "capture_type": "esp"
  }
}
```

## Output Interpretation

### Health Status
- **healthy**: Phase1 established, no critical issues
- **degraded**: Tunnel up but warnings present (NPU, counter thresholds)
- **critical**: Phase1 down, one-way traffic, or severe counter issues
- **unknown**: Unable to determine status

### NPU Flag Meanings
| Flag | Meaning | Impact |
|------|---------|--------|
| 00 | No offload | All ESP in kernel - high CPU |
| 01 | Egress only | Ingress in kernel |
| 02 | Ingress only | Egress in kernel |
| 03 | Full offload | Optimal performance |

### SA Status
| Value | Meaning |
|-------|---------|
| sa=0 | No active SA - selector mismatch or no traffic |
| sa=1 | Active SA with traffic |
| sa=2 | SA rekey in progress |

### Key Counters (threshold >100 triggers warning)
| Counter | Indicates |
|---------|-----------|
| dpd.fail.old.hit | CPU under heavy load |
| isakmp.timeout.initiator | Phase1 negotiation failures |
| isakmp.retrans.send | Peer not responding |
| quick.retrans.send | Phase2 issues |

## Credential Requirements

Requires SSH credentials in fortigate_credentials.yaml:
```yaml
devices:
  my-fortigate:
    host: 192.168.209.35
    api_token: "your-api-token"
    ssh_username: "admin"
    ssh_password: "password"
```

## Related Tools

- `fortigate-ipsec` - CRUD for Phase1/Phase2 config
- `fortigate-ipsec-tunnel` - Basic tunnel up/down/status
- `fortigate-health-check` - Overall device health
- `fortigate-sdwan-health` - SD-WAN member status

## CLI Equivalent Commands

The tool executes these commands via SSH:
```
diagnose vpn ike gateway list name <tunnel>
diagnose vpn tunnel list name <tunnel>
diagnose vpn ike errors
diagnose sniffer packet <intf> "<filter>" 6 <count> l
```
