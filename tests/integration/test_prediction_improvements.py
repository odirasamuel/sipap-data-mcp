"""
Integration tests for prediction logic improvements.

Validates that the improvements made to the statistical tools
would produce better predictions for scenarios like Lorient vs Troyes.

SCENARIO: Lorient vs Troyes H2H analysis
- Raw H2H: 6/15 BTTS (40%)
- Old system: 82% BTTS No (incorrect - actual was BTTS Yes 1-2)
- Problem: 1 match in 2025 with BTTS No got 30% weight

EXPECTED IMPROVEMENTS:
1. Football season partitioning (Aug-Jul not Jan-Dec)
2. Sample guards exclude buckets with <3 matches
3. Team form blending provides additional signal
4. Confidence penalties when signals conflict
"""

import pytest
from datetime import datetime
from sipap_data_mcp.tools.statistical.base import (
    RecencyWeightCalculator,
    DataQualityClassifier,
    get_football_season,
    calculate_final_confidence,
    calculate_confidence_penalty,
)


class TestLorientVsTroyesScenario:
    """Test improvements using Lorient vs Troyes scenario."""

    def test_football_season_partitioning(self):
        """Verify matches are partitioned by football season (Aug-Jul)."""
        # Match from Jan 2026 should be in season 2025
        jan_match = datetime(2026, 1, 15)
        assert get_football_season(jan_match) == 2025

        # Match from Oct 2025 should also be in season 2025
        oct_match = datetime(2025, 10, 1)
        assert get_football_season(oct_match) == 2025

        # Both are in same season, so they should be grouped together
        assert get_football_season(jan_match) == get_football_season(oct_match)

    def test_single_match_bucket_excluded(self):
        """Verify that a bucket with only 1 match is excluded."""
        # Simulate the problematic scenario:
        # Recent: 1 match (BTTS No) - should be EXCLUDED
        # Last season: 5 matches (3 BTTS Yes)
        # Older: 9 matches (3 BTTS Yes)

        recent = [{"home_score": 0, "away_score": 1}]  # 1 match, 0% BTTS
        last_season = [
            {"home_score": 1, "away_score": 1},  # BTTS Yes
            {"home_score": 2, "away_score": 1},  # BTTS Yes
            {"home_score": 2, "away_score": 0},  # BTTS No
            {"home_score": 1, "away_score": 2},  # BTTS Yes
            {"home_score": 0, "away_score": 0},  # BTTS No
        ]  # 3/5 = 60% BTTS
        older = [
            {"home_score": 1, "away_score": 1},  # BTTS Yes
            {"home_score": 0, "away_score": 2},  # BTTS No
            {"home_score": 2, "away_score": 1},  # BTTS Yes
            {"home_score": 2, "away_score": 0},  # BTTS No
            {"home_score": 0, "away_score": 0},  # BTTS No
            {"home_score": 1, "away_score": 3},  # BTTS Yes
            {"home_score": 3, "away_score": 0},  # BTTS No
            {"home_score": 0, "away_score": 0},  # BTTS No
            {"home_score": 1, "away_score": 0},  # BTTS No
        ]  # 3/9 = 33.3% BTTS

        def both_teams_scored(m):
            return m["home_score"] > 0 and m["away_score"] > 0

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=both_teams_scored
        )

        # Recent should be EXCLUDED (only 1 match)
        assert breakdown["recent"]["included"] is False
        assert "Below minimum" in breakdown["recent"]["reason"]

        # With recent excluded:
        # last_season: 60% BTTS * (0.3 / 0.5) normalized = 60% * 0.6 = 36%
        # older: 33.3% BTTS * (0.2 / 0.5) normalized = 33.3% * 0.4 = 13.3%
        # Total: ~49.3%

        # Without sample guard (old behavior):
        # recent: 0% * 0.5 = 0%
        # last_season: 60% * 0.3 = 18%
        # older: 33.3% * 0.2 = 6.67%
        # Total: ~24.7%

        # New behavior should give higher BTTS probability
        assert prob > 0.40  # Should be around 49%
        assert prob < 0.60

    def test_confidence_penalty_when_signals_conflict(self):
        """Verify confidence is reduced when H2H and form disagree."""
        # Scenario: H2H says 30% BTTS, Form says 65% BTTS
        h2h_prob = 0.30
        form_prob = 0.65

        penalty, reason = calculate_confidence_penalty(h2h_prob, form_prob)

        # 35% disagreement = large disagreement = 0.70 penalty
        assert penalty == 0.70
        assert "Large disagreement" in reason

        # Calculate final confidence
        result = calculate_final_confidence(
            base_confidence=0.65,  # Going with form
            h2h_prob=h2h_prob,
            form_prob=form_prob,
            data_quality="medium"  # 8 matches
        )

        # 0.65 * 0.9 (quality) * 0.70 (signal) = 0.4095
        assert result["final_confidence"] < 0.50
        assert len(result["adjustments"]) == 2

    def test_no_penalty_when_signals_aligned(self):
        """Verify no penalty when H2H and form agree."""
        h2h_prob = 0.55
        form_prob = 0.60

        penalty, reason = calculate_confidence_penalty(h2h_prob, form_prob)

        assert penalty == 1.0
        assert "aligned" in reason.lower()

    def test_market_specific_thresholds(self):
        """Verify BTTS uses its own quality thresholds."""
        # BTTS threshold: high=10, medium=5
        # Default threshold: high=12, medium=6

        assert DataQualityClassifier.assess(10, market="BTTS") == "high"
        assert DataQualityClassifier.assess(10, market="default") == "medium"

        assert DataQualityClassifier.assess(5, market="BTTS") == "medium"
        assert DataQualityClassifier.assess(5, market="default") == "low"


class TestImprovedWeightingLogic:
    """Test the improved weighting with various scenarios."""

    def test_all_buckets_valid_uses_standard_weights(self):
        """When all buckets have >= 3 matches, use standard 50/30/20."""
        recent = [{"val": 1} for _ in range(5)]  # 100%
        last_season = [{"val": 0} for _ in range(4)]  # 0%
        older = [{"val": 1} for _ in range(3)]  # 100%

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["val"] == 1
        )

        # (1.0 * 0.5) + (0.0 * 0.3) + (1.0 * 0.2) = 0.7
        assert prob == 0.7
        assert breakdown["recent"]["included"] is True
        assert breakdown["last_season"]["included"] is True
        assert breakdown["older"]["included"] is True

    def test_two_buckets_valid_normalizes_weights(self):
        """When only 2 buckets valid, weights are normalized."""
        recent = [{"val": 1} for _ in range(5)]  # 100%
        last_season = [{"val": 0}]  # 1 match - EXCLUDED
        older = [{"val": 0} for _ in range(4)]  # 0%

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["val"] == 1
        )

        # Normalized: recent 0.5/0.7 = 0.714, older 0.2/0.7 = 0.286
        # (1.0 * 0.714) + (0.0 * 0.286) = 0.714
        assert breakdown["last_season"]["included"] is False
        assert 0.71 <= prob <= 0.72

    def test_fallback_to_all_data_when_no_bucket_valid(self):
        """When no bucket meets minimum, use all data combined."""
        recent = [{"val": 1}]  # 1 match
        last_season = [{"val": 0}]  # 1 match
        older = [{"val": 1}]  # 1 match

        prob, breakdown = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=lambda m: m["val"] == 1
        )

        # Fallback: 2/3 = 0.6667
        assert "fallback" in breakdown
        assert 0.66 <= prob <= 0.67


class TestFootballSeasonBoundaries:
    """Test football season partitioning edge cases."""

    def test_july_31_is_still_previous_season(self):
        """July 31 should be in the previous season."""
        assert get_football_season(datetime(2026, 7, 31, 23, 59, 59)) == 2025

    def test_august_1_is_new_season(self):
        """August 1 should start a new season."""
        assert get_football_season(datetime(2026, 8, 1, 0, 0, 0)) == 2026

    def test_iso_string_parsing(self):
        """Test ISO string date parsing."""
        # Various ISO formats
        assert get_football_season("2025-12-25T15:00:00Z") == 2025
        assert get_football_season("2026-01-15T15:00:00+00:00") == 2025
        assert get_football_season("2026-08-01T15:00:00Z") == 2026
