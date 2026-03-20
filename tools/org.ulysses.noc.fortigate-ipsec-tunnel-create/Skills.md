# FortiGate IPsec Tunnel Create - Skills Guide

## Purpose
Creates a **SINGLE IPsec tunnel** (Phase1 + Phase2) on a FortiGate device.
This tool is for adding tunnels to **existing** configurations, NOT for initial SD-WAN setup.

## When to Use This Tool

| Scenario | Use This Tool? | Alternative |
|----------|---------------|-------------|
| Add 2nd/3rd tunnel to existing SD-WAN | **YES** | - |
| Create tunnel for non-SD-WAN VPN | **YES** | - |
| Initial SD-WAN hub setup | NO | `fortigate-sdwan-hub-template` |
| Initial SD-WAN spoke setup | NO | `fortigate-sdwan-spoke-template` |
| Full SD-WAN topology with BGP | NO | `fortigate-single-hub-bgp-sdwan` |

## CRITICAL Prerequisites

### 1. Credentials MUST Exist First
Before using this tool, verify credentials exist for the target device:

```
Tool: fortigate-health-check
Parameters: {"target_ip": "192.168.x.x"}
```

**If credentials error:** Use `credential-manager` or `fortigate-device-register` first.

### 2. Matching PSK on Both Ends
The PSK (Pre-Shared Key) **MUST be identical** on Hub and Spoke.
- Keep PSK simple during testing (e.g., `password`)
- Complex PSKs can cause encoding issues via API

### 3. Unique network-id Per Tunnel
**CRITICAL FOR SD-WAN:** Each tunnel MUST have a unique `network_id` (1-255).

| Tunnel | network_id |
|--------|-----------|
| First tunnel (VPN1) | 1 |
| Second tunnel (VPN2) | 2 |
| Third tunnel (VPN3) | 3 |

**Failure to use unique network-id causes SD-WAN routing conflicts!**

## Tunnel Types - CRITICAL DIFFERENCE

### Static Tunnel (Spoke/Initiator)
- **Use when:** Device initiates connection TO a hub
- **Settings:**
  - `tunnel_type: "static"`
  - `remote_gw`: Hub's WAN IP address (required)
  - `net_device: "enable"` (auto-set by tool)
  - `localid`: Set to help hub identify this spoke

### Dynamic Tunnel (Hub/Responder)
- **Use when:** Device accepts connections FROM spokes
- **Settings:**
  - `tunnel_type: "dynamic"`
  - `remote_gw`: Not used (accepts any)
  - `net_device: "disable"` (auto-set by tool) **← CRITICAL!**
  - `peertype: "any"`

### Why net-device Matters

| Setting | Tunnel Type | Behavior |
|---------|------------|----------|
| `net-device enable` | Static (Spoke) | Interface created immediately, can be used |
| `net-device disable` | Dynamic (Hub) | Interface exists immediately for SD-WAN |
| `net-device enable` | Dynamic (Hub) | **BREAKS SD-WAN!** Interface not in datasource |

**Issue #3 from testing:** `net-device enable` on Hub dynamic tunnel caused:
- Error: `entry not found in datasource`
- Could not add tunnel to SD-WAN zone
- **Solution:** Always use `net-device disable` for dynamic/Hub tunnels

## Workflow for Adding Second Tunnel

### Step 1: Check Existing Tunnel Config
```
# Get current network_id from existing tunnel
GET /api/v2/cmdb/vpn.ipsec/phase1-interface/{existing_tunnel}
```

### Step 2: Create Hub Side First (Dynamic)
```yaml
Tool: fortigate-ipsec-tunnel-create
Parameters:
  target_ip: "192.168.215.15"    # Hub IP
  tunnel_name: "SPOKE_VPN2"      # New tunnel name
  tunnel_type: "dynamic"         # Hub = dynamic
  psk: "password"                # Must match spoke
  network_id: 2                  # UNIQUE - existing uses 1
  interface: "port1"             # WAN interface
  exchange_ip: "172.16.255.253"  # Hub's loopback IP (SD-WAN overlay routing)
  transport: "auto"              # Default for hub
```

### Step 3: Create Spoke Side (Static)
```yaml
Tool: fortigate-ipsec-tunnel-create
Parameters:
  target_ip: "192.168.209.30"    # Spoke IP
  tunnel_name: "HUB2-VPN2"       # New tunnel name
  tunnel_type: "static"          # Spoke = static
  remote_gw: "192.168.215.15"    # Hub WAN IP
  psk: "password"                # Must match hub
  network_id: 2                  # UNIQUE - same as hub side
  interface: "wan"               # WAN interface
  localid: "spoke-HUB2-VPN2"     # Helps hub identify
  exchange_ip: "172.16.0.2"      # Spoke's loopback IP (SD-WAN overlay routing)
  transport: "udp"               # Default for spoke
```

### Step 4: Tunnel Won't Come Up Yet!
**Issue #4:** Tunnel requires firewall policy reference.

Options:
1. Add tunnel to existing SD-WAN zone (recommended)
2. Create firewall policy with tunnel as interface

### Step 5: Add to SD-WAN Zone
For Spoke - update SD-WAN members to include new tunnel:
```
PUT /api/v2/cmdb/system/sdwan
Body: Add new member with unique seq-num (e.g., 101)
```

**Issue #5:** SD-WAN source IP must exist or use "0.0.0.0"

## Common Issues Index

| Issue | Symptom | Cause | Solution |
|-------|---------|-------|----------|
| #1 | No creation tool | Only management tools existed | Use this tool |
| #2 | Tunnel down | PSK mismatch | Use identical simple PSK |
| #3 | Can't add to SD-WAN | `net-device enable` on Hub | Tool auto-sets correctly |
| #4 | Tunnel won't negotiate | No firewall policy | Add to SD-WAN zone |
| #5 | SD-WAN member error | Invalid source IP | Use "0.0.0.0" for new tunnels |
| #6 | Routing conflicts | Duplicate network_id | Use unique ID per tunnel |
| #7 | Hub not accepting | Wrong tunnel type | Hub=dynamic, Spoke=static |

## Parameter Reference

### Required Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `target_ip` | FortiGate management IP | `"192.168.209.30"` |
| `tunnel_name` | Phase1/Phase2 name | `"HUB2-VPN2"` |
| `tunnel_type` | `"static"` or `"dynamic"` | `"static"` |
| `psk` | Pre-shared key | `"password"` |
| `network_id` | Unique overlay ID (1-255) | `2` |

### Conditional Parameters
| Parameter | Required When | Description |
|-----------|--------------|-------------|
| `remote_gw` | `tunnel_type="static"` | Hub's WAN IP |
| `interface` | Always recommended | WAN interface name |
| `localid` | Spoke tunnels | Identifier for hub |

### Optional Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `exchange_ip` | none | Loopback IP for SD-WAN overlay routing (recommended) |
| `transport` | `"udp"` (spoke) / `"auto"` (hub) | Transport mode for IPsec |
| `ike_version` | `2` | IKE version (1 or 2) |
| `proposal` | `"aes256-sha256"` | Encryption proposal |
| `dhgrp` | `"20 21"` | DH groups |
| `dpd` | `"on-idle"` | Dead peer detection |

### New SD-WAN Overlay Parameters (from Fortinet 4D-Demo)
| Parameter | Purpose | When to Use |
|-----------|---------|-------------|
| `exchange_ip` | Sets `exchange-ip-addr4` for SD-WAN overlay routing | When using SD-WAN with loopback IPs |
| `transport` | Sets `transport udp` or `auto` | Always - ensures consistent behavior |
| `auto-discovery-*` | ADVPN shortcut discovery | Auto-enabled by tool |
| `location-id` | SD-WAN device identifier | Set via SD-WAN templates, not this tool |

## Output Schema

```json
{
  "success": true,
  "target_ip": "192.168.209.30",
  "tunnel_name": "HUB2-VPN2",
  "tunnel_type": "static",
  "network_id": 2,
  "phase1_created": true,
  "phase2_created": true,
  "net_device": "enable",
  "message": "IPsec tunnel created. Add to SD-WAN zone or firewall policy to activate.",
  "next_steps": [
    "Add tunnel interface to SD-WAN zone",
    "Or create firewall policy referencing tunnel",
    "Verify PSK matches on peer device"
  ]
}
```

## AI Decision Tree

```
User wants IPsec tunnel
    │
    ├─► New SD-WAN deployment?
    │       YES → Use sdwan-hub-template / sdwan-spoke-template
    │       NO ↓
    │
    ├─► Adding tunnel to existing setup?
    │       YES → Use THIS tool (fortigate-ipsec-tunnel-create)
    │
    ├─► Check credentials exist
    │       NO → Use credential-manager first
    │       YES ↓
    │
    ├─► Determine tunnel type
    │       Hub/Responder → tunnel_type="dynamic"
    │       Spoke/Initiator → tunnel_type="static"
    │
    ├─► Get unique network_id
    │       Check existing tunnels for used IDs
    │       Use next available (1, 2, 3...)
    │
    ├─► Create tunnel with matching PSK on both ends
    │
    └─► Post-creation: Add to SD-WAN zone
```

## FortiOS Version Compatibility
- **Tested:** FortiOS 7.6.5
- **Minimum:** FortiOS 7.0+ (IKEv2 features)
- **API:** REST API with Bearer token authentication
