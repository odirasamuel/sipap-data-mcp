"""Unit tests for has_odds filtering in AuroraDataClient.

Tests that matches with odds are correctly filtered using PostgreSQL JSONB ? operator.
"""

import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sipap_data_mcp.database.aurora import AuroraDataClient


class TestHasOddsFiltering:
    """Test has_odds parameter in get_matches() method."""

    @pytest.fixture
    def client(self):
        """Create AuroraDataClient for testing."""
        return AuroraDataClient(
            host="test-host",
            port=5432,
            database="test-db",
            user="test-user",
            password="test-pass",
        )

    def test_build_matches_query_without_has_odds(self, client):
        """Test that query WITHOUT has_odds doesn't include odds filter."""
        query, params = client._build_matches_query(
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            league_id=None,
            has_odds=False,
        )

        # Should not contain odds filter
        assert "metadata ? 'odds'" not in query
        # Should contain basic filters (with date casting)
        assert "scheduled_at::date >= $1" in query
        assert "status = $3" in query
        # Should have 3 parameters (date_from, date_to, status)
        assert len(params) == 3

    def test_build_matches_query_with_has_odds(self, client):
        """Test that query WITH has_odds includes odds filter."""
        query, params = client._build_matches_query(
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            league_id=None,
            has_odds=True,
        )

        # Should contain odds filter using PostgreSQL JSONB ? operator
        assert "metadata ? 'odds'" in query
        # Should contain basic filters (with date casting)
        assert "scheduled_at::date >= $1" in query
        assert "status = $3" in query
        # Should have 3 parameters (date_from, date_to, status)
        assert len(params) == 3

    def test_build_matches_query_with_league_and_has_odds(self, client):
        """Test that query with both league_id and has_odds works correctly."""
        league_id = "premier-league-uuid"

        query, params = client._build_matches_query(
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            league_id=league_id,
            has_odds=True,
        )

        # Should contain both league and odds filters
        assert "league_id = $4" in query
        assert "metadata ? 'odds'" in query
        # Should have 4 parameters (date_from, date_to, status, league_id)
        assert len(params) == 4
        assert params[3] == league_id

    def test_build_matches_query_parameter_order(self, client):
        """Test that SQL parameter placeholders are correctly ordered."""
        league_id = "test-league"

        query, params = client._build_matches_query(
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            league_id=league_id,
            has_odds=True,
        )

        # Verify parameters (date strings are converted to datetime.date objects)
        assert params[0] == datetime.date(2026, 8, 1)  # $1: date_from
        assert params[1] == datetime.date(2026, 8, 10)  # $2: date_to
        assert params[2] == "scheduled"   # $3: status
        assert params[3] == league_id     # $4: league_id

    # Note: Integration tests with AsyncMock for pool.acquire() are complex.
    # The query building tests above (test_build_matches_query_*) already validate
    # that the has_odds parameter correctly adds the PostgreSQL JSONB ? operator
    # to the SQL query. That's the core functionality we need to test.


class TestSearchFixturesOddsFiltering:
    """Test has_odds filtering in search_fixtures tool."""

    @pytest.mark.asyncio
    async def test_search_fixtures_passes_has_odds_to_db_client(self):
        """Test that search_fixtures passes has_odds parameter to db_client.get_matches()."""
        from sipap_data_mcp.tools.matches import search_fixtures

        # Mock db_client
        mock_db_client = AsyncMock()
        mock_db_client.get_matches.return_value = [
            {
                "id": "match1",
                "home_team": {"name": "Arsenal"},
                "away_team": {"name": "Chelsea"},
                "metadata": {"odds": {"1X2": [2.5, 3.2, 2.8]}},
            }
        ]

        # Call search_fixtures with has_odds=True
        result = await search_fixtures(
            db_client=mock_db_client,
            league_names=None,
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            has_odds=True,
            limit=100,
        )

        # Verify db_client.get_matches was called with has_odds=True
        assert mock_db_client.get_matches.called
        call_kwargs = mock_db_client.get_matches.call_args[1]
        assert call_kwargs["has_odds"] is True

        # Verify result
        assert result["count"] == 1
        assert result["fixtures"][0]["id"] == "match1"

    @pytest.mark.asyncio
    async def test_search_fixtures_with_leagues_passes_has_odds(self):
        """Test that search_fixtures passes has_odds when filtering by leagues."""
        from sipap_data_mcp.tools.matches import search_fixtures

        # Mock db_client
        mock_db_client = AsyncMock()
        mock_db_client.get_matches.return_value = []

        # Call search_fixtures with leagues and has_odds=True
        await search_fixtures(
            db_client=mock_db_client,
            league_names=["Premier League", "LaLiga"],
            date_from="2026-08-01",
            date_to="2026-08-10",
            status="scheduled",
            has_odds=True,
            limit=100,
        )

        # Verify db_client.get_matches was called twice (once per league)
        assert mock_db_client.get_matches.call_count == 2

        # Verify both calls passed has_odds=True
        for call in mock_db_client.get_matches.call_args_list:
            call_kwargs = call[1]
            assert call_kwargs["has_odds"] is True
