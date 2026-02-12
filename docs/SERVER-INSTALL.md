# Server Installation Guide

This guide covers installing the MCP Trust Anchor server on Rocky Linux 8/9 or RHEL-compatible systems.

## Prerequisites

- Rocky Linux 8/9 or RHEL 8/9
- Python 3.10 or higher
- Redis 6+
- Root access (for production install)
- Network access from client endpoints

## Quick Install

The fastest way to install is using the automated script:

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-trust-anchor.git
cd mcp-trust-anchor

# Run installer as root
sudo ./server/install.sh
```

The installer will:
1. Check Python version
2. Install Redis (if needed)
3. Create directories and virtual environment
4. Generate RSA keypair
5. Install systemd service
6. Start the server

## Manual Installation

### Step 1: Install System Dependencies

```bash
# Install Python 3.11
sudo dnf install python3.11 python3.11-pip

# Install Redis
sudo dnf install redis
sudo systemctl enable redis
sudo systemctl start redis
```

### Step 2: Create Directories

```bash
sudo mkdir -p /opt/trust-anchor/{keys,venv}
sudo mkdir -p /etc/trust-anchor
sudo mkdir -p /var/log/trust-anchor
```

### Step 3: Create Service User

```bash
sudo useradd -r -s /sbin/nologin trust-anchor
```

### Step 4: Install Application

```bash
# Copy server files
sudo cp -r server/trust_anchor /opt/trust-anchor/
sudo cp -r server/publisher_node /opt/trust-anchor/
sudo cp -r server/security /opt/trust-anchor/

# Create virtual environment
sudo python3.11 -m venv /opt/trust-anchor/venv
sudo /opt/trust-anchor/venv/bin/pip install --upgrade pip
sudo /opt/trust-anchor/venv/bin/pip install -r server/requirements.txt

# Set ownership
sudo chown -R trust-anchor:trust-anchor /opt/trust-anchor
sudo chown -R trust-anchor:trust-anchor /var/log/trust-anchor
```

### Step 5: Generate RSA Keys

```bash
# Generate keypair
sudo openssl genrsa -out /opt/trust-anchor/keys/private.pem 2048
sudo openssl rsa -in /opt/trust-anchor/keys/private.pem \
    -pubout -out /opt/trust-anchor/keys/public.pem

# Set permissions
sudo chmod 600 /opt/trust-anchor/keys/private.pem
sudo chmod 644 /opt/trust-anchor/keys/public.pem
sudo chown trust-anchor:trust-anchor /opt/trust-anchor/keys/*.pem
```

### Step 6: Configure Environment

Create `/etc/trust-anchor/trust-anchor.env`:

```bash
# Trust Anchor Configuration
TRUST_ANCHOR_HOST=0.0.0.0
TRUST_ANCHOR_PORT=8000
REDIS_URL=redis://localhost:6379/0
PRIVATE_KEY_PATH=/opt/trust-anchor/keys/private.pem
PUBLIC_KEY_PATH=/opt/trust-anchor/keys/public.pem
LOG_LEVEL=INFO

# Publisher API keys (comma-separated)
PUBLISHER_KEYS=your-secure-key-here
```

### Step 7: Install Systemd Service

Create `/etc/systemd/system/trust-anchor.service`:

```ini
[Unit]
Description=MCP Trust Anchor Server
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=trust-anchor
WorkingDirectory=/opt/trust-anchor
EnvironmentFile=/etc/trust-anchor/trust-anchor.env
ExecStart=/opt/trust-anchor/venv/bin/uvicorn trust_anchor.main:app \
    --host ${TRUST_ANCHOR_HOST} --port ${TRUST_ANCHOR_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trust-anchor
sudo systemctl start trust-anchor
```

## Verification

### Check Service Status

```bash
sudo systemctl status trust-anchor
```

### Test Health Endpoint

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","timestamp":"..."}
```

### Test Public Key Endpoint

```bash
curl http://localhost:8000/keys/public
# Expected: {"public_key":"-----BEGIN PUBLIC KEY-----\n..."}
```

### Run Test Suite

```bash
./scripts/test-installation.sh http://localhost:8000
```

## Firewall Configuration

Open port 8000 for client access:

```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## Load Sample Tools

After the server is running, load the sample tools:

```bash
cd /path/to/mcp-trust-anchor
python tools/register-tools.py --server http://localhost:8000
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_ANCHOR_HOST` | `0.0.0.0` | Bind address |
| `TRUST_ANCHOR_PORT` | `8000` | HTTP port |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `PRIVATE_KEY_PATH` | `/opt/trust-anchor/keys/private.pem` | RSA private key path |
| `PUBLIC_KEY_PATH` | `/opt/trust-anchor/keys/public.pem` | RSA public key path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PUBLISHER_KEYS` | `dev-publisher-key` | Comma-separated publisher API keys |

## Troubleshooting

### Service Won't Start

Check logs:
```bash
sudo journalctl -u trust-anchor -f
```

Common issues:
- **Redis not running**: `sudo systemctl start redis`
- **Key file permissions**: Ensure trust-anchor user can read key files
- **Port in use**: Check if another service uses port 8000

### Connection Refused

- Check firewall: `sudo firewall-cmd --list-ports`
- Check binding: `ss -tlnp | grep 8000`

### Signature Verification Fails

- Ensure keypair was generated correctly
- Check key file permissions
- Verify public key is accessible at `/keys/public`

## Backup and Recovery

### Backup Redis Data

```bash
# Trigger RDB snapshot
redis-cli BGSAVE

# Copy RDB file
sudo cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

### Backup Keys

```bash
sudo cp /opt/trust-anchor/keys/*.pem /backup/keys/
```

### Key Rotation

1. Generate new keypair
2. Re-sign all tools with new key
3. Clients will auto-fetch new public key (24h cache)

## Development Mode

For local development without systemd:

```bash
./server/install.sh --dev

# Start manually
source .local/venv/bin/activate
export $(cat .local/config/trust-anchor.env | xargs)
uvicorn trust_anchor.main:app --reload --host 0.0.0.0 --port 8000
```
