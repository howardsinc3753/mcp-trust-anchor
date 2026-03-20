#!/usr/bin/env python3
"""
FortiGate Config SSH Tool

Execute configuration commands on FortiGate via SSH.
Write-capable tool for provisioning workflows.

Author: Trust-Bot Tool Maker
Version: 1.0.0
Created: 2026-01-25
"""

import json
import logging
import time
from typing import Any, Dict, List

import paramiko

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "FG@dm!n2026!"


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute commands on FortiGate via SSH."""
    target_ip = params.get("target_ip")
    commands = params.get("commands", [])
    admin_user = params.get("admin_user", DEFAULT_ADMIN_USER)
    admin_password = params.get("admin_password", DEFAULT_ADMIN_PASSWORD)

    if not target_ip:
        return {"success": False, "error": "Missing target_ip"}
    if not commands:
        return {"success": False, "error": "Missing commands"}

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            target_ip,
            port=22,
            username=admin_user,
            password=admin_password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )

        shell = client.invoke_shell()
        time.sleep(2)

        # Clear initial output
        while shell.recv_ready():
            shell.recv(4096)

        output = ""
        for cmd in commands:
            logger.info(f"Executing: {cmd}")
            shell.send(cmd + "\n")
            time.sleep(1)

            # Read output
            while shell.recv_ready():
                chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                output += chunk

        # Final read
        time.sleep(2)
        while shell.recv_ready():
            output += shell.recv(4096).decode('utf-8', errors='ignore')

        client.close()

        return {
            "success": True,
            "output": output
        }

    except Exception as e:
        logger.exception(f"Error: {e}")
        return {"success": False, "error": str(e)}


def main(context) -> Dict[str, Any]:
    if hasattr(context, "parameters"):
        params = context.parameters
    elif isinstance(context, dict):
        params = context
    else:
        params = {}
    return execute(params)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("Usage: python tool.py <target_ip> <command>")
        sys.exit(1)
    result = main({"target_ip": sys.argv[1], "commands": sys.argv[2:]})
    print(json.dumps(result, indent=2))
