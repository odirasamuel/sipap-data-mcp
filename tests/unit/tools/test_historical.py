"""Unit tests for historical data tools.

Following TDD methodology: Tests written BEFORE implementation.
These tests define the expected behavior of historical data MCP tools.
"""

from unittest.mock import AsyncMock

import pytest

from tests.fixtures.matches import SAMPLE_MATCH


class TestQueryHistory:
    """Tests for query_history MCP tool."""

    @pytest.mark.asyncio
    async def test_query_history_by_team(self, mock_db_client):
        """Test query_history returns historical matches for a team."""
        from sipap_data_mcp.tools.historical import query_history

        # Arrange
        historical_matches = [
            {**SAMPLE_MATCH, "status": "finished", "home_score": 2, "away_score": 1},
            {**SAMPLE_MATCH, "id": "550e8400-e29b-41d4-a716-446655440099", "status": "finished", "home_score": 1, "away_score": 1},  # noqa: E501
        ]
        mock_db_client.query_match_history = AsyncMock(return_value=historical_matches)

        # Act
        result = await query_history(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            limit=10
        )

        # Assert
        assert isinstance(result, dict)
        assert "matches" in result
        assert len(result["matches"]) == 2
        assert all(m["status"] == "finished" for m in result["matches"])
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id=None,
            date_from=None,
            date_to=None,
            limit=10
        )

    @pytest.mark.asyncio
    async def test_query_history_with_date_range(self, mock_db_client):
        """Test query_history filters by date range."""
        from sipap_data_mcp.tools.historical import query_history

        # Arrange
        historical_matches = [
            {**SAMPLE_MATCH, "status": "finished", "scheduled_at": "2026-01-15T15:00:00Z"},
        ]
        mock_db_client.query_match_history = AsyncMock(return_value=historical_matches)

        # Act
        result = await query_history(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            date_from="2026-01-01",
            date_to="2026-01-31",
            limit=50
        )

        # Assert
        assert len(result["matches"]) == 1
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id=None,
            date_from="2026-01-01",
            date_to="2026-01-31",
            limit=50
        )

    @pytest.mark.asyncio
    async def test_query_history_with_league_filter(self, mock_db_client):
        """Test query_history filters by league."""
        from sipap_data_mcp.tools.historical import query_history

        # Arrange
        mock_db_client.query_match_history = AsyncMock(return_value=[])

        # Act
        result = await query_history(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id="550e8400-e29b-41d4-a716-446655440020",
            limit=20
        )

        # Assert
        assert result["matches"] == []
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id="550e8400-e29b-41d4-a716-446655440020",
            date_from=None,
            date_to=None,
            limit=20
        )

    @pytest.mark.asyncio
    async def test_query_history_invalid_team_uuid(self, mock_db_client):
        """Test query_history validates team UUID format."""
        from sipap_data_mcp.tools.historical import query_history

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await query_history(
                db_client=mock_db_client,
                team_id="not-a-uuid",
                limit=10
            )

    @pytest.mark.asyncio
    async def test_query_history_invalid_league_uuid(self, mock_db_client):
        """Test query_history validates league UUID format."""
        from sipap_data_mcp.tools.historical import query_history

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await query_history(
                db_client=mock_db_client,
                team_id="550e8400-e29b-41d4-a716-446655440010",
                league_id="not-a-uuid",
                limit=10
            )

    @pytest.mark.asyncio
    async def test_query_history_invalid_date_format(self, mock_db_client):
        """Test query_history validates date format."""
        from sipap_data_mcp.tools.historical import query_history

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid date format"):
            await query_history(
                db_client=mock_db_client,
                team_id="550e8400-e29b-41d4-a716-446655440010",
                date_from="invalid-date",
                limit=10
            )

    @pytest.mark.asyncio
    async def test_query_history_default_limit(self, mock_db_client):
        """Test query_history uses default limit of 20."""
        from sipap_data_mcp.tools.historical import query_history

        # Arrange
        mock_db_client.query_match_history = AsyncMock(return_value=[])

        # Act
        await query_history(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010"
        )

        # Assert
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id=None,
            date_from=None,
            date_to=None,
            limit=20
        )


class TestGetFormData:
    """Tests for get_form_data MCP tool."""

    @pytest.mark.asyncio
    async def test_get_form_data_success(self, mock_db_client):
        """Test get_form_data calculates team form from recent matches."""
        from sipap_data_mcp.tools.historical import get_form_data

        team_id = "550e8400-e29b-41d4-a716-446655440010"

        # Arrange - Recent 5 matches: W, W, D, L, W
        recent_matches = [
            {"id": "1", "scheduled_at": "2026-07-01T15:00:00Z", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440011", "home_score": 2, "away_score": 1, "status": "finished"},  # noqa: E501
            {"id": "2", "scheduled_at": "2026-06-24T15:00:00Z", "home_team_id": "550e8400-e29b-41d4-a716-446655440011", "away_team_id": team_id, "home_score": 1, "away_score": 2, "status": "finished"},  # noqa: E501
            {"id": "3", "scheduled_at": "2026-06-17T15:00:00Z", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440012", "home_score": 1, "away_score": 2, "status": "finished"},  # noqa: E501
            {"id": "4", "scheduled_at": "2026-06-10T15:00:00Z", "home_team_id": "550e8400-e29b-41d4-a716-446655440012", "away_team_id": team_id, "home_score": 0, "away_score": 0, "status": "finished"},  # noqa: E501
            {"id": "5", "scheduled_at": "2026-06-03T15:00:00Z", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440013", "home_score": 3, "away_score": 1, "status": "finished"},  # noqa: E501
        ]
        mock_db_client.query_match_history = AsyncMock(return_value=recent_matches)

        # Act
        result = await get_form_data(
            db_client=mock_db_client,
            team_id=team_id,
            num_matches=5
        )

        # Assert
        assert isinstance(result, dict)
        assert "form" in result
        assert len(result["form"]) == 5
        assert result["form"] == ["W", "W", "L", "D", "W"]  # Most recent first
        assert "wins" in result
        assert "draws" in result
        assert "losses" in result
        assert result["wins"] == 3
        assert result["draws"] == 1
        assert result["losses"] == 1

    @pytest.mark.asyncio
    async def test_get_form_data_with_points(self, mock_db_client):
        """Test get_form_data calculates points from recent form."""
        from sipap_data_mcp.tools.historical import get_form_data

        team_id = "550e8400-e29b-41d4-a716-446655440010"

        # Arrange - 2W, 1D, 2L = 7 points
        recent_matches = [
            {"id": "1", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440011", "home_score": 2, "away_score": 1, "status": "finished", "scheduled_at": "2026-07-01T15:00:00Z"},  # noqa: E501
            {"id": "2", "home_team_id": "550e8400-e29b-41d4-a716-446655440011", "away_team_id": team_id, "home_score": 1, "away_score": 1, "status": "finished", "scheduled_at": "2026-06-24T15:00:00Z"},  # noqa: E501
            {"id": "3", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440012", "home_score": 3, "away_score": 0, "status": "finished", "scheduled_at": "2026-06-17T15:00:00Z"},  # noqa: E501
            {"id": "4", "home_team_id": "550e8400-e29b-41d4-a716-446655440012", "away_team_id": team_id, "home_score": 2, "away_score": 0, "status": "finished", "scheduled_at": "2026-06-10T15:00:00Z"},  # noqa: E501
            {"id": "5", "home_team_id": team_id, "away_team_id": "550e8400-e29b-41d4-a716-446655440013", "home_score": 0, "away_score": 1, "status": "finished", "scheduled_at": "2026-06-03T15:00:00Z"},  # noqa: E501
        ]
        mock_db_client.query_match_history = AsyncMock(return_value=recent_matches)

        # Act
        result = await get_form_data(
            db_client=mock_db_client,
            team_id=team_id,
            num_matches=5
        )

        # Assert
        assert "points" in result
        assert result["points"] == 7  # 2 wins (6) + 1 draw (1) = 7
        assert result["wins"] == 2
        assert result["draws"] == 1
        assert result["losses"] == 2

    @pytest.mark.asyncio
    async def test_get_form_data_empty_history(self, mock_db_client):
        """Test get_form_data handles teams with no match history."""
        from sipap_data_mcp.tools.historical import get_form_data

        # Arrange
        mock_db_client.query_match_history = AsyncMock(return_value=[])

        # Act
        result = await get_form_data(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            num_matches=5
        )

        # Assert
        assert result["form"] == []
        assert result["wins"] == 0
        assert result["draws"] == 0
        assert result["losses"] == 0
        assert result["points"] == 0

    @pytest.mark.asyncio
    async def test_get_form_data_invalid_uuid(self, mock_db_client):
        """Test get_form_data validates UUID format."""
        from sipap_data_mcp.tools.historical import get_form_data

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_form_data(
                db_client=mock_db_client,
                team_id="not-a-uuid",
                num_matches=5
            )

    @pytest.mark.asyncio
    async def test_get_form_data_default_num_matches(self, mock_db_client):
        """Test get_form_data uses default of 5 matches."""
        from sipap_data_mcp.tools.historical import get_form_data

        # Arrange
        mock_db_client.query_match_history = AsyncMock(return_value=[])

        # Act
        await get_form_data(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010"
        )

        # Assert
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id=None,
            date_from=None,
            date_to=None,
            limit=5
        )

    @pytest.mark.asyncio
    async def test_get_form_data_custom_num_matches(self, mock_db_client):
        """Test get_form_data respects custom num_matches parameter."""
        from sipap_data_mcp.tools.historical import get_form_data

        # Arrange
        mock_db_client.query_match_history = AsyncMock(return_value=[])

        # Act
        await get_form_data(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            num_matches=10
        )

        # Assert
        mock_db_client.query_match_history.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            league_id=None,
            date_from=None,
            date_to=None,
            limit=10
        )
