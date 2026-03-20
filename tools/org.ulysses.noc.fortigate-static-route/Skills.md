# FortiGate Static Route
## Purpose
Manage static routes. Essential for SD-WAN health check routes.

## Example: Add health check route
```json
{"canonical_id": "org.ulysses.noc.fortigate-static-route/1.0.0", "parameters": {"target_ip": "192.168.209.35", "action": "add", "dst": "172.16.255.253/32", "device": "HUB1-VPN1"}}
```
