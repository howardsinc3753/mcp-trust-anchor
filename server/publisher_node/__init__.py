"""
Publisher Node - Tool Signing API

Integrated into Trust Anchor as /publisher/* endpoints.
All signing happens server-side using the RSA private key.
"""

from .router import router as publisher_router

__all__ = ["publisher_router"]
