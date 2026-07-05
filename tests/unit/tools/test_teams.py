"""Unit tests for team tools.

Following TDD methodology: Tests written BEFORE implementation.
These tests define the expected behavior of team-related MCP tools.
"""

from unittest.mock import AsyncMock

import pytest

from tests.fixtures.teams import SAMPLE_LEAGUE_TABLE, SAMPLE_TEAM_STATS


class TestGetTeamStats:
    """Tests for get_team_stats MCP tool."""

    @pytest.mark.asyncio
    async def test_get_team_stats_success(self, mock_db_client):
        """Test get_team_stats returns team statistics."""
        from sipap_data_mcp.tools.teams import get_team_stats

        # Arrange
        mock_db_client.get_team_stats = AsyncMock(return_value=SAMPLE_TEAM_STATS)

        # Act
        result = await get_team_stats(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            season="2024-2025"
        )

        # Assert
        assert isinstance(result, dict)
        assert "stats" in result
        assert result["stats"]["team_name"] == "Arsenal"
        assert result["stats"]["matches_played"] == 38
        assert result["stats"]["points"] == 91

        mock_db_client.get_team_stats.assert_called_once_with(
            team_id="550e8400-e29b-41d4-a716-446655440010",
            season="2024-2025"
        )

    @pytest.mark.asyncio
    async def test_get_team_stats_not_found(self, mock_db_client):
        """Test get_team_stats raises error when team stats not found."""
        from sipap_data_mcp.tools.teams import get_team_stats

        # Arrange
        mock_db_client.get_team_stats = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Team stats not found"):
            await get_team_stats(
                db_client=mock_db_client,
                team_id="00000000-0000-0000-0000-000000000000",  # Valid UUID format
                season="2024-2025"
            )

    @pytest.mark.asyncio
    async def test_get_team_stats_invalid_uuid(self, mock_db_client):
        """Test get_team_stats validates UUID format."""
        from sipap_data_mcp.tools.teams import get_team_stats

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_team_stats(
                db_client=mock_db_client,
                team_id="not-a-uuid",
                season="2024-2025"
            )

    @pytest.mark.asyncio
    async def test_get_team_stats_invalid_season_format(self, mock_db_client):
        """Test get_team_stats validates season format."""
        from sipap_data_mcp.tools.teams import get_team_stats

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid season format"):
            await get_team_stats(
                db_client=mock_db_client,
                team_id="550e8400-e29b-41d4-a716-446655440000",
                season="invalid"
            )

    @pytest.mark.asyncio
    async def test_get_team_stats_with_home_away_records(self, mock_db_client):
        """Test get_team_stats returns home/away records."""
        from sipap_data_mcp.tools.teams import get_team_stats

        # Arrange
        mock_db_client.get_team_stats = AsyncMock(return_value=SAMPLE_TEAM_STATS)

        # Act
        result = await get_team_stats(
            db_client=mock_db_client,
            team_id="550e8400-e29b-41d4-a716-446655440010",
            season="2024-2025"
        )

        # Assert
        assert "home_record" in result["stats"]
        assert result["stats"]["home_record"]["wins"] == 16
        assert "away_record" in result["stats"]
        assert result["stats"]["away_record"]["wins"] == 12


class TestGetLeagueTable:
    """Tests for get_league_table MCP tool."""

    @pytest.mark.asyncio
    async def test_get_league_table_success(self, mock_db_client):
        """Test get_league_table returns league standings."""
        from sipap_data_mcp.tools.teams import get_league_table

        # Arrange
        mock_db_client.get_league_table = AsyncMock(return_value=SAMPLE_LEAGUE_TABLE)

        # Act
        result = await get_league_table(
            db_client=mock_db_client,
            league_id="550e8400-e29b-41d4-a716-446655440020",
            season="2024-2025"
        )

        # Assert
        assert isinstance(result, dict)
        assert "standings" in result
        assert len(result["standings"]) == 2
        assert result["standings"][0]["position"] == 1
        assert result["standings"][0]["team_name"] == "Arsenal"
        assert result["standings"][1]["position"] == 2

        mock_db_client.get_league_table.assert_called_once_with(
            league_id="550e8400-e29b-41d4-a716-446655440020",
            season="2024-2025"
        )

    @pytest.mark.asyncio
    async def test_get_league_table_empty(self, mock_db_client):
        """Test get_league_table returns empty list when no standings found."""
        from sipap_data_mcp.tools.teams import get_league_table

        # Arrange
        mock_db_client.get_league_table = AsyncMock(return_value=[])

        # Act
        result = await get_league_table(
            db_client=mock_db_client,
            league_id="550e8400-e29b-41d4-a716-446655440020",
            season="2024-2025"
        )

        # Assert
        assert result["standings"] == []

    @pytest.mark.asyncio
    async def test_get_league_table_invalid_uuid(self, mock_db_client):
        """Test get_league_table validates UUID format."""
        from sipap_data_mcp.tools.teams import get_league_table

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_league_table(
                db_client=mock_db_client,
                league_id="not-a-uuid",
                season="2024-2025"
            )

    @pytest.mark.asyncio
    async def test_get_league_table_sorted_by_position(self, mock_db_client):
        """Test get_league_table returns standings sorted by position."""
        from sipap_data_mcp.tools.teams import get_league_table

        # Arrange
        mock_db_client.get_league_table = AsyncMock(return_value=SAMPLE_LEAGUE_TABLE)

        # Act
        result = await get_league_table(
            db_client=mock_db_client,
            league_id="550e8400-e29b-41d4-a716-446655440020",
            season="2024-2025"
        )

        # Assert - verify ordering
        positions = [standing["position"] for standing in result["standings"]]
        assert positions == sorted(positions)  # Should be [1, 2]


class TestGetHeadToHead:
    """Tests for get_head_to_head MCP tool."""

    @pytest.mark.asyncio
    async def test_get_head_to_head_success(self, mock_db_client):
        """Test get_head_to_head returns historical matchup data."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Arrange
        h2h_data = {
            "team1_id": "550e8400-e29b-41d4-a716-446655440010",
            "team2_id": "550e8400-e29b-41d4-a716-446655440011",
            "team1_name": "Arsenal",
            "team2_name": "Chelsea",
            "total_matches": 10,
            "team1_wins": 4,
            "team2_wins": 3,
            "draws": 3,
            "recent_matches": []
        }
        mock_db_client.get_head_to_head = AsyncMock(return_value=h2h_data)

        # Act
        result = await get_head_to_head(
            db_client=mock_db_client,
            team1_id="550e8400-e29b-41d4-a716-446655440010",
            team2_id="550e8400-e29b-41d4-a716-446655440011",
            limit=10
        )

        # Assert
        assert isinstance(result, dict)
        assert "head_to_head" in result
        assert result["head_to_head"]["team1_name"] == "Arsenal"
        assert result["head_to_head"]["team2_name"] == "Chelsea"
        assert result["head_to_head"]["total_matches"] == 10
        assert result["head_to_head"]["team1_wins"] == 4

        mock_db_client.get_head_to_head.assert_called_once_with(
            team1_id="550e8400-e29b-41d4-a716-446655440010",
            team2_id="550e8400-e29b-41d4-a716-446655440011",
            limit=10
        )

    @pytest.mark.asyncio
    async def test_get_head_to_head_no_history(self, mock_db_client):
        """Test get_head_to_head handles teams with no match history."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Arrange
        h2h_data = {
            "team1_id": "550e8400-e29b-41d4-a716-446655440010",
            "team2_id": "550e8400-e29b-41d4-a716-446655440011",
            "team1_name": "Arsenal",
            "team2_name": "New Team",
            "total_matches": 0,
            "team1_wins": 0,
            "team2_wins": 0,
            "draws": 0,
            "recent_matches": []
        }
        mock_db_client.get_head_to_head = AsyncMock(return_value=h2h_data)

        # Act
        result = await get_head_to_head(
            db_client=mock_db_client,
            team1_id="550e8400-e29b-41d4-a716-446655440010",
            team2_id="550e8400-e29b-41d4-a716-446655440011"
        )

        # Assert
        assert result["head_to_head"]["total_matches"] == 0

    @pytest.mark.asyncio
    async def test_get_head_to_head_invalid_team1_uuid(self, mock_db_client):
        """Test get_head_to_head validates team1_id UUID format."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_head_to_head(
                db_client=mock_db_client,
                team1_id="not-a-uuid",
                team2_id="550e8400-e29b-41d4-a716-446655440011"
            )

    @pytest.mark.asyncio
    async def test_get_head_to_head_invalid_team2_uuid(self, mock_db_client):
        """Test get_head_to_head validates team2_id UUID format."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_head_to_head(
                db_client=mock_db_client,
                team1_id="550e8400-e29b-41d4-a716-446655440000",
                team2_id="not-a-uuid"
            )

    @pytest.mark.asyncio
    async def test_get_head_to_head_same_team(self, mock_db_client):
        """Test get_head_to_head raises error when both teams are the same."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot compare team with itself"):
            await get_head_to_head(
                db_client=mock_db_client,
                team1_id="550e8400-e29b-41d4-a716-446655440000",
                team2_id="550e8400-e29b-41d4-a716-446655440000"
            )

    @pytest.mark.asyncio
    async def test_get_head_to_head_with_limit(self, mock_db_client):
        """Test get_head_to_head respects limit parameter."""
        from sipap_data_mcp.tools.teams import get_head_to_head

        # Arrange
        h2h_data = {
            "team1_id": "550e8400-e29b-41d4-a716-446655440010",
            "team2_id": "550e8400-e29b-41d4-a716-446655440011",
            "team1_name": "Arsenal",
            "team2_name": "Chelsea",
            "total_matches": 50,
            "team1_wins": 20,
            "team2_wins": 18,
            "draws": 12,
            "recent_matches": []
        }
        mock_db_client.get_head_to_head = AsyncMock(return_value=h2h_data)

        # Act
        await get_head_to_head(
            db_client=mock_db_client,
            team1_id="550e8400-e29b-41d4-a716-446655440010",
            team2_id="550e8400-e29b-41d4-a716-446655440011",
            limit=5
        )

        # Assert
        mock_db_client.get_head_to_head.assert_called_once_with(
            team1_id="550e8400-e29b-41d4-a716-446655440010",
            team2_id="550e8400-e29b-41d4-a716-446655440011",
            limit=5
        )
