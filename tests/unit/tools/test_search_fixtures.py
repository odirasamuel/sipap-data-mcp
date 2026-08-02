"""Unit tests for search_fixtures tool."""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sipap_data_mcp.tools.matches import map_league_name_to_id, search_fixtures


class TestLeagueNameMapping:
    """Test league name to ID mapping."""

    def test_map_league_name_premier_league(self):
        """Test mapping Premier League variations."""
        assert map_league_name_to_id("Premier League") == "premier-league"
        assert map_league_name_to_id("EPL") == "premier-league"
        assert map_league_name_to_id("English Premier League") == "premier-league"
        assert map_league_name_to_id("england") == "premier-league"

    def test_map_league_name_laliga(self):
        """Test mapping LaLiga variations."""
        assert map_league_name_to_id("LaLiga") == "laliga"
        assert map_league_name_to_id("La Liga") == "laliga"
        assert map_league_name_to_id("Spanish League") == "laliga"
        assert map_league_name_to_id("spain") == "laliga"

    def test_map_league_name_serie_a(self):
        """Test mapping Serie A variations."""
        assert map_league_name_to_id("Serie A") == "serie-a"
        assert map_league_name_to_id("Italian League") == "serie-a"
        assert map_league_name_to_id("italy") == "serie-a"

    def test_map_league_name_bundesliga(self):
        """Test mapping Bundesliga variations."""
        assert map_league_name_to_id("Bundesliga") == "bundesliga"
        assert map_league_name_to_id("German League") == "bundesliga"
        assert map_league_name_to_id("germany") == "bundesliga"

    def test_map_league_name_unknown(self):
        """Test mapping unknown league names."""
        assert map_league_name_to_id("Unknown League") is None
        assert map_league_name_to_id("Fake League") is None

    def test_map_league_name_case_insensitive(self):
        """Test mapping is case-insensitive."""
        assert map_league_name_to_id("PREMIER LEAGUE") == "premier-league"
        assert map_league_name_to_id("premier league") == "premier-league"
        assert map_league_name_to_id("PrEmIeR lEaGuE") == "premier-league"


class TestSearchFixtures:
    """Test search_fixtures tool."""

    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        client = MagicMock()
        client.get_matches = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_search_fixtures_defaults(self, mock_db_client):
        """Test search_fixtures with default parameters."""
        # Setup mock
        mock_fixtures = [
            {"id": "fixture1", "home_team": "Arsenal", "away_team": "Chelsea"},
            {"id": "fixture2", "home_team": "Barcelona", "away_team": "Madrid"},
        ]
        mock_db_client.get_matches.return_value = mock_fixtures

        # Call search_fixtures with defaults
        result = await search_fixtures(db_client=mock_db_client)

        # Verify defaults were applied
        assert result["count"] == 2
        assert result["fixtures"] == mock_fixtures
        assert result["filters_applied"]["status"] == "scheduled"
        assert result["filters_applied"]["has_odds"] is True
        assert result["filters_applied"]["limit"] == 100

        # Verify date_from is today
        today = datetime.now(UTC).date().isoformat()
        assert result["filters_applied"]["date_from"] == today

        # Verify date_to is today + 7 days
        future = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()
        assert result["filters_applied"]["date_to"] == future

    @pytest.mark.asyncio
    async def test_search_fixtures_with_league_filter(self, mock_db_client):
        """Test search_fixtures with league filtering."""
        mock_fixtures = [
            {"id": "fixture1", "league": "Premier League"},
        ]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            league_names=["Premier League", "LaLiga"],
        )

        # Verify league IDs were mapped
        assert result["filters_applied"]["league_names"] == ["Premier League", "LaLiga"]
        assert result["filters_applied"]["league_ids"] == ["premier-league", "laliga"]

        # Verify get_matches was called twice (once per league)
        assert mock_db_client.get_matches.call_count == 2

    @pytest.mark.asyncio
    async def test_search_fixtures_with_date_range(self, mock_db_client):
        """Test search_fixtures with explicit date range."""
        mock_fixtures = [{"id": "fixture1"}]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            date_from="2026-08-03",
            date_to="2026-08-10",
        )

        # Verify dates were passed through
        assert result["filters_applied"]["date_from"] == "2026-08-03"
        assert result["filters_applied"]["date_to"] == "2026-08-10"

        # Verify get_matches was called with correct dates
        mock_db_client.get_matches.assert_called_once()
        call_args = mock_db_client.get_matches.call_args[1]
        assert call_args["date_from"] == "2026-08-03"
        assert call_args["date_to"] == "2026-08-10"

    @pytest.mark.asyncio
    async def test_search_fixtures_with_limit(self, mock_db_client):
        """Test search_fixtures respects limit parameter."""
        # Mock 100 fixtures
        mock_fixtures = [{"id": f"fixture{i}"} for i in range(100)]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            limit=10,
        )

        # Verify only 10 fixtures returned
        assert result["count"] == 10
        assert len(result["fixtures"]) == 10

    @pytest.mark.asyncio
    async def test_search_fixtures_with_status_filter(self, mock_db_client):
        """Test search_fixtures with status filter."""
        mock_fixtures = [{"id": "fixture1", "status": "live"}]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            status="live",
        )

        # Verify status filter applied
        assert result["filters_applied"]["status"] == "live"

        # Verify get_matches called with correct status
        mock_db_client.get_matches.assert_called_once()
        call_args = mock_db_client.get_matches.call_args[1]
        assert call_args["status"] == "live"

    @pytest.mark.asyncio
    async def test_search_fixtures_no_leagues(self, mock_db_client):
        """Test search_fixtures with no league filter queries all leagues."""
        mock_fixtures = [{"id": "fixture1"}]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            league_names=None,
        )

        # Verify get_matches called once with league_id=None
        mock_db_client.get_matches.assert_called_once()
        call_args = mock_db_client.get_matches.call_args[1]
        assert call_args["league_id"] is None

    @pytest.mark.asyncio
    async def test_search_fixtures_unknown_league_skipped(self, mock_db_client):
        """Test search_fixtures silently skips unknown leagues."""
        mock_fixtures = [{"id": "fixture1"}]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            league_names=["Premier League", "Unknown League", "LaLiga"],
        )

        # Verify only valid leagues mapped
        assert result["filters_applied"]["league_ids"] == ["premier-league", "laliga"]

        # Verify get_matches called twice (not three times)
        assert mock_db_client.get_matches.call_count == 2

    @pytest.mark.asyncio
    async def test_search_fixtures_has_odds_false(self, mock_db_client):
        """Test search_fixtures with has_odds=False includes all matches."""
        mock_fixtures = [
            {"id": "fixture1"},
            {"id": "fixture2"},
        ]
        mock_db_client.get_matches.return_value = mock_fixtures

        result = await search_fixtures(
            db_client=mock_db_client,
            has_odds=False,
        )

        # Verify has_odds filter recorded
        assert result["filters_applied"]["has_odds"] is False

        # Verify all fixtures returned
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_search_fixtures_empty_result(self, mock_db_client):
        """Test search_fixtures with no matching fixtures."""
        mock_db_client.get_matches.return_value = []

        result = await search_fixtures(db_client=mock_db_client)

        # Verify empty result
        assert result["count"] == 0
        assert result["fixtures"] == []
