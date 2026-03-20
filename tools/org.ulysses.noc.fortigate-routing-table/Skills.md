# FortiGate Routing Table Skills

## Purpose

View the IPv4 routing table on a FortiGate device. This is essential for:
- Verifying routes exist to destination networks
- Troubleshooting "destination unreachable" issues
- Understanding traffic flow paths
- Checking static vs dynamic route configuration
- Validating VPN tunnel routes

## When to Use This Tool

**Use this tool when the user asks:**
- "Show me the routing table"
- "Does the firewall have a route to X?"
- "What's the next hop for 10.0.0.0?"
- "How does traffic get to the internet?"
- "Which interface does traffic to X go out?"
- "Are there any static routes configured?"
- "Show me VPN/tunnel routes"
- "Why can't I reach network X?" (after verifying health)

**Do NOT use this tool for:**
- Checking current traffic sessions (use fortigate-session-table)
- Modifying routing configuration
- BGP/OSPF neighbor status (different API)
- Interface status (use fortigate-interface-status)
- ARP resolution issues (use fortigate-arp-table)

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate management IP address |
| `filter_destination` | string | No | - | Filter routes matching this IP |
| `filter_type` | string | No | all | Route type: static, connect, ospf, bgp, rip, all |
| `filter_interface` | string | No | - | Filter by outgoing interface |
| `timeout` | integer | No | 30 | Request timeout in seconds |

## Troubleshooting Workflow

### Step 1: Verify Connectivity Path
When user reports "can't reach X", check routing:
```
fortigate-routing-table(filter_destination="X.X.X.X")
```
This shows which routes would match traffic to that destination.

### Step 2: Check Default Route
Verify internet access path:
```
fortigate-routing-table(filter_destination="8.8.8.8")
```
Should return the default route (0.0.0.0/0).

### Step 3: Check Specific Route Types
```
fortigate-routing-table(filter_type="static")  # Manual routes
fortigate-routing-table(filter_type="connect")  # Directly connected
```

## Interpreting Results

### Route Types

| Type | Meaning | Distance |
|------|---------|----------|
| `connect` | Directly connected network | 0 |
| `static` | Manually configured route | 10 (default) |
| `ospf` | OSPF learned route | 110 |
| `bgp` | BGP learned route | 20 (eBGP) / 200 (iBGP) |
| `rip` | RIP learned route | 120 |

### Administrative Distance
Lower distance = more preferred route. When multiple routes exist:
- Distance 0: Directly connected (most preferred)
- Distance 10: Static routes
- Distance 20-200: Dynamic routing protocols

### Gateway Values
| Gateway | Meaning |
|---------|---------|
| `0.0.0.0` | Directly connected (no next hop needed) |
| IP address | Next hop router to forward traffic to |

### Common Issues to Watch For

1. **Missing default route** - No internet access
2. **Wrong next hop** - Traffic going to wrong router
3. **Missing tunnel routes** - VPN tunnel down or not established
4. **Overlapping routes** - More specific route overriding intended path
5. **Asymmetric routing** - Different paths in/out can break stateful inspection

## Example Usage

### View All Routes
```json
{
    "target_ip": "192.168.1.1"
}
```

### Find Route for Specific IP
```json
{
    "target_ip": "192.168.1.1",
    "filter_destination": "10.50.25.100"
}
```

### View Only Static Routes
```json
{
    "target_ip": "192.168.1.1",
    "filter_type": "static"
}
```

### View Routes Through Specific Interface
```json
{
    "target_ip": "192.168.1.1",
    "filter_interface": "wan1"
}
```

## Sample Response

```json
{
    "success": true,
    "target_ip": "192.168.209.62",
    "total_routes": 20,
    "returned_count": 4,
    "routes": [
        {
            "destination": "0.0.0.0/0",
            "gateway": "66.110.253.1",
            "interface": "wan1",
            "type": "static",
            "distance": 10,
            "metric": 0,
            "priority": 1,
            "is_tunnel": false
        },
        {
            "destination": "10.0.0.0/8",
            "gateway": "192.168.209.71",
            "interface": "internal",
            "type": "static",
            "distance": 10,
            "metric": 0,
            "priority": 1,
            "is_tunnel": false
        },
        {
            "destination": "192.168.209.0/24",
            "gateway": "0.0.0.0",
            "interface": "internal",
            "type": "connect",
            "distance": 0,
            "metric": 0,
            "priority": 0,
            "is_tunnel": false
        }
    ]
}
```

**Interpretation:**
"The FortiGate has 20 routes total. The default route (0.0.0.0/0) sends internet traffic via gateway 66.110.253.1 out wan1. Traffic to 10.0.0.0/8 is routed via 192.168.209.71 on the internal interface. The 192.168.209.0/24 network is directly connected."

### Key Fields for NOC Analysis

| Field | NOC Use |
|-------|---------|
| `destination` | Target network in CIDR |
| `gateway` | Next hop (0.0.0.0 = connected) |
| `interface` | Egress interface |
| `type` | How route was learned |
| `distance` | Route preference (lower = preferred) |
| `is_tunnel` | VPN/tunnel route indicator |

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
- `org.ulysses.noc.fortigate-arp-table/1.0.0` - View ARP cache
- `org.ulysses.noc.fortigate-interface-status/1.0.0` - Check interface status
