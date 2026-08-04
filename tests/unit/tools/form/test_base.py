"""
Unit tests for form analysis base classes.

Tests:
- FormWeightCalculator
- FormTrendCalculator
- ConsistencyAnalyzer
- BaseFormTool
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sipap_data_mcp.tools.form.base import (
    FormWeightCalculator,
    FormTrendCalculator,
    ConsistencyAnalyzer,
    BaseFormTool
)


class TestFormWeightCalculator:
    """Test FormWeightCalculator class."""

    def test_calculate_points_perfect_last_5(self):
        """Test calculation when last 5 matches are all wins."""
        # Arrange
        last_5 = [
            {"home_team": "Arsenal", "away_team": "Chelsea", "home_score": 2, "away_score": 1},
            {"home_team": "Arsenal", "away_team": "Liverpool", "home_score": 3, "away_score": 0},
            {"home_team": "Man City", "away_team": "Arsenal", "home_score": 0, "away_score": 2},
            {"home_team": "Arsenal", "away_team": "Spurs", "home_score": 1, "away_score": 0},
            {"home_team": "Arsenal", "away_team": "West Ham", "home_score": 2, "away_score": 0}
        ]
        previous_5 = []
        longer_term = []

        # Act
        result = FormWeightCalculator.calculate_points(
            last_5=last_5,
            previous_5=previous_5,
            longer_term=longer_term,
            team="Arsenal"
        )

        # Assert
        assert result["last_5_points"] == 15  # 5 wins
        assert result["weighted_points"] == 9.0  # (15/15 * 0.6) * 15 = 9.0

    def test_calculate_points_with_draws_and_losses(self):
        """Test calculation with mixed results."""
        # Arrange
        last_5 = [
            {"home_team": "Arsenal", "away_team": "Chelsea", "home_score": 2, "away_score": 1},  # Win
            {"home_team": "Arsenal", "away_team": "Liverpool", "home_score": 1, "away_score": 1},  # Draw
            {"home_team": "Man City", "away_team": "Arsenal", "home_score": 2, "away_score": 0},  # Loss
            {"home_team": "Arsenal", "away_team": "Spurs", "home_score": 1, "away_score": 0},  # Win
            {"home_team": "Arsenal", "away_team": "West Ham", "home_score": 0, "away_score": 2}  # Loss
        ]
        previous_5 = []
        longer_term = []

        # Act
        result = FormWeightCalculator.calculate_points(
            last_5=last_5,
            previous_5=previous_5,
            longer_term=longer_term,
            team="Arsenal"
        )

        # Assert
        assert result["last_5_points"] == 7  # 2W (6) + 1D (1) = 7
        assert result["weighted_points"] == 4.2  # (7/15 * 0.6) * 15 = 4.2

    def test_calculate_points_empty_lists(self):
        """Test calculation with empty match lists."""
        # Act
        result = FormWeightCalculator.calculate_points(
            last_5=[],
            previous_5=[],
            longer_term=[],
            team="Arsenal"
        )

        # Assert
        assert result["weighted_points"] == 0.0
        assert result["last_5_points"] == 0
        assert result["max_possible"] == 15.0


class TestFormTrendCalculator:
    """Test FormTrendCalculator class."""

    def test_analyze_improving_trend(self):
        """Test detection of improving form."""
        # Act
        result = FormTrendCalculator.analyze(
            last_5_points=13,
            previous_5_points=9
        )

        # Assert
        assert result["trend"] == "improving"
        assert result["points_change"] == 4
        assert result["percentage_change"] == 44.4

    def test_analyze_declining_trend(self):
        """Test detection of declining form."""
        # Act
        result = FormTrendCalculator.analyze(
            last_5_points=6,
            previous_5_points=12
        )

        # Assert
        assert result["trend"] == "declining"
        assert result["points_change"] == -6
        assert result["percentage_change"] == -50.0

    def test_analyze_stable_trend(self):
        """Test detection of stable form."""
        # Act
        result = FormTrendCalculator.analyze(
            last_5_points=10,
            previous_5_points=9
        )

        # Assert
        assert result["trend"] == "stable"
        assert result["points_change"] == 1
        assert abs(result["percentage_change"] - 11.1) < 0.1

    def test_analyze_zero_previous_points(self):
        """Test handling of zero previous points."""
        # Act
        result = FormTrendCalculator.analyze(
            last_5_points=10,
            previous_5_points=0
        )

        # Assert
        assert result["trend"] == "improving"
        assert result["percentage_change"] == 0.0  # Avoid division by zero


class TestConsistencyAnalyzer:
    """Test ConsistencyAnalyzer class."""

    def test_analyze_consistent_wins(self):
        """Test analysis of consistent winning form."""
        # Arrange
        matches = [
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 2, "away_score": 0},
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 3, "away_score": 1},
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 2, "away_score": 1},
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 1, "away_score": 0},
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 2, "away_score": 0}
        ]

        # Act
        result = ConsistencyAnalyzer.analyze(matches, "Arsenal")

        # Assert
        assert result["volatility"] == "low"
        assert result["pattern"] == "consistent"
        assert result["consistency_rating"] > 80

    def test_analyze_erratic_form(self):
        """Test analysis of erratic form."""
        # Arrange
        matches = [
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 3, "away_score": 0},  # Win
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 0, "away_score": 3},  # Loss
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 3, "away_score": 0},  # Win
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 0, "away_score": 3},  # Loss
            {"home_team": "Arsenal", "away_team": "Team", "home_score": 1, "away_score": 1}   # Draw
        ]

        # Act
        result = ConsistencyAnalyzer.analyze(matches, "Arsenal")

        # Assert
        assert result["volatility"] in ["medium", "high"]
        assert result["std_deviation"] > 1.0

    def test_analyze_empty_matches(self):
        """Test analysis with no matches."""
        # Act
        result = ConsistencyAnalyzer.analyze([], "Arsenal")

        # Assert
        assert result["consistency_rating"] == 0
        assert result["volatility"] == "high"
        assert result["pattern"] == "erratic"


class TestBaseFormTool:
    """Test BaseFormTool class."""

    @pytest.mark.asyncio
    async def test_get_recent_team_matches_success(self):
        """Test successful retrieval of recent team matches."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {}
            },
            {
                "id": "2",
                "scheduled_at": datetime(2026, 7, 25),
                "home_team": "Liverpool",
                "away_team": "Arsenal",
                "home_score": 1,
                "away_score": 2,
                "status": "finished",
                "league": "Premier League",
                "metadata": {}
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseFormTool.get_recent_team_matches(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League",
            match_limit=10
        )

        # Assert
        assert len(result) == 2
        assert result[0]["home_team"] == "Arsenal"
        assert result[1]["away_team"] == "Arsenal"

    @pytest.mark.asyncio
    async def test_get_recent_team_matches_venue_filter_home(self):
        """Test retrieval with home venue filter."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {}
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseFormTool.get_recent_team_matches(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League",
            match_limit=10,
            venue="home"
        )

        # Assert
        assert len(result) == 1
        assert result[0]["home_team"] == "Arsenal"

    @pytest.mark.asyncio
    async def test_get_recent_h2h_matches_success(self):
        """Test successful retrieval of recent h2h matches."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {}
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseFormTool.get_recent_h2h_matches(
            pool=mock_pool,
            home_team="Arsenal",
            away_team="Chelsea",
            league="Premier League",
            match_limit=10
        )

        # Assert
        assert len(result) == 1
        assert result[0]["home_team"] == "Arsenal"
        assert result[0]["away_team"] == "Chelsea"

    @pytest.mark.asyncio
    async def test_get_recent_team_matches_no_data(self):
        """Test retrieval when no matches exist."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        # Act
        result = await BaseFormTool.get_recent_team_matches(
            pool=mock_pool,
            team="Arsenal",
            league="Premier League",
            match_limit=10
        )

        # Assert
        assert result == []
