"""
Runbooks Router - Runbook catalog and retrieval

Endpoints:
- GET /runbooks           : List all runbooks
- GET /runbooks/get/{id}  : Get runbook by ID
- GET /runbooks/get/{id}/skills : Get Skills.md for a runbook
- GET /runbooks/get/{id}/steps  : Get execution steps
- POST /runbooks/register : Register a new runbook
"""

import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runbooks", tags=["Runbooks"])


@router.get("")
async def list_runbooks(
    domain: str = Query(None, description="Filter by domain"),
    vendor: str = Query(None, description="Filter by vendor"),
    intent: str = Query(None, description="Filter by intent"),
):
    """List all registered runbooks with optional filters."""
    redis = get_redis()

    all_runbooks = list(redis.smembers("runbooks:all"))

    if domain:
        domain_runbooks = redis.smembers(f"runbooks:domain:{domain}")
        all_runbooks = [r for r in all_runbooks if r in domain_runbooks]

    if vendor:
        vendor_runbooks = redis.smembers(f"runbooks:vendor:{vendor}")
        all_runbooks = [r for r in all_runbooks if r in vendor_runbooks]

    if intent:
        intent_runbooks = redis.smembers(f"runbooks:intent:{intent}")
        all_runbooks = [r for r in all_runbooks if r in intent_runbooks]

    # Get summary info
    runbooks = []
    for runbook_id in sorted(all_runbooks):
        manifest_json = redis.get(f"runbook:{runbook_id}")
        if manifest_json:
            try:
                manifest = json.loads(manifest_json)
                runbooks.append({
                    "runbook_id": runbook_id,
                    "name": manifest.get("name", ""),
                    "description": manifest.get("description", ""),
                    "intent": manifest.get("metadata", {}).get("intent", ""),
                    "step_count": len(manifest.get("steps", [])),
                })
            except json.JSONDecodeError:
                continue

    return {"count": len(runbooks), "runbooks": runbooks}


@router.get("/get/{runbook_id:path}")
async def get_runbook(runbook_id: str):
    """Get a runbook by ID."""
    redis = get_redis()

    manifest_json = redis.get(f"runbook:{runbook_id}")
    if not manifest_json:
        raise HTTPException(status_code=404, detail=f"Runbook not found: {runbook_id}")

    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid runbook manifest")

    return {
        "runbook_id": runbook_id,
        "manifest": manifest,
        "skills_md": redis.get(f"runbook:{runbook_id}:skills"),
        "status": redis.get(f"runbook:{runbook_id}:status") or "draft",
    }


@router.get("/get/{runbook_id:path}/skills")
async def get_runbook_skills(runbook_id: str):
    """Get Skills.md content for a runbook."""
    redis = get_redis()

    if not redis.exists(f"runbook:{runbook_id}"):
        raise HTTPException(status_code=404, detail=f"Runbook not found: {runbook_id}")

    skills = redis.get(f"runbook:{runbook_id}:skills")

    if not skills:
        return {
            "runbook_id": runbook_id,
            "skills": None,
            "message": "No Skills.md found for this runbook"
        }

    return {
        "runbook_id": runbook_id,
        "skills": skills,
        "content_type": "text/markdown"
    }


@router.get("/get/{runbook_id:path}/steps")
async def get_runbook_steps(runbook_id: str):
    """Get execution steps for a runbook."""
    redis = get_redis()

    manifest_json = redis.get(f"runbook:{runbook_id}")
    if not manifest_json:
        raise HTTPException(status_code=404, detail=f"Runbook not found: {runbook_id}")

    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid runbook manifest")

    steps = manifest.get("steps", [])

    return {
        "runbook_id": runbook_id,
        "step_count": len(steps),
        "steps": steps,
    }


@router.get("/for-tool/{tool_canonical_id:path}")
async def get_runbooks_for_tool(tool_canonical_id: str):
    """Get all runbooks that use a specific tool."""
    redis = get_redis()

    runbooks = list(redis.smembers(f"tool:{tool_canonical_id}:runbooks"))

    return {
        "tool_canonical_id": tool_canonical_id,
        "runbook_count": len(runbooks),
        "runbooks": runbooks,
    }


@router.post("/register")
async def register_runbook(data: dict):
    """Register a new runbook."""
    redis = get_redis()

    manifest = data.get("manifest", {})
    runbook_id = manifest.get("runbook_id")

    if not runbook_id:
        raise HTTPException(
            status_code=400,
            detail="manifest.runbook_id is required"
        )

    # Store manifest
    redis.set(f"runbook:{runbook_id}", json.dumps(manifest))

    # Store skills if provided
    if data.get("skills_md"):
        redis.set(f"runbook:{runbook_id}:skills", data["skills_md"])

    # Set status
    redis.set(f"runbook:{runbook_id}:status", "draft")

    # Add to indexes
    redis.sadd("runbooks:all", runbook_id)

    metadata = manifest.get("metadata", {})
    if metadata.get("domain"):
        redis.sadd(f"runbooks:domain:{metadata['domain']}", runbook_id)
    if metadata.get("vendor"):
        redis.sadd(f"runbooks:vendor:{metadata['vendor']}", runbook_id)
    if metadata.get("intent"):
        redis.sadd(f"runbooks:intent:{metadata['intent']}", runbook_id)

    # Index tool relationships
    for step in manifest.get("steps", []):
        tool_id = step.get("tool_canonical_id")
        if tool_id:
            redis.sadd(f"tool:{tool_id}:runbooks", runbook_id)

    logger.info(f"Runbook registered: {runbook_id}")

    return {
        "status": "success",
        "runbook_id": runbook_id,
    }


@router.delete("/delete/{runbook_id:path}")
async def delete_runbook(runbook_id: str):
    """Delete a runbook."""
    redis = get_redis()

    if not redis.exists(f"runbook:{runbook_id}"):
        raise HTTPException(status_code=404, detail=f"Runbook not found: {runbook_id}")

    # Remove from indexes
    redis.srem("runbooks:all", runbook_id)

    for pattern in redis.scan_iter(f"runbooks:*"):
        redis.srem(pattern, runbook_id)

    # Delete all runbook data
    for key in redis.scan_iter(f"runbook:{runbook_id}*"):
        redis.delete(key)

    logger.info(f"Runbook deleted: {runbook_id}")

    return {"status": "deleted", "runbook_id": runbook_id}
