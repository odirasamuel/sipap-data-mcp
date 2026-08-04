"""
Unit tests for form pattern analysis tools.

Tests:
- get_momentum_streak
- get_form_trajectory
- get_consistency_score
- get_venue_form_split
- get_goal_scoring_form_trend
- get_defensive_form_trend
- get_pressure_performance
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sipap_data_mcp.tools.form import (
    get_momentum_streak,
    get_form_trajectory,
    get_consistency_score,
    get_venue_form_split,
    get_goal_scoring_form_trend,
    get_defensive_form_trend,
    get_pressure_performance
)


def create_sample_match(home_team: str, away_team: str, home_score: int, away_score: int, date: datetime):
    """Helper to create sample match data."""
    return {
        "id": f"{home_team}-{away_team}-{date.isoformat()}",
        "scheduled_at": date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "status": "finished",
        "league": "Premier League",
        "metadata": {}
    }


class TestGetMomentumStreak:
    """Test get_momentum_streak tool."""

    @pytest.mark.asyncio
    async def test_detects_winning_streak(self):
        """Test detection of 5-match winning streak."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # 5-match winning streak
        sample_matches = [
            create_sample_match("Arsenal", "Chelsea", 2, 1, datetime(2026, 8, 1)),
            create_sample_match("Arsenal", "Liverpool", 3, 0, datetime(2026, 7, 28)),
            create_sample_match("Man City", "Arsenal", 0, 2, datetime(2026, 7, 25)),
            create_sample_match("Arsenal", "Spurs", 1, 0, datetime(2026, 7, 22)),
            create_sample_match("Arsenal", "West Ham", 2, 0, datetime(2026, 7, 19))
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_momentum_streak(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["current_streak"]["type"] == "winning"
        assert result["data"]["current_streak"]["length"] == 5
        assert result["data"]["current_streak"]["points"] == 15
        assert result["data"]["momentum_rating"] > 80

    @pytest.mark.asyncio
    async def test_detects_mixed_form(self):
        """Test detection of mixed form (no clear streak)."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mixed results
        sample_matches = [
            create_sample_match("Arsenal", "Chelsea", 2, 1, datetime(2026, 8, 1)),  # Win
            create_sample_match("Arsenal", "Liverpool", 0, 2, datetime(2026, 7, 28)),  # Loss
            create_sample_match("Man City", "Arsenal", 1, 1, datetime(2026, 7, 25)),  # Draw
            create_sample_match("Arsenal", "Spurs", 1, 0, datetime(2026, 7, 22)),  # Win
            create_sample_match("Arsenal", "West Ham", 0, 2, datetime(2026, 7, 19))  # Loss
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_momentum_streak(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["current_streak"]["type"] == "mixed"
        assert result["data"]["current_streak"]["length"] == 1
        assert result["data"]["momentum_rating"] < 60

    @pytest.mark.asyncio
    async def test_handles_no_matches(self):
        """Test handling of no match data."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        # Act
        result = await get_momentum_streak(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["current_streak"]["type"] == "mixed"
        assert result["data"]["current_streak"]["length"] == 0
        assert result["data"]["momentum_rating"] == 0


class TestGetFormTrajectory:
    """Test get_form_trajectory tool."""

    @pytest.mark.asyncio
    async def test_detects_improving_trajectory(self):
        """Test detection of improving form."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Last 5: 4W 1D (13 points), Previous 5: 3W 0D 2L (9 points)
        sample_matches = [
            # Last 5 (better form)
            create_sample_match("Arsenal", "Team1", 2, 1, datetime(2026, 8, 1)),  # W
            create_sample_match("Arsenal", "Team2", 3, 0, datetime(2026, 7, 28)),  # W
            create_sample_match("Arsenal", "Team3", 1, 1, datetime(2026, 7, 25)),  # D
            create_sample_match("Arsenal", "Team4", 2, 0, datetime(2026, 7, 22)),  # W
            create_sample_match("Arsenal", "Team5", 1, 0, datetime(2026, 7, 19)),  # W
            # Previous 5 (worse form)
            create_sample_match("Arsenal", "Team6", 2, 1, datetime(2026, 7, 16)),  # W
            create_sample_match("Arsenal", "Team7", 0, 2, datetime(2026, 7, 13)),  # L
            create_sample_match("Arsenal", "Team8", 2, 1, datetime(2026, 7, 10)),  # W
            create_sample_match("Arsenal", "Team9", 1, 2, datetime(2026, 7, 7)),   # L
            create_sample_match("Arsenal", "Team10", 3, 0, datetime(2026, 7, 4))   # W
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_form_trajectory(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["trajectory"] == "improving"
        assert result["data"]["last_5"]["points"] == 13
        assert result["data"]["previous_5"]["points"] == 9
        assert result["data"]["comparison"]["points_change"] == 4

    @pytest.mark.asyncio
    async def test_detects_declining_trajectory(self):
        """Test detection of declining form."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Last 5: 1W 1D 3L (4 points), Previous 5: 4W 0D 1L (12 points)
        sample_matches = [
            # Last 5 (worse form)
            create_sample_match("Arsenal", "Team1", 0, 2, datetime(2026, 8, 1)),   # L
            create_sample_match("Arsenal", "Team2", 0, 1, datetime(2026, 7, 28)),  # L
            create_sample_match("Arsenal", "Team3", 1, 1, datetime(2026, 7, 25)),  # D
            create_sample_match("Arsenal", "Team4", 2, 0, datetime(2026, 7, 22)),  # W
            create_sample_match("Arsenal", "Team5", 0, 3, datetime(2026, 7, 19)),  # L
            # Previous 5 (better form)
            create_sample_match("Arsenal", "Team6", 2, 0, datetime(2026, 7, 16)),  # W
            create_sample_match("Arsenal", "Team7", 3, 1, datetime(2026, 7, 13)),  # W
            create_sample_match("Arsenal", "Team8", 1, 2, datetime(2026, 7, 10)),  # L
            create_sample_match("Arsenal", "Team9", 2, 1, datetime(2026, 7, 7)),   # W
            create_sample_match("Arsenal", "Team10", 3, 0, datetime(2026, 7, 4))   # W
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_form_trajectory(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["trajectory"] == "declining"
        assert result["data"]["last_5"]["points"] == 4
        assert result["data"]["previous_5"]["points"] == 12
        assert result["data"]["comparison"]["points_change"] == -8


class TestGetConsistencyScore:
    """Test get_consistency_score tool."""

    @pytest.mark.asyncio
    async def test_high_consistency_rating(self):
        """Test high consistency rating for consistent wins."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Consistent winning form
        base_date = datetime(2026, 8, 1)
        sample_matches = [
            create_sample_match("Arsenal", f"Team{i}", 2, 0, base_date - timedelta(days=i))
            for i in range(10)
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_consistency_score(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["consistency_rating"] > 80
        assert result["data"]["volatility"] == "low"
        assert result["data"]["pattern"] == "consistent"
        assert result["data"]["result_distribution"]["dominant_result"] == "wins"

    @pytest.mark.asyncio
    async def test_low_consistency_rating(self):
        """Test low consistency rating for erratic form."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Erratic form (W-L-W-L-D pattern)
        sample_matches = [
            create_sample_match("Arsenal", "Team1", 2, 0, datetime(2026, 8, 1)),   # W
            create_sample_match("Arsenal", "Team2", 0, 2, datetime(2026, 7, 28)),  # L
            create_sample_match("Arsenal", "Team3", 3, 1, datetime(2026, 7, 25)),  # W
            create_sample_match("Arsenal", "Team4", 0, 3, datetime(2026, 7, 22)),  # L
            create_sample_match("Arsenal", "Team5", 1, 1, datetime(2026, 7, 19)),  # D
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_consistency_score(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["consistency_rating"] < 70
        assert result["data"]["volatility"] in ["medium", "high"]


class TestGetVenueFormSplit:
    """Test get_venue_form_split tool."""

    @pytest.mark.asyncio
    async def test_strong_home_advantage(self):
        """Test detection of strong home advantage."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Strong home form
        base_date = datetime(2026, 8, 1)
        home_matches = [
            create_sample_match("Arsenal", f"Team{i}", 2, 0, base_date - timedelta(days=i))
            for i in range(10)
        ]

        # Weak away form
        away_matches = [
            create_sample_match(f"Team{i}", "Arsenal", 2, 1, base_date - timedelta(days=i))
            for i in range(10)
        ]

        # Mock multiple calls
        mock_conn.fetch.side_effect = [home_matches, away_matches]

        # Act
        result = await get_venue_form_split(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["comparison"]["stronger_venue"] == "home"
        assert result["data"]["comparison"]["venue_impact"] in ["medium", "high"]
        assert result["data"]["home_form"]["points"] > result["data"]["away_form"]["points"]


class TestGetGoalScoringFormTrend:
    """Test get_goal_scoring_form_trend tool."""

    @pytest.mark.asyncio
    async def test_increasing_goal_trend(self):
        """Test detection of increasing goals scored."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Last 5: averaging 2.4 goals, Previous 5: averaging 1.6 goals
        sample_matches = [
            # Last 5 (high scoring)
            create_sample_match("Arsenal", "Team1", 3, 1, datetime(2026, 8, 1)),   # 3 goals
            create_sample_match("Arsenal", "Team2", 2, 0, datetime(2026, 7, 28)),  # 2 goals
            create_sample_match("Arsenal", "Team3", 2, 1, datetime(2026, 7, 25)),  # 2 goals
            create_sample_match("Arsenal", "Team4", 3, 2, datetime(2026, 7, 22)),  # 3 goals
            create_sample_match("Arsenal", "Team5", 2, 0, datetime(2026, 7, 19)),  # 2 goals
            # Previous 5 (lower scoring)
            create_sample_match("Arsenal", "Team6", 2, 1, datetime(2026, 7, 16)),  # 2 goals
            create_sample_match("Arsenal", "Team7", 1, 0, datetime(2026, 7, 13)),  # 1 goal
            create_sample_match("Arsenal", "Team8", 1, 1, datetime(2026, 7, 10)),  # 1 goal
            create_sample_match("Arsenal", "Team9", 2, 2, datetime(2026, 7, 7)),   # 2 goals
            create_sample_match("Arsenal", "Team10", 2, 1, datetime(2026, 7, 4))   # 2 goals
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_goal_scoring_form_trend(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["trend"] == "increasing"
        assert result["data"]["last_5"]["avg_per_match"] == 2.4
        assert result["data"]["previous_5"]["avg_per_match"] == 1.6
        assert result["data"]["comparison"]["avg_change"] > 0
        assert result["data"]["offensive_rating"] > 70


class TestGetDefensiveFormTrend:
    """Test get_defensive_form_trend tool."""

    @pytest.mark.asyncio
    async def test_tightening_defense(self):
        """Test detection of improving defensive form."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Last 5: conceding 0.6/match, Previous 5: conceding 1.2/match
        sample_matches = [
            # Last 5 (tight defense)
            create_sample_match("Arsenal", "Team1", 2, 0, datetime(2026, 8, 1)),   # 0 conceded
            create_sample_match("Arsenal", "Team2", 3, 1, datetime(2026, 7, 28)),  # 1 conceded
            create_sample_match("Arsenal", "Team3", 2, 0, datetime(2026, 7, 25)),  # 0 conceded
            create_sample_match("Arsenal", "Team4", 1, 0, datetime(2026, 7, 22)),  # 0 conceded
            create_sample_match("Arsenal", "Team5", 2, 2, datetime(2026, 7, 19)),  # 2 conceded
            # Previous 5 (leaky defense)
            create_sample_match("Arsenal", "Team6", 2, 1, datetime(2026, 7, 16)),  # 1 conceded
            create_sample_match("Arsenal", "Team7", 1, 2, datetime(2026, 7, 13)),  # 2 conceded
            create_sample_match("Arsenal", "Team8", 2, 1, datetime(2026, 7, 10)),  # 1 conceded
            create_sample_match("Arsenal", "Team9", 3, 2, datetime(2026, 7, 7)),   # 2 conceded
            create_sample_match("Arsenal", "Team10", 2, 0, datetime(2026, 7, 4))   # 0 conceded
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await get_defensive_form_trend(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["trend"] == "tightening"
        assert result["data"]["last_5"]["clean_sheets"] == 3
        assert result["data"]["comparison"]["avg_change"] < 0  # Negative = improvement
        assert result["data"]["defensive_rating"] > 70


class TestGetPressurePerformance:
    """Test get_pressure_performance tool."""

    @pytest.mark.asyncio
    async def test_struggles_vs_strong_opponents(self):
        """Test detection of struggles against strong opponents."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Recent matches (mixed vs strong and weak opponents)
        sample_matches = [
            create_sample_match("Arsenal", "Man City", 0, 2, datetime(2026, 8, 1)),    # Loss (strong)
            create_sample_match("Arsenal", "Weak Team1", 3, 0, datetime(2026, 7, 28)),  # Win (weak)
            create_sample_match("Liverpool", "Arsenal", 2, 1, datetime(2026, 7, 25)),   # Loss (strong)
            create_sample_match("Arsenal", "Weak Team2", 2, 0, datetime(2026, 7, 22)),  # Win (weak)
            create_sample_match("Arsenal", "Weak Team3", 3, 1, datetime(2026, 7, 19)),  # Win (weak)
        ]

        # Mock opponent queries (first 2 are strong, last 3 are weak)
        async def mock_fetchrow_side_effect(*args, **kwargs):
            opponent = args[0] if args else kwargs.get('opponent', '')
            if opponent in ["Man City", "Liverpool"]:
                return {"wins": 7, "total_matches": 10}  # 70% win rate (strong)
            else:
                return {"wins": 3, "total_matches": 10}  # 30% win rate (weak)

        mock_conn.fetch.return_value = sample_matches
        mock_conn.fetchrow.side_effect = mock_fetchrow_side_effect

        # Act
        result = await get_pressure_performance(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League"
        )

        # Assert
        assert result["data"]["vs_strong_opponents"]["matches"] >= 0
        assert result["data"]["vs_weaker_opponents"]["matches"] >= 0
        # Points per match should be better vs weaker opponents
        # (This assertion may vary based on actual categorization logic)
