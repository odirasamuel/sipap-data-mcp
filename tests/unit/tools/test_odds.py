"""Tests for odds intelligence MCP tools.

Tests cover:
- get_match_odds: Retrieve betting odds from multiple bookmakers
- get_odds_movements: Track odds changes over time
"""

from unittest.mock import AsyncMock

import pytest


class TestGetMatchOdds:
    """Test suite for get_match_odds tool."""

    @pytest.mark.asyncio
    async def test_get_match_odds_success(self, mock_db_client):
        """Test get_match_odds returns odds data for a match."""
        from sipap_data_mcp.tools.odds import get_match_odds

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        odds_data = {
            "match_id": match_id,
            "bookmakers": [
                {
                    "bookmaker": "Bet365",
                    "home_odds": 2.10,
                    "draw_odds": 3.40,
                    "away_odds": 3.60,
                    "updated_at": "2026-07-05T10:00:00Z"
                },
                {
                    "bookmaker": "William Hill",
                    "home_odds": 2.15,
                    "draw_odds": 3.30,
                    "away_odds": 3.50,
                    "updated_at": "2026-07-05T10:05:00Z"
                }
            ],
            "best_odds": {
                "home": {"odds": 2.15, "bookmaker": "William Hill"},
                "draw": {"odds": 3.40, "bookmaker": "Bet365"},
                "away": {"odds": 3.60, "bookmaker": "Bet365"}
            },
            "average_odds": {
                "home": 2.125,
                "draw": 3.35,
                "away": 3.55
            }
        }
        mock_db_client.get_match_odds = AsyncMock(return_value=odds_data)

        # Act
        result = await get_match_odds(
            db_client=mock_db_client,
            match_id=match_id
        )

        # Assert
        assert isinstance(result, dict)
        assert "bookmakers" in result
        assert "best_odds" in result
        assert "average_odds" in result
        assert len(result["bookmakers"]) == 2
        assert result["best_odds"]["home"]["odds"] == 2.15
        mock_db_client.get_match_odds.assert_called_once_with(match_id)

    @pytest.mark.asyncio
    async def test_get_match_odds_not_found(self, mock_db_client):
        """Test get_match_odds when match has no odds data."""
        from sipap_data_mcp.tools.odds import get_match_odds

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440099"
        mock_db_client.get_match_odds = AsyncMock(return_value=None)

        # Act
        result = await get_match_odds(
            db_client=mock_db_client,
            match_id=match_id
        )

        # Assert
        assert result is None
        mock_db_client.get_match_odds.assert_called_once_with(match_id)

    @pytest.mark.asyncio
    async def test_get_match_odds_invalid_uuid(self, mock_db_client):
        """Test get_match_odds validates UUID format."""
        from sipap_data_mcp.tools.odds import get_match_odds

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_match_odds(
                db_client=mock_db_client,
                match_id="not-a-valid-uuid"
            )

    @pytest.mark.asyncio
    async def test_get_match_odds_empty_bookmakers(self, mock_db_client):
        """Test get_match_odds handles empty bookmaker list."""
        from sipap_data_mcp.tools.odds import get_match_odds

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        odds_data = {
            "match_id": match_id,
            "bookmakers": [],
            "best_odds": {},
            "average_odds": {}
        }
        mock_db_client.get_match_odds = AsyncMock(return_value=odds_data)

        # Act
        result = await get_match_odds(
            db_client=mock_db_client,
            match_id=match_id
        )

        # Assert
        assert result["bookmakers"] == []


class TestGetOddsMovements:
    """Test suite for get_odds_movements tool."""

    @pytest.mark.asyncio
    async def test_get_odds_movements_success(self, mock_db_client):
        """Test get_odds_movements returns odds changes over time."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        movements_data = {
            "match_id": match_id,
            "time_window": "24h",
            "movements": [
                {
                    "timestamp": "2026-07-05T10:00:00Z",
                    "bookmaker": "Bet365",
                    "home_odds": 2.10,
                    "draw_odds": 3.40,
                    "away_odds": 3.60
                },
                {
                    "timestamp": "2026-07-05T14:00:00Z",
                    "bookmaker": "Bet365",
                    "home_odds": 2.00,
                    "draw_odds": 3.50,
                    "away_odds": 3.80
                }
            ],
            "opening_odds": {
                "home": 2.10,
                "draw": 3.40,
                "away": 3.60
            },
            "current_odds": {
                "home": 2.00,
                "draw": 3.50,
                "away": 3.80
            },
            "movement_summary": {
                "home": -0.10,
                "draw": +0.10,
                "away": +0.20
            }
        }
        mock_db_client.get_odds_movements = AsyncMock(return_value=movements_data)

        # Act
        result = await get_odds_movements(
            db_client=mock_db_client,
            match_id=match_id,
            time_window="24h"
        )

        # Assert
        assert isinstance(result, dict)
        assert "movements" in result
        assert "opening_odds" in result
        assert "current_odds" in result
        assert "movement_summary" in result
        assert len(result["movements"]) == 2
        assert result["movement_summary"]["home"] == -0.10
        mock_db_client.get_odds_movements.assert_called_once_with(match_id, "24h")

    @pytest.mark.asyncio
    async def test_get_odds_movements_default_time_window(self, mock_db_client):
        """Test get_odds_movements uses default 24h time window."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        movements_data = {
            "match_id": match_id,
            "time_window": "24h",
            "movements": [],
            "opening_odds": {},
            "current_odds": {},
            "movement_summary": {}
        }
        mock_db_client.get_odds_movements = AsyncMock(return_value=movements_data)

        # Act
        result = await get_odds_movements(
            db_client=mock_db_client,
            match_id=match_id
        )

        # Assert
        assert result["time_window"] == "24h"
        mock_db_client.get_odds_movements.assert_called_once_with(match_id, "24h")

    @pytest.mark.asyncio
    async def test_get_odds_movements_invalid_uuid(self, mock_db_client):
        """Test get_odds_movements validates UUID format."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid UUID"):
            await get_odds_movements(
                db_client=mock_db_client,
                match_id="invalid-uuid"
            )

    @pytest.mark.asyncio
    async def test_get_odds_movements_invalid_time_window(self, mock_db_client):
        """Test get_odds_movements validates time_window format."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid time_window"):
            await get_odds_movements(
                db_client=mock_db_client,
                match_id=match_id,
                time_window="invalid"
            )

    @pytest.mark.asyncio
    async def test_get_odds_movements_no_movements(self, mock_db_client):
        """Test get_odds_movements when no odds movements exist."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_db_client.get_odds_movements = AsyncMock(return_value=None)

        # Act
        result = await get_odds_movements(
            db_client=mock_db_client,
            match_id=match_id
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_odds_movements_custom_time_windows(self, mock_db_client):
        """Test get_odds_movements with different time windows."""
        from sipap_data_mcp.tools.odds import get_odds_movements

        # Arrange
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        movements_data = {
            "match_id": match_id,
            "time_window": "1h",
            "movements": [],
            "opening_odds": {},
            "current_odds": {},
            "movement_summary": {}
        }
        mock_db_client.get_odds_movements = AsyncMock(return_value=movements_data)

        # Test various time windows
        time_windows = ["1h", "6h", "12h", "24h", "48h", "7d"]

        for window in time_windows:
            movements_data["time_window"] = window
            result = await get_odds_movements(
                db_client=mock_db_client,
                match_id=match_id,
                time_window=window
            )
            assert result["time_window"] == window
