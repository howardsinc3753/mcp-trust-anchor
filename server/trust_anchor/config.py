"""
Configuration for MCP Trust Anchor

Simplified configuration for the standalone Trust Anchor server.
HTTP-only for v1 (no mTLS).
"""

import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Default ports
TRUST_ANCHOR_PORT = 8000
REDIS_PORT = 6379


class Settings(BaseModel):
    """Application settings loaded from environment"""

    # Application
    app_name: str = "MCP Trust Anchor"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = TRUST_ANCHOR_PORT

    # Redis
    redis_host: str = "localhost"
    redis_port: int = REDIS_PORT
    redis_db: int = 0
    redis_password: str | None = None

    # Master Node Identity
    master_node_id: str = "TRUST-ANCHOR-001"

    # Keys directory
    keys_dir: Path = Path("/opt/trust-anchor/keys")

    # Publisher API key
    publisher_api_key: str = "test-publisher-key-2025"

    class Config:
        env_prefix = "MCP_"
        arbitrary_types_allowed = True


def get_settings() -> Settings:
    """Get application settings from environment"""
    keys_dir_str = os.getenv("TRUST_ANCHOR_KEYS_DIR", "/opt/trust-anchor/keys")

    return Settings(
        app_name=os.getenv("MCP_APP_NAME", "MCP Trust Anchor"),
        app_version=os.getenv("MCP_APP_VERSION", "1.0.0"),
        debug=os.getenv("MCP_DEBUG", "false").lower() == "true",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", str(TRUST_ANCHOR_PORT))),
        redis_host=os.getenv("MCP_REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("MCP_REDIS_PORT", str(REDIS_PORT))),
        redis_db=int(os.getenv("MCP_REDIS_DB", "0")),
        redis_password=os.getenv("MCP_REDIS_PASSWORD"),
        master_node_id=os.getenv("MCP_MASTER_NODE_ID", "TRUST-ANCHOR-001"),
        keys_dir=Path(keys_dir_str),
        publisher_api_key=os.getenv("PUBLISHER_API_KEY", "test-publisher-key-2025"),
    )


settings = get_settings()
