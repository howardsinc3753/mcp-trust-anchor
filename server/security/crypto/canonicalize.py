"""
Manifest Canonicalization Module

Provides deterministic JSON serialization for cryptographic signing.

Why Canonicalization?
- JSON does not define a canonical form
- {"a":1,"b":2} and {"b":2,"a":1} are semantically identical
- But their byte representations differ
- This would cause signature verification to fail

Rules:
1. Keys sorted alphabetically (recursive)
2. No whitespace (compact separators)
3. UTF-8 encoding
4. No trailing newline
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def canonicalize_manifest(manifest: Dict[str, Any]) -> bytes:
    """
    Produce deterministic JSON bytes for signing.

    Args:
        manifest: Dictionary to canonicalize

    Returns:
        UTF-8 encoded bytes of canonical JSON
    """
    canonical_str = json.dumps(
        manifest,
        sort_keys=True,           # Alphabetical key ordering
        separators=(',', ':'),    # No whitespace
        ensure_ascii=False,       # Allow Unicode
        allow_nan=False,          # Strict JSON compliance
    )

    return canonical_str.encode('utf-8')


def canonicalize_for_display(manifest: Dict[str, Any]) -> str:
    """
    Produce deterministic JSON string for display/logging.

    Same as canonicalize_manifest but returns string instead of bytes.
    """
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    )


def hash_canonical(manifest: Dict[str, Any], algorithm: str = "sha256") -> str:
    """
    Hash the canonical form of a manifest.

    Args:
        manifest: Dictionary to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hex-encoded hash string
    """
    import hashlib

    canonical = canonicalize_manifest(manifest)
    hasher = hashlib.new(algorithm)
    hasher.update(canonical)
    return hasher.hexdigest()


def manifests_equal(manifest1: Dict[str, Any], manifest2: Dict[str, Any]) -> bool:
    """
    Check if two manifests are semantically equal.

    Uses canonicalization to compare regardless of key ordering.
    """
    return canonicalize_manifest(manifest1) == canonicalize_manifest(manifest2)
