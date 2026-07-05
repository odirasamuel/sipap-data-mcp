"""Tests for Redis cache client.

Tests cover:
- Connection management (connect, close)
- Get/set operations with TTL
- JSON serialization/deserialization
- Cache miss handling
- Error handling (connection failures)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestRedisCache:
    """Test suite for RedisCache client."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test RedisCache connects to Redis successfully."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")

            # Act
            await cache.connect()

            # Assert
            assert cache._client is not None
            mock_from_url.assert_called_once()
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test RedisCache handles connection failures gracefully."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")

            cache = RedisCache(url="redis://localhost:6379/0")

            # Act & Assert
            with pytest.raises(RuntimeError, match="Failed to connect to Redis"):
                await cache.connect()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test RedisCache closes connection properly."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.close = AsyncMock()
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            await cache.close()

            # Assert
            mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_success(self):
        """Test RedisCache.get retrieves cached value."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            cached_data = {"team": "Arsenal", "wins": 10}
            mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            result = await cache.get("team:arsenal:stats")

            # Assert
            assert result == cached_data
            mock_redis.get.assert_called_once_with("team:arsenal:stats")

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test RedisCache.get returns None on cache miss."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.get = AsyncMock(return_value=None)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            result = await cache.get("nonexistent:key")

            # Assert
            assert result is None
            mock_redis.get.assert_called_once_with("nonexistent:key")

    @pytest.mark.asyncio
    async def test_get_not_connected(self):
        """Test RedisCache.get raises error when not connected."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        cache = RedisCache(url="redis://localhost:6379/0")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await cache.get("some:key")

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test RedisCache.set stores value with TTL."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.setex = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            data = {"team": "Arsenal", "wins": 10}

            # Act
            await cache.set("team:arsenal:stats", data, ttl=3600)

            # Assert
            mock_redis.setex.assert_called_once_with(
                "team:arsenal:stats",
                3600,
                json.dumps(data)
            )

    @pytest.mark.asyncio
    async def test_set_not_connected(self):
        """Test RedisCache.set raises error when not connected."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        cache = RedisCache(url="redis://localhost:6379/0")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await cache.set("some:key", {"data": "value"}, ttl=60)

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test RedisCache.delete removes key."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=1)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            result = await cache.delete("team:arsenal:stats")

            # Assert
            assert result is True
            mock_redis.delete.assert_called_once_with("team:arsenal:stats")

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test RedisCache.delete returns False when key doesn't exist."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=0)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            result = await cache.delete("nonexistent:key")

            # Assert
            assert result is False
            mock_redis.delete.assert_called_once_with("nonexistent:key")

    @pytest.mark.asyncio
    async def test_exists_success(self):
        """Test RedisCache.exists checks key existence."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.exists = AsyncMock(return_value=1)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act
            result = await cache.exists("team:arsenal:stats")

            # Assert
            assert result is True
            mock_redis.exists.assert_called_once_with("team:arsenal:stats")

    @pytest.mark.asyncio
    async def test_json_serialization_complex_types(self):
        """Test RedisCache handles complex JSON types."""
        from sipap_data_mcp.cache.redis import RedisCache

        # Arrange
        with patch("sipap_data_mcp.cache.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)

            complex_data = {
                "team": "Arsenal",
                "stats": {
                    "wins": 10,
                    "draws": 5,
                    "losses": 3
                },
                "players": ["Saka", "Odegaard", "Rice"],
                "active": True,
                "rating": 85.5
            }

            mock_redis.get = AsyncMock(return_value=json.dumps(complex_data))
            mock_redis.setex = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_redis

            cache = RedisCache(url="redis://localhost:6379/0")
            await cache.connect()

            # Act - Set
            await cache.set("team:arsenal:complex", complex_data, ttl=3600)

            # Act - Get
            result = await cache.get("team:arsenal:complex")

            # Assert
            assert result == complex_data
            assert isinstance(result["stats"], dict)
            assert isinstance(result["players"], list)
            assert isinstance(result["active"], bool)
            assert isinstance(result["rating"], float)
