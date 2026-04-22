# MCP Trust Anchor Server — container image
#
# Used by docker-compose.yml at the repo root. If you're doing a native install,
# you don't need this — see server/install.sh.

FROM python:3.11-slim

WORKDIR /opt/trust-anchor

# OS deps: openssl for first-run key generation, curl for healthchecks
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY trust_anchor ./trust_anchor
COPY publisher_node ./publisher_node
COPY security ./security

# Entrypoint: generate RSA keypair on first boot if missing, then launch uvicorn.
# Keys live on a volume, so they persist across container restarts.
COPY <<'EOF' /usr/local/bin/entrypoint.sh
#!/bin/sh
set -e

KEYS_DIR="${KEYS_DIR:-/opt/trust-anchor/keys}"
mkdir -p "$KEYS_DIR"

if [ ! -f "$KEYS_DIR/private.pem" ]; then
  echo "[entrypoint] No RSA keypair found — generating one-time keypair at $KEYS_DIR"
  openssl genrsa -out "$KEYS_DIR/private.pem" 2048 2>/dev/null
  openssl rsa -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem" 2>/dev/null
  chmod 600 "$KEYS_DIR/private.pem"
  chmod 644 "$KEYS_DIR/public.pem"
  echo "[entrypoint] Keypair generated. To rotate: docker volume rm trust-anchor-keys"
fi

exec uvicorn trust_anchor.main:app \
    --host "${TRUST_ANCHOR_HOST:-0.0.0.0}" \
    --port "${TRUST_ANCHOR_PORT:-8000}"
EOF

RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
