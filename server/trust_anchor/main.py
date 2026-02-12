"""
MCP Trust Anchor - FastAPI Application

Central authority for tool signing and verification.
Serves as the Trust Anchor for the MCP tool registry.

Endpoints:
- /tools/*      : Tool catalog and retrieval
- /keys/*       : Public key distribution
- /runbooks/*   : Runbook catalog
- /subscribers/*: MCP Bridge registration
- /publisher/*  : Tool signing API (requires X-Publisher-Key)
"""

import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .config import settings
from .redis_client import get_redis_client, get_redis
from .routers import tools_router, keys_router, runbooks_router, subscribers_router

# Import Publisher router
from ..publisher_node import publisher_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("trust-anchor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup and shutdown."""
    logger.info("=" * 60)
    logger.info("MCP TRUST ANCHOR STARTING")
    logger.info("=" * 60)

    # Test Redis connection
    logger.info("Checking Redis connectivity...")
    redis_client = get_redis_client()
    if redis_client.ping():
        logger.info("Redis connection: OK")
    else:
        logger.error("Redis connection: FAILED")
        logger.error("Trust Anchor requires Redis. Please start Redis first.")

    # Check if keys exist
    from pathlib import Path
    keys_dir = settings.keys_dir
    if (keys_dir / "private.pem").exists() and (keys_dir / "public.pem").exists():
        logger.info(f"Signing keys: OK ({keys_dir})")
    else:
        logger.warning(f"Signing keys: NOT FOUND ({keys_dir})")
        logger.warning("Run /keys/generate or scripts/generate-keys.sh to create keys")

    logger.info("=" * 60)
    logger.info("MCP TRUST ANCHOR READY")
    logger.info(f"Host: {settings.host}:{settings.port}")
    logger.info(f"Docs: http://{settings.host}:{settings.port}/docs")
    logger.info("=" * 60)

    yield  # Application runs

    # Shutdown
    logger.info("MCP Trust Anchor shutting down...")


# OpenAPI description
openapi_description = """
# MCP Trust Anchor API

Central authority for the MCP tool signing and verification system.

## Authentication

### Public Endpoints (No Auth)
- `/health`, `/version`, `/docs`
- `/keys/public` - Get public key for verification
- `/tools`, `/tools/*` - Tool catalog
- `/runbooks`, `/runbooks/*` - Runbook catalog

### API Key Authentication (Publisher API)
Publisher endpoints require the `X-Publisher-Key` header:

```
X-Publisher-Key: your-api-key-here
```

**Endpoints:** `/publisher/submit-tool`, `/publisher/certify/*`, `/publisher/pending`

## Quick Start

### 1. Get Public Key
```bash
curl http://trust-anchor:8000/keys/public
```

### 2. Submit a Tool
```bash
curl -X POST http://trust-anchor:8000/publisher/submit-tool \\
  -H "Content-Type: application/json" \\
  -H "X-Publisher-Key: your-api-key" \\
  -d @tool-submission.json
```

### 3. Certify the Tool
```bash
curl -X POST http://trust-anchor:8000/publisher/certify/org.example.tool%2F1.0.0 \\
  -H "X-Publisher-Key: your-api-key"
```

### 4. List Certified Tools
```bash
curl http://trust-anchor:8000/tools?status=certified
```
"""

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=openapi_description,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Include routers
app.include_router(tools_router)
app.include_router(keys_router)
app.include_router(runbooks_router)
app.include_router(subscribers_router)
app.include_router(publisher_router)


# =============================================================================
# Core Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "master_node_id": settings.master_node_id,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    redis_client = get_redis_client()
    redis_ok = redis_client.ping()

    # Check keys
    from pathlib import Path
    keys_ok = (settings.keys_dir / "private.pem").exists()

    if redis_ok and keys_ok:
        status = "healthy"
        http_status = 200
    elif redis_ok and not keys_ok:
        status = "degraded"  # Can operate but can't sign tools
        http_status = 200
    else:
        status = "unhealthy"
        http_status = 503

    return JSONResponse(
        status_code=http_status,
        content={
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "redis": "ok" if redis_ok else "failed",
                "keys": "ok" if keys_ok else "missing",
            },
            "master_node_id": settings.master_node_id,
        },
    )


@app.get("/version")
async def version():
    """Version info endpoint"""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "api_version": "v1",
        "master_node_id": settings.master_node_id,
    }


@app.get("/ping-redis")
async def ping_redis():
    """Test Redis connectivity"""
    redis_client = get_redis_client()

    if not redis_client.ping():
        raise HTTPException(status_code=503, detail="Redis connection failed")

    info = redis_client.get_info()
    return {
        "status": "connected",
        "redis_info": info,
    }


def main():
    """Run the Trust Anchor server."""
    uvicorn.run(
        "server.trust_anchor.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
