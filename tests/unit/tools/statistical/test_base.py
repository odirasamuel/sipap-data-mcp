"""
Unit tests for statistical analysis base classes.

Tests:
- get_football_season (NEW: football season partitioning)
- RecencyWeightCalculator (UPDATED: sample guards, tuple return)
- DataQualityClassifier (UPDATED: market-specific thresholds)
- calculate_confidence_penalty (NEW)
- calculate_final_confidence (NEW)
- BaseStatisticalTool
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sipap_data_mcp.tools.statistical.base import (
    RecencyWeightCalculator,
    DataQualityClassifier,
    BaseStatisticalTool,
    get_football_season,
    calculate_confidence_penalty,
    calculate_final_confidence,
    MIN_SAMPLES_FOR_WEIGHTING,
)


class TestGetFootballSeason:
    """Test football season partitioning (Aug-Jul)."""

    def test_august_belongs_to_new_season(self):
        """August starts a new season."""
        # Aug 15, 2025 -> season 2025
        assert get_football_season(datetime(2025, 8, 15)) == 2025
        # Aug 1, 2026 -> season 2026
        assert get_football_season(datetime(2026, 8, 1)) == 2026

    def test_december_belongs_to_current_season(self):
        """December is still in the season that started in August."""
        # Dec 20, 2025 -> season 2025
        assert get_football_season(datetime(2025, 12, 20)) == 2025
        # Dec 31, 2025 -> season 2025
        assert get_football_season(datetime(2025, 12, 31)) == 2025

    def test_january_belongs_to_previous_season(self):
        """January is in the season that started last August."""
        # Jan 10, 2026 -> season 2025
        assert get_football_season(datetime(2026, 1, 10)) == 2025
        # Jan 1, 2026 -> season 2025
        assert get_football_season(datetime(2026, 1, 1)) == 2025

    def test_july_belongs_to_previous_season(self):
        """July is at the end of the season that started last August."""
        # Jul 30, 2026 -> season 2025
        assert get_football_season(datetime(2026, 7, 30)) == 2025
        # Jul 31, 2026 -> season 2025
        assert get_football_season(datetime(2026, 7, 31)) == 2025

    def test_boundary_august_first(self):
        """August 1st is the first day of a new season."""
        # Aug 1, 2026 -> season 2026
        assert get_football_season(datetime(2026, 8, 1)) == 2026

    def test_iso_string_input(self):
        """Test ISO string date input."""
        # ISO string: Aug 15, 2025
        assert get_football_season("2025-08-15T14:00:00Z") == 2025
        # ISO string: Jan 10, 2026
        assert get_football_season("2026-01-10T14:00:00+00:00") == 2025


class TestRecencyWeightCalculator:
    """Test RecencyWeightCalculator class with sample guards."""

    def test_calculate_returns_tuple(self):
        """Test that calculate returns (probability, breakdown) tuple."""
        recent = [{"home_score": 2, "away_score": 1} for _ in range(5)]
        last_season = [{"home_score": 1, "away_score": 2} for _ in range(5)]
        older = [{"home_score": 1, "away_score": 1} for _ in range(5)]

        result = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        prob, breakdown = result
        assert isinstance(prob, float)
        assert isinstance(breakdown, dict)

    def test_calculate_with_all_valid_buckets(self):
        """Test weighted calculation when all buckets have >= MIN_SAMPLES."""
        recent = [{"home_score": 2, "away_score": 1} for _ in range(10)]  # 100% home wins
        last_season = [{"home_score": 1, "away_score": 2} for _ in range(5)]  # 0% home wins
        older = [{"home_score": 1, "away_score": 1} for _ in range(8)]  # 0% home wins

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # All buckets valid: (1.0 * 0.5) + (0.0 * 0.3) + (0.0 * 0.2) = 0.5
        assert prob == 0.5
        assert breakdown["recent"]["included"] is True
        assert breakdown["last_season"]["included"] is True
        assert breakdown["older"]["included"] is True

    def test_calculate_excludes_small_buckets(self):
        """Test that buckets with < MIN_SAMPLES are excluded and weights normalized."""
        recent = [{"home_score": 2, "away_score": 1} for _ in range(10)]  # 100% home wins
        last_season = [{"home_score": 1, "away_score": 2}]  # 1 match (excluded)
        older = [{"home_score": 1, "away_score": 1} for _ in range(8)]  # 0% home wins

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # last_season excluded (only 1 match)
        # normalized: recent = 0.5/0.7, older = 0.2/0.7
        # (1.0 * 0.714) + (0.0 * 0.286) = 0.714
        assert breakdown["last_season"]["included"] is False
        assert "Below minimum" in breakdown["last_season"]["reason"]
        assert breakdown["recent"]["included"] is True
        assert breakdown["older"]["included"] is True
        # Check weights are normalized in breakdown
        assert "normalized_weights" in breakdown
        assert 0.7 <= prob <= 0.72  # Allow small rounding variance

    def test_calculate_with_empty_lists_returns_default(self):
        """Test weighted calculation with all empty lists returns 0.5 fallback."""
        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=[],
            last_season=[],
            older_seasons=[],
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        assert prob == 0.5
        assert "fallback" in breakdown

    def test_calculate_fallback_to_all_data(self):
        """Test fallback when no bucket meets minimum samples."""
        recent = [{"home_score": 2, "away_score": 1}]  # 1 match
        last_season = [{"home_score": 1, "away_score": 2}]  # 1 match
        older = [{"home_score": 1, "away_score": 1}]  # 1 match

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["home_score"] > m["away_score"]
        )

        # Falls back to all data combined: 1/3 = 0.3333
        assert "fallback" in breakdown
        assert abs(prob - 0.3333) < 0.01

    def test_calculate_rounds_to_4_decimals(self):
        """Test that result is rounded to 4 decimal places."""
        recent = [{"val": i} for i in range(7)]  # 3/7 = 0.428571...
        last_season = [{"val": 1} for _ in range(4)]  # 0/4 = 0
        older = [{"val": 0} for _ in range(4)]  # 4/4 = 1.0

        prob, _ = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["val"] < 3
        )

        assert isinstance(prob, float)
        assert len(str(prob).split('.')[-1]) <= 4


class TestDataQualityClassifier:
    """Test DataQualityClassifier with market-specific thresholds."""

    def test_assess_default_thresholds(self):
        """Test classification with default thresholds."""
        # Default thresholds: high=12, medium=6
        assert DataQualityClassifier.assess(12) == "high"
        assert DataQualityClassifier.assess(15) == "high"
        assert DataQualityClassifier.assess(6) == "medium"
        assert DataQualityClassifier.assess(11) == "medium"
        assert DataQualityClassifier.assess(5) == "low"
        assert DataQualityClassifier.assess(0) == "low"

    def test_assess_btts_market_thresholds(self):
        """Test classification for BTTS market (simpler market)."""
        # BTTS: high=10, medium=5
        assert DataQualityClassifier.assess(10, market="BTTS") == "high"
        assert DataQualityClassifier.assess(5, market="BTTS") == "medium"
        assert DataQualityClassifier.assess(4, market="BTTS") == "low"

    def test_assess_combination_market_thresholds(self):
        """Test classification for combination markets (need more data)."""
        # Combination markets: high=15, medium=8
        assert DataQualityClassifier.assess(15, market="1X2_BTTS") == "high"
        assert DataQualityClassifier.assess(8, market="1X2_BTTS") == "medium"
        assert DataQualityClassifier.assess(7, market="1X2_BTTS") == "low"

        assert DataQualityClassifier.assess(15, market="DC_OU2.5") == "high"
        assert DataQualityClassifier.assess(14, market="DC_OU2.5") == "medium"

    def test_assess_halftime_market_thresholds(self):
        """Test classification for halftime markets."""
        # HT markets: high=8, medium=4
        assert DataQualityClassifier.assess(8, market="HT_1X2") == "high"
        assert DataQualityClassifier.assess(4, market="HT_1X2") == "medium"
        assert DataQualityClassifier.assess(3, market="HT_1X2") == "low"

    def test_assess_unknown_market_uses_default(self):
        """Test that unknown market uses default thresholds."""
        # Unknown market should use default: high=12, medium=6
        assert DataQualityClassifier.assess(12, market="UNKNOWN_MARKET") == "high"
        assert DataQualityClassifier.assess(6, market="UNKNOWN_MARKET") == "medium"
        assert DataQualityClassifier.assess(5, market="UNKNOWN_MARKET") == "low"


class TestCalculateConfidencePenalty:
    """Test confidence penalty for conflicting signals."""

    def test_large_disagreement_penalty(self):
        """Test penalty for large disagreement (>30%)."""
        penalty, reason = calculate_confidence_penalty(0.30, 0.65)
        assert penalty == 0.70
        assert "Large disagreement" in reason

    def test_moderate_disagreement_penalty(self):
        """Test penalty for moderate disagreement (20-30%)."""
        penalty, reason = calculate_confidence_penalty(0.40, 0.65)
        assert penalty == 0.85
        assert "Moderate disagreement" in reason

    def test_minor_disagreement_penalty(self):
        """Test penalty for minor disagreement (10-20%)."""
        penalty, reason = calculate_confidence_penalty(0.50, 0.65)
        assert penalty == 0.95
        assert "Minor disagreement" in reason

    def test_no_penalty_when_aligned(self):
        """Test no penalty when signals are aligned (<10%)."""
        penalty, reason = calculate_confidence_penalty(0.60, 0.65)
        assert penalty == 1.0
        assert "aligned" in reason.lower()

    def test_exact_match_no_penalty(self):
        """Test no penalty when signals match exactly."""
        penalty, reason = calculate_confidence_penalty(0.50, 0.50)
        assert penalty == 1.0


class TestCalculateFinalConfidence:
    """Test final confidence calculation with all adjustments."""

    def test_high_quality_no_signal_disagreement(self):
        """Test confidence with high quality data and aligned signals."""
        result = calculate_final_confidence(
            base_confidence=0.80,
            h2h_prob=0.75,
            form_prob=0.80,
            data_quality="high"
        )

        assert result["final_confidence"] == 0.80  # No penalty
        assert result["base_confidence"] == 0.80
        assert result["data_quality"] == "high"
        assert len(result["adjustments"]) == 0

    def test_medium_quality_applies_penalty(self):
        """Test confidence with medium quality data."""
        result = calculate_final_confidence(
            base_confidence=0.80,
            data_quality="medium"
        )

        # 0.80 * 0.9 = 0.72
        assert result["final_confidence"] == 0.72
        assert "Quality penalty" in result["adjustments"][0]

    def test_low_quality_applies_larger_penalty(self):
        """Test confidence with low quality data."""
        result = calculate_final_confidence(
            base_confidence=0.80,
            data_quality="low"
        )

        # 0.80 * 0.75 = 0.60
        assert result["final_confidence"] == 0.60
        assert "Quality penalty" in result["adjustments"][0]

    def test_signal_disagreement_penalty_stacks(self):
        """Test that quality and signal penalties stack."""
        result = calculate_final_confidence(
            base_confidence=0.80,
            h2h_prob=0.30,
            form_prob=0.65,  # Large disagreement (35%)
            data_quality="medium"
        )

        # 0.80 * 0.9 (quality) * 0.70 (signal) = 0.504
        assert result["final_confidence"] == 0.504
        assert len(result["adjustments"]) == 2

    def test_no_form_prob_skips_signal_penalty(self):
        """Test that signal penalty is skipped when form_prob is None."""
        result = calculate_final_confidence(
            base_confidence=0.80,
            h2h_prob=0.30,
            form_prob=None,
            data_quality="high"
        )

        assert result["final_confidence"] == 0.80  # No penalty
        assert len(result["adjustments"]) == 0


class TestBaseStatisticalTool:
    """Test BaseStatisticalTool class."""

    @pytest.mark.asyncio
    async def test_get_h2h_matches_success(self):
        """Test successful retrieval of h2h matches."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Use scheduled_at (DB field name) not scheduled
        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),  # Season 2026
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            },
            {
                "id": "2",
                "scheduled_at": datetime(2026, 2, 15),  # Season 2025 (Feb is in prev season)
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "home_score": 1,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            },
            {
                "id": "3",
                "scheduled_at": datetime(2025, 9, 10),  # Season 2025
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 3,
                "away_score": 0,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        result = await BaseStatisticalTool.get_h2h_matches(
            pool=mock_pool,
            home_team="Arsenal",
            away_team="Chelsea",
            league="Premier League",
            seasons_back=6,
            current_form_matches=2
        )

        assert len(result["all_matches"]) == 3
        assert len(result["recent_matches"]) == 2
        # Football seasons: 2026 (Aug 2026) and 2025 (Sep 2025, Feb 2026)
        assert result["seasons_analyzed"] == 2
        assert result["earliest_match"] == datetime(2025, 9, 10)
        assert result["latest_match"] == datetime(2026, 8, 1)

    @pytest.mark.asyncio
    async def test_get_h2h_matches_no_data(self):
        """Test h2h matches retrieval when no data exists."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        result = await BaseStatisticalTool.get_h2h_matches(
            pool=mock_pool,
            home_team="Arsenal",
            away_team="Chelsea",
            league="Premier League"
        )

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
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),  # Season 2026
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            },
            {
                "id": "2",
                "scheduled_at": datetime(2026, 7, 25),  # Season 2025 (July is in prev season)
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "home_score": 3,
                "away_score": 1,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="home",
            league="Premier League",
            seasons_back=6,
            current_form_matches=10
        )

        assert len(result["all_matches"]) == 2
        assert len(result["recent_matches"]) == 2
        # Two seasons: 2026 and 2025
        assert result["seasons_analyzed"] == 2
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_team_matches_away_venue(self):
        """Test retrieval of team matches for away venue."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        sample_matches = [
            {
                "id": "1",
                "scheduled_at": datetime(2026, 8, 1),
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "home_score": 1,
                "away_score": 2,
                "status": "finished",
                "league": "Premier League",
                "metadata": {},
            }
        ]

        mock_conn.fetch.return_value = sample_matches

        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="away",
            league="Premier League"
        )

        assert len(result["all_matches"]) == 1
        assert result["all_matches"][0]["away_team"] == "Arsenal"

    @pytest.mark.asyncio
    async def test_get_team_matches_partitions_by_football_season(self):
        """Test that team matches are correctly partitioned by football season (Aug-Jul)."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Create matches across multiple football seasons using scheduled_at
        sample_matches = [
            # Season 2025: Oct 2025 to Jul 2026
            {"id": "1", "scheduled_at": datetime(2026, 5, 1), "home_team": "Arsenal",
             "away_team": "Chelsea", "home_score": 2, "away_score": 1, "status": "finished",
             "league": "Premier League", "metadata": {}},  # Season 2025 (May 2026)
            {"id": "2", "scheduled_at": datetime(2025, 10, 1), "home_team": "Arsenal",
             "away_team": "Liverpool", "home_score": 1, "away_score": 1, "status": "finished",
             "league": "Premier League", "metadata": {}},  # Season 2025 (Oct 2025)
            # Season 2024: Aug 2024 to Jul 2025
            {"id": "3", "scheduled_at": datetime(2025, 2, 1), "home_team": "Arsenal",
             "away_team": "Man City", "home_score": 0, "away_score": 2, "status": "finished",
             "league": "Premier League", "metadata": {}},  # Season 2024 (Feb 2025)
            {"id": "4", "scheduled_at": datetime(2024, 9, 1), "home_team": "Arsenal",
             "away_team": "Spurs", "home_score": 3, "away_score": 1, "status": "finished",
             "league": "Premier League", "metadata": {}},  # Season 2024 (Sep 2024)
        ]

        mock_conn.fetch.return_value = sample_matches

        result = await BaseStatisticalTool.get_team_matches(
            pool=mock_pool,
            team="Arsenal",
            venue="home",
            league="Premier League",
            current_form_matches=2
        )

        assert len(result["all_matches"]) == 4
        assert len(result["recent_matches"]) == 2  # Last 2 matches
        # Verify football seasons are used (Aug-Jul partitioning)
        # Should have 2 seasons: 2025 and 2024
        assert result["seasons_analyzed"] == 2
