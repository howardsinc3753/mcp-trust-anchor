"""
Subscribers Router - MCP Bridge registration and heartbeat

Endpoints:
- POST /subscribers/register : Register an MCP Bridge endpoint
- POST /subscribers/{id}/heartbeat : Receive heartbeat from endpoint
- GET /subscribers           : List all registered endpoints
- GET /subscribers/{id}      : Get specific endpoint details
- DELETE /subscribers/{id}   : Unregister an endpoint
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscribers", tags=["Subscribers"])


class SubscriberRegistration(BaseModel):
    """Registration request from MCP Bridge"""
    hostname: str
    endpoint_id: Optional[str] = None
    platform: str = "unknown"
    version: str = "unknown"
    capabilities: list[str] = []


class SubscriberHeartbeat(BaseModel):
    """Heartbeat from MCP Bridge"""
    status: str = "online"
    tool_count: int = 0
    last_execution: Optional[str] = None


@router.post("/register")
async def register_subscriber(
    registration: SubscriberRegistration,
    request: Request
):
    """Register a new MCP Bridge endpoint."""
    redis = get_redis()

    # Generate endpoint ID if not provided
    endpoint_id = registration.endpoint_id or f"{registration.hostname}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Get client IP
    ip_address = None
    if request.client:
        ip_address = request.client.host

    now = datetime.now(timezone.utc).isoformat()

    # Store subscriber record
    record = {
        "endpoint_id": endpoint_id,
        "hostname": registration.hostname,
        "platform": registration.platform,
        "version": registration.version,
        "ip_address": ip_address,
        "capabilities": json.dumps(registration.capabilities),
        "status": "online",
        "registered_at": now,
        "last_heartbeat": now,
    }

    redis.hset(f"subscriber:{endpoint_id}", mapping=record)
    redis.sadd("subscribers:all", endpoint_id)
    redis.sadd("subscribers:status:online", endpoint_id)

    logger.info(f"Subscriber registered: {endpoint_id} from {ip_address}")

    return {
        "endpoint_id": endpoint_id,
        "registered_at": now,
        "status": "online",
        "heartbeat_interval_seconds": 60,
    }


@router.post("/{endpoint_id}/heartbeat")
async def subscriber_heartbeat(endpoint_id: str, heartbeat: SubscriberHeartbeat):
    """Receive heartbeat from MCP Bridge."""
    redis = get_redis()

    if not redis.exists(f"subscriber:{endpoint_id}"):
        raise HTTPException(status_code=404, detail="Subscriber not found")

    now = datetime.now(timezone.utc).isoformat()

    # Update heartbeat
    redis.hset(f"subscriber:{endpoint_id}", "last_heartbeat", now)
    redis.hset(f"subscriber:{endpoint_id}", "status", heartbeat.status)
    redis.hset(f"subscriber:{endpoint_id}", "tool_count", heartbeat.tool_count)

    if heartbeat.last_execution:
        redis.hset(f"subscriber:{endpoint_id}", "last_execution", heartbeat.last_execution)

    # Update status index
    redis.srem("subscribers:status:stale", endpoint_id)
    redis.srem("subscribers:status:offline", endpoint_id)
    redis.sadd("subscribers:status:online", endpoint_id)

    return {
        "status": "acknowledged",
        "endpoint_id": endpoint_id,
        "server_time": now,
    }


@router.get("")
async def list_subscribers(status: Optional[str] = None):
    """List all registered subscribers."""
    redis = get_redis()

    if status:
        endpoint_ids = list(redis.smembers(f"subscribers:status:{status}"))
    else:
        endpoint_ids = list(redis.smembers("subscribers:all"))

    subscribers = []
    for endpoint_id in sorted(endpoint_ids):
        record = redis.hgetall(f"subscriber:{endpoint_id}")
        if record:
            # Parse capabilities back to list
            if record.get("capabilities"):
                try:
                    record["capabilities"] = json.loads(record["capabilities"])
                except json.JSONDecodeError:
                    record["capabilities"] = []
            subscribers.append(record)

    return {
        "count": len(subscribers),
        "subscribers": subscribers,
    }


@router.get("/stats")
async def get_subscriber_stats():
    """Get subscriber statistics."""
    redis = get_redis()

    return {
        "total": redis.scard("subscribers:all"),
        "online": redis.scard("subscribers:status:online"),
        "stale": redis.scard("subscribers:status:stale"),
        "offline": redis.scard("subscribers:status:offline"),
    }


@router.get("/{endpoint_id}")
async def get_subscriber(endpoint_id: str):
    """Get details for a specific subscriber."""
    redis = get_redis()

    record = redis.hgetall(f"subscriber:{endpoint_id}")

    if not record:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    # Parse capabilities
    if record.get("capabilities"):
        try:
            record["capabilities"] = json.loads(record["capabilities"])
        except json.JSONDecodeError:
            record["capabilities"] = []

    return record


@router.delete("/{endpoint_id}")
async def delete_subscriber(endpoint_id: str):
    """Unregister a subscriber."""
    redis = get_redis()

    if not redis.exists(f"subscriber:{endpoint_id}"):
        raise HTTPException(status_code=404, detail="Subscriber not found")

    # Remove from indexes
    redis.srem("subscribers:all", endpoint_id)
    redis.srem("subscribers:status:online", endpoint_id)
    redis.srem("subscribers:status:stale", endpoint_id)
    redis.srem("subscribers:status:offline", endpoint_id)

    # Delete record
    redis.delete(f"subscriber:{endpoint_id}")

    logger.info(f"Subscriber deleted: {endpoint_id}")

    return {"status": "deleted", "endpoint_id": endpoint_id}


@router.post("/update-statuses")
async def update_subscriber_statuses():
    """
    Update subscriber statuses based on heartbeat times.

    Transitions:
    - online -> stale (no heartbeat for 5 min)
    - stale -> offline (no heartbeat for 15 min)
    """
    redis = get_redis()

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(minutes=5)
    offline_threshold = now - timedelta(minutes=15)

    updated = {"to_stale": 0, "to_offline": 0}

    for endpoint_id in redis.smembers("subscribers:all"):
        record = redis.hgetall(f"subscriber:{endpoint_id}")
        if not record:
            continue

        last_heartbeat_str = record.get("last_heartbeat", "")
        if not last_heartbeat_str:
            continue

        try:
            last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        current_status = record.get("status", "unknown")

        if last_heartbeat < offline_threshold:
            if current_status != "offline":
                redis.hset(f"subscriber:{endpoint_id}", "status", "offline")
                redis.srem("subscribers:status:online", endpoint_id)
                redis.srem("subscribers:status:stale", endpoint_id)
                redis.sadd("subscribers:status:offline", endpoint_id)
                updated["to_offline"] += 1
        elif last_heartbeat < stale_threshold:
            if current_status == "online":
                redis.hset(f"subscriber:{endpoint_id}", "status", "stale")
                redis.srem("subscribers:status:online", endpoint_id)
                redis.sadd("subscribers:status:stale", endpoint_id)
                updated["to_stale"] += 1

    return {
        "status": "updated",
        "transitions": updated,
        "stats": {
            "total": redis.scard("subscribers:all"),
            "online": redis.scard("subscribers:status:online"),
            "stale": redis.scard("subscribers:status:stale"),
            "offline": redis.scard("subscribers:status:offline"),
        },
    }
