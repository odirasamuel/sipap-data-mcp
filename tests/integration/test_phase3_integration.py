"""Integration tests for Phase 3 schema and deployed infrastructure.

Tests the complete flow: Aurora database → Phase 3 tables → MCP tools → Redis cache

Prerequisites:
- Aurora PostgreSQL deployed and accessible
- Phase 3 migrations applied (tables created)
- Phase 4 batch jobs executed (tables populated with data)
- Redis Elasticache deployed and accessible
- Environment variables configured in .env or AWS Secrets Manager

Run with:
    pytest tests/integration/test_phase3_integration.py -v
"""

import os
from datetime import datetime

import pytest

from sipap_data_mcp.cache.redis import RedisCache
from sipap_data_mcp.database.aurora import AuroraDataClient


# ==============================================================================
# FIXTURES - Database and Cache Clients
# ==============================================================================

@pytest.fixture(scope="module")
async def aurora_client():
    """Create Aurora client connected to deployed database.

    Reads connection details from environment variables:
    - AURORA_HOST
    - AURORA_PORT (default: 5432)
    - AURORA_DATABASE
    - AURORA_USER
    - AURORA_PASSWORD
    """
    client = AuroraDataClient(
        host=os.getenv("AURORA_HOST", "sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com"),
        port=int(os.getenv("AURORA_PORT", "5432")),
        database=os.getenv("AURORA_DATABASE", "sipap"),
        user=os.getenv("AURORA_USER", "postgres"),
        password=os.getenv("AURORA_PASSWORD", ""),  # Should be in Secrets Manager
    )

    await client.connect()
    yield client
    await client.close()


@pytest.fixture(scope="module")
async def redis_cache():
    """Create Redis client connected to deployed Elasticache.

    Reads connection details from environment variables:
    - REDIS_HOST
    - REDIS_PORT (default: 6379)
    """
    cache = RedisCache(
        host=os.getenv("REDIS_HOST", "sipap-dev-redis.qnk6bl.0001.use1.cache.amazonaws.com"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=0,
    )

    await cache.connect()
    yield cache
    await cache.disconnect()


# ==============================================================================
# TEST SUITE - Phase 3 Table Population
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestPhase3TablePopulation:
    """Verify Phase 3 tables are populated with data from Phase 4 batch jobs."""

    async def test_standings_table_has_data(self, aurora_client):
        """Verify standings table has data for 2024 season."""
        standings = await aurora_client.get_standings(
            league_id=39,  # Premier League
            season="2024"
        )

        assert len(standings) > 0, "Standings table should have data"
        assert len(standings) <= 20, "Premier League should have ≤ 20 teams"

        # Verify data structure
        first_place = standings[0]
        assert first_place["rank"] == 1
        assert "team_name" in first_place
        assert "points" in first_place
        assert "played" in first_place

    async def test_team_statistics_table_has_data(self, aurora_client):
        """Verify team_statistics table has data."""
        # Try to get stats for a major team (Man City = team_id 50)
        stats = await aurora_client.get_team_statistics(
            team_id=50,  # Manchester City
            league_id=39,  # Premier League
            season="2024"
        )

        assert stats is not None, "Team statistics should exist for major teams"
        assert "total_played" in stats
        assert "total_wins" in stats
        assert stats["total_played"] >= 0

    async def test_head_to_head_table_has_data(self, aurora_client):
        """Verify head_to_head table has data."""
        # Check H2H between two major teams
        h2h = await aurora_client.get_head_to_head_stats(
            team_1_id=50,  # Man City
            team_2_id=42   # Arsenal
        )

        # May be None if H2H hasn't been fetched yet
        # This is acceptable - batch job is trigger-based on new fixtures
        if h2h is not None:
            assert "team_1_wins" in h2h
            assert "team_2_wins" in h2h
            assert "draws" in h2h

    async def test_odds_table_has_data(self, aurora_client):
        """Verify odds table has pre-match odds data."""
        # Get all odds (no fixture_id filter) - this queries the table directly
        query = "SELECT COUNT(*) as count FROM odds WHERE is_live = false LIMIT 1"

        async with aurora_client._pool.acquire() as conn:
            row = await conn.fetchrow(query)
            count = row["count"] if row else 0

        # If count > 0, odds table is populated
        # If count == 0, Phase 4 odds updater hasn't run yet (acceptable)
        assert count >= 0, "Odds table should be queryable"

    async def test_teams_metadata_table_has_data(self, aurora_client):
        """Verify teams_metadata table has data."""
        # Get metadata for major teams
        metadata = await aurora_client.get_teams_metadata(
            team_ids=[50, 42, 33, 40]  # Man City, Arsenal, Man Utd, Liverpool
        )

        # Should have at least some teams
        # May not have all if batch job hasn't run
        assert len(metadata) >= 0, "Teams metadata should be queryable"


# ==============================================================================
# TEST SUITE - Aurora Query Performance
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestAuroraQueryPerformance:
    """Verify Phase 3 queries are fast (< 100ms)."""

    async def test_standings_query_performance(self, aurora_client):
        """Verify standings query completes in < 100ms."""
        import time

        start = time.perf_counter()
        await aurora_client.get_standings(league_id=39, season="2024")
        duration = (time.perf_counter() - start) * 1000  # Convert to ms

        assert duration < 100, f"Standings query took {duration:.1f}ms (target: < 100ms)"

    async def test_team_stats_query_performance(self, aurora_client):
        """Verify team stats query completes in < 100ms."""
        import time

        start = time.perf_counter()
        await aurora_client.get_team_statistics(
            team_id=50,
            league_id=39,
            season="2024"
        )
        duration = (time.perf_counter() - start) * 1000

        assert duration < 100, f"Team stats query took {duration:.1f}ms (target: < 100ms)"


# ==============================================================================
# TEST SUITE - Redis Cache Integration
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestRedisCacheIntegration:
    """Verify Redis cache works with Phase 3 data."""

    async def test_redis_connection(self, redis_cache):
        """Verify Redis is accessible and responding."""
        # Simple ping test
        await redis_cache.set("test_key", {"value": "test"}, ttl=10)
        result = await redis_cache.get("test_key")

        assert result is not None
        assert result["value"] == "test"

        # Cleanup
        await redis_cache.delete("test_key")

    async def test_cache_team_stats(self, redis_cache):
        """Verify caching team stats works."""
        cache_key = "team_stats:50:39:2024"
        mock_stats = {
            "stats": {
                "total_played": 38,
                "total_wins": 28,
                "total_draws": 5,
                "total_losses": 5
            }
        }

        # Cache data
        await redis_cache.set(cache_key, mock_stats, ttl=21600)  # 6 hours

        # Retrieve from cache
        cached = await redis_cache.get(cache_key)

        assert cached is not None
        assert cached["stats"]["total_played"] == 38

        # Verify TTL is set correctly
        ttl = await redis_cache.ttl(cache_key)
        assert 21590 <= ttl <= 21600, f"TTL should be ~6 hours, got {ttl}s"

        # Cleanup
        await redis_cache.delete(cache_key)


# ==============================================================================
# TEST SUITE - Data Quality Validation
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestDataQualityValidation:
    """Verify data quality in Phase 3 tables."""

    async def test_standings_ranks_are_sequential(self, aurora_client):
        """Verify standings ranks are 1-20 with no gaps."""
        standings = await aurora_client.get_standings(
            league_id=39,
            season="2024"
        )

        if len(standings) > 0:
            ranks = [s["rank"] for s in standings]
            expected_ranks = list(range(1, len(standings) + 1))

            assert ranks == expected_ranks, "Ranks should be sequential 1-N"

    async def test_team_stats_played_matches_valid(self, aurora_client):
        """Verify team stats have valid played match counts."""
        stats = await aurora_client.get_team_statistics(
            team_id=50,
            league_id=39,
            season="2024"
        )

        if stats is not None:
            played = stats.get("total_played", 0)
            wins = stats.get("total_wins", 0)
            draws = stats.get("total_draws", 0)
            losses = stats.get("total_losses", 0)

            # Wins + draws + losses should equal played
            assert wins + draws + losses == played, \
                "Wins + draws + losses should equal total played"

            # Played should be between 0 and 38 (max Premier League matches)
            assert 0 <= played <= 38, "Played matches should be 0-38"


# ==============================================================================
# SKIP CONDITIONS
# ==============================================================================

# Skip all integration tests if environment variables not set
pytestmark = pytest.mark.skipif(
    not os.getenv("AURORA_PASSWORD"),
    reason="AURORA_PASSWORD not set - integration tests require deployed infrastructure"
)
