"""Example: Using Redis cache with SIPAP Data MCP tools for improved performance.

This example demonstrates:
- Cache-aside pattern with Redis
- TTL configuration for different data types
- Cache miss handling and fallback to database
- Performance improvements (<100ms responses)
"""

import asyncio
import hashlib
import json
import os
from typing import Any

from sipap_data_mcp.cache.redis import RedisCache
from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.matches import get_match_schedule
from sipap_data_mcp.tools.odds import get_match_odds
from sipap_data_mcp.tools.teams import get_team_stats

# TTL Configuration (as per SIPAP architecture)
TTL_MATCH_SCHEDULE = 3600      # 1 hour (data changes frequently)
TTL_TEAM_STATS = 86400          # 24 hours (stable data)
TTL_ODDS = 600                  # 10 minutes (odds move fast)
TTL_HISTORICAL = 604800         # 7 days (historical data rarely changes)


def generate_cache_key(tool_name: str, **params: Any) -> str:
    """Generate consistent cache key from tool name and parameters.

    Args:
        tool_name: Name of the tool (e.g., "get_match_schedule")
        **params: Tool parameters

    Returns:
        Cache key (e.g., "tool:get_match_schedule:hash")

    Example:
        >>> generate_cache_key("get_team_stats", team_id="123", season="2024-2025")
        'tool:get_team_stats:a5f3c9...'
    """
    # Sort params for consistent hashing
    sorted_params = json.dumps(params, sort_keys=True)

    # Hash parameters to create short, consistent key
    param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:8]

    return f"tool:{tool_name}:{param_hash}"


async def cached_get_match_schedule(
    cache: RedisCache,
    db_client: AuroraDataClient,
    date_from: str,
    date_to: str,
    league_id: str | None = None,
    status: str = "scheduled"
) -> dict[str, Any]:
    """Get match schedule with caching (1-hour TTL).

    Cache-aside pattern:
    1. Check cache first
    2. On cache hit: return cached data (fast)
    3. On cache miss: query database, store in cache, return

    Args:
        cache: Redis cache client
        db_client: Database client
        date_from: Start date (ISO 8601)
        date_to: End date (ISO 8601)
        league_id: Optional league filter
        status: Match status filter

    Returns:
        Match schedule data
    """
    # Generate cache key
    cache_key = generate_cache_key(
        "get_match_schedule",
        date_from=date_from,
        date_to=date_to,
        league_id=league_id,
        status=status
    )

    # Try cache first
    cached_data = await cache.get(cache_key)
    if cached_data is not None:
        print(f"✅ Cache HIT: {cache_key}")
        return cached_data

    print(f"❌ Cache MISS: {cache_key}")

    # Cache miss - query database
    result = await get_match_schedule(
        db_client=db_client,
        date_from=date_from,
        date_to=date_to,
        league_id=league_id,
        status=status
    )

    # Store in cache with TTL
    await cache.set(cache_key, result, ttl=TTL_MATCH_SCHEDULE)

    return result


async def cached_get_team_stats(
    cache: RedisCache,
    db_client: AuroraDataClient,
    team_id: str,
    season: str = "2024-2025"
) -> dict[str, Any] | None:
    """Get team stats with caching (24-hour TTL).

    Args:
        cache: Redis cache client
        db_client: Database client
        team_id: Team UUID
        season: Season (YYYY-YYYY format)

    Returns:
        Team stats data or None if not found
    """
    cache_key = generate_cache_key("get_team_stats", team_id=team_id, season=season)

    # Try cache first
    cached_data = await cache.get(cache_key)
    if cached_data is not None:
        print(f"✅ Cache HIT: {cache_key}")
        return cached_data

    print(f"❌ Cache MISS: {cache_key}")

    # Cache miss - query database
    result = await get_team_stats(
        db_client=db_client,
        team_id=team_id,
        season=season
    )

    # Store in cache with 24-hour TTL (team stats are stable)
    if result is not None:
        await cache.set(cache_key, result, ttl=TTL_TEAM_STATS)

    return result


async def cached_get_match_odds(
    cache: RedisCache,
    db_client: AuroraDataClient,
    match_id: str
) -> dict[str, Any] | None:
    """Get match odds with caching (10-minute TTL).

    Odds move frequently, so short TTL is used.

    Args:
        cache: Redis cache client
        db_client: Database client
        match_id: Match UUID

    Returns:
        Match odds data or None if not found
    """
    cache_key = generate_cache_key("get_match_odds", match_id=match_id)

    # Try cache first
    cached_data = await cache.get(cache_key)
    if cached_data is not None:
        print(f"✅ Cache HIT: {cache_key}")
        return cached_data

    print(f"❌ Cache MISS: {cache_key}")

    # Cache miss - query database
    result = await get_match_odds(
        db_client=db_client,
        match_id=match_id
    )

    # Store in cache with 10-minute TTL (odds move fast)
    if result is not None:
        await cache.set(cache_key, result, ttl=TTL_ODDS)

    return result


async def main():
    """Demonstrate cached data access patterns."""
    # Initialize clients
    cache = RedisCache(url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    db_client = AuroraDataClient(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "sipap"),
        user=os.environ.get("DB_USER", "sipap_readonly"),
        password=os.environ.get("DB_PASSWORD", ""),
    )

    try:
        # Connect to Redis and database
        print("Connecting to Redis and database...")
        await cache.connect()
        await db_client.connect()
        print("✅ Connected successfully\n")

        # Example 1: Get match schedule (1-hour cache)
        print("=" * 60)
        print("Example 1: Match Schedule with Caching (1-hour TTL)")
        print("=" * 60)

        # First call - cache miss
        print("\n🔍 First call (expect cache miss):")
        result1 = await cached_get_match_schedule(
            cache=cache,
            db_client=db_client,
            date_from="2026-07-06",
            date_to="2026-07-13",
            status="scheduled"
        )
        print(f"Retrieved {len(result1.get('matches', []))} matches\n")

        # Second call - cache hit
        print("🔍 Second call (expect cache hit):")
        result2 = await cached_get_match_schedule(
            cache=cache,
            db_client=db_client,
            date_from="2026-07-06",
            date_to="2026-07-13",
            status="scheduled"
        )
        print(f"Retrieved {len(result2.get('matches', []))} matches (from cache)")

        # Example 2: Get team stats (24-hour cache)
        print("\n" + "=" * 60)
        print("Example 2: Team Stats with Caching (24-hour TTL)")
        print("=" * 60)

        team_id = "550e8400-e29b-41d4-a716-446655440010"  # Arsenal

        # First call - cache miss
        print("\n🔍 First call (expect cache miss):")
        stats1 = await cached_get_team_stats(
            cache=cache,
            db_client=db_client,
            team_id=team_id,
            season="2024-2025"
        )
        if stats1:
            print(f"Team: {stats1.get('team_name', 'Unknown')}")
            print(f"Wins: {stats1.get('wins', 0)}")

        # Second call - cache hit
        print("\n🔍 Second call (expect cache hit):")
        stats2 = await cached_get_team_stats(
            cache=cache,
            db_client=db_client,
            team_id=team_id,
            season="2024-2025"
        )
        if stats2:
            print(f"Team: {stats2.get('team_name', 'Unknown')} (from cache)")

        # Example 3: Get match odds (10-minute cache)
        print("\n" + "=" * 60)
        print("Example 3: Match Odds with Caching (10-minute TTL)")
        print("=" * 60)

        match_id = "550e8400-e29b-41d4-a716-446655440000"

        # First call - cache miss
        print("\n🔍 First call (expect cache miss):")
        odds1 = await cached_get_match_odds(
            cache=cache,
            db_client=db_client,
            match_id=match_id
        )
        if odds1:
            print(f"Bookmakers: {len(odds1.get('bookmakers', []))}")

        # Second call - cache hit
        print("\n🔍 Second call (expect cache hit):")
        odds2 = await cached_get_match_odds(
            cache=cache,
            db_client=db_client,
            match_id=match_id
        )
        if odds2:
            print(f"Bookmakers: {len(odds2.get('bookmakers', []))} (from cache)")

        # Example 4: Cache invalidation
        print("\n" + "=" * 60)
        print("Example 4: Manual Cache Invalidation")
        print("=" * 60)

        cache_key = generate_cache_key("get_match_odds", match_id=match_id)
        print(f"\n🗑️  Deleting cache key: {cache_key}")
        deleted = await cache.delete(cache_key)
        print(f"Deleted: {deleted}")

        # Next call will be cache miss
        print("\n🔍 Next call (expect cache miss after delete):")
        odds3 = await cached_get_match_odds(
            cache=cache,
            db_client=db_client,
            match_id=match_id
        )
        if odds3:
            print(f"Bookmakers: {len(odds3.get('bookmakers', []))}")

        # Example 5: Check cache existence
        print("\n" + "=" * 60)
        print("Example 5: Check Cache Existence")
        print("=" * 60)

        cache_key = generate_cache_key("get_match_odds", match_id=match_id)
        exists = await cache.exists(cache_key)
        print(f"\nCache key exists: {exists}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up resources
        await cache.close()
        await db_client.close()
        print("\n✅ Connections closed")


if __name__ == "__main__":
    asyncio.run(main())
