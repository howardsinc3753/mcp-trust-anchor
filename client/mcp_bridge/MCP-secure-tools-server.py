#!/usr/bin/env python3
"""
MCP-secure-tools-server.py

MCP Server Bridge - Exposes cryptographically verified tools to AI agents.

This server:
1. Connects to Trust Anchor for tool discovery and execution
2. Verifies tool signatures before execution
3. Exposes MCP tools to Claude Desktop / Claude Code

Usage:
    python MCP-secure-tools-server.py

Claude Desktop config (%APPDATA%\\Claude\\claude_desktop_config.json):
{
    "mcpServers": {
        "secure-tools": {
            "command": "python",
            "args": ["C:\\...\\mcp_bridge\\MCP-secure-tools-server.py"],
            "env": {
                "TRUST_ANCHOR_URL": "http://192.168.x.x:8000"
            }
        }
    }
}
"""

import asyncio
import json
import platform
import socket
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Local imports
from subscriber_node.secure_executor import SecureSubscriberClient, SecureToolExecutor
from mcp_bridge.config import (
    TRUST_ANCHOR_URL,
    MCP_BRIDGE_VERSION,
    HEARTBEAT_INTERVAL,
    CREDENTIAL_SEARCH_PATHS,
)

# Global state
server = Server("secure-tools")
client: Optional[SecureSubscriberClient] = None
executor: Optional[SecureToolExecutor] = None
endpoint_id: Optional[str] = None


@server.list_tools()
async def list_tools():
    """Return list of available MCP tools."""
    return [
        Tool(
            name="list_certified_tools",
            description="List available certified tools from Trust Anchor.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Filter by domain"},
                    "vendor": {"type": "string", "description": "Filter by vendor"}
                }
            }
        ),
        Tool(
            name="list_accessible_devices",
            description="List devices this endpoint can access with credentials.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_type": {"type": "string", "description": "Filter by device type"}
                }
            }
        ),
        Tool(
            name="get_tool_skills",
            description="Get the Skills.md guidance document for a tool.",
            inputSchema={
                "type": "object",
                "properties": {
                    "canonical_id": {"type": "string", "description": "Tool canonical ID"},
                    "oid": {"type": "string", "description": "Tool OID (alternative)"}
                }
            }
        ),
        Tool(
            name="execute_certified_tool",
            description="Execute a CRYPTOGRAPHICALLY VERIFIED tool from Trust Anchor.",
            inputSchema={
                "type": "object",
                "properties": {
                    "canonical_id": {"type": "string", "description": "Tool canonical ID"},
                    "oid": {"type": "string", "description": "Tool OID (alternative)"},
                    "parameters": {"type": "object", "description": "Tool parameters"}
                },
                "required": ["parameters"]
            }
        ),
        Tool(
            name="list_runbooks",
            description="List available runbooks from Trust Anchor.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Filter by domain"},
                    "vendor": {"type": "string", "description": "Filter by vendor"},
                    "intent": {"type": "string", "description": "Filter by intent"}
                }
            }
        ),
        Tool(
            name="get_runbook_skills",
            description="Get the Skills.md guidance document for a runbook.",
            inputSchema={
                "type": "object",
                "properties": {
                    "runbook_id": {"type": "string", "description": "Runbook ID"}
                },
                "required": ["runbook_id"]
            }
        ),
        Tool(
            name="execute_runbook",
            description="Execute a multi-step runbook against a device.",
            inputSchema={
                "type": "object",
                "properties": {
                    "runbook_id": {"type": "string", "description": "Runbook ID"},
                    "device": {"type": "string", "description": "Target device IP"},
                    "parameters": {"type": "object", "description": "Additional parameters"}
                },
                "required": ["runbook_id", "device"]
            }
        ),
        Tool(
            name="get_runbooks_for_tool",
            description="Find runbooks that use a specific tool.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_canonical_id": {"type": "string", "description": "Tool canonical ID"}
                },
                "required": ["tool_canonical_id"]
            }
        ),
        Tool(
            name="route_query",
            description="Semantic search for certified tools and runbooks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"},
                    "top_k": {"type": "integer", "description": "Number of results", "default": 5},
                    "include_runbooks": {"type": "boolean", "description": "Include runbooks", "default": True}
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls from AI agent."""
    try:
        if name == "list_certified_tools":
            return await _handle_list_certified_tools(arguments)
        elif name == "list_accessible_devices":
            return await _handle_list_accessible_devices(arguments)
        elif name == "get_tool_skills":
            return await _handle_get_tool_skills(arguments)
        elif name == "execute_certified_tool":
            return await _handle_execute_certified_tool(arguments)
        elif name == "list_runbooks":
            return await _handle_list_runbooks(arguments)
        elif name == "get_runbook_skills":
            return await _handle_get_runbook_skills(arguments)
        elif name == "execute_runbook":
            return await _handle_execute_runbook(arguments)
        elif name == "get_runbooks_for_tool":
            return await _handle_get_runbooks_for_tool(arguments)
        elif name == "route_query":
            return await _handle_route_query(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_list_certified_tools(arguments: dict):
    """List available certified tools from Trust Anchor."""
    try:
        tools = client.list_tools(
            domain=arguments.get("domain"),
            vendor=arguments.get("vendor"),
        )
        result = {"count": len(tools), "tools": tools}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing tools: {str(e)}")]


async def _handle_list_accessible_devices(arguments: dict):
    """List devices from local credential config files."""
    device_type = arguments.get("device_type")
    devices = _list_local_devices(device_type)
    result = {
        "count": len(devices),
        "devices": devices,
        "note": "Credentials are stored locally, never sent to Trust Anchor"
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _handle_get_tool_skills(arguments: dict):
    """Get Skills.md for a tool."""
    canonical_id = arguments.get("canonical_id")
    oid = arguments.get("oid")

    if oid and not canonical_id:
        canonical_id = client.resolve_oid(oid)
        if not canonical_id:
            return [TextContent(type="text", text=f"Could not resolve OID '{oid}'")]

    if not canonical_id:
        return [TextContent(type="text", text="Error: Must provide canonical_id or oid")]

    skills = client.get_skills(canonical_id)
    if skills:
        return [TextContent(type="text", text=skills)]
    else:
        return [TextContent(type="text", text=f"No Skills.md found for tool: {canonical_id}")]


async def _handle_execute_certified_tool(arguments: dict):
    """Execute a CRYPTOGRAPHICALLY VERIFIED tool."""
    canonical_id = arguments.get("canonical_id")
    oid = arguments.get("oid")
    parameters = arguments.get("parameters", {})

    if oid and not canonical_id:
        canonical_id = client.resolve_oid(oid)
        if not canonical_id:
            return [TextContent(type="text", text=f"Could not resolve OID '{oid}'")]

    if not canonical_id:
        return [TextContent(type="text", text="Error: Must provide canonical_id or oid")]

    # Load credentials for target device
    target_ip = parameters.get("target_ip")
    credentials = None
    if target_ip:
        credentials = _load_credentials_for_device(target_ip)

    # Execute with CRYPTOGRAPHIC VERIFICATION
    result = executor.execute(canonical_id, parameters, credentials)

    response = {
        "success": result.success,
        "canonical_id": result.canonical_id,
        "execution_time_ms": result.execution_time_ms,
        "security": {
            "mode": "SECURE",
            "signature_verified": False,
            "hash_verified": False,
        }
    }

    if result.verification:
        response["security"] = {
            "mode": "SECURE",
            "signature_verified": result.verification.signature_verified,
            "hash_verified": result.verification.hash_verified,
            "verification_status": result.verification.status.value,
            "verification_message": result.verification.message,
        }

    if result.success:
        response["result"] = result.result
    else:
        response["error"] = result.error

    if hasattr(result, 'stdout') and result.stdout:
        response["stdout"] = result.stdout
    if hasattr(result, 'stderr') and result.stderr and not result.success:
        response["stderr"] = result.stderr

    return [TextContent(type="text", text=json.dumps(response, indent=2))]


async def _handle_list_runbooks(arguments: dict):
    """List available runbooks from Trust Anchor."""
    try:
        runbooks = client.list_runbooks(
            domain=arguments.get("domain"),
            vendor=arguments.get("vendor"),
            intent=arguments.get("intent"),
        )
        result = {"count": len(runbooks), "runbooks": runbooks}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing runbooks: {str(e)}")]


async def _handle_get_runbook_skills(arguments: dict):
    """Get Skills.md for a runbook."""
    runbook_id = arguments.get("runbook_id")
    if not runbook_id:
        return [TextContent(type="text", text="Error: Must provide runbook_id")]

    skills = client.get_runbook_skills(runbook_id)
    if skills:
        return [TextContent(type="text", text=skills)]
    else:
        return [TextContent(type="text", text=f"No Skills.md found for runbook: {runbook_id}")]


async def _handle_execute_runbook(arguments: dict):
    """Execute a multi-step runbook."""
    runbook_id = arguments.get("runbook_id")
    device = arguments.get("device")
    parameters = arguments.get("parameters", {})

    if not runbook_id:
        return [TextContent(type="text", text="Error: Must provide runbook_id")]
    if not device:
        return [TextContent(type="text", text="Error: Must provide device (target IP)")]

    # Runbook execution would be implemented here
    return [TextContent(type="text", text=json.dumps({
        "status": "not_implemented",
        "message": "Runbook execution requires RunbookExecutor (not included in v1)",
        "runbook_id": runbook_id,
        "device": device
    }, indent=2))]


async def _handle_get_runbooks_for_tool(arguments: dict):
    """Find runbooks that use a specific tool."""
    tool_canonical_id = arguments.get("tool_canonical_id")
    if not tool_canonical_id:
        return [TextContent(type="text", text="Error: Must provide tool_canonical_id")]

    try:
        import httpx
        response = httpx.get(
            f"{TRUST_ANCHOR_URL}/runbooks/for-tool/{tool_canonical_id}",
            timeout=30.0
        )
        if response.status_code == 404:
            return [TextContent(type="text", text=json.dumps({
                "tool_canonical_id": tool_canonical_id,
                "runbook_count": 0,
                "runbooks": []
            }, indent=2))]

        response.raise_for_status()
        return [TextContent(type="text", text=json.dumps(response.json(), indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error finding runbooks: {str(e)}")]


async def _handle_route_query(arguments: dict):
    """Route query to semantic search (if RAG available)."""
    query = arguments.get("query")
    if not query:
        return [TextContent(type="text", text="Error: Must provide 'query' parameter")]

    try:
        import httpx
        payload = {
            "query": query,
            "top_k": arguments.get("top_k", 5),
            "include_runbooks": arguments.get("include_runbooks", True),
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(f"{TRUST_ANCHOR_URL}/v1/route", json=payload)
            if response.status_code == 404:
                return [TextContent(type="text", text=json.dumps({
                    "error": "Semantic Tool Router not available",
                    "fallback": "Use list_certified_tools to browse available tools"
                }, indent=2))]

            response.raise_for_status()
            result = response.json()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error in route_query: {str(e)}")]


def _list_local_devices(device_type: Optional[str] = None) -> list:
    """List devices from local credential config files."""
    devices = []

    for search_path in CREDENTIAL_SEARCH_PATHS:
        config_dir = Path(search_path)
        if not config_dir.exists():
            continue

        for config_file in config_dir.glob("*_credentials.yaml"):
            vendor = config_file.stem.replace("_credentials", "")

            if device_type and vendor.lower() != device_type.lower():
                continue

            try:
                import yaml
                with open(config_file) as f:
                    config = yaml.safe_load(f)

                if not config:
                    continue

                for device_id, device_info in config.get("devices", {}).items():
                    if isinstance(device_info, dict):
                        devices.append({
                            "device_id": device_id,
                            "vendor": vendor,
                            "ip_address": device_info.get("host", "unknown"),
                            "has_credentials": bool(device_info.get("api_token")),
                        })
            except Exception:
                continue

    return devices


def _load_credentials_for_device(target_ip: str) -> Optional[dict]:
    """Load credentials for a specific device by IP."""
    for search_path in CREDENTIAL_SEARCH_PATHS:
        config_dir = Path(search_path)
        if not config_dir.exists():
            continue

        for config_file in config_dir.glob("*_credentials.yaml"):
            try:
                import yaml
                with open(config_file) as f:
                    config = yaml.safe_load(f)

                if not config:
                    continue

                # Check default_lookup
                if "default_lookup" in config and target_ip in config["default_lookup"]:
                    device_name = config["default_lookup"][target_ip]
                    if device_name in config.get("devices", {}):
                        return config["devices"][device_name]

                # Search by host
                for device_info in config.get("devices", {}).values():
                    if isinstance(device_info, dict) and device_info.get("host") == target_ip:
                        return device_info

            except Exception:
                continue

    return None


async def register_with_trust_anchor():
    """Register this MCP Bridge with Trust Anchor."""
    global endpoint_id

    hostname = socket.gethostname()
    plat = platform.system().lower()

    print(f"Registering with Trust Anchor at {TRUST_ANCHOR_URL}...", file=sys.stderr)

    result = client.register_endpoint(
        name=f"MCP Secure Bridge - {hostname}",
        hostname=hostname,
        platform=plat,
        mcp_bridge_version=MCP_BRIDGE_VERSION,
    )

    if result:
        endpoint_id = result.get("endpoint_id")
        print(f"Registered as: {endpoint_id}", file=sys.stderr)
    else:
        endpoint_id = f"unregistered-{hostname}"
        print(f"Warning: Could not register. Operating as: {endpoint_id}", file=sys.stderr)


async def heartbeat_loop():
    """Send periodic heartbeats to Trust Anchor."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        if endpoint_id and not endpoint_id.startswith("unregistered"):
            tools_cached = len(executor.get_cached_tools()) if executor else 0
            client.heartbeat(endpoint_id, tools_cached)


async def main():
    """Main entry point for MCP server."""
    global client, executor

    print(f"MCP SECURE Tools Server v{MCP_BRIDGE_VERSION}", file=sys.stderr)
    print(f"SECURITY: Cryptographic signature verification ENABLED", file=sys.stderr)
    print(f"Trust Anchor: {TRUST_ANCHOR_URL}", file=sys.stderr)

    # Initialize secure subscriber infrastructure
    try:
        client = SecureSubscriberClient(TRUST_ANCHOR_URL)
        executor = SecureToolExecutor(client)

        # Verify Trust Anchor connectivity
        health = client.health_check()
        print(f"Trust Anchor status: {health.get('status', 'unknown')}", file=sys.stderr)

        # Verify public key is accessible
        key_result = client.get_public_key()
        if key_result:
            _, key_version = key_result
            print(f"Public key loaded (version: {key_version})", file=sys.stderr)
        else:
            print("WARNING: Could not load public key", file=sys.stderr)

    except Exception as e:
        print(f"Warning: Could not connect to Trust Anchor: {e}", file=sys.stderr)
        print("Server will start but tool operations may fail.", file=sys.stderr)

    # Register with Trust Anchor
    await register_with_trust_anchor()

    # Start heartbeat in background
    asyncio.create_task(heartbeat_loop())

    # List locally accessible devices
    devices = _list_local_devices()
    print(f"Found {len(devices)} locally accessible device(s)", file=sys.stderr)

    print("MCP SECURE Server ready. Waiting for connections...", file=sys.stderr)

    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
