"""
Publisher Node Configuration

Configuration settings for the Publisher Node.
"""

import os
import secrets
import logging
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass
class PublisherConfig:
    """Publisher Node configuration."""
    api_key: str
    keys_dir: Path
    key_version: str = "1"
    strict_mode: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        if isinstance(self.keys_dir, str):
            self.keys_dir = Path(self.keys_dir)

        # Read key version if file exists
        version_file = self.keys_dir / "key_version.txt"
        if version_file.exists():
            self.key_version = version_file.read_text().strip()

    @property
    def private_key_path(self) -> Path:
        """Path to private key file."""
        return self.keys_dir / "private.pem"

    @property
    def public_key_path(self) -> Path:
        """Path to public key file."""
        return self.keys_dir / "public.pem"

    def keys_available(self) -> bool:
        """Check if both keys are available."""
        return self.private_key_path.exists() and self.public_key_path.exists()


def _get_default_keys_dir() -> Path:
    """Get default keys directory."""
    # Check environment first
    env_dir = os.environ.get("TRUST_ANCHOR_KEYS_DIR")
    if env_dir:
        return Path(env_dir)

    # Default to /opt/trust-anchor/keys or relative ./keys
    default_path = Path("/opt/trust-anchor/keys")
    if default_path.exists():
        return default_path

    # Fallback to project-relative keys directory
    return Path(__file__).parent.parent / "keys"


def _get_or_generate_api_key() -> str:
    """Get API key from environment or generate one."""
    env_key = os.environ.get("PUBLISHER_API_KEY")

    if env_key:
        return env_key

    # Generate a secure random key for development
    generated_key = secrets.token_urlsafe(32)
    logger.warning(
        f"PUBLISHER_API_KEY not set. Generated development key: {generated_key}"
    )
    logger.warning(
        "Set PUBLISHER_API_KEY environment variable in production!"
    )

    os.environ["PUBLISHER_API_KEY"] = generated_key
    return generated_key


@lru_cache(maxsize=1)
def get_publisher_config() -> PublisherConfig:
    """Get Publisher configuration (cached)."""
    keys_dir = _get_default_keys_dir()
    api_key = _get_or_generate_api_key()
    strict_mode = os.environ.get("PUBLISHER_STRICT_MODE", "true").lower() in ("true", "1", "yes")

    config = PublisherConfig(
        api_key=api_key,
        keys_dir=keys_dir,
        strict_mode=strict_mode,
    )

    logger.info(f"Publisher config loaded: keys_dir={config.keys_dir}, key_version={config.key_version}")

    return config


def clear_config_cache():
    """Clear the configuration cache (for testing)."""
    get_publisher_config.cache_clear()
