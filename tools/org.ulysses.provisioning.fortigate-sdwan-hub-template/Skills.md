# FortiGate SD-WAN Hub Template - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.provisioning.fortigate-sdwan-hub-template/1.0.0`
- **Domain:** provisioning
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Case
Provision a FortiGate as an SD-WAN hub to accept spoke VPN connections.

### What It Creates
1. **Loopback Interface** - For health checks and BGP peering
2. **IPsec Phase1** - Dynamic mode tunnel (accepts spoke connections)
3. **IPsec Phase2** - Quick mode config
4. **SD-WAN Zone** - Overlay zone for traffic steering
5. **SD-WAN Member** - Tunnel assigned to zone
6. **Firewall Address** - Loopback subnet object
7. **Firewall Policy** - Loopback ↔ SD-WAN zone

### Hub vs Spoke Differences
| Setting | Hub | Spoke |
|---------|-----|-------|
| IPsec Mode | dynamic (accepts connections) | static (initiates to hub) |
| remote-gw | Not set (any) | Hub's WAN IP |
| Loopback | Hub range (e.g., 172.16.255.x) | Spoke range (e.g., 172.16.0.x) |

## Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| target_ip | Hub FortiGate management IP | 192.168.215.15 |
| loopback_ip | Hub loopback with mask | "172.16.255.253 255.255.255.255" |
| psk | Pre-shared key | "secretkey123" |

## Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| loopback_name | Hub_Lo | Loopback interface name |
| tunnel_name | SPOKE_VPN1 | IPsec tunnel name (spokes connect here) |
| wan_interface | auto-detect | WAN port for tunnel binding |
| sdwan_zone | SDWAN_OVERLAY | Zone name |
| network_id | 1 | Overlay network ID (must match spoke) |

**Note:** FortiOS does not allow hyphens in some object names. Use underscores instead.

## Auto-Configured Settings (from Fortinet 4D-Demo)

This tool automatically configures the following settings based on best practices:

| Setting | Value | Purpose |
|---------|-------|---------|
| `location-id` | Loopback IP | SD-WAN device identification |
| `exchange-ip-addr4` | Loopback IP | SD-WAN overlay routing |
| `auto-discovery-sender` | enable | Hub sends ADVPN shortcuts to spokes |
| `dhgrp` | 20 21 | Modern DH groups for security |
| `transport` | auto | Flexible transport for hub |
| `net-device` | disable | Required for dynamic tunnels with SD-WAN |
| `priority` | 10 | SD-WAN member base priority |
| `priority-in-sla` | 10 | Priority when SLA met |
| `priority-out-sla` | 20 | Priority when SLA not met |

## Example Usage

```json
{
  "target_ip": "192.168.215.15",
  "loopback_ip": "172.16.255.253 255.255.255.255",
  "psk": "fortinet123",
  "tunnel_name": "SPOKE_VPN1",
  "sdwan_zone": "SDWAN_OVERLAY"
}
```

## Output

```json
{
  "success": true,
  "components_created": [
    "loopback:Hub_Lo",
    "phase1:SPOKE_VPN1",
    "phase2:SPOKE_VPN1",
    "sdwan:enabled",
    "zone:SDWAN_OVERLAY",
    "member:SPOKE_VPN1->SDWAN_OVERLAY",
    "address:SDWAN_Loopbacks",
    "policy:SDWAN_Overlay_Traffic"
  ],
  "config_summary": {
    "loopback": "Hub_Lo (172.16.255.253 255.255.255.255)",
    "tunnel": "SPOKE_VPN1 (dynamic - accepts spokes)",
    "wan_interface": "wan1",
    "sdwan_zone": "SDWAN_OVERLAY",
    "network_id": 1
  }
}
```

## Topology

```
[Spoke 1: 192.168.209.30]              [Spoke 2: 10.x.x.x]
    └── wan ───IPsec────►          ◄────IPsec─── wan ──┘
                     ╲                    ╱
                      ╲                  ╱
                       ▼                ▼
                    [Hub: 192.168.215.15]
                    └── wan1 (listens)
                    └── Hub_Lo (172.16.255.253)
                              │
                        SD-WAN Zone: SDWAN_OVERLAY
                              │
                    Accepts spoke connections
```

## Network ID Matching

The `network_id` parameter **must match** between hub and spoke:
- Hub: `network_id: 1` for SPOKE_VPN1 tunnel
- Spoke: `network_id: 1` for HUB1_VPN1 tunnel

Multiple overlays can use different network IDs (e.g., VPN2 uses network_id: 2).

## Prerequisites

### Credential Check (CRITICAL)
Before using this tool, verify credentials are configured:

1. **Check for existing credentials:**
   - Primary path: `~/.config/mcp/fortigate_credentials.yaml`
   - Windows secondary: `~/AppData/Local/mcp/fortigate_credentials.yaml`
   - System-wide: `C:/ProgramData/mcp/fortigate_credentials.yaml`

2. **If no credentials exist:**
   Use `fortigate-credential-manager` to register the device first:
   ```
   fortigate-credential-manager action=register target_ip=192.168.215.15
   ```

3. **Verify credential access:**
   Use `fortigate-health-check` to confirm connectivity before provisioning.

## PSK Configuration (CRITICAL)

### PSK Best Practices
| Guideline | Reason |
|-----------|--------|
| Use identical PSK on Hub and Spoke | Mismatched PSK = tunnel won't establish |
| Keep PSK simple during initial setup | Complex PSKs can have encoding issues |
| Test with simple PSK first (e.g., "password") | Eliminates PSK as variable during troubleshooting |
| Change to strong PSK after tunnel verified | Production security |

### PSK Troubleshooting
If tunnel won't establish and config looks correct:
1. Simplify PSK to something basic (e.g., "password")
2. Apply identical PSK on both hub AND spoke
3. Bring tunnel up - if it works, original PSK had issues
4. Then change to production-strength PSK

## Critical Technical Details

### net-device Setting (CRITICAL FOR SD-WAN)
This tool correctly sets `net-device: disable` for hub (dynamic) tunnels.

| Tunnel Type | net-device | Why |
|-------------|------------|-----|
| Dynamic (Hub) | `disable` | Required for SD-WAN member addition |
| Static (Spoke) | `enable` | Standard for initiating tunnels |

**WARNING:** If `net-device enable` is set on a dynamic tunnel, you will get:
```
"entry not found in datasource"
```
when trying to add the tunnel as an SD-WAN member.

### Firewall Policy Requirement
Tunnels will NOT negotiate until they are referenced in a firewall policy.
This tool creates the required policy automatically.

## Troubleshooting

### Tunnel Won't Come Up
1. **Check PSK** - Must be identical on hub and spoke
2. **Check Firewall Policy** - Tunnel must be in a policy or SD-WAN zone that's in a policy
3. **Check WAN Connectivity** - Spoke must reach hub's WAN IP
4. **Check Phase1 Settings** - IKE version, proposals must match

### Can't Add Tunnel to SD-WAN Zone
1. **Check net-device** - Must be `disable` for dynamic tunnels
2. Fix via CLI: `config vpn ipsec phase1-interface` → `edit <tunnel>` → `unset net-device`

### SD-WAN Member Source IP Error
If you get IP validation error when adding member:
- Use `source: "0.0.0.0"` for new tunnels
- Only set specific source IP if interface already has that IP

## Adding Additional Tunnels

To add a second VPN tunnel to an existing hub (e.g., VPN2 for redundancy):

**Use `fortigate-ipsec-tunnel-create` instead of this template:**
```json
{
  "target_ip": "192.168.215.15",
  "tunnel_name": "SPOKE_VPN2",
  "tunnel_type": "dynamic",
  "interface": "wan1",
  "psk": "password",
  "network_id": 2
}
```

The separate tool is preferred because:
- This template creates full SD-WAN infrastructure (loopback, zone, policy)
- For additional tunnels, you only need Phase1 + Phase2
- `fortigate-ipsec-tunnel-create` handles net-device automatically

## Related Tools
- `fortigate-sdwan-spoke-template` - Configure spoke side
- `fortigate-ipsec-tunnel-create` - Add individual tunnels to existing setup
- `fortigate-credential-manager` - Register device credentials
- `fortigate-set-hostname` - Set device name first
- `fortigate-health-check` - Verify device status
