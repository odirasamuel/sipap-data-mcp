"""Unit tests for match tools.

Following TDD methodology: Tests written BEFORE implementation.
These tests define the expected behavior of match-related MCP tools.
"""

from unittest.mock import AsyncMock

import pytest

from tests.fixtures.matches import SAMPLE_MATCH, SAMPLE_MATCH_LIST


class TestGetMatchSchedule:
    """Tests for get_match_schedule MCP tool."""

    @pytest.mark.asyncio
    async def test_get_match_schedule_success(self, mock_db_client):
        """Test get_match_schedule returns matches for date range."""
        from sipap_data_mcp.tools.matches import get_match_schedule

        # Arrange
        mock_db_client.get_matches.return_value = SAMPLE_MATCH_LIST

        # Act
        result = await get_match_schedule(
            db_client=mock_db_client,
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled"
        )

        # Assert
        assert isinstance(result, dict)
        assert "matches" in result
        assert isinstance(result["matches"], list)
        assert len(result["matches"]) == 3
        assert result["matches"][0]["home_team"] == "Arsenal"

        # Verify database was called correctly
        mock_db_client.get_matches.assert_called_once_with(
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled",
            league_id=None
        )

    @pytest.mark.asyncio
    async def test_get_match_schedule_with_league_filter(self, mock_db_client):
        """Test get_match_schedule with league_id filter."""
        from sipap_data_mcp.tools.matches import get_match_schedule

        # Arrange
        mock_db_client.get_matches.return_value = [SAMPLE_MATCH]

        # Act
        result = await get_match_schedule(
            db_client=mock_db_client,
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled",
            league_id="league-uuid-1"
        )

        # Assert
        assert len(result["matches"]) == 1
        mock_db_client.get_matches.assert_called_once_with(
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled",
            league_id="league-uuid-1"
        )

    @pytest.mark.asyncio
    async def test_get_match_schedule_invalid_date_format(self, mock_db_client):
        """Test get_match_schedule raises ValueError for invalid date."""
        from sipap_data_mcp.tools.matches import get_match_schedule

        # Arrange
        mock_db_client.get_matches.side_effect = ValueError("Invalid date format")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid date format"):
            await get_match_schedule(
                db_client=mock_db_client,
                date_from="invalid-date",
                date_to="2026-07-12",
                status="scheduled"
            )

    @pytest.mark.asyncio
    async def test_get_match_schedule_empty_results(self, mock_db_client):
        """Test get_match_schedule returns empty list when no matches found."""
        from sipap_data_mcp.tools.matches import get_match_schedule

        # Arrange
        mock_db_client.get_matches.return_value = []

        # Act
        result = await get_match_schedule(
            db_client=mock_db_client,
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled"
        )

        # Assert
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_get_match_schedule_database_error(self, mock_db_client):
        """Test get_match_schedule handles database errors gracefully."""
        from sipap_data_mcp.tools.matches import get_match_schedule

        # Arrange
        mock_db_client.get_matches.side_effect = RuntimeError("Database connection failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database connection failed"):
            await get_match_schedule(
                db_client=mock_db_client,
                date_from="2026-07-05",
                date_to="2026-07-12",
                status="scheduled"
            )


class TestGetMatchDetails:
    """Tests for get_match_details MCP tool."""

    @pytest.mark.asyncio
    async def test_get_match_details_success(self, mock_db_client):
        """Test get_match_details returns detailed match data."""
        from sipap_data_mcp.tools.matches import get_match_details

        # Arrange
        mock_db_client.get_match = AsyncMock(return_value=SAMPLE_MATCH)

        # Act
        result = await get_match_details(
            db_client=mock_db_client,
            match_id="550e8400-e29b-41d4-a716-446655440000"
        )

        # Assert
        assert isinstance(result, dict)
        assert "match" in result
        assert result["match"]["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result["match"]["home_team"] == "Arsenal"
        assert result["match"]["away_team"] == "Chelsea"

        mock_db_client.get_match.assert_called_once_with(
            match_id="550e8400-e29b-41d4-a716-446655440000"
        )

    @pytest.mark.asyncio
    async def test_get_match_details_not_found(self, mock_db_client):
        """Test get_match_details raises error when match not found."""
        from sipap_data_mcp.tools.matches import get_match_details

        # Arrange
        mock_db_client.get_match = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Match not found"):
            await get_match_details(
                db_client=mock_db_client,
                match_id="00000000-0000-0000-0000-000000000000"  # Valid UUID format
            )

    @pytest.mark.asyncio
    async def test_get_match_details_invalid_uuid(self, mock_db_client):
        """Test get_match_details validates UUID format."""
        from sipap_data_mcp.tools.matches import get_match_details

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_match_details(
                db_client=mock_db_client,
                match_id="not-a-uuid"
            )


class TestGetLiveMatches:
    """Tests for get_live_matches MCP tool."""

    @pytest.mark.asyncio
    async def test_get_live_matches_success(self, mock_db_client):
        """Test get_live_matches returns currently live matches."""
        from sipap_data_mcp.tools.matches import get_live_matches

        # Arrange
        live_match = {**SAMPLE_MATCH, "status": "live", "home_score": 1, "away_score": 1}
        mock_db_client.get_matches.return_value = [live_match]

        # Act
        result = await get_live_matches(db_client=mock_db_client)

        # Assert
        assert isinstance(result, dict)
        assert "matches" in result
        assert len(result["matches"]) == 1
        assert result["matches"][0]["status"] == "live"

        # Verify database was called with status="live"
        mock_db_client.get_matches.assert_called_once()
        call_kwargs = mock_db_client.get_matches.call_args.kwargs
        assert call_kwargs["status"] == "live"

    @pytest.mark.asyncio
    async def test_get_live_matches_no_live_matches(self, mock_db_client):
        """Test get_live_matches returns empty list when no matches are live."""
        from sipap_data_mcp.tools.matches import get_live_matches

        # Arrange
        mock_db_client.get_matches.return_value = []

        # Act
        result = await get_live_matches(db_client=mock_db_client)

        # Assert
        assert result["matches"] == []


class TestSearchMatches:
    """Tests for search_matches MCP tool."""

    @pytest.mark.asyncio
    async def test_search_matches_by_team_name(self, mock_db_client):
        """Test search_matches finds matches by team name."""
        from sipap_data_mcp.tools.matches import search_matches

        # Arrange
        mock_db_client.search_matches = AsyncMock(return_value=SAMPLE_MATCH_LIST)

        # Act
        result = await search_matches(
            db_client=mock_db_client,
            query="Arsenal"
        )

        # Assert
        assert isinstance(result, dict)
        assert "matches" in result
        assert len(result["matches"]) == 3

        mock_db_client.search_matches.assert_called_once_with(query="Arsenal")

    @pytest.mark.asyncio
    async def test_search_matches_no_results(self, mock_db_client):
        """Test search_matches returns empty list when no matches found."""
        from sipap_data_mcp.tools.matches import search_matches

        # Arrange
        mock_db_client.search_matches = AsyncMock(return_value=[])

        # Act
        result = await search_matches(
            db_client=mock_db_client,
            query="Nonexistent Team"
        )

        # Assert
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_search_matches_empty_query(self, mock_db_client):
        """Test search_matches raises error for empty query."""
        from sipap_data_mcp.tools.matches import search_matches

        # Act & Assert
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await search_matches(
                db_client=mock_db_client,
                query=""
            )
