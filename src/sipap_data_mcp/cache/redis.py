"""Redis cache client for SIPAP Data MCP.

Provides async Redis operations for caching tool responses to reduce
database load and improve response times.
"""

import json
import ssl
from typing import Any

import redis.asyncio as redis


class RedisCache:
    """Async Redis cache client.

    Example:
        ```python
        cache = RedisCache(url="redis://localhost:6379/0")
        await cache.connect()

        # Set with TTL
        await cache.set("team:arsenal:stats", {"wins": 10}, ttl=3600)

        # Get
        data = await cache.get("team:arsenal:stats")

        await cache.close()
        ```
    """

    def __init__(self, url: str) -> None:
        """Initialize Redis cache client.

        Args:
            url: Redis connection URL (e.g., "redis://localhost:6379/0")
        """
        self._url = url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis server.

        Raises:
            RuntimeError: If connection fails
        """
        try:
            # ElastiCache Redis requires TLS/SSL connection
            # Convert redis:// to rediss:// for SSL - this enables TLS automatically
            url = self._url.replace("redis://", "rediss://") if self._url.startswith("redis://") else self._url

            self._client = redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                ssl_cert_reqs=ssl.CERT_NONE  # Skip certificate verification for AWS ElastiCache
            )
            # Verify connection
            await self._client.ping()
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Redis: {e}") from e

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _ensure_connected(self) -> None:
        """Ensure Redis client is connected.

        Raises:
            RuntimeError: If client is not connected
        """
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value as dict, or None if not found

        Raises:
            RuntimeError: If client is not connected
        """
        self._ensure_connected()

        assert self._client is not None  # Type narrowing for mypy
        value = await self._client.get(key)

        if value is None:
            return None

        # Deserialize JSON
        result: dict[str, Any] = json.loads(value)
        return result

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds

        Raises:
            RuntimeError: If client is not connected
        """
        self._ensure_connected()

        assert self._client is not None  # Type narrowing for mypy

        # Serialize to JSON
        serialized = json.dumps(value)

        # Set with expiration
        await self._client.setex(key, ttl, serialized)

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if key didn't exist

        Raises:
            RuntimeError: If client is not connected
        """
        self._ensure_connected()

        assert self._client is not None  # Type narrowing for mypy
        result = await self._client.delete(key)

        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise

        Raises:
            RuntimeError: If client is not connected
        """
        self._ensure_connected()

        assert self._client is not None  # Type narrowing for mypy
        result = await self._client.exists(key)

        return result > 0
