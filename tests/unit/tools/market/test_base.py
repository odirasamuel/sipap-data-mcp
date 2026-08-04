"""
Unit tests for market intelligence base utilities.

Tests:
- ImpliedProbabilityCalculator
- ExpectedValueCalculator
- OddsValidator
"""

import pytest
from sipap_data_mcp.tools.market.base import (
    ExpectedValueCalculator,
    ImpliedProbabilityCalculator,
    OddsValidator,
)


class TestImpliedProbabilityCalculator:
    """Test implied probability calculations."""

    def test_decimal_to_probability_even_odds(self):
        """Test conversion of even money (2.00 odds)."""
        result = ImpliedProbabilityCalculator.decimal_to_probability(2.00)
        assert result == 0.50

    def test_decimal_to_probability_favorites(self):
        """Test conversion of favorite odds (1.50)."""
        result = ImpliedProbabilityCalculator.decimal_to_probability(1.50)
        assert result == pytest.approx(0.6667, rel=1e-3)

    def test_decimal_to_probability_underdogs(self):
        """Test conversion of underdog odds (4.00)."""
        result = ImpliedProbabilityCalculator.decimal_to_probability(4.00)
        assert result == 0.25

    def test_decimal_to_probability_invalid_odds(self):
        """Test handling of invalid odds (<= 1.0)."""
        result = ImpliedProbabilityCalculator.decimal_to_probability(1.00)
        assert result == 0.0

        result = ImpliedProbabilityCalculator.decimal_to_probability(0.50)
        assert result == 0.0

    def test_remove_overround_h2h_market(self):
        """Test overround removal for h2h market."""
        # Typical h2h with 6% overround
        probs = {
            "home": 0.476,  # 2.10 odds
            "draw": 0.294,  # 3.40 odds
            "away": 0.278   # 3.60 odds
        }  # Sum = 1.048 (4.8% overround)

        result = ImpliedProbabilityCalculator.remove_overround(probs)

        # Should sum to 1.0
        assert sum(result.values()) == pytest.approx(1.0)

        # Proportions should be maintained
        assert result["home"] > result["draw"] > result["away"]

    def test_remove_overround_zero_total(self):
        """Test handling of zero total (edge case)."""
        probs = {"home": 0.0, "draw": 0.0, "away": 0.0}

        result = ImpliedProbabilityCalculator.remove_overround(probs)

        # Should return uniform distribution
        assert result == {"home": pytest.approx(0.333, rel=1e-2),
                         "draw": pytest.approx(0.333, rel=1e-2),
                         "away": pytest.approx(0.333, rel=1e-2)}

    def test_calculate_overround(self):
        """Test overround calculation."""
        probs = {
            "home": 0.476,
            "draw": 0.294,
            "away": 0.278
        }

        overround = ImpliedProbabilityCalculator.calculate_overround(probs)

        assert overround == pytest.approx(4.8, rel=1e-1)


class TestExpectedValueCalculator:
    """Test expected value calculations."""

    def test_calculate_ev_positive(self):
        """Test EV calculation for positive EV opportunity."""
        # Model says 60%, market odds 2.00 (implies 50%)
        ev = ExpectedValueCalculator.calculate_ev(
            model_probability=0.60,
            market_odds=2.00
        )

        assert ev == pytest.approx(20.0)  # +20% EV

    def test_calculate_ev_negative(self):
        """Test EV calculation for negative EV."""
        # Model says 40%, market odds 2.00 (implies 50%)
        ev = ExpectedValueCalculator.calculate_ev(
            model_probability=0.40,
            market_odds=2.00
        )

        assert ev == pytest.approx(-20.0)  # -20% EV

    def test_calculate_ev_break_even(self):
        """Test EV calculation at break-even point."""
        # Model probability matches implied probability
        ev = ExpectedValueCalculator.calculate_ev(
            model_probability=0.50,
            market_odds=2.00
        )

        assert ev == pytest.approx(0.0)

    def test_calculate_ev_invalid_odds(self):
        """Test EV calculation with invalid odds."""
        ev = ExpectedValueCalculator.calculate_ev(
            model_probability=0.60,
            market_odds=1.00
        )

        assert ev == -100.0

    def test_calculate_kelly_stake_positive_ev(self):
        """Test Kelly stake calculation for +EV opportunity."""
        result = ExpectedValueCalculator.calculate_kelly_stake(
            model_probability=0.60,
            market_odds=2.00,
            bankroll=1000.0,
            kelly_fraction=0.25
        )

        assert result["kelly_percentage"] > 0
        assert result["fractional_kelly"] > 0
        assert result["stake"] > 0
        assert result["expected_value"] > 0

    def test_calculate_kelly_stake_negative_ev(self):
        """Test Kelly stake for negative EV (should be zero)."""
        result = ExpectedValueCalculator.calculate_kelly_stake(
            model_probability=0.40,
            market_odds=2.00,
            bankroll=1000.0
        )

        assert result["kelly_percentage"] == 0.0
        assert result["fractional_kelly"] == 0.0
        assert result["stake"] == 0.0
        assert result["expected_value"] < 0

    def test_calculate_value_rating_high_ev_high_confidence(self):
        """Test value rating with high EV and high confidence."""
        rating = ExpectedValueCalculator.calculate_value_rating(
            expected_value=20.0,
            confidence=90
        )

        assert rating >= 78  # Should be high rating (79 actual)

    def test_calculate_value_rating_low_ev_low_confidence(self):
        """Test value rating with low EV and low confidence."""
        rating = ExpectedValueCalculator.calculate_value_rating(
            expected_value=5.0,
            confidence=50
        )

        assert rating < 60  # Should be medium rating

    def test_calculate_value_rating_negative_ev(self):
        """Test value rating with negative EV."""
        rating = ExpectedValueCalculator.calculate_value_rating(
            expected_value=-10.0,
            confidence=80
        )

        assert rating < 50  # Should be low rating


class TestOddsValidator:
    """Test odds validation."""

    def test_is_valid_decimal_odds_valid(self):
        """Test validation of valid decimal odds."""
        assert OddsValidator.is_valid_decimal_odds(2.00) is True
        assert OddsValidator.is_valid_decimal_odds(1.50) is True
        assert OddsValidator.is_valid_decimal_odds(10.00) is True

    def test_is_valid_decimal_odds_invalid(self):
        """Test validation of invalid decimal odds."""
        assert OddsValidator.is_valid_decimal_odds(1.00) is False
        assert OddsValidator.is_valid_decimal_odds(0.50) is False
        assert OddsValidator.is_valid_decimal_odds(-1.00) is False

    def test_validate_h2h_odds_valid(self):
        """Test validation of valid h2h odds."""
        odds = {"home": 2.10, "draw": 3.40, "away": 3.60}

        assert OddsValidator.validate_h2h_odds(odds) is True

    def test_validate_h2h_odds_missing_outcome(self):
        """Test validation when outcome is missing."""
        odds = {"home": 2.10, "draw": 3.40}  # Missing away

        assert OddsValidator.validate_h2h_odds(odds) is False

    def test_validate_h2h_odds_invalid_value(self):
        """Test validation with invalid odds value."""
        odds = {"home": 1.00, "draw": 3.40, "away": 3.60}

        assert OddsValidator.validate_h2h_odds(odds) is False

    def test_validate_totals_odds_valid(self):
        """Test validation of valid totals odds."""
        odds = {"over": 1.95, "under": 1.95}

        assert OddsValidator.validate_totals_odds(odds) is True

    def test_validate_totals_odds_invalid(self):
        """Test validation of invalid totals odds."""
        odds = {"over": 1.95}  # Missing under

        assert OddsValidator.validate_totals_odds(odds) is False
