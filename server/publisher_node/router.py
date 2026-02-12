"""
Publisher Node Router

FastAPI router for Publisher endpoints.
All endpoints except /health require X-Publisher-Key authentication.

Endpoints:
- POST /publisher/submit-tool   - Submit new tool for signing
- GET  /publisher/my-tools      - List submitted tools
- GET  /publisher/tool/{id}     - Get tool details
- POST /publisher/certify/{id}  - Certify pending tool
- POST /publisher/reject/{id}   - Reject pending tool
- GET  /publisher/pending       - List pending tools
- GET  /publisher/health        - Health check (no auth)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Depends, Query, status

from .auth import require_publisher_key
from .config import get_publisher_config
from .models import (
    ToolSubmission,
    ToolSubmissionResponse,
    ToolDetailResponse,
    ToolListResponse,
    ToolListItem,
    PendingToolsResponse,
    CertifyRequest,
    CertifyResponse,
    RejectRequest,
    RejectResponse,
    HealthResponse,
    ToolStatus,
)
from .signing import get_signing_service

# Import Redis client
from ..trust_anchor.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publisher", tags=["Publisher"])


# =============================================================================
# HEALTH CHECK (No Authentication)
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Publisher health check. No authentication required."""
    config = get_publisher_config()

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        keys_loaded=config.keys_available(),
        key_version=config.key_version,
    )


# =============================================================================
# TOOL SUBMISSION
# =============================================================================

@router.post(
    "/submit-tool",
    response_model=ToolSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_tool(
    submission: ToolSubmission,
    _: None = Depends(require_publisher_key),
):
    """
    Submit a new tool for signing and certification.

    The tool will be signed with the Trust Anchor private key
    and stored with status 'pending' until manually certified.

    Requires X-Publisher-Key header.
    """
    redis = get_redis()
    canonical_id = submission.manifest.get("canonical_id", "")
    version = submission.manifest.get("version", "")

    logger.info(f"Tool submission received: {canonical_id}")

    # Check if tool already exists
    if redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool version already exists: {canonical_id}",
        )

    # Sign the tool
    signing_service = get_signing_service()
    sign_result = signing_service.sign_tool(
        canonical_id=canonical_id,
        version=version,
        code_python=submission.code_python,
    )

    if not sign_result.success:
        logger.error(f"Failed to sign tool {canonical_id}: {sign_result.error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signing failed: {sign_result.error}",
        )

    # Store in Redis
    now = datetime.now(timezone.utc).isoformat()

    # Store manifest
    redis.set(f"tool:{canonical_id}", json.dumps(submission.manifest))

    # Store code
    redis.set(f"tool:{canonical_id}:code_python", submission.code_python)

    # Store skills if provided
    if submission.skills_md:
        redis.set(f"tool:{canonical_id}:skills", submission.skills_md)

    # Store signature data
    redis.set(f"tool:{canonical_id}:signature", sign_result.signature_b64)
    redis.set(f"tool:{canonical_id}:code_hash", sign_result.code_hash)
    redis.set(f"tool:{canonical_id}:signing_payload", json.dumps(sign_result.signing_payload))
    redis.set(f"tool:{canonical_id}:signed_at", sign_result.signed_at.isoformat())
    redis.set(f"tool:{canonical_id}:signed_by_key", sign_result.key_id)
    redis.set(f"tool:{canonical_id}:submitted_at", now)
    redis.set(f"tool:{canonical_id}:status", "pending")

    # Add to indexes
    redis.sadd("tools:all", canonical_id)
    redis.sadd("tools:status:pending", canonical_id)

    # Add domain/vendor indexes if available
    metadata = submission.manifest.get("metadata", {})
    if metadata.get("domain"):
        redis.sadd(f"tools:domain:{metadata['domain']}", canonical_id)
    if metadata.get("vendor"):
        redis.sadd(f"tools:vendor:{metadata['vendor']}", canonical_id)

    logger.info(f"Tool submitted successfully: {canonical_id}")

    return ToolSubmissionResponse(
        canonical_id=canonical_id,
        status=ToolStatus.PENDING,
        code_hash=sign_result.code_hash,
        signed_at=sign_result.signed_at,
        key_id=sign_result.key_id,
    )


# =============================================================================
# TOOL LISTING
# =============================================================================

@router.get("/my-tools", response_model=ToolListResponse)
async def list_my_tools(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = Depends(require_publisher_key),
):
    """List tools with optional status filter. Requires X-Publisher-Key header."""
    redis = get_redis()

    if status_filter:
        tool_ids = list(redis.smembers(f"tools:status:{status_filter}"))
    else:
        tool_ids = list(redis.smembers("tools:all"))

    # Sort and paginate
    tool_ids = sorted(tool_ids)[offset:offset + limit]

    tools = []
    for canonical_id in tool_ids:
        manifest_json = redis.get(f"tool:{canonical_id}")
        if manifest_json:
            try:
                manifest = json.loads(manifest_json)
                submitted_at = redis.get(f"tool:{canonical_id}:submitted_at")
                tools.append(ToolListItem(
                    canonical_id=canonical_id,
                    name=manifest.get("name", ""),
                    status=ToolStatus(redis.get(f"tool:{canonical_id}:status") or "pending"),
                    submitted_at=datetime.fromisoformat(submitted_at) if submitted_at else datetime.now(timezone.utc),
                ))
            except (json.JSONDecodeError, ValueError):
                continue

    return ToolListResponse(
        tools=tools,
        total=len(tools),
        limit=limit,
        offset=offset,
    )


@router.get("/pending", response_model=PendingToolsResponse)
async def list_pending_tools(
    _: None = Depends(require_publisher_key),
):
    """List all tools awaiting certification. Requires X-Publisher-Key header."""
    redis = get_redis()
    tool_ids = list(redis.smembers("tools:status:pending"))

    tools = []
    for canonical_id in sorted(tool_ids):
        manifest_json = redis.get(f"tool:{canonical_id}")
        if manifest_json:
            try:
                manifest = json.loads(manifest_json)
                submitted_at = redis.get(f"tool:{canonical_id}:submitted_at")
                tools.append(ToolListItem(
                    canonical_id=canonical_id,
                    name=manifest.get("name", ""),
                    status=ToolStatus.PENDING,
                    submitted_at=datetime.fromisoformat(submitted_at) if submitted_at else datetime.now(timezone.utc),
                ))
            except (json.JSONDecodeError, ValueError):
                continue

    return PendingToolsResponse(
        tools=tools,
        count=len(tools),
    )


# =============================================================================
# TOOL DETAILS
# =============================================================================

@router.get("/tool/{canonical_id:path}", response_model=ToolDetailResponse)
async def get_tool_details(
    canonical_id: str,
    _: None = Depends(require_publisher_key),
):
    """Get details of a specific tool. Requires X-Publisher-Key header."""
    canonical_id = unquote(canonical_id)
    redis = get_redis()

    manifest_json = redis.get(f"tool:{canonical_id}")
    if not manifest_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {canonical_id}",
        )

    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid manifest data",
        )

    signed_at_str = redis.get(f"tool:{canonical_id}:signed_at")
    submitted_at_str = redis.get(f"tool:{canonical_id}:submitted_at")
    certified_at_str = redis.get(f"tool:{canonical_id}:certified_at")

    return ToolDetailResponse(
        canonical_id=canonical_id,
        manifest=manifest,
        status=ToolStatus(redis.get(f"tool:{canonical_id}:status") or "pending"),
        code_hash=redis.get(f"tool:{canonical_id}:code_hash") or "",
        signed_at=datetime.fromisoformat(signed_at_str) if signed_at_str else datetime.now(timezone.utc),
        key_id=redis.get(f"tool:{canonical_id}:signed_by_key") or "",
        submitted_at=datetime.fromisoformat(submitted_at_str) if submitted_at_str else datetime.now(timezone.utc),
        certified_at=datetime.fromisoformat(certified_at_str) if certified_at_str else None,
        certified_by=redis.get(f"tool:{canonical_id}:certified_by"),
    )


# =============================================================================
# CERTIFICATION
# =============================================================================

@router.post("/certify/{canonical_id:path}", response_model=CertifyResponse)
async def certify_tool(
    canonical_id: str,
    request: Optional[CertifyRequest] = None,
    _: None = Depends(require_publisher_key),
):
    """Certify a pending tool. Requires X-Publisher-Key header."""
    canonical_id = unquote(canonical_id)
    redis = get_redis()

    # Check tool exists
    if not redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {canonical_id}",
        )

    # Check tool is pending
    current_status = redis.get(f"tool:{canonical_id}:status")
    if current_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool is not pending (current status: {current_status})",
        )

    # Update status
    now = datetime.now(timezone.utc)
    redis.set(f"tool:{canonical_id}:status", "certified")
    redis.set(f"tool:{canonical_id}:certified_at", now.isoformat())
    redis.set(f"tool:{canonical_id}:certified_by", "admin")

    if request and request.notes:
        redis.set(f"tool:{canonical_id}:certification_notes", request.notes)

    # Update indexes
    redis.srem("tools:status:pending", canonical_id)
    redis.sadd("tools:status:certified", canonical_id)

    logger.info(f"Tool certified: {canonical_id}")

    return CertifyResponse(
        canonical_id=canonical_id,
        status=ToolStatus.CERTIFIED,
        certified_at=now,
        certified_by="admin",
    )


@router.post("/reject/{canonical_id:path}", response_model=RejectResponse)
async def reject_tool(
    canonical_id: str,
    request: RejectRequest,
    _: None = Depends(require_publisher_key),
):
    """Reject a pending tool. Requires X-Publisher-Key header."""
    canonical_id = unquote(canonical_id)
    redis = get_redis()

    # Check tool exists
    if not redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {canonical_id}",
        )

    # Check tool is pending
    current_status = redis.get(f"tool:{canonical_id}:status")
    if current_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool is not pending (current status: {current_status})",
        )

    # Update status
    now = datetime.now(timezone.utc)
    redis.set(f"tool:{canonical_id}:status", "rejected")
    redis.set(f"tool:{canonical_id}:rejected_at", now.isoformat())
    redis.set(f"tool:{canonical_id}:rejection_reason", request.reason)

    # Update indexes
    redis.srem("tools:status:pending", canonical_id)
    redis.sadd("tools:status:rejected", canonical_id)

    logger.info(f"Tool rejected: {canonical_id}, reason: {request.reason}")

    return RejectResponse(
        canonical_id=canonical_id,
        status=ToolStatus.REJECTED,
        rejected_at=now,
        reason=request.reason,
    )
