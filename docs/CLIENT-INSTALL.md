# Client Installation Guide

This guide covers installing the MCP Trust Anchor client on Windows and Linux endpoints for use with Claude Desktop or Claude Code.

## Overview

The client consists of two components:
- **MCP Bridge**: MCP server that connects Claude to the Trust Anchor ecosystem
- **Subscriber Node**: Fetches, verifies, and executes signed tools

## Prerequisites

- Windows 10/11 or Linux (Ubuntu 20.04+, Rocky Linux 8+)
- Python 3.10 or higher
- Claude Desktop or Claude Code installed
- Network access to Trust Anchor server

## Windows Installation

### Quick Install (PowerShell)

```powershell
# Download or clone the repository
git clone https://github.com/your-org/mcp-trust-anchor.git
cd mcp-trust-anchor

# Run bootstrap (as Administrator for Program Files install)
.\client\bootstrap.ps1 -TrustAnchorUrl "http://your-server:8000"
```

### Bootstrap Options

```powershell
# Custom installation directory
.\bootstrap.ps1 -InstallDir "C:\Tools\MCP" -TrustAnchorUrl "http://server:8000"

# Skip Claude Desktop configuration (manual setup)
.\bootstrap.ps1 -SkipClaudeConfig -TrustAnchorUrl "http://server:8000"

# Force reinstall
.\bootstrap.ps1 -Force -TrustAnchorUrl "http://server:8000"
```

### Manual Installation

1. **Install Python 3.10+**
   - Download from [python.org](https://www.python.org/downloads/)
   - Ensure "Add to PATH" is checked during install

2. **Create directories**
   ```powershell
   mkdir "C:\Program Files\MCP-Trust-Anchor"
   mkdir "$env:USERPROFILE\.config\mcp"
   ```

3. **Copy client files**
   ```powershell
   Copy-Item -Recurse client\mcp_bridge "C:\Program Files\MCP-Trust-Anchor\"
   Copy-Item -Recurse client\subscriber_node "C:\Program Files\MCP-Trust-Anchor\"
   ```

4. **Create virtual environment**
   ```powershell
   python -m venv "C:\Program Files\MCP-Trust-Anchor\venv"
   & "C:\Program Files\MCP-Trust-Anchor\venv\Scripts\pip" install httpx pyyaml cryptography mcp
   ```

5. **Configure Claude Desktop**

   Edit `%APPDATA%\Claude\claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "secure-tools": {
         "command": "C:\\Program Files\\MCP-Trust-Anchor\\venv\\Scripts\\python.exe",
         "args": ["C:\\Program Files\\MCP-Trust-Anchor\\mcp_bridge\\MCP-secure-tools-server.py"],
         "env": {
           "TRUST_ANCHOR_URL": "http://your-server:8000",
           "CREDENTIAL_PATH": "C:\\Users\\YourUser\\.config\\mcp"
         }
       }
     }
   }
   ```

6. **Restart Claude Desktop**

## Linux Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-trust-anchor.git
cd mcp-trust-anchor

# Run bootstrap
./client/bootstrap.sh --server http://your-server:8000
```

### Bootstrap Options

```bash
# Custom installation directory
./bootstrap.sh --server http://server:8000 --install-dir ~/mcp-tools

# Skip Claude Code configuration
./bootstrap.sh --server http://server:8000 --skip-claude
```

### Manual Installation

1. **Install Python 3.10+**
   ```bash
   # Rocky Linux / RHEL
   sudo dnf install python3.11

   # Ubuntu / Debian
   sudo apt install python3.10
   ```

2. **Create directories**
   ```bash
   mkdir -p ~/.local/share/mcp-trust-anchor
   mkdir -p ~/.config/mcp
   ```

3. **Copy client files**
   ```bash
   cp -r client/mcp_bridge ~/.local/share/mcp-trust-anchor/
   cp -r client/subscriber_node ~/.local/share/mcp-trust-anchor/
   ```

4. **Create virtual environment**
   ```bash
   python3 -m venv ~/.local/share/mcp-trust-anchor/venv
   source ~/.local/share/mcp-trust-anchor/venv/bin/activate
   pip install httpx pyyaml cryptography mcp
   ```

5. **Configure Claude Code**

   Edit `~/.config/claude/claude_code_config.json`:
   ```json
   {
     "mcpServers": {
       "secure-tools": {
         "command": "~/.local/share/mcp-trust-anchor/venv/bin/python",
         "args": ["~/.local/share/mcp-trust-anchor/mcp_bridge/MCP-secure-tools-server.py"],
         "env": {
           "TRUST_ANCHOR_URL": "http://your-server:8000",
           "CREDENTIAL_PATH": "~/.config/mcp"
         }
       }
     }
   }
   ```

6. **Restart Claude Code**

## Credential Configuration

Credentials are stored locally and never sent to the Trust Anchor server.

### FortiGate Credentials

Create `~/.config/mcp/fortigate_credentials.yaml`:

```yaml
# FortiGate device credentials
devices:
  lab-fortigate:
    host: "192.168.1.1"
    api_token: "your-api-token-here"
    verify_ssl: false

  prod-fortigate:
    host: "10.0.0.1"
    api_token: "production-api-token"
    verify_ssl: true

# Map IPs to device names for automatic lookup
default_lookup:
  "192.168.1.1": "lab-fortigate"
  "10.0.0.1": "prod-fortigate"
```

### Credential Security

- Set restrictive permissions: `chmod 600 ~/.config/mcp/*.yaml`
- Credentials are injected at runtime, never stored in tool code
- Result sanitization prevents credential leakage in output

## Verification

### Test Connectivity

```bash
# Test Trust Anchor connection
curl http://your-server:8000/health

# Test public key fetch
curl http://your-server:8000/keys/public
```

### Test MCP Bridge

```bash
# Start MCP Bridge manually (for testing)
source ~/.local/share/mcp-trust-anchor/venv/bin/activate
export TRUST_ANCHOR_URL="http://your-server:8000"
python ~/.local/share/mcp-trust-anchor/mcp_bridge/MCP-secure-tools-server.py
```

### Test in Claude

After restarting Claude, ask:
- "List available tools"
- "What FortiGate tools do you have?"
- "Check health of FortiGate at 192.168.1.1"

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_ANCHOR_URL` | `http://localhost:8000` | Trust Anchor server URL |
| `CREDENTIAL_PATH` | `~/.config/mcp` | Local credential directory |
| `LOG_LEVEL` | `INFO` | Logging level |

### File Locations

**Windows:**
```
C:\Program Files\MCP-Trust-Anchor\
├── mcp_bridge\
├── subscriber_node\
├── venv\
└── config.env

%USERPROFILE%\.config\mcp\
├── fortigate_credentials.yaml
└── [other credential files]

%APPDATA%\Claude\
└── claude_desktop_config.json
```

**Linux:**
```
~/.local/share/mcp-trust-anchor/
├── mcp_bridge/
├── subscriber_node/
├── venv/
└── config.env

~/.config/mcp/
├── fortigate_credentials.yaml
└── [other credential files]

~/.config/claude/
└── claude_code_config.json
```

## Troubleshooting

### MCP Server Won't Start

1. Check Python version: `python --version` (need 3.10+)
2. Check dependencies: `pip list | grep mcp`
3. Check Trust Anchor connectivity: `curl $TRUST_ANCHOR_URL/health`

### Tools Not Showing

1. Verify MCP server is configured in Claude config
2. Restart Claude Desktop/Code
3. Check Claude logs for MCP errors

### Signature Verification Fails

1. Ensure Trust Anchor server is accessible
2. Check if tools are properly signed
3. Try clearing public key cache (restart client)

### Credentials Not Found

1. Check credential file exists and has correct path
2. Verify YAML syntax: `python -c "import yaml; yaml.safe_load(open('file.yaml'))"`
3. Check file permissions (should be 600)

### Connection Timeout

1. Check firewall allows connection to Trust Anchor
2. Verify server URL is correct
3. Test with curl: `curl -v http://server:8000/health`

## Break-Glass Mode

For emergencies when verification needs to be bypassed:

```bash
# Windows PowerShell
$env:TRUST_ANCHOR_BREAK_GLASS = "1"

# Linux/Mac
export TRUST_ANCHOR_BREAK_GLASS=1
```

**Warning**: Break-glass mode bypasses all security verification. Use only in emergencies and ensure it's logged and audited.

## Uninstallation

### Windows

```powershell
# Remove installation
Remove-Item -Recurse "C:\Program Files\MCP-Trust-Anchor"

# Remove Claude config (edit to remove secure-tools section)
notepad "$env:APPDATA\Claude\claude_desktop_config.json"

# Optionally remove credentials
Remove-Item -Recurse "$env:USERPROFILE\.config\mcp"
```

### Linux

```bash
# Remove installation
rm -rf ~/.local/share/mcp-trust-anchor

# Edit Claude config to remove secure-tools
vim ~/.config/claude/claude_code_config.json

# Optionally remove credentials
rm -rf ~/.config/mcp
```
