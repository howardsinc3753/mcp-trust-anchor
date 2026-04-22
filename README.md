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

👉 **For local evaluation, see [QUICKSTART.md](QUICKSTART.md)** — 3-minute walk-through
covering both the Docker and native paths end-to-end, including how to prove
the signed-tool pipeline works with the shipped mock FortiGate.

The sections below are the full reference. Clone the repo first:

```bash
git clone <this-repo-url> mcp-trust-anchor
cd mcp-trust-anchor
```

### Server — Option 1: Docker (easiest, cross-platform)

**Docker is optional but recommended for local eval.** One command, no Rocky VM required.

```bash
docker compose up -d              # starts Trust Anchor + Redis; keys auto-generated
curl http://localhost:8000/health
```

Works on macOS, Windows, and Linux with Docker Desktop or Docker Engine + Compose v2.
See [docker-compose.yml](docker-compose.yml) and [.env.example](.env.example) for knobs.

### Server — Option 2: Native install (Rocky Linux / RHEL)

Use this for production deployment with systemd.

```bash
sudo ./server/install.sh
curl http://localhost:8000/health
```

### Register Sample Tools

```bash
python scripts/load-sample-tools.py --server http://localhost:8000
```

This signs every tool in `tools/` with your server's private key. Required on first
install — shipped tools are intentionally unsigned (or signed under a different key).

### Client — wire up your AI editor

Works with Claude Desktop, Claude Code (VS Code extension), and GitHub Copilot (VS Code).
One command, detects installed editors, writes the right config for each:

```bash
python scripts/configure-editors.py --server http://localhost:8000
```

Or use the platform-specific bootstrap (installs the MCP bridge + configures Claude Desktop only):

```powershell
# Windows
.\client\bootstrap.ps1 -TrustAnchorUrl "http://localhost:8000"
```
```bash
# Linux / macOS
./client/bootstrap.sh --server http://localhost:8000
```

Restart the editor(s) after configuring. For Copilot, switch chat mode to **Agent**.

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

### No FortiGate on hand? Use the mock

A stdlib-only Python stub is included so you can prove the signed-tool
pipeline without any real hardware:

```bash
python scripts/mock-fortigate.py
cp scripts/sample_credentials.yaml.example ~/.config/mcp/mock_credentials.yaml
```

Or run the mock as a Docker profile:

```bash
docker compose --profile mock up -d
```

Then ask your AI editor to call `fortigate-health-check` against `127.0.0.1`.

## Publishing Tools

Two ways to publish a tool once your Trust Anchor is up:

**AI-driven (recommended for humans):** In Claude Code / Claude Desktop / GitHub Copilot,
ask: *"Publish `path/to/my-tool.py` as a new NOC monitoring tool."* The agent will
discover the publisher wizard via Trust Anchor and drive it.

**CLI (for scripting / CI):**

```bash
python scripts/publish.py path/to/my-tool.py \
    --domain noc \
    --intent monitor \
    --description "What this tool does"
```

See [docs/TOOL-AUTHORING.md](docs/TOOL-AUTHORING.md) for the full authoring guide.

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
