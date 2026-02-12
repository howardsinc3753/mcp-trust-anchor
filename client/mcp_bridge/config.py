"""
MCP Bridge Configuration

Environment variables override defaults.
"""

import os
from pathlib import Path

# Trust Anchor connection (HTTP for v1)
TRUST_ANCHOR_URL = os.environ.get("TRUST_ANCHOR_URL", "http://localhost:8000")

# TLS Configuration (optional for v1)
# For v2, this would use PKI certificates
VERIFY_SSL = False  # HTTP mode for v1

# MCP Bridge identification
MCP_BRIDGE_VERSION = "1.0.0"

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "60"))

# Credential file locations (searched in order)
CREDENTIAL_SEARCH_PATHS = [
    # User-specific locations
    os.path.expanduser("~/.config/mcp"),
    os.path.expanduser("~/AppData/Local/mcp"),
    # System-wide locations
    "C:/ProgramData/mcp",
    # Project-relative (for development)
    os.path.join(os.path.dirname(__file__), "..", "..", "config"),
]

# Supported credential file patterns
CREDENTIAL_FILE_PATTERNS = [
    "*_credentials.yaml",
    "*_credentials.yml",
]
