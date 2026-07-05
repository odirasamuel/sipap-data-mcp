"""Caching layer for SIPAP Data MCP.

Provides Redis-based caching for tool responses to reduce database load
and improve response times.
"""

from sipap_data_mcp.cache.redis import RedisCache

__all__ = ["RedisCache"]
