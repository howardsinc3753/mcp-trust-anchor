# MCP Trust Anchor

A cryptographically-secured tool execution framework for AI assistants. Trust Anchor provides signed, verified tool execution for Claude Desktop and Claude Code via the Model Context Protocol (MCP).

## Overview

MCP Trust Anchor enables organizations to:

- **Sign and verify tools** - RSA-2048 signatures ensure tool integrity
- **Execute tools securely** - Signature verification before every execution
- **Keep credentials local** - Credentials never leave the endpoint
- **Semantic tool discovery** - Natural language search for tools

```
┌─────────────────────────────────┐         ┌─────────────────────────────┐
│     ROCKY LINUX SERVER          │         │     WINDOWS/LINUX CLIENT    │
│                                 │         │                             │
│  Trust Anchor (FastAPI :8000)   │  HTTP   │  Claude Code/Desktop        │
│  ├─ Tool Registry               │◄────────┤  └─ MCP Bridge              │
│  ├─ Publisher API (signing)     │         │     └─ Subscriber Node      │
│  ├─ Public Key Distribution     │         │        └─ SecureExecutor    │
│  └─ Redis (storage)             │         │                             │
│                                 │         │  Credentials (local only)   │
│  RSA Private Key (server-side)  │         │  RSA Public Key (cached)    │
└─────────────────────────────────┘         └─────────────────────────────┘
```

## Quick Start

### Server Installation (Rocky Linux)

```bash
# Clone the repo
git clone https://github.com/your-org/mcp-trust-anchor.git
cd mcp-trust-anchor

# Run the installer
sudo ./server/install.sh

# Verify it's running
curl http://localhost:8000/health
```

### Client Installation (Windows)

```powershell
# Download and run bootstrap
.\client\bootstrap.ps1 -TrustAnchorUrl "http://your-server:8000"

# Restart Claude Desktop
```

### Client Installation (Linux)

```bash
# Run bootstrap
./client/bootstrap.sh --server http://your-server:8000

# Restart Claude Code
```

### Register Sample Tools

```bash
python tools/register-tools.py --server http://localhost:8000
```

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Trust Anchor | Server | Central registry, tool signing, key distribution |
| Publisher Node | Server | Tool submission and certification API |
| MCP Bridge | Client | MCP server for Claude, routes tool calls |
| Subscriber Node | Client | Fetches tools, verifies signatures, executes |

### Security Model

1. **Tool Signing**: Tools are signed server-side with RSA-2048 private key
2. **Signature Verification**: Clients verify signatures using cached public key
3. **Hash Verification**: Code hash prevents tampering after signing
4. **Credential Isolation**: Credentials stored locally, never sent to server

### Data Flow

```
1. Developer creates tool → submits to Trust Anchor
2. Trust Anchor signs tool → stores in Redis
3. User asks Claude to "check firewall health"
4. MCP Bridge → fetches tool + signature from Trust Anchor
5. Subscriber Node → verifies signature with public key
6. If valid → execute tool locally with local credentials
7. If invalid → BLOCK execution, log security event
```

## Tool Structure

Each tool consists of three files:

```
tools/my-tool/
├── manifest.yaml      # Tool metadata, parameters, capabilities
├── my_tool.py         # Python implementation
└── Skills.md          # AI guidance (when/how to use)
```

See [TOOL-AUTHORING.md](docs/TOOL-AUTHORING.md) for the complete guide.

## Configuration

### Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_ANCHOR_HOST` | `0.0.0.0` | Bind address |
| `TRUST_ANCHOR_PORT` | `8000` | HTTP port |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `PRIVATE_KEY_PATH` | `/opt/trust-anchor/keys/private.pem` | RSA private key |
| `PUBLIC_KEY_PATH` | `/opt/trust-anchor/keys/public.pem` | RSA public key |
| `PUBLISHER_KEYS` | `dev-publisher-key` | Allowed publisher API keys |

### Client Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_ANCHOR_URL` | `http://localhost:8000` | Server URL |
| `CREDENTIAL_PATH` | `~/.config/mcp` | Local credential directory |

## API Reference

### Trust Anchor Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/keys/public` | GET | Get public key for verification |
| `/tools/list` | GET | List all certified tools |
| `/tools/get/{id}` | GET | Get tool by canonical ID |
| `/tools/get/{id}/signature` | GET | Get tool signature data |
| `/publisher/submit-tool` | POST | Submit new tool (requires API key) |
| `/publisher/certify/{id}` | POST | Sign/certify a tool |

### MCP Tools (exposed to Claude)

| Tool | Description |
|------|-------------|
| `list_certified_tools` | List available tools |
| `list_accessible_devices` | List devices with credentials |
| `get_tool_skills` | Get Skills.md for a tool |
| `execute_certified_tool` | Execute a signed tool |
| `route_query` | Semantic search for tools |

## Documentation

- [Server Installation Guide](docs/SERVER-INSTALL.md)
- [Client Installation Guide](docs/CLIENT-INSTALL.md)
- [Tool Authoring Guide](docs/TOOL-AUTHORING.md)
- [Architecture Deep-Dive](docs/ARCHITECTURE.md)

## Sample Tools

| Tool | Description |
|------|-------------|
| `fortigate-health-check` | Check FortiGate firewall health metrics |
| `sample-echo` | Simple echo for testing the framework |

## Requirements

### Server
- Rocky Linux 8/9 or RHEL-compatible
- Python 3.10+
- Redis 6+

### Client
- Windows 10/11 or Linux
- Python 3.10+
- Claude Desktop or Claude Code

## License

[TBD - Apache 2.0 or proprietary]

## Contributing

[TBD - contribution guidelines]
