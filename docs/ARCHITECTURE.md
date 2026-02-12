# MCP Trust Anchor Architecture

## Overview

MCP Trust Anchor is a cryptographically-secured tool execution framework designed to enable AI assistants (Claude) to safely execute operational tools while maintaining security boundaries.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROCKY LINUX SERVER                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Trust Anchor (FastAPI :8000)                      │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ /tools/*     │  │ /keys/*      │  │ /publisher/* │               │   │
│  │  │ Tool catalog │  │ Public key   │  │ Tool signing │               │   │
│  │  │ retrieval    │  │ distribution │  │ certification│               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                      Redis Storage                           │    │   │
│  │  │  • Tool manifests     • Code (Python)     • Signatures      │    │   │
│  │  │  • Skills.md docs     • Runbooks          • Subscribers     │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────┐                                                   │
│  │   RSA Private Key   │  ◄── /opt/trust-anchor/keys/private.pem          │
│  │   (NEVER LEAVES)    │      Used only for signing tools                  │
│  └─────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP (port 8000)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WINDOWS/LINUX CLIENT                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 Claude Desktop / Claude Code                         │   │
│  │                                                                      │   │
│  │  "Check the health of my FortiGate at 192.168.1.1"                  │   │
│  │                           │                                          │   │
│  │                           ▼ MCP Protocol                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                     MCP Bridge                               │    │   │
│  │  │  • Exposes tools to Claude via MCP                          │    │   │
│  │  │  • Routes tool execution requests                           │    │   │
│  │  │  • Semantic search (route_query)                            │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                   Subscriber Node                            │    │   │
│  │  │                                                              │    │   │
│  │  │  SecureToolExecutor:                                        │    │   │
│  │  │  1. Fetch tool + signature from Trust Anchor                │    │   │
│  │  │  2. Verify signature with cached public key                 │    │   │
│  │  │  3. Verify code hash matches                                │    │   │
│  │  │  4. Execute tool locally                                    │    │   │
│  │  │  5. Sanitize output (remove credentials)                    │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐                          │
│  │   RSA Public Key    │  │    Credentials      │                          │
│  │   (cached 24h)      │  │   (local only)      │                          │
│  │   from Trust Anchor │  │   ~/.config/mcp/    │                          │
│  └─────────────────────┘  └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Security Model

### Cryptographic Verification

Every tool execution goes through cryptographic verification:

```
┌────────────────────────────────────────────────────────────────────┐
│                    Tool Signing (Server-Side)                       │
│                                                                     │
│  1. Developer submits: manifest.yaml + code.py + Skills.md         │
│                                                                     │
│  2. Trust Anchor creates signing payload:                          │
│     {                                                               │
│       "canonical_id": "org.example.tool/1.0.0",                    │
│       "version": "1.0.0",                                          │
│       "code_hash_sha256": "abc123...",                             │
│       "signed_at": "2024-01-15T10:30:00Z"                          │
│     }                                                               │
│                                                                     │
│  3. Sign with private key:                                         │
│     signature = RSA-PKCS1v15-SHA256(private_key, payload)          │
│                                                                     │
│  4. Store in Redis: tool + signature + code_hash                   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                 Tool Verification (Client-Side)                     │
│                                                                     │
│  1. Fetch tool + signature from Trust Anchor                       │
│                                                                     │
│  2. Fetch/cache public key (24h TTL)                               │
│                                                                     │
│  3. Verify signature:                                              │
│     verify(public_key, signature, signing_payload) == VALID        │
│                                                                     │
│  4. Verify code hash:                                              │
│     sha256(received_code) == signing_payload.code_hash_sha256      │
│                                                                     │
│  5. If BOTH pass → Execute tool                                    │
│     If EITHER fails → BLOCK and log security event                 │
└────────────────────────────────────────────────────────────────────┘
```

### Credential Isolation

Credentials NEVER leave the client endpoint:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Credential Flow                              │
│                                                                  │
│  Trust Anchor Server          Client Endpoint                   │
│  ──────────────────          ────────────────                   │
│                                                                  │
│  [Tool Code]                  [Credential File]                 │
│  (no credentials)             ~/.config/mcp/                    │
│       │                       fortigate_credentials.yaml        │
│       │                              │                          │
│       ▼                              │                          │
│  HTTP Response                       │                          │
│  {                                   │                          │
│    "code": "...",                   ▼                          │
│    "manifest": {...}         ┌─────────────────┐               │
│  }                           │ Execution       │               │
│       │                      │ Context         │               │
│       │                      │                 │               │
│       └──────────────────────┤ parameters: {}  │               │
│                              │ credentials: {  │◄──────────────┘
│                              │   api_token:... │
│                              │ }               │
│                              └─────────────────┘
│                                     │
│                                     ▼
│                              [Tool Executes]
│                              (credentials injected
│                               at runtime locally)
└─────────────────────────────────────────────────────────────────┘
```

### Break-Glass Mode

For emergency situations, verification can be bypassed:

```bash
# Bypass ALL verification (use with caution!)
export TRUST_ANCHOR_BREAK_GLASS=1

# Bypass only signature verification
export TRUST_ANCHOR_SKIP_SIGNING=1

# Bypass only hash verification
export TRUST_ANCHOR_SKIP_HASH=1
```

All bypasses are logged at CRITICAL level for audit purposes.

## Component Details

### Trust Anchor Server

The central authority that:
- Stores tool manifests, code, and documentation
- Signs tools with RSA private key
- Distributes public key to clients
- Provides tool catalog and search

**Key files:**
- `server/trust_anchor/main.py` - FastAPI application
- `server/publisher_node/router.py` - Tool submission/signing API
- `server/security/crypto/signing.py` - RSA signing logic

### MCP Bridge

The MCP server that:
- Connects to Claude via Model Context Protocol
- Exposes tools as MCP functions
- Routes execution requests to Subscriber Node
- Provides semantic search via `route_query`

**Key files:**
- `client/mcp_bridge/MCP-secure-tools-server.py` - MCP server

### Subscriber Node

The execution engine that:
- Fetches tools from Trust Anchor
- Verifies signatures and hashes
- Executes tools in sandbox
- Sanitizes output to prevent credential leakage

**Key files:**
- `client/subscriber_node/secure_executor.py` - Verification logic
- `client/subscriber_node/executor.py` - Execution and sanitization

## Data Flows

### Tool Registration Flow

```
Developer                   Trust Anchor                Redis
    │                            │                        │
    │ POST /publisher/submit-tool│                        │
    │ {manifest, code, skills}   │                        │
    │ X-Publisher-Key: xxx       │                        │
    │───────────────────────────►│                        │
    │                            │ Validate manifest      │
    │                            │ Compute code hash      │
    │                            │ Store in Redis         │
    │                            │───────────────────────►│
    │                            │                        │
    │ POST /publisher/certify/id │                        │
    │───────────────────────────►│                        │
    │                            │ Create signing payload │
    │                            │ Sign with private key  │
    │                            │ Store signature        │
    │                            │───────────────────────►│
    │                            │                        │
    │◄─────────────────────────  │                        │
    │ {status: "certified"}      │                        │
```

### Tool Execution Flow

```
Claude          MCP Bridge       Subscriber Node      Trust Anchor
   │                │                   │                   │
   │ "check health" │                   │                   │
   │───────────────►│                   │                   │
   │                │                   │                   │
   │                │ execute_certified │                   │
   │                │ _tool(id, params) │                   │
   │                │──────────────────►│                   │
   │                │                   │                   │
   │                │                   │ GET /tools/get/id │
   │                │                   │──────────────────►│
   │                │                   │◄──────────────────│
   │                │                   │ {code, signature} │
   │                │                   │                   │
   │                │                   │ Verify signature  │
   │                │                   │ Verify code hash  │
   │                │                   │                   │
   │                │                   │ Execute tool      │
   │                │                   │ Inject credentials│
   │                │                   │ Sanitize output   │
   │                │                   │                   │
   │                │◄──────────────────│                   │
   │                │ {result}          │                   │
   │◄───────────────│                   │                   │
   │ "FortiGate is  │                   │                   │
   │  healthy..."   │                   │                   │
```

## Result Sanitization (SANITIZE-001)

The executor sanitizes all tool output to prevent credential leakage:

```python
SENSITIVE_PATTERNS = [
    r'api[_-]?token',
    r'api[_-]?key',
    r'password',
    r'secret',
    r'bearer\s+\S+',
    r'authorization:\s*\S+',
]

def sanitize_result(result: dict) -> dict:
    """Recursively scan and redact sensitive values."""
    for key, value in result.items():
        if matches_sensitive_pattern(key):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitize_result(value)
    return result
```

## Network Requirements

| Component | Port | Protocol | Direction |
|-----------|------|----------|-----------|
| Trust Anchor | 8000 | HTTP | Inbound from clients |
| Redis | 6379 | TCP | Local only |
| Tool execution | Various | HTTPS | Outbound to devices |

## File Locations

### Server
```
/opt/trust-anchor/
├── trust_anchor/        # FastAPI app
├── publisher_node/      # Signing API
├── security/            # Crypto modules
├── keys/
│   ├── private.pem      # RSA private key (600)
│   └── public.pem       # RSA public key (644)
└── venv/                # Python environment

/etc/trust-anchor/
└── trust-anchor.env     # Configuration

/var/log/trust-anchor/   # Logs
```

### Client
```
~/.local/share/mcp-trust-anchor/  (Linux)
C:\Program Files\MCP-Trust-Anchor\ (Windows)
├── mcp_bridge/
├── subscriber_node/
├── venv/
└── config.env

~/.config/mcp/                    (Linux)
%USERPROFILE%\.config\mcp\        (Windows)
├── fortigate_credentials.yaml
└── [other credential files]
```
