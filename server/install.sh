#!/bin/bash
#
# MCP Trust Anchor - Server Installation Script
# For Rocky Linux 8/9 or RHEL-compatible systems
#
# Usage: sudo ./install.sh [options]
#   --no-redis      Skip Redis installation (use existing)
#   --no-keys       Skip RSA key generation (use existing)
#   --dev           Development mode (no systemd services)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/trust-anchor"
KEYS_DIR="/opt/trust-anchor/keys"
VENV_DIR="/opt/trust-anchor/venv"
CONFIG_DIR="/etc/trust-anchor"
LOG_DIR="/var/log/trust-anchor"
SERVICE_USER="trust-anchor"

# Parse arguments
SKIP_REDIS=false
SKIP_KEYS=false
DEV_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-redis)
            SKIP_REDIS=true
            shift
            ;;
        --no-keys)
            SKIP_KEYS=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}MCP Trust Anchor Server Install${NC}"
echo -e "${GREEN}================================${NC}"
echo

# Check if running as root
if [[ $EUID -ne 0 ]] && [[ "$DEV_MODE" != "true" ]]; then
    echo -e "${RED}Error: This script must be run as root (or use --dev for local install)${NC}"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Check Python version
echo -e "${YELLOW}[1/8] Checking Python version...${NC}"
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$PYTHON_VERSION >= 3.10" | bc -l 2>/dev/null || echo "0") == "1" ]] || \
       [[ "$PYTHON_VERSION" == "3.10" ]] || [[ "$PYTHON_VERSION" == "3.11" ]] || [[ "$PYTHON_VERSION" == "3.12" ]]; then
        PYTHON_CMD="python3"
    else
        echo -e "${RED}Error: Python 3.10+ required. Found: $PYTHON_VERSION${NC}"
        echo "Install with: dnf install python3.11"
        exit 1
    fi
else
    echo -e "${RED}Error: Python 3 not found${NC}"
    echo "Install with: dnf install python3.11"
    exit 1
fi
echo -e "  Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Step 2: Install Redis (if not skipped)
echo -e "${YELLOW}[2/8] Setting up Redis...${NC}"
if [[ "$SKIP_REDIS" == "true" ]]; then
    echo "  Skipped (--no-redis)"
elif command -v redis-server &> /dev/null; then
    echo "  Redis already installed"
else
    echo "  Installing Redis..."
    dnf install -y redis || yum install -y redis
fi

# Start Redis
if [[ "$DEV_MODE" != "true" ]] && [[ "$SKIP_REDIS" != "true" ]]; then
    systemctl enable redis
    systemctl start redis
    echo "  Redis started"
fi

# Step 3: Create directories
echo -e "${YELLOW}[3/8] Creating directories...${NC}"
if [[ "$DEV_MODE" == "true" ]]; then
    INSTALL_DIR="$SCRIPT_DIR/.local"
    KEYS_DIR="$INSTALL_DIR/keys"
    VENV_DIR="$INSTALL_DIR/venv"
    CONFIG_DIR="$INSTALL_DIR/config"
    LOG_DIR="$INSTALL_DIR/logs"
fi

mkdir -p "$INSTALL_DIR"
mkdir -p "$KEYS_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
echo "  Install dir: $INSTALL_DIR"
echo "  Keys dir: $KEYS_DIR"

# Step 4: Create virtual environment
echo -e "${YELLOW}[4/8] Creating Python virtual environment...${NC}"
$PYTHON_CMD -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip wheel
echo "  Virtual environment created at $VENV_DIR"

# Step 5: Install Python dependencies
echo -e "${YELLOW}[5/8] Installing Python dependencies...${NC}"
pip install -r "$SCRIPT_DIR/requirements.txt"
echo "  Dependencies installed"

# Step 6: Generate RSA keys (if not skipped)
echo -e "${YELLOW}[6/8] Setting up RSA keys...${NC}"
if [[ "$SKIP_KEYS" == "true" ]]; then
    echo "  Skipped (--no-keys)"
elif [[ -f "$KEYS_DIR/private.pem" ]]; then
    echo "  Keys already exist at $KEYS_DIR"
else
    echo "  Generating RSA-2048 keypair..."
    openssl genrsa -out "$KEYS_DIR/private.pem" 2048
    openssl rsa -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem"
    chmod 600 "$KEYS_DIR/private.pem"
    chmod 644 "$KEYS_DIR/public.pem"
    echo "  Keys generated at $KEYS_DIR"
fi

# Step 7: Copy application files
echo -e "${YELLOW}[7/8] Copying application files...${NC}"
cp -r "$SCRIPT_DIR/trust_anchor" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/publisher_node" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/security" "$INSTALL_DIR/"

# Create environment file
cat > "$CONFIG_DIR/trust-anchor.env" << EOF
# MCP Trust Anchor Configuration
TRUST_ANCHOR_HOST=0.0.0.0
TRUST_ANCHOR_PORT=8000
REDIS_URL=redis://localhost:6379/0
PRIVATE_KEY_PATH=$KEYS_DIR/private.pem
PUBLIC_KEY_PATH=$KEYS_DIR/public.pem
LOG_LEVEL=INFO
PUBLISHER_KEYS=dev-publisher-key
EOF

echo "  Config file: $CONFIG_DIR/trust-anchor.env"

# Step 8: Install systemd service (if not dev mode)
echo -e "${YELLOW}[8/8] Setting up systemd service...${NC}"
if [[ "$DEV_MODE" == "true" ]]; then
    echo "  Skipped (--dev mode)"
    echo
    echo -e "${GREEN}Development Installation Complete!${NC}"
    echo
    echo "To start the server manually:"
    echo "  source $VENV_DIR/bin/activate"
    echo "  cd $INSTALL_DIR"
    echo "  export \$(cat $CONFIG_DIR/trust-anchor.env | xargs)"
    echo "  uvicorn trust_anchor.main:app --host 0.0.0.0 --port 8000"
else
    # Create service user
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /sbin/nologin "$SERVICE_USER"
    fi
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"

    # Install systemd service
    cat > /etc/systemd/system/trust-anchor.service << EOF
[Unit]
Description=MCP Trust Anchor Server
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_DIR/trust-anchor.env
ExecStart=$VENV_DIR/bin/uvicorn trust_anchor.main:app --host \${TRUST_ANCHOR_HOST} --port \${TRUST_ANCHOR_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable trust-anchor
    systemctl start trust-anchor
    echo "  Service installed and started"

    echo
    echo -e "${GREEN}Installation Complete!${NC}"
    echo
    echo "Service status:"
    systemctl status trust-anchor --no-pager || true
fi

echo
echo "Trust Anchor should now be running at: http://localhost:8000"
echo
echo "Quick test:"
echo "  curl http://localhost:8000/health"
echo
echo "Keys location: $KEYS_DIR"
echo "  - Private key: $KEYS_DIR/private.pem (server only)"
echo "  - Public key: $KEYS_DIR/public.pem (distribute to clients)"
echo
echo "Next steps:"
echo "  1. Configure firewall: firewall-cmd --add-port=8000/tcp --permanent"
echo "  2. Register sample tools: python scripts/load-sample-tools.py --server http://localhost:8000"
echo "  3. Wire up your AI editor: python scripts/configure-editors.py --server http://localhost:8000"
echo
echo -e "${GREEN}Smoke test:${NC}"
echo "  curl http://localhost:8000/health    # should return {\"status\":\"healthy\"}"
echo
echo -e "${YELLOW}Tip:${NC} If you just want to evaluate locally and don't need systemd, the Docker path"
echo "is often easier: from the repo root, run  ${GREEN}docker compose up -d${NC}  instead."
echo "See QUICKSTART.md for both paths side by side."
