"""
Unit tests for statistical analysis base classes.

Tests:
- RecencyWeightCalculator
- DataQualityClassifier
- BaseStatisticalTool
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sipap_data_mcp.tools.statistical.base import (
    RecencyWeightCalculator,
    DataQualityClassifier,
    BaseStatisticalTool
)


class TestRecencyWeightCalculator:
    """Test RecencyWeightCalculator class."""

    def test_calculate_with_all_home_wins_recent(self):
        """Test weighted calculation when recent matches are all home wins."""
        # Arrange
        recent = [{"home_score": 2, "away_score": 1} for _ in range(10)]  # 100% home wins
        last_season = [{"home_score": 1, "away_score": 2} for _ in range(5)]  # 0% home wins
        older = [{"home_score": 1, "away_score": 1} for _ in range(8)]  # 0% home wins

        # Act
        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # Assert
        # Expected: (1.0 * 0.5) + (0.0 * 0.3) + (0.0 * 0.2) = 0.5
        assert result == 0.5

    def test_calculate_with_balanced_results(self):
        """Test weighted calculation with balanced results across periods."""
        # Arrange
        recent = [
            {"home_score": 2, "away_score": 1},  # Win
            {"home_score": 1, "away_score": 2},  # Loss
        ]  # 50% home wins
        last_season = [
            {"home_score": 2, "away_score": 1},
            {"home_score": 2, "away_score": 1},
            {"home_score": 1, "away_score": 2},
            {"home_score": 1, "away_score": 2},
        ]  # 50% home wins
        older = [
            {"home_score": 2, "away_score": 1},
            {"home_score": 1, "away_score": 2},
        ]  # 50% home wins

        # Act
        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # Assert
        # Expected: (0.5 * 0.5) + (0.5 * 0.3) + (0.5 * 0.2) = 0.5
        assert result == 0.5

    def test_calculate_with_empty_lists(self):
        """Test weighted calculation with empty lists."""
        # Arrange
        recent = []
        last_season = []
        older = []

        # Act
        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # Assert
        assert result == 0.0

    def test_calculate_with_only_recent_data(self):
        """Test weighted calculation with only recent matches."""
        # Arrange
        recent = [{"home_score": 3, "away_score": 0} for _ in range(5)]  # 100% home wins
        last_season = []
        older = []

        # Act
        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # Assert
        # Expected: (1.0 * 0.5) + (0.0 * 0.3) + (0.0 * 0.2) = 0.5
        assert result == 0.5

    def test_calculate_rounds_to_4_decimals(self):
        """Test that result is rounded to 4 decimal places."""
        # Arrange
        recent = [{"val": i} for i in range(7)]  # 3/7 = 0.428571...
        last_season = [{"val": 1}]  # 1/1 = 1.0
        older = [{"val": 0}, {"val": 1}]  # 1/2 = 0.5

        # Act
        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["val"] < 3
        )

        # Assert
        # Expected: (3/7 * 0.5) + (1.0 * 0.3) + (0.5 * 0.2)
        # = 0.2143 + 0.3 + 0.1 = 0.6143
        assert isinstance(result, float)
        assert len(str(result).split('.')[-1]) <= 4


class TestDataQualityClassifier:
    """Test DataQualityClassifier class."""

    def test_assess_high_quality(self):
        """Test classification for high quality data (≥15 matches)."""
        assert DataQualityClassifier.assess(15) == "high"
        assert DataQualityClassifier.assess(20) == "high"
        assert DataQualityClassifier.assess(100) == "high"

    def test_assess_medium_quality(self):
        """Test classification for medium quality data (8-14 matches)."""
        assert DataQualityClassifier.assess(8) == "medium"
        assert DataQualityClassifier.assess(10) == "medium"
        assert DataQualityClassifier.assess(14) == "medium"

    def test_assess_low_quality(self):
        """Test classification for low quality data (<8 matches)."""
        assert DataQualityClassifier.assess(0) == "low"
        assert DataQualityClassifier.assess(5) == "low"
        assert DataQualityClassifier.assess(7) == "low"

    def test_assess_boundary_cases(self):
        """Test classification at boundary values."""
        assert DataQualityClassifier.assess(7) == "low"
        assert DataQualityClassifier.assess(8) == "medium"
        assert DataQualityClassifier.assess(14) == "medium"
        assert DataQualityClassifier.assess(15) == "high"


class TestBaseStatisticalTool:
    """Test BaseStatisticalTool class."""

    @pytest.mark.asyncio
    async def test_get_h2h_matches_success(self):
        """Test successful retrieval of h2h matches."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Sample data
        sample_matches = [
            {
                "id": "1",
                "scheduled": datetime(2026, 8, 1),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2026
            },
            {
                "id": "2",
                "scheduled": datetime(2026, 2, 15),
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "home_score": 1,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2026
            },
            {
                "id": "3",
                "scheduled": datetime(2025, 9, 10),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 3,
                "away_score": 0,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2025
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseStatisticalTool.get_h2h_matches(
            pool=mock_pool,
            home_team="Arsenal",
            away_team="Chelsea",
            league="Premier League",
            seasons_back=6,
            current_form_matches=2
        )

        # Assert
        assert len(result["all_matches"]) == 3
        assert len(result["recent_matches"]) == 2  # Last 2 matches
        assert len(result["last_season"]) == 1  # 2025 season
        assert len(result["older_seasons"]) == 0
        assert result["seasons_analyzed"] == 2  # 2026, 2025
        assert result["earliest_match"] == datetime(2025, 9, 10)
        assert result["latest_match"] == datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_get_h2h_matches_no_data(self):
        """Test h2h matches retrieval when no data exists."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        # Act
        result = await BaseStatisticalTool.get_h2h_matches(
            pool=mock_pool,
            home_team="Arsenal",
            away_team="Chelsea",
            league="Premier League"
        )

        # Assert
        assert result["all_matches"] == []
        assert result["recent_matches"] == []
        assert result["last_season"] == []
        assert result["older_seasons"] == []
        assert result["seasons_analyzed"] == 0
        assert result["earliest_match"] is None
        assert result["latest_match"] is None

    @pytest.mark.asyncio
    async def test_get_team_matches_home_venue(self):
        """Test retrieval of team matches for home venue."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled": datetime(2026, 8, 1),
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2026
            },
            {
                "id": "2",
                "scheduled": datetime(2026, 7, 25),
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "home_score": 3,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2026
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="home",
            league="Premier League",
            seasons_back=6,
            current_form_matches=10
        )

        # Assert
        assert len(result["all_matches"]) == 2
        assert len(result["recent_matches"]) == 2
        assert result["seasons_analyzed"] == 1
        # Verify query was called with correct parameters
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_team_matches_away_venue(self):
        """Test retrieval of team matches for away venue."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled": datetime(2026, 8, 1),
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "home_score": 1,
                "away_score": 2,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
                "season_year": 2026
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="away",
            league="Premier League"
        )

        # Assert
        assert len(result["all_matches"]) == 1
        assert result["all_matches"][0]["away_team"] == "Arsenal"

    @pytest.mark.asyncio
    async def test_get_team_matches_partitions_by_season(self):
        """Test that team matches are correctly partitioned by season."""
        # Arrange
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Create matches across multiple seasons
        current_year = datetime.now().year
        sample_matches = [
            {"id": "1", "scheduled": datetime(current_year, 7, 1), "home_team": "Arsenal",
             "away_team": "Chelsea", "home_score": 2, "away_score": 1, "status": "finished",
             "league": "Premier League", "metadata": {}, "season_year": current_year},
            {"id": "2", "scheduled": datetime(current_year - 1, 8, 1), "home_team": "Arsenal",
             "away_team": "Liverpool", "home_score": 1, "away_score": 1, "status": "finished",
             "league": "Premier League", "metadata": {}, "season_year": current_year - 1},
            {"id": "3", "scheduled": datetime(current_year - 2, 9, 1), "home_team": "Arsenal",
             "away_team": "Man City", "home_score": 0, "away_score": 2, "status": "finished",
             "league": "Premier League", "metadata": {}, "season_year": current_year - 2},
        ]

        mock_conn.fetch.return_value = sample_matches

        # Act
        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="home",
            league="Premier League",
            current_form_matches=1
        )

        # Assert
        assert len(result["recent_matches"]) == 1  # Last 1 match
        assert len(result["last_season"]) == 1  # current_year - 1
        assert len(result["older_seasons"]) == 1  # current_year - 2
        assert result["seasons_analyzed"] == 3
