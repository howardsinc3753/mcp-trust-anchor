#!/bin/bash
#
# MCP Trust Anchor - Linux Client Bootstrap
#
# Installs the MCP Bridge and Subscriber Node components for Claude Code.
#
# Usage: ./bootstrap.sh [options]
#   --server URL     Trust Anchor server URL (default: http://localhost:8000)
#   --install-dir    Installation directory (default: ~/.local/share/mcp-trust-anchor)
#   --skip-claude    Skip Claude Code configuration
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Defaults
TRUST_ANCHOR_URL="http://localhost:8000"
INSTALL_DIR="$HOME/.local/share/mcp-trust-anchor"
SKIP_CLAUDE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server)
            TRUST_ANCHOR_URL="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --skip-claude)
            SKIP_CLAUDE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}MCP Trust Anchor - Client Bootstrap${NC}"
echo -e "${GREEN}======================================${NC}"
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Check Python
echo -e "${CYAN}[1/6] Checking Python installation...${NC}"
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ "$PYTHON_VERSION" == "3.10" ]] || [[ "$PYTHON_VERSION" == "3.11" ]] || [[ "$PYTHON_VERSION" == "3.12" ]]; then
        PYTHON_CMD="python3"
    else
        echo -e "${RED}  Python 3.10+ required. Found: $PYTHON_VERSION${NC}"
        exit 1
    fi
else
    echo -e "${RED}  Python 3 not found!${NC}"
    exit 1
fi
echo "  Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Step 2: Create directories
echo -e "${CYAN}[2/6] Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/mcp_bridge"
mkdir -p "$INSTALL_DIR/subscriber_node/crypto"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$HOME/.config/mcp"
echo "  Install dir: $INSTALL_DIR"

# Step 3: Copy client files
echo -e "${CYAN}[3/6] Copying client files...${NC}"
cp -r "$SCRIPT_DIR/mcp_bridge/"* "$INSTALL_DIR/mcp_bridge/"
cp -r "$SCRIPT_DIR/subscriber_node/"* "$INSTALL_DIR/subscriber_node/"
echo "  Copied: mcp_bridge, subscriber_node"

# Step 4: Create virtual environment
echo -e "${CYAN}[4/6] Setting up Python environment...${NC}"
VENV_DIR="$INSTALL_DIR/venv"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "  Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip wheel > /dev/null
pip install httpx pyyaml cryptography mcp > /dev/null
echo "  Dependencies installed"

# Step 5: Create configuration
echo -e "${CYAN}[5/6] Creating configuration...${NC}"

cat > "$INSTALL_DIR/config.env" << EOF
# MCP Trust Anchor Client Configuration
TRUST_ANCHOR_URL=$TRUST_ANCHOR_URL
CREDENTIAL_PATH=$HOME/.config/mcp
LOG_LEVEL=INFO
EOF
echo "  Config: $INSTALL_DIR/config.env"

# Create credential template
if [[ ! -f "$HOME/.config/mcp/fortigate_credentials.yaml" ]]; then
    cat > "$HOME/.config/mcp/fortigate_credentials.yaml.template" << 'EOF'
# FortiGate Credentials Template
# Copy to: ~/.config/mcp/fortigate_credentials.yaml

devices:
  my-fortigate:
    host: "192.168.1.1"
    api_token: "YOUR_API_TOKEN_HERE"
    verify_ssl: false

default_lookup:
  "192.168.1.1": "my-fortigate"
EOF
    echo "  Credential template: ~/.config/mcp/fortigate_credentials.yaml.template"
fi

# Step 6: Configure Claude Code
echo -e "${CYAN}[6/6] Configuring Claude Code...${NC}"

if [[ "$SKIP_CLAUDE" == "true" ]]; then
    echo "  Skipped (--skip-claude)"
else
    CLAUDE_CONFIG_DIR="$HOME/.config/claude"
    CLAUDE_CONFIG="$CLAUDE_CONFIG_DIR/claude_code_config.json"

    mkdir -p "$CLAUDE_CONFIG_DIR"

    # MCP server config for Claude Code
    MCP_CONFIG=$(cat << EOF
{
  "mcpServers": {
    "secure-tools": {
      "command": "$VENV_DIR/bin/python",
      "args": ["$INSTALL_DIR/mcp_bridge/MCP-secure-tools-server.py"],
      "env": {
        "TRUST_ANCHOR_URL": "$TRUST_ANCHOR_URL",
        "CREDENTIAL_PATH": "$HOME/.config/mcp"
      }
    }
  }
}
EOF
)

    if [[ -f "$CLAUDE_CONFIG" ]]; then
        echo "  Found existing Claude config"
        # Would need jq to merge properly, for now just notify user
        echo -e "${YELLOW}  Please manually add MCP server to: $CLAUDE_CONFIG${NC}"
        echo "  Server config:"
        echo "$MCP_CONFIG"
    else
        echo "$MCP_CONFIG" > "$CLAUDE_CONFIG"
        echo "  Created: $CLAUDE_CONFIG"
    fi
fi

# Done
echo
echo -e "${GREEN}Installation Complete!${NC}"
echo
echo "Installation directory: $INSTALL_DIR"
echo "Trust Anchor URL: $TRUST_ANCHOR_URL"
echo
echo "Next steps:"
echo "  1. Configure credentials: ~/.config/mcp/fortigate_credentials.yaml"
echo "  2. Restart Claude Code to load the MCP server"
echo "  3. Test: Ask Claude 'list available tools'"
echo
echo "To test manually:"
echo "  source $VENV_DIR/bin/activate"
echo "  python $INSTALL_DIR/mcp_bridge/MCP-secure-tools-server.py"
echo

# Quick connectivity test
echo -e "${CYAN}Testing Trust Anchor connectivity...${NC}"
if curl -s --max-time 5 "$TRUST_ANCHOR_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}  Trust Anchor is reachable!${NC}"
else
    echo -e "${YELLOW}  Could not reach Trust Anchor at $TRUST_ANCHOR_URL${NC}"
    echo "  Make sure the server is running and accessible"
fi
