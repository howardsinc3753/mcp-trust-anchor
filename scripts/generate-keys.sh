#!/bin/bash
#
# Generate RSA keypair for MCP Trust Anchor
#
# Usage: ./generate-keys.sh [output-dir]
#

set -e

# Default output directory
OUTPUT_DIR="${1:-./keys}"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Generating RSA-2048 keypair...${NC}"
echo

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate private key
PRIVATE_KEY="$OUTPUT_DIR/private.pem"
PUBLIC_KEY="$OUTPUT_DIR/public.pem"

if [[ -f "$PRIVATE_KEY" ]]; then
    echo "Warning: Private key already exists at $PRIVATE_KEY"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Generate RSA-2048 private key
echo "Generating private key..."
openssl genrsa -out "$PRIVATE_KEY" 2048

# Extract public key
echo "Extracting public key..."
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"

# Set permissions
chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo
echo -e "${GREEN}Keys generated successfully!${NC}"
echo
echo "Private key: $PRIVATE_KEY (KEEP SECRET - server only)"
echo "Public key:  $PUBLIC_KEY (distribute to clients)"
echo
echo "Key info:"
openssl rsa -in "$PRIVATE_KEY" -text -noout 2>/dev/null | head -1

# Show fingerprint
echo
echo "Public key fingerprint (SHA256):"
openssl rsa -in "$PRIVATE_KEY" -pubout -outform DER 2>/dev/null | openssl dgst -sha256 | cut -d' ' -f2
