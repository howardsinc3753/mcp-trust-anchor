"""
Secure Tool Executor - Cryptographic Verification Before Execution

Executes tools with signature verification:
1. Fetches tool + signature data from Trust Anchor
2. Fetches public key from Trust Anchor (cached 24h)
3. Verifies signature matches the signing payload
4. Verifies code hash matches the code received
5. Only executes if both verifications pass

Break-Glass Mode:
Set environment variables to bypass verification:
- TRUST_ANCHOR_BREAK_GLASS=1    : Bypass ALL security checks
- TRUST_ANCHOR_SKIP_SIGNING=1   : Bypass signature verification only
- TRUST_ANCHOR_SKIP_HASH=1      : Bypass hash verification only

All bypasses are logged at CRITICAL level for audit purposes.
"""

import os
import hashlib
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .client import SubscriberClient, ToolData
from .executor import ToolExecutor, ExecutionResult, ExecutionContext

logger = logging.getLogger(__name__)


# Break-glass environment variables
BREAK_GLASS_ENV = "TRUST_ANCHOR_BREAK_GLASS"
SKIP_SIGNING_ENV = "TRUST_ANCHOR_SKIP_SIGNING"
SKIP_HASH_ENV = "TRUST_ANCHOR_SKIP_HASH"

# Public key cache duration
PUBLIC_KEY_CACHE_TTL = timedelta(hours=24)


def is_break_glass_enabled() -> bool:
    """Check if full break-glass mode is enabled."""
    return os.environ.get(BREAK_GLASS_ENV, "").lower() in ("1", "true", "yes")


def is_signing_skip_enabled() -> bool:
    """Check if signature verification should be skipped."""
    return (
        os.environ.get(SKIP_SIGNING_ENV, "").lower() in ("1", "true", "yes")
        or is_break_glass_enabled()
    )


def is_hash_skip_enabled() -> bool:
    """Check if hash verification should be skipped."""
    return (
        os.environ.get(SKIP_HASH_ENV, "").lower() in ("1", "true", "yes")
        or is_break_glass_enabled()
    )


class VerificationStatus(str, Enum):
    """Status of security verification."""
    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_HASH = "invalid_hash"
    MISSING_SIGNATURE = "missing_signature"
    MISSING_PUBLIC_KEY = "missing_public_key"
    BREAK_GLASS = "break_glass"
    UNSIGNED_TOOL = "unsigned_tool"
    ERROR = "error"


@dataclass
class SignatureData:
    """Signature data fetched from Trust Anchor."""
    signature_b64: str
    code_hash: str
    signing_payload: Dict[str, Any]
    signed_at: Optional[str] = None
    signed_by_key: Optional[str] = None
    status: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of security verification."""
    valid: bool
    status: VerificationStatus
    message: str
    signature_verified: bool = False
    hash_verified: bool = False
    break_glass_used: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecureToolData:
    """Extended tool data with signature information."""
    tool: ToolData
    signature_data: Optional[SignatureData] = None
    is_signed: bool = False


@dataclass
class SecureExecutionResult(ExecutionResult):
    """Execution result with security verification details."""
    verification: Optional[VerificationResult] = None
    security_mode: str = "secure"


@dataclass
class CachedPublicKey:
    """Cached public key with expiration."""
    public_key_pem: bytes
    version: str
    fetched_at: datetime
    expires_at: datetime


class PublicKeyCache:
    """Simple in-memory cache for Trust Anchor public key."""

    def __init__(self):
        self._cached_key: Optional[CachedPublicKey] = None

    def get(self) -> Optional[CachedPublicKey]:
        """Get cached key if not expired."""
        if self._cached_key is None:
            return None

        if datetime.now(timezone.utc) > self._cached_key.expires_at:
            logger.info("Public key cache expired")
            self._cached_key = None
            return None

        return self._cached_key

    def set(self, public_key_pem: bytes, version: str):
        """Cache a public key."""
        now = datetime.now(timezone.utc)
        self._cached_key = CachedPublicKey(
            public_key_pem=public_key_pem,
            version=version,
            fetched_at=now,
            expires_at=now + PUBLIC_KEY_CACHE_TTL,
        )
        logger.info(f"Public key cached: version={version}")

    def invalidate(self):
        """Invalidate the cache."""
        if self._cached_key:
            logger.warning("Public key cache invalidated")
        self._cached_key = None


class SecureSubscriberClient(SubscriberClient):
    """Extended subscriber client with signature data fetching."""

    def __init__(
        self,
        master_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        verify: bool = False
    ):
        super().__init__(master_url, timeout, verify)
        self._public_key_cache = PublicKeyCache()

    def get_signature_data(self, canonical_id: str) -> Optional[SignatureData]:
        """Fetch signature data for a tool."""
        try:
            response = self._client.get(
                f"{self.master_url}/tools/get/{canonical_id}/signature"
            )

            if response.status_code == 404:
                logger.debug(f"No signature data for {canonical_id}")
                return None

            response.raise_for_status()
            data = response.json()

            # Parse signing payload if it's a string
            signing_payload = data.get("signing_payload", {})
            if isinstance(signing_payload, str):
                signing_payload = json.loads(signing_payload)

            return SignatureData(
                signature_b64=data.get("signature", ""),
                code_hash=data.get("code_hash", ""),
                signing_payload=signing_payload,
                signed_at=data.get("signed_at"),
                signed_by_key=data.get("signed_by_key"),
                status=data.get("status"),
            )

        except Exception as e:
            logger.warning(f"Failed to fetch signature data for {canonical_id}: {e}")
            return None

    def get_public_key(self, force_refresh: bool = False) -> Optional[Tuple[bytes, str]]:
        """Fetch Trust Anchor public key (cached 24h)."""
        # Check cache first
        if not force_refresh:
            cached = self._public_key_cache.get()
            if cached:
                logger.debug(f"Using cached public key: version={cached.version}")
                return (cached.public_key_pem, cached.version)

        try:
            response = self._client.get(f"{self.master_url}/keys/public")

            if response.status_code == 404:
                logger.error("Public key endpoint not found")
                return None

            response.raise_for_status()
            data = response.json()

            public_key_pem = data.get("public_key", "")
            version = data.get("version", "1")

            if not public_key_pem:
                logger.error("Empty public key returned from Trust Anchor")
                return None

            # Convert to bytes
            key_bytes = public_key_pem.encode("utf-8")

            # Cache it
            self._public_key_cache.set(key_bytes, version)

            logger.info(f"Fetched public key from Trust Anchor: version={version}")
            return (key_bytes, version)

        except Exception as e:
            logger.error(f"Failed to fetch public key: {e}")
            return None

    def invalidate_public_key_cache(self):
        """Invalidate public key cache."""
        self._public_key_cache.invalidate()

    def get_secure_tool(self, canonical_id: str) -> Optional[SecureToolData]:
        """Fetch tool with signature data."""
        tool = self.get_tool_with_skills(canonical_id)
        if not tool:
            return None

        signature_data = self.get_signature_data(canonical_id)

        return SecureToolData(
            tool=tool,
            signature_data=signature_data,
            is_signed=signature_data is not None and bool(signature_data.signature_b64),
        )


class SecureToolExecutor:
    """
    Secure tool executor with cryptographic verification.

    Wraps the standard ToolExecutor and adds:
    1. Signature verification using Trust Anchor public key
    2. Code hash verification to detect tampering
    3. Break-glass bypass for emergencies
    """

    def __init__(self, client: SecureSubscriberClient):
        self.client = client
        self._base_executor = ToolExecutor(client)
        self._tool_cache: Dict[str, SecureToolData] = {}

    def _get_verifier(self, public_key_pem: bytes):
        """Get SignatureVerifier instance."""
        # Import from server's security module (copied to client)
        try:
            from .crypto.signing import SignatureVerifier
        except ImportError:
            # Fallback: inline implementation
            import base64
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            from cryptography.exceptions import InvalidSignature

            class SignatureVerifier:
                def __init__(self, public_key_pem: bytes):
                    self._public_key = serialization.load_pem_public_key(
                        public_key_pem, backend=default_backend()
                    )

                def verify(self, manifest, signature_b64):
                    try:
                        canonical = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
                        signature = base64.b64decode(signature_b64)
                        self._public_key.verify(signature, canonical, padding.PKCS1v15(), hashes.SHA256())
                        return type('Result', (), {'valid': True, 'reason': 'VALID', 'message': 'OK'})()
                    except InvalidSignature:
                        return type('Result', (), {'valid': False, 'reason': 'INVALID', 'message': 'Signature mismatch'})()
                    except Exception as e:
                        return type('Result', (), {'valid': False, 'reason': 'ERROR', 'message': str(e)})()

            return SignatureVerifier(public_key_pem)

        return SignatureVerifier(public_key_pem)

    def _compute_code_hash(self, code: str) -> str:
        """Compute SHA-256 hash of code."""
        normalized = code.replace('\r\n', '\n').strip()
        code_bytes = normalized.encode('utf-8')
        return hashlib.sha256(code_bytes).hexdigest()

    def verify_tool(self, secure_tool: SecureToolData) -> VerificationResult:
        """Verify tool signature and code hash."""
        canonical_id = secure_tool.tool.canonical_id

        # Check break-glass mode
        if is_break_glass_enabled():
            logger.critical(f"BREAK-GLASS: Bypassing ALL verification for {canonical_id}")
            return VerificationResult(
                valid=True,
                status=VerificationStatus.BREAK_GLASS,
                message="All verification bypassed (break-glass mode)",
                break_glass_used=True,
                details={"warning": "SECURITY BYPASS ACTIVE"}
            )

        # Check if tool is signed
        if not secure_tool.is_signed or not secure_tool.signature_data:
            logger.warning(f"Tool {canonical_id} is not signed")
            return VerificationResult(
                valid=False,
                status=VerificationStatus.UNSIGNED_TOOL,
                message="Tool is not signed - cannot verify integrity",
                details={"canonical_id": canonical_id}
            )

        sig_data = secure_tool.signature_data
        signature_verified = False
        hash_verified = False

        # Verify signature
        if is_signing_skip_enabled():
            logger.critical(f"BREAK-GLASS: Skipping signature verification for {canonical_id}")
            signature_verified = True
        else:
            key_result = self.client.get_public_key()
            if not key_result:
                return VerificationResult(
                    valid=False,
                    status=VerificationStatus.MISSING_PUBLIC_KEY,
                    message="Cannot fetch Trust Anchor public key",
                    details={"canonical_id": canonical_id}
                )

            public_key_pem, key_version = key_result

            try:
                verifier = self._get_verifier(public_key_pem)
                verify_result = verifier.verify(sig_data.signing_payload, sig_data.signature_b64)

                if not verify_result.valid:
                    logger.error(f"SECURITY: Signature verification FAILED for {canonical_id}")
                    self.client.invalidate_public_key_cache()
                    return VerificationResult(
                        valid=False,
                        status=VerificationStatus.INVALID_SIGNATURE,
                        message=f"Signature verification failed: {verify_result.message}",
                        details={"canonical_id": canonical_id, "key_version": key_version}
                    )

                signature_verified = True
                logger.info(f"Signature verified for {canonical_id}")

            except Exception as e:
                logger.error(f"Signature verification error for {canonical_id}: {e}")
                return VerificationResult(
                    valid=False,
                    status=VerificationStatus.ERROR,
                    message=f"Signature verification error: {e}",
                    details={"canonical_id": canonical_id, "error": str(e)}
                )

        # Verify code hash
        if is_hash_skip_enabled():
            logger.critical(f"BREAK-GLASS: Skipping hash verification for {canonical_id}")
            hash_verified = True
        else:
            if not secure_tool.tool.code_python:
                hash_verified = True
            else:
                computed_hash = self._compute_code_hash(secure_tool.tool.code_python)
                expected_hash = sig_data.code_hash or sig_data.signing_payload.get("code_hash_sha256", "")

                if computed_hash != expected_hash:
                    logger.error(f"SECURITY: Hash mismatch for {canonical_id}")
                    return VerificationResult(
                        valid=False,
                        status=VerificationStatus.INVALID_HASH,
                        message="Code hash mismatch - tool code may have been tampered",
                        details={
                            "canonical_id": canonical_id,
                            "expected_hash": expected_hash,
                            "computed_hash": computed_hash,
                        }
                    )

                hash_verified = True
                logger.info(f"Code hash verified for {canonical_id}")

        return VerificationResult(
            valid=True,
            status=VerificationStatus.VALID,
            message="Tool verified successfully",
            signature_verified=signature_verified,
            hash_verified=hash_verified,
            break_glass_used=is_signing_skip_enabled() or is_hash_skip_enabled(),
            details={"canonical_id": canonical_id, "signed_at": sig_data.signed_at}
        )

    def fetch_tool(self, canonical_id: str, use_cache: bool = True) -> Optional[SecureToolData]:
        """Fetch tool with signature data."""
        if use_cache and canonical_id in self._tool_cache:
            return self._tool_cache[canonical_id]

        secure_tool = self.client.get_secure_tool(canonical_id)
        if secure_tool and use_cache:
            self._tool_cache[canonical_id] = secure_tool

        return secure_tool

    def execute(
        self,
        canonical_id: str,
        parameters: dict,
        credentials: Optional[dict] = None,
    ) -> SecureExecutionResult:
        """Execute a tool with security verification."""
        import time
        start_time = time.time()

        # Fetch tool
        secure_tool = self.fetch_tool(canonical_id)
        if not secure_tool:
            return SecureExecutionResult(
                success=False,
                canonical_id=canonical_id,
                error=f"Tool not found: {canonical_id}",
                security_mode="secure",
            )

        # Verify tool
        verification = self.verify_tool(secure_tool)

        if not verification.valid:
            return SecureExecutionResult(
                success=False,
                canonical_id=canonical_id,
                error=f"Security verification failed: {verification.message}",
                verification=verification,
                security_mode="secure",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Execute tool
        tool = secure_tool.tool

        # Check for documentation-only tools
        runtime_language = self._base_executor._get_runtime_language(tool)
        if runtime_language == "none":
            return SecureExecutionResult(
                success=True,
                canonical_id=canonical_id,
                result={
                    "type": "documentation",
                    "content": tool.skills_md or "No Skills.md content available",
                    "manifest": tool.manifest,
                },
                verification=verification,
                security_mode="secure",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not tool.code_python:
            return SecureExecutionResult(
                success=False,
                canonical_id=canonical_id,
                error="Tool has no Python implementation",
                verification=verification,
                security_mode="secure",
            )

        # Build execution context
        context = ExecutionContext(
            parameters=parameters,
            credentials=credentials or {},
            metadata={
                "canonical_id": canonical_id,
                "manifest": tool.manifest,
                "verified": True,
                "verification_status": verification.status.value,
            },
        )

        # Execute in sandbox
        result = self._base_executor._execute_python(tool.code_python, context)

        return SecureExecutionResult(
            success=result.success,
            canonical_id=canonical_id,
            result=result.result,
            error=result.error,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time_ms=(time.time() - start_time) * 1000,
            verification=verification,
            security_mode="secure",
        )

    def clear_cache(self):
        """Clear the tool cache."""
        self._tool_cache.clear()

    def get_cached_tools(self) -> list[str]:
        """Get list of cached tool IDs."""
        return list(self._tool_cache.keys())
