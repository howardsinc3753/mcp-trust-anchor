"""
Tools Router - Tool catalog and retrieval

Endpoints:
- GET /tools               : List all tools
- GET /tools/get/{id}      : Get tool by canonical ID
- GET /tools/get/{id}/skills : Get Skills.md for a tool
- GET /tools/get/{id}/signature : Get signature data
- POST /tools/register     : Register a new tool
- DELETE /tools/delete/{id} : Delete a tool
"""

import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("")
async def list_tools(
    domain: str = Query(None, description="Filter by domain"),
    vendor: str = Query(None, description="Filter by vendor"),
    status: str = Query(None, description="Filter by status"),
):
    """List all registered tools with optional filters."""
    redis = get_redis()

    # Get all tool IDs
    all_tools = list(redis.smembers("tools:all"))

    if domain:
        domain_tools = redis.smembers(f"tools:domain:{domain}")
        all_tools = [t for t in all_tools if t in domain_tools]

    if vendor:
        vendor_tools = redis.smembers(f"tools:vendor:{vendor}")
        all_tools = [t for t in all_tools if t in vendor_tools]

    if status:
        status_tools = redis.smembers(f"tools:status:{status}")
        all_tools = [t for t in all_tools if t in status_tools]

    # Get summary info for each tool
    tools = []
    for canonical_id in sorted(all_tools):
        manifest_json = redis.get(f"tool:{canonical_id}")
        if manifest_json:
            try:
                manifest = json.loads(manifest_json)
                tools.append({
                    "canonical_id": canonical_id,
                    "name": manifest.get("name", ""),
                    "description": manifest.get("description", ""),
                    "version": manifest.get("version", ""),
                    "status": redis.get(f"tool:{canonical_id}:status") or "draft",
                })
            except json.JSONDecodeError:
                continue

    return {"count": len(tools), "tools": tools}


@router.get("/get/{canonical_id:path}")
async def get_tool(canonical_id: str):
    """Get a tool by canonical ID including manifest and code."""
    redis = get_redis()

    manifest_json = redis.get(f"tool:{canonical_id}")
    if not manifest_json:
        raise HTTPException(status_code=404, detail=f"Tool not found: {canonical_id}")

    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid tool manifest in storage")

    return {
        "canonical_id": canonical_id,
        "manifest": manifest,
        "code_python": redis.get(f"tool:{canonical_id}:code_python"),
        "skills_md": redis.get(f"tool:{canonical_id}:skills"),
        "status": redis.get(f"tool:{canonical_id}:status") or "draft",
        "signed_at": redis.get(f"tool:{canonical_id}:signed_at"),
    }


@router.get("/get/{canonical_id:path}/skills")
async def get_tool_skills(canonical_id: str):
    """Get Skills.md content for a tool."""
    redis = get_redis()

    if not redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(status_code=404, detail=f"Tool not found: {canonical_id}")

    skills = redis.get(f"tool:{canonical_id}:skills")

    if not skills:
        return {
            "canonical_id": canonical_id,
            "skills": None,
            "message": "No Skills.md found for this tool"
        }

    return {
        "canonical_id": canonical_id,
        "skills": skills,
        "content_type": "text/markdown"
    }


@router.get("/get/{canonical_id:path}/signature")
async def get_tool_signature(canonical_id: str):
    """Get signature data for a tool (for verification)."""
    redis = get_redis()

    if not redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(status_code=404, detail=f"Tool not found: {canonical_id}")

    signature = redis.get(f"tool:{canonical_id}:signature")
    if not signature:
        raise HTTPException(status_code=404, detail="Tool is not signed")

    return {
        "canonical_id": canonical_id,
        "signature": signature,
        "code_hash": redis.get(f"tool:{canonical_id}:code_hash"),
        "signing_payload": redis.get(f"tool:{canonical_id}:signing_payload"),
        "signed_at": redis.get(f"tool:{canonical_id}:signed_at"),
        "signed_by_key": redis.get(f"tool:{canonical_id}:signed_by_key"),
        "status": redis.get(f"tool:{canonical_id}:status"),
    }


@router.post("/register")
async def register_tool(data: dict):
    """
    Register a tool (without signing).

    Use /publisher/submit-tool for signed tool submission.
    """
    redis = get_redis()

    manifest = data.get("manifest", {})
    canonical_id = manifest.get("canonical_id")

    if not canonical_id:
        raise HTTPException(
            status_code=400,
            detail="manifest.canonical_id is required"
        )

    # Store manifest
    redis.set(f"tool:{canonical_id}", json.dumps(manifest))

    # Store code if provided
    if data.get("code_python"):
        redis.set(f"tool:{canonical_id}:code_python", data["code_python"])

    # Store skills if provided
    if data.get("skills_md"):
        redis.set(f"tool:{canonical_id}:skills", data["skills_md"])

    # Set status
    redis.set(f"tool:{canonical_id}:status", "draft")

    # Add to indexes
    redis.sadd("tools:all", canonical_id)

    metadata = manifest.get("metadata", {})
    if metadata.get("domain"):
        redis.sadd(f"tools:domain:{metadata['domain']}", canonical_id)
    if metadata.get("vendor"):
        redis.sadd(f"tools:vendor:{metadata['vendor']}", canonical_id)

    redis.sadd("tools:status:draft", canonical_id)

    logger.info(f"Tool registered: {canonical_id}")

    return {
        "status": "success",
        "canonical_id": canonical_id,
        "message": "Tool registered. Use /publisher/submit-tool for signed submission."
    }


@router.delete("/delete/{canonical_id:path}")
async def delete_tool(canonical_id: str):
    """Delete a tool from the registry."""
    redis = get_redis()

    if not redis.exists(f"tool:{canonical_id}"):
        raise HTTPException(status_code=404, detail=f"Tool not found: {canonical_id}")

    # Remove from all indexes
    redis.srem("tools:all", canonical_id)

    # Remove domain/vendor/status indexes
    for pattern in redis.scan_iter(f"tools:*"):
        redis.srem(pattern, canonical_id)

    # Delete all tool data
    for key in redis.scan_iter(f"tool:{canonical_id}*"):
        redis.delete(key)

    logger.info(f"Tool deleted: {canonical_id}")

    return {"status": "deleted", "canonical_id": canonical_id}


@router.get("/stats")
async def get_tool_stats():
    """Get tool registry statistics."""
    redis = get_redis()

    total = redis.scard("tools:all")

    # Count by status
    status_counts = {}
    for status in ["draft", "pending", "certified", "rejected", "deprecated"]:
        count = redis.scard(f"tools:status:{status}")
        if count > 0:
            status_counts[status] = count

    return {
        "total_tools": total,
        "by_status": status_counts,
    }
