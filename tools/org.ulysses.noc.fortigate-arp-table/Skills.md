# FortiGate ARP Table Skills

## Purpose

View the ARP (Address Resolution Protocol) cache on a FortiGate device. This is essential for:
- Verifying MAC address resolution for IPs
- Troubleshooting Layer 2 connectivity issues
- Identifying devices on the network by MAC address
- Detecting IP conflicts or duplicate MACs
- Finding rogue or unknown devices

## When to Use This Tool

**Use this tool when the user asks:**
- "Show me the ARP table"
- "What's the MAC address for IP X?"
- "What devices are on the internal interface?"
- "Is 192.168.1.50 in the ARP cache?"
- "Find devices with MAC starting with XX:XX"
- "Can the firewall see host X on Layer 2?"
- "Are there any IP conflicts?"
- "What MAC does the gateway have?"

**Do NOT use this tool for:**
- Routing issues (use fortigate-routing-table)
- Session/connection info (use fortigate-session-table)
- Interface status (use fortigate-interface-status)
- DHCP leases (different API)
- Modifying ARP entries

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `filter_ip` | string | No | - | Filter entries containing this IP |
| `filter_mac` | string | No | - | Filter entries containing this MAC |
| `filter_interface` | string | No | - | Filter by interface name |
| `timeout` | integer | No | 30 | Request timeout in seconds |

## Troubleshooting Workflow

### Step 1: Check if Host is Reachable at Layer 2
```
fortigate-arp-table(filter_ip="192.168.1.50")
```
If no entry exists, the firewall hasn't seen this IP on any interface.

### Step 2: Find All Devices on an Interface
```
fortigate-arp-table(filter_interface="internal")
```
Shows all learned MAC addresses on the internal network.

### Step 3: Identify a Device by MAC
```
fortigate-arp-table(filter_mac="00:11:22")
```
Find the IP(s) associated with a specific vendor/device.

## Interpreting Results

### ARP Entry Age

| Age | Meaning |
|-----|---------|
| 0-60 seconds | Recently active, currently communicating |
| 60-300 seconds | Recently seen, may still be reachable |
| 300+ seconds | Stale entry, host may be offline |

### Common MAC Address Prefixes (OUI)

| Prefix | Vendor |
|--------|--------|
| 00:00:5E | IANA (VRRP/HSRP virtual MACs) |
| 00:0C:29 | VMware |
| 00:50:56 | VMware |
| 52:54:00 | QEMU/KVM |
| 00:1A:2B | Cisco |
| 94:18:82 | Dell |
| 04:D5:90 | Fortinet |

### Red Flags to Watch For

1. **Multiple IPs with same MAC** - Could be normal (multiple IPs on one host) or IP conflict
2. **Same IP with different MACs** - IP conflict or ARP spoofing
3. **Age = 0 for many entries** - Active network or scan in progress
4. **Unexpected MACs on interface** - Rogue device or misconfigured VLAN
5. **Missing gateway ARP entry** - Layer 2 connectivity issue to gateway

## Example Usage

### View All ARP Entries
```json
{
    "target_ip": "192.168.1.1"
}
```

### Find Specific Host
```json
{
    "target_ip": "192.168.1.1",
    "filter_ip": "192.168.1.50"
}
```

### Find by MAC Address
```json
{
    "target_ip": "192.168.1.1",
    "filter_mac": "00:0C:29"
}
```

### Show Devices on Internal Interface
```json
{
    "target_ip": "192.168.1.1",
    "filter_interface": "internal"
}
```

## Sample Response

```json
{
    "success": true,
    "target_ip": "192.168.209.62",
    "total_entries": 14,
    "returned_count": 14,
    "entries": [
        {
            "ip": "66.110.253.1",
            "mac": "00:20:03:00:00:01",
            "interface": "wan1",
            "age": 0
        },
        {
            "ip": "192.168.209.105",
            "mac": "04:0E:3C:3A:8B:22",
            "interface": "internal",
            "age": 0
        },
        {
            "ip": "192.168.209.115",
            "mac": "94:18:82:82:E7:04",
            "interface": "internal",
            "age": 47
        },
        {
            "ip": "192.168.215.9",
            "mac": "5C:62:8B:40:57:51",
            "interface": "_default",
            "age": 1
        }
    ]
}
```

**Interpretation:**
"The FortiGate has 14 ARP entries. The gateway (66.110.253.1) has MAC 00:20:03:00:00:01 on wan1 and is actively communicating (age=0). Host 192.168.209.115 (Dell server based on MAC 94:18:82) was last seen 47 seconds ago on the internal interface."

### Key Fields for NOC Analysis

| Field | NOC Use |
|-------|---------|
| `ip` | IP address of device |
| `mac` | MAC address (use first 3 octets to identify vendor) |
| `interface` | Where device is connected |
| `age` | How recently device communicated (lower = more active) |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `target_ip is required` | Missing parameter | Provide FortiGate IP |
| `No API credentials found` | Missing config | Add device to ~/.config/mcp/fortigate_credentials.yaml |
| `Connection failed` | Network issue | Check network path to FortiGate |
| `HTTP 401 Unauthorized` | Invalid token | Verify API token permissions |

## Related Tools

- `org.ulysses.noc.fortigate-health-check/1.0.0` - Check device health FIRST
- `org.ulysses.noc.fortigate-session-table/1.0.0` - View active sessions
- `org.ulysses.noc.fortigate-routing-table/1.0.0` - View routing table
- `org.ulysses.noc.fortigate-interface-status/1.0.0` - Check interface status
