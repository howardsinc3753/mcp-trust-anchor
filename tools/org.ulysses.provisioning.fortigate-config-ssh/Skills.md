# FortiGate Config SSH Skills

## Overview

Execute configuration commands on FortiGate via SSH with password authentication.
Write-capable tool for initial device provisioning before API credentials exist.

## When to Use

- Initial device setup and configuration
- When API credentials don't exist yet
- Emergency configuration changes
- Network troubleshooting on new devices

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_ip` | string | Yes | - | FortiGate IP |
| `commands` | array | Yes | - | List of CLI commands |
| `admin_password` | string | No | `FG@dm!n2026!` | Admin password |
| `admin_user` | string | No | `admin` | Admin username |

## Example Usage

```python
execute_certified_tool(
    canonical_id="org.ulysses.provisioning.fortigate-config-ssh/1.0.0",
    parameters={
        "target_ip": "192.168.209.45",
        "commands": [
            "config system dns",
            "set primary 8.8.8.8",
            "set secondary 8.8.4.4",
            "end",
            "execute ping google.com"
        ]
    }
)
```
