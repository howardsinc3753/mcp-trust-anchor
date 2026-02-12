"""
Publisher Node Authentication

API key authentication middleware for Publisher endpoints.
All /publisher/* endpoints (except /health) require the X-Publisher-Key header.
"""

import logging
import secrets
from typing import Optional
from fastapi import HTTPException, Header, status

from .config import get_publisher_config

logger = logging.getLogger(__name__)

# Header name for API key
PUBLISHER_KEY_HEADER = "X-Publisher-Key"


def _constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(val1.encode(), val2.encode())


async def require_publisher_key(
    x_publisher_key: Optional[str] = Header(None, alias="X-Publisher-Key")
) -> None:
    """
    FastAPI dependency that validates the X-Publisher-Key header.

    Raises:
        HTTPException 401: If header is missing or invalid
    """
    if x_publisher_key is None:
        logger.warning("Publisher API access attempted without X-Publisher-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Publisher-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    config = get_publisher_config()

    if not _constant_time_compare(x_publisher_key, config.api_key):
        logger.warning("Publisher API access attempted with invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid publisher API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug("Publisher API key validated successfully")


async def optional_publisher_key(
    x_publisher_key: Optional[str] = Header(None, alias="X-Publisher-Key")
) -> bool:
    """
    FastAPI dependency that checks API key but doesn't require it.

    Returns True if valid key provided, False otherwise.
    """
    if x_publisher_key is None:
        return False

    config = get_publisher_config()
    return _constant_time_compare(x_publisher_key, config.api_key)
