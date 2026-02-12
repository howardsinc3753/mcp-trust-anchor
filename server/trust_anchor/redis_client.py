"""
Redis client for MCP Trust Anchor
"""

import redis
from typing import Optional
from .config import settings


class RedisClient:
    """Redis client wrapper for tool registry operations"""

    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
            )

    @property
    def client(self) -> redis.Redis:
        """Get the Redis client instance"""
        return self._client

    def ping(self) -> bool:
        """Test Redis connectivity"""
        try:
            return self._client.ping()
        except redis.ConnectionError:
            return False

    def get_info(self) -> dict:
        """Get Redis server info"""
        try:
            info = self._client.info()
            return {
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": self._client.dbsize(),
            }
        except redis.ConnectionError:
            return {"error": "Redis connection failed"}


def get_redis_client() -> RedisClient:
    """Get Redis client singleton"""
    return RedisClient()


def get_redis() -> redis.Redis:
    """Get raw Redis connection for dependency injection"""
    return get_redis_client().client
