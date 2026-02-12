"""
Cryptographic Signing Module

Provides RSA-based signing and verification for tool manifests.

Algorithm: RSA-2048 + PKCS1v15 + SHA256
"""

from .signing import ManifestSigner, SignatureVerifier
from .keys import KeyManager
from .canonicalize import canonicalize_manifest

__all__ = [
    "ManifestSigner",
    "SignatureVerifier",
    "KeyManager",
    "canonicalize_manifest",
]
