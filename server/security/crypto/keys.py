"""
Key Management Module

Manages RSA keypairs for the Trust Anchor signing service.

Security Requirements:
- Private key: 600 permissions (owner read/write only)
- Private key: Never transmitted over network
- Public key: Distributed via /keys/public endpoint
"""

import os
import stat
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

# Cryptography imports
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


# Configuration
DEFAULT_KEY_SIZE = 2048
DEFAULT_PUBLIC_EXPONENT = 65537
DEFAULT_KEY_VERSION = "1"


# Exceptions
class KeyError(Exception):
    """Base exception for key operations."""
    pass


class KeyNotFoundError(KeyError):
    """Raised when key file is not found."""
    pass


class KeyGenerationError(KeyError):
    """Raised when key generation fails."""
    pass


@dataclass
class KeyMetadata:
    """Metadata about the current keypair."""
    version: str
    generated_at: str
    key_size: int
    algorithm: str
    public_key_fingerprint: str


class KeyManager:
    """
    Manages RSA keypairs for Trust Anchor signing.

    This class handles:
    - Keypair generation with proper permissions
    - Key loading and validation
    - Public key export for distribution
    """

    def __init__(self, keys_dir: str):
        """Initialize KeyManager."""
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography package not installed. "
                "Run: pip install cryptography"
            )

        self.keys_dir = Path(keys_dir)
        self.private_key_path = self.keys_dir / "private.pem"
        self.public_key_path = self.keys_dir / "public.pem"
        self.version_path = self.keys_dir / "key_version.txt"

        self._private_key = None
        self._public_key = None
        self._version = None

        logger.info(f"KeyManager initialized with keys_dir={keys_dir}")

    def generate_keypair(
        self,
        key_size: int = DEFAULT_KEY_SIZE,
        version: Optional[str] = None
    ) -> KeyMetadata:
        """
        Generate new RSA keypair.

        Creates:
        - private.pem: RSA private key (600 permissions)
        - public.pem: RSA public key
        - key_version.txt: Version identifier
        """
        logger.info(f"Generating new RSA-{key_size} keypair")

        try:
            self.keys_dir.mkdir(parents=True, exist_ok=True)

            # Generate keypair
            private_key = rsa.generate_private_key(
                public_exponent=DEFAULT_PUBLIC_EXPONENT,
                key_size=key_size,
                backend=default_backend()
            )
            public_key = private_key.public_key()

            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            # Serialize public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Write private key with restricted permissions
            self._write_private_key(private_pem)

            # Write public key
            self.public_key_path.write_bytes(public_pem)
            logger.info(f"Public key written to {self.public_key_path}")

            # Write version
            if version is None:
                version = self._next_version()
            self.version_path.write_text(version)

            # Store in memory
            self._private_key = private_key
            self._public_key = public_key
            self._version = version

            # Create metadata
            metadata = KeyMetadata(
                version=version,
                generated_at=datetime.utcnow().isoformat() + "Z",
                key_size=key_size,
                algorithm="RSA-PKCS1v15-SHA256",
                public_key_fingerprint=self._fingerprint(public_pem)
            )

            logger.info(f"Keypair generated: version={version}")
            return metadata

        except Exception as e:
            logger.error(f"Key generation failed: {e}")
            raise KeyGenerationError(f"Failed to generate keypair: {e}")

    def _write_private_key(self, pem_data: bytes):
        """Write private key with secure permissions."""
        self.private_key_path.write_bytes(pem_data)

        # Set permissions to 600 (owner read/write only)
        try:
            os.chmod(self.private_key_path, stat.S_IRUSR | stat.S_IWUSR)
            logger.info(f"Private key written with 600 permissions")
        except Exception as e:
            logger.warning(f"Could not set file permissions (Windows?): {e}")

    def _next_version(self) -> str:
        """Get next version number."""
        if self.version_path.exists():
            try:
                current = int(self.version_path.read_text().strip())
                return str(current + 1)
            except (ValueError, OSError):
                pass
        return DEFAULT_KEY_VERSION

    def _fingerprint(self, pem_data: bytes) -> str:
        """Calculate key fingerprint (first 16 chars of SHA256)."""
        import hashlib
        return hashlib.sha256(pem_data).hexdigest()[:16]

    def load_keys(self) -> bool:
        """Load existing keypair from disk."""
        logger.info("Loading keypair from disk")

        if not self.private_key_path.exists():
            raise KeyNotFoundError(f"Private key not found: {self.private_key_path}")
        if not self.public_key_path.exists():
            raise KeyNotFoundError(f"Public key not found: {self.public_key_path}")

        # Load private key
        try:
            private_pem = self.private_key_path.read_bytes()
            self._private_key = serialization.load_pem_private_key(
                private_pem,
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise KeyError(f"Failed to load private key: {e}")

        # Load public key
        try:
            public_pem = self.public_key_path.read_bytes()
            self._public_key = serialization.load_pem_public_key(
                public_pem,
                backend=default_backend()
            )
        except Exception as e:
            raise KeyError(f"Failed to load public key: {e}")

        # Load version
        if self.version_path.exists():
            self._version = self.version_path.read_text().strip()
        else:
            self._version = DEFAULT_KEY_VERSION

        logger.info(f"Keypair loaded: version={self._version}")
        return True

    def keys_exist(self) -> bool:
        """Check if key files exist."""
        return self.private_key_path.exists() and self.public_key_path.exists()

    def get_private_key(self):
        """Get private key for signing (internal use only)."""
        if self._private_key is None:
            raise KeyError("Private key not loaded. Call load_keys() first.")
        return self._private_key

    def get_public_key(self):
        """Get public key for verification."""
        if self._public_key is None:
            raise KeyError("Public key not loaded. Call load_keys() first.")
        return self._public_key

    def export_public_key(self) -> bytes:
        """Export public key in PEM format for distribution."""
        if self._public_key is None:
            raise KeyError("Public key not loaded. Call load_keys() first.")

        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def get_version(self) -> str:
        """Get current key version."""
        return self._version or DEFAULT_KEY_VERSION


def ensure_keys_exist(keys_dir: str) -> KeyManager:
    """Ensure keys exist, generating if necessary."""
    manager = KeyManager(keys_dir)

    if not manager.keys_exist():
        logger.info("No keys found, generating new keypair")
        manager.generate_keypair()
    else:
        manager.load_keys()

    return manager
