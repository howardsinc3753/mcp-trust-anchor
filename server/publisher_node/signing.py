"""
Publisher Node Signing Service

Wrapper around security/crypto modules for tool signing.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .config import get_publisher_config
from .models import SigningPayload

logger = logging.getLogger(__name__)


@dataclass
class SigningResult:
    """Result of signing a tool."""
    signature_b64: str
    code_hash: str
    signing_payload: Dict[str, Any]
    signed_at: datetime
    key_id: str
    success: bool = True
    error: Optional[str] = None


class ToolSigningService:
    """
    Service for signing tool code and manifests.

    Handles:
    - Code hash computation (SHA-256)
    - Signing payload creation
    - RSA signature generation
    """

    def __init__(self):
        """Initialize signing service with keys from config."""
        self._config = get_publisher_config()
        self._key_manager = None
        self._signer = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of key manager and signer."""
        if self._initialized:
            return

        if not self._config.keys_available():
            raise RuntimeError(
                f"RSA keys not found at {self._config.keys_dir}. "
                f"Run key generation first."
            )

        # Import here to avoid circular imports
        from ..security.crypto.keys import KeyManager
        from ..security.crypto.signing import ManifestSigner

        # Initialize key manager
        self._key_manager = KeyManager(str(self._config.keys_dir))
        self._key_manager.load_keys()

        # Initialize signer with key manager
        self._signer = ManifestSigner(self._key_manager)

        self._initialized = True
        logger.info(f"ToolSigningService initialized with key version {self._config.key_version}")

    def compute_code_hash(self, code: str) -> str:
        """Compute SHA-256 hash of Python code."""
        normalized = code.replace('\r\n', '\n').strip()
        code_bytes = normalized.encode('utf-8')

        hasher = hashlib.sha256()
        hasher.update(code_bytes)

        return hasher.hexdigest()

    def build_signing_payload(
        self,
        canonical_id: str,
        version: str,
        code_hash: str,
    ) -> SigningPayload:
        """Build the payload that will be signed."""
        return SigningPayload(
            canonical_id=canonical_id,
            version=version,
            code_hash_sha256=code_hash,
            signed_at=datetime.now(timezone.utc),
            key_id=self._config.key_version,
        )

    def sign_tool(
        self,
        canonical_id: str,
        version: str,
        code_python: str,
    ) -> SigningResult:
        """
        Sign a tool's code.

        Full signing flow:
        1. Compute SHA-256 hash of code
        2. Build signing payload
        3. Canonicalize payload
        4. Sign with RSA private key
        """
        try:
            self._ensure_initialized()

            # Step 1: Compute code hash
            code_hash = self.compute_code_hash(code_python)
            logger.debug(f"Computed code hash: {code_hash[:16]}...")

            # Step 2: Build signing payload
            payload = self.build_signing_payload(canonical_id, version, code_hash)
            payload_dict = payload.to_canonical_dict()
            logger.debug(f"Built signing payload for {canonical_id}")

            # Step 3: Sign the payload
            sign_result = self._signer.sign(payload_dict)

            if not sign_result.success:
                logger.error(f"Signing failed: {sign_result.error}")
                return SigningResult(
                    signature_b64="",
                    code_hash=code_hash,
                    signing_payload=payload_dict,
                    signed_at=payload.signed_at,
                    key_id=self._config.key_version,
                    success=False,
                    error=sign_result.error,
                )

            logger.info(f"Successfully signed tool {canonical_id}")

            return SigningResult(
                signature_b64=sign_result.signature,
                code_hash=code_hash,
                signing_payload=payload_dict,
                signed_at=payload.signed_at,
                key_id=self._config.key_version,
                success=True,
            )

        except Exception as e:
            logger.exception(f"Error signing tool {canonical_id}: {e}")
            return SigningResult(
                signature_b64="",
                code_hash="",
                signing_payload={},
                signed_at=datetime.now(timezone.utc),
                key_id=self._config.key_version,
                success=False,
                error=str(e),
            )

    def verify_signature(
        self,
        signing_payload: Dict[str, Any],
        signature_b64: str,
    ) -> bool:
        """Verify a signature (for testing/validation)."""
        try:
            self._ensure_initialized()

            from ..security.crypto.signing import SignatureVerifier

            public_key_pem = self._key_manager.export_public_key()
            verifier = SignatureVerifier(public_key_pem)
            result = verifier.verify(signing_payload, signature_b64)
            return result.valid

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False


# Module-level singleton
_signing_service: Optional[ToolSigningService] = None


def get_signing_service() -> ToolSigningService:
    """Get or create the signing service singleton."""
    global _signing_service
    if _signing_service is None:
        _signing_service = ToolSigningService()
    return _signing_service
