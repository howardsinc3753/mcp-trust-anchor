"""
Keys Router - Public key distribution for signature verification

Endpoints:
- GET /keys/public    : Retrieve public key for signature verification
- GET /keys/status    : Key status and rotation info
- GET /keys/fingerprint : Get key fingerprint
- POST /keys/generate : Generate new signing keys (admin)
"""

import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keys", tags=["Keys"])

# Key storage configuration
KEYS_DIR = Path(__file__).parent.parent.parent.parent / "keys"

# Algorithm identifier
SIGNING_ALGORITHM = "RSA-2048-PKCS1v15-SHA256"


def _get_key_manager():
    """Get or create the KeyManager instance."""
    from ...security.crypto.keys import KeyManager
    return KeyManager(str(KEYS_DIR))


def _get_public_key_pem() -> str:
    """Load the public key in PEM format."""
    public_key_path = KEYS_DIR / "public.pem"

    if not public_key_path.exists():
        logger.error(f"Public key not found: {public_key_path}")
        raise HTTPException(
            status_code=500,
            detail="Public key not configured. Run key generation."
        )

    try:
        return public_key_path.read_text()
    except IOError as e:
        logger.error(f"Cannot read public key: {e}")
        raise HTTPException(
            status_code=500,
            detail="Cannot read public key"
        )


def _get_key_version() -> str:
    """Get current key version from metadata."""
    version_path = KEYS_DIR / "key_version.txt"

    if version_path.exists():
        try:
            return version_path.read_text().strip()
        except Exception:
            pass

    return "1"


def _get_key_created_at() -> str:
    """Get key creation timestamp."""
    public_key_path = KEYS_DIR / "public.pem"

    if public_key_path.exists():
        mtime = public_key_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).isoformat()

    return datetime.now().isoformat()


@router.get("/public")
async def get_public_key():
    """
    Get the Trust Anchor's public key for signature verification.

    Returns:
        - public_key: PEM-encoded RSA public key
        - version: Key version identifier
        - algorithm: Signing algorithm identifier
        - created_at: Key creation timestamp
    """
    try:
        public_key = _get_public_key_pem()
        version = _get_key_version()
        created_at = _get_key_created_at()

        logger.info(f"Public key requested, version={version}")

        return {
            "public_key": public_key,
            "version": version,
            "algorithm": SIGNING_ALGORITHM,
            "created_at": created_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_public_key: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_key_status():
    """
    Get key status and metadata.
    """
    public_key_path = KEYS_DIR / "public.pem"
    private_key_path = KEYS_DIR / "private.pem"

    status = {
        "initialized": public_key_path.exists() and private_key_path.exists(),
        "public_key_exists": public_key_path.exists(),
        "private_key_exists": private_key_path.exists(),
        "version": _get_key_version() if public_key_path.exists() else None,
        "created_at": _get_key_created_at() if public_key_path.exists() else None,
        "algorithm": SIGNING_ALGORITHM,
        "keys_directory": str(KEYS_DIR),
    }

    if not status["initialized"]:
        status["message"] = "Keys not initialized. Run key generation."

    return status


@router.post("/generate")
async def generate_keys():
    """
    Generate new signing keys.

    WARNING: This will overwrite existing keys.
    """
    try:
        key_manager = _get_key_manager()
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        metadata = key_manager.generate_keypair()

        logger.info(f"Keys generated: version={metadata.version}")

        return {
            "status": "success",
            "message": "Keys generated successfully",
            "version": metadata.version,
            "algorithm": metadata.algorithm,
            "created_at": metadata.generated_at
        }

    except Exception as e:
        logger.error(f"Key generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Key generation failed: {str(e)}"
        )


@router.get("/fingerprint")
async def get_key_fingerprint():
    """Get the public key fingerprint (SHA-256)."""
    import hashlib

    try:
        public_key_pem = _get_public_key_pem()

        fingerprint = hashlib.sha256(
            public_key_pem.encode()
        ).hexdigest()

        formatted = ':'.join(
            fingerprint[i:i+2]
            for i in range(0, len(fingerprint), 2)
        )

        return {
            "fingerprint": fingerprint,
            "formatted": formatted,
            "algorithm": "sha256"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fingerprint generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Cannot compute fingerprint"
        )
