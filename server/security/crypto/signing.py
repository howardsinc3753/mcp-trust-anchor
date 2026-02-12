"""
Manifest Signing and Verification Module

Provides RSA-based signing and verification for tool manifests.

Algorithm Details:
- Key: RSA-2048
- Padding: PKCS1v15
- Hash: SHA-256
- Encoding: Base64 for signature transport
"""

import os
import base64
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Cryptography imports
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .canonicalize import canonicalize_manifest
from .keys import KeyManager

logger = logging.getLogger(__name__)


# Break-glass environment variables
BREAK_GLASS_ENV = "TRUST_ANCHOR_BREAK_GLASS"
SKIP_SIGNING_ENV = "TRUST_ANCHOR_SKIP_SIGNING"


def is_break_glass_enabled() -> bool:
    """Check if break-glass mode is enabled."""
    return os.environ.get(BREAK_GLASS_ENV, "").lower() in ("1", "true", "yes")


def is_signing_skip_enabled() -> bool:
    """Check if signing verification should be skipped."""
    return (
        os.environ.get(SKIP_SIGNING_ENV, "").lower() in ("1", "true", "yes")
        or is_break_glass_enabled()
    )


@dataclass
class SigningResult:
    """Result of a signing operation."""
    success: bool
    signature: Optional[str]  # Base64-encoded signature
    canonical_hash: Optional[str]  # SHA256 of canonical form
    error: Optional[str] = None
    signed_at: Optional[str] = None
    key_version: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of a verification operation."""
    valid: bool
    reason: str
    message: str
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class ManifestSigner:
    """
    Signs tool manifests using Trust Anchor private key.

    This class is used by the Trust Anchor server to sign
    manifests when tools are registered.
    """

    def __init__(self, key_manager: KeyManager):
        """Initialize signer with key manager."""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography package not installed")

        self.key_manager = key_manager
        logger.info("ManifestSigner initialized")

    def sign(self, manifest: Dict[str, Any]) -> SigningResult:
        """
        Sign a tool manifest.

        Steps:
        1. Canonicalize manifest to deterministic JSON
        2. Sign with private key using RSA-PKCS1v15-SHA256
        3. Encode signature as base64
        """
        logger.info(f"Signing manifest: {manifest.get('canonical_id', 'unknown')}")

        try:
            # Get private key
            private_key = self.key_manager.get_private_key()

            # Canonicalize
            canonical = canonicalize_manifest(manifest)

            # Compute hash for reference
            import hashlib
            canonical_hash = hashlib.sha256(canonical).hexdigest()

            # Sign
            signature_bytes = private_key.sign(
                canonical,
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            # Encode
            signature_b64 = base64.b64encode(signature_bytes).decode('ascii')

            result = SigningResult(
                success=True,
                signature=signature_b64,
                canonical_hash=canonical_hash,
                signed_at=datetime.utcnow().isoformat() + "Z",
                key_version=self.key_manager.get_version()
            )

            logger.info(f"Manifest signed: hash={canonical_hash[:16]}...")
            return result

        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return SigningResult(
                success=False,
                signature=None,
                canonical_hash=None,
                error=str(e)
            )


class SignatureVerifier:
    """
    Verifies manifest signatures using Trust Anchor public key.

    This class is used by MCP Bridge to verify tool integrity
    before execution.
    """

    def __init__(self, public_key_pem: bytes):
        """Initialize verifier with public key."""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography package not installed")

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        self._public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend()
        )
        logger.info("SignatureVerifier initialized")

    def verify(
        self,
        manifest: Dict[str, Any],
        signature_b64: str
    ) -> VerificationResult:
        """
        Verify manifest signature.

        Steps:
        1. Check for break-glass bypass
        2. Canonicalize manifest
        3. Decode base64 signature
        4. Verify with public key
        """
        canonical_id = manifest.get("canonical_id", "unknown")
        logger.info(f"Verifying signature: {canonical_id}")

        # Check break-glass
        if is_signing_skip_enabled():
            logger.critical(
                f"BREAK-GLASS: Signature verification BYPASSED for {canonical_id}."
            )
            return VerificationResult(
                valid=True,
                reason="BREAK_GLASS_BYPASS",
                message="Signature verification bypassed (break-glass mode)",
                details={"warning": "SECURITY BYPASS ACTIVE"}
            )

        try:
            # Canonicalize
            canonical = canonicalize_manifest(manifest)

            # Decode signature
            try:
                signature = base64.b64decode(signature_b64)
            except Exception as e:
                return VerificationResult(
                    valid=False,
                    reason="INVALID_SIGNATURE_FORMAT",
                    message=f"Could not decode signature: {e}"
                )

            # Verify
            try:
                self._public_key.verify(
                    signature,
                    canonical,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except InvalidSignature:
                logger.warning(f"SECURITY: Invalid signature for {canonical_id}")
                return VerificationResult(
                    valid=False,
                    reason="INVALID_SIGNATURE",
                    message="Signature does not match manifest - possible tampering",
                    details={"canonical_id": canonical_id}
                )

            # Success
            logger.info(f"Signature valid: {canonical_id}")
            return VerificationResult(
                valid=True,
                reason="VALID",
                message="Signature verification successful",
                details={"canonical_id": canonical_id}
            )

        except Exception as e:
            logger.error(f"Verification error: {e}")
            return VerificationResult(
                valid=False,
                reason="VERIFICATION_ERROR",
                message=f"Unexpected error: {e}"
            )

    @classmethod
    def from_pem_file(cls, pem_path: str) -> "SignatureVerifier":
        """Create verifier from PEM file path."""
        from pathlib import Path
        pem_data = Path(pem_path).read_bytes()
        return cls(pem_data)


def sign_manifest(
    manifest: Dict[str, Any],
    key_manager: KeyManager
) -> Tuple[str, str]:
    """
    Sign a manifest and return signature + hash.

    Convenience function for simple signing.
    """
    signer = ManifestSigner(key_manager)
    result = signer.sign(manifest)
    if not result.success:
        raise Exception(f"Signing failed: {result.error}")
    return result.signature, result.canonical_hash


def verify_manifest(
    manifest: Dict[str, Any],
    signature_b64: str,
    public_key_pem: bytes
) -> bool:
    """
    Verify a manifest signature.

    Convenience function for simple verification.
    """
    verifier = SignatureVerifier(public_key_pem)
    result = verifier.verify(manifest, signature_b64)
    return result.valid
