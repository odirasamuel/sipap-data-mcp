"""
Unit tests for market intelligence tools.

Tests:
- get_implied_probabilities
- get_value_opportunities
"""

import pytest
from sipap_data_mcp.tools.market import (
    get_implied_probabilities,
    get_value_opportunities,
)


class TestGetImpliedProbabilities:
    """Test implied probabilities tool."""

    @pytest.mark.asyncio
    async def test_h2h_market_typical_overround(self):
        """Test h2h market with typical 5% overround."""
        odds = {
            "home": 2.10,
            "draw": 3.40,
            "away": 3.60
        }

        result = await get_implied_probabilities(odds, market_type="h2h")

        # Check structure
        assert result["tool"] == "get_implied_probabilities"
        assert "data" in result
        assert "metadata" in result

        # Check data
        data = result["data"]
        assert data["market_type"] == "h2h"
        assert data["odds"] == odds

        # Check implied probabilities
        assert "implied_probabilities" in data
        assert abs(sum(data["implied_probabilities"].values()) - 1.048) < 0.01

        # Check overround (actual is around 4.8%)
        assert 4.0 < data["overround"] < 6.0

        # Check true probabilities sum to 1.0
        assert abs(sum(data["true_probabilities"].values()) - 1.0) < 0.001

        # Check efficiency rating (overround ~4.8% → efficiency ~86)
        assert data["efficiency_rating"] >= 85  # Good overround

    @pytest.mark.asyncio
    async def test_h2h_market_excellent_overround(self):
        """Test h2h market with low overround."""
        odds = {
            "home": 2.05,
            "draw": 3.50,
            "away": 3.70
        }

        result = await get_implied_probabilities(odds, market_type="h2h")

        data = result["data"]

        # Low overround should give good efficiency rating (actual ~88)
        assert data["efficiency_rating"] >= 85

    @pytest.mark.asyncio
    async def test_totals_market(self):
        """Test totals (over/under) market."""
        odds = {
            "over": 1.95,
            "under": 1.95
        }

        result = await get_implied_probabilities(odds, market_type="totals")

        data = result["data"]
        assert data["market_type"] == "totals"

        # Two-way market should have lower overround
        assert data["overround"] < 10.0

        # True probabilities should sum to 1.0
        assert abs(sum(data["true_probabilities"].values()) - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_invalid_h2h_odds(self):
        """Test handling of invalid h2h odds."""
        odds = {
            "home": 2.10,
            "draw": 3.40
            # Missing away
        }

        result = await get_implied_probabilities(odds, market_type="h2h")

        data = result["data"]
        assert "error" in data
        assert data["efficiency_rating"] == 0

    @pytest.mark.asyncio
    async def test_invalid_odds_values(self):
        """Test handling of invalid odds values (<= 1.0)."""
        odds = {
            "home": 1.00,  # Invalid
            "draw": 3.40,
            "away": 3.60
        }

        result = await get_implied_probabilities(odds, market_type="h2h")

        data = result["data"]
        assert "error" in data


class TestGetValueOpportunities:
    """Test value opportunities tool."""

    @pytest.mark.asyncio
    async def test_positive_ev_opportunity(self):
        """Test detection of +EV opportunity."""
        odds = {
            "home": 2.10,
            "draw": 3.40,
            "away": 3.60
        }

        # Model thinks home has 60% chance (market implies ~45%)
        model_probs = {
            "home": 0.60,
            "draw": 0.25,
            "away": 0.15
        }

        result = await get_value_opportunities(
            odds_data=odds,
            model_probabilities=model_probs,
            confidence=80,
            market_type="h2h",
            min_ev_threshold=5.0
        )

        # Check structure
        assert result["tool"] == "get_value_opportunities"
        assert "data" in result
        assert "metadata" in result

        # Should find home as +EV opportunity
        data = result["data"]
        assert len(data["opportunities"]) > 0

        # Check best opportunity
        assert data["best_opportunity"] is not None
        assert data["best_opportunity"]["outcome"] == "home"
        assert data["best_opportunity"]["expected_value"] > 5.0

        # Check opportunity details
        opportunity = data["opportunities"][0]
        assert opportunity["outcome"] == "home"
        assert opportunity["expected_value"] > 0
        assert opportunity["value_rating"] > 70  # High confidence + high EV

        # Check Kelly stake calculation
        assert "kelly_stake" in opportunity
        assert opportunity["kelly_stake"]["stake"] > 0

    @pytest.mark.asyncio
    async def test_no_value_opportunities(self):
        """Test when no +EV opportunities exist."""
        odds = {
            "home": 2.10,
            "draw": 3.40,
            "away": 3.60
        }

        # Model agrees with market (no edge)
        model_probs = {
            "home": 0.45,
            "draw": 0.30,
            "away": 0.25
        }

        result = await get_value_opportunities(
            odds_data=odds,
            model_probabilities=model_probs,
            confidence=70,
            min_ev_threshold=5.0
        )

        data = result["data"]
        assert len(data["opportunities"]) == 0
        assert data["best_opportunity"] is None

    @pytest.mark.asyncio
    async def test_multiple_value_opportunities(self):
        """Test multiple +EV opportunities ranked by value."""
        odds = {
            "home": 2.50,
            "draw": 3.20,
            "away": 3.00
        }

        # Model thinks home and away both undervalued
        model_probs = {
            "home": 0.50,  # Odds imply ~40%
            "draw": 0.20,
            "away": 0.35   # Odds imply ~33%, increase model to create +EV
        }

        result = await get_value_opportunities(
            odds_data=odds,
            model_probabilities=model_probs,
            confidence=75,
            min_ev_threshold=3.0
        )

        data = result["data"]

        # Should find at least one opportunity (home definitely +EV)
        assert len(data["opportunities"]) >= 1

        # Should be sorted by value rating
        if len(data["opportunities"]) > 1:
            ratings = [opp["value_rating"] for opp in data["opportunities"]]
            assert ratings == sorted(ratings, reverse=True)

    @pytest.mark.asyncio
    async def test_confidence_affects_value_rating(self):
        """Test that confidence affects value rating."""
        odds = {"home": 2.00, "draw": 3.50, "away": 4.00}
        model_probs = {"home": 0.60, "draw": 0.25, "away": 0.15}

        # High confidence
        result_high = await get_value_opportunities(
            odds, model_probs, confidence=90, min_ev_threshold=0.0
        )

        # Low confidence
        result_low = await get_value_opportunities(
            odds, model_probs, confidence=50, min_ev_threshold=0.0
        )

        # High confidence should give higher value rating (same EV)
        high_rating = result_high["data"]["opportunities"][0]["value_rating"]
        low_rating = result_low["data"]["opportunities"][0]["value_rating"]

        assert high_rating > low_rating

    @pytest.mark.asyncio
    async def test_min_ev_threshold_filtering(self):
        """Test minimum EV threshold filters opportunities."""
        odds = {"home": 2.10, "draw": 3.40, "away": 3.60}
        model_probs = {"home": 0.52, "draw": 0.28, "away": 0.20}

        # Low threshold - should find opportunity
        result_low = await get_value_opportunities(
            odds, model_probs, min_ev_threshold=1.0
        )

        # High threshold - might not find opportunity
        result_high = await get_value_opportunities(
            odds, model_probs, min_ev_threshold=15.0
        )

        assert len(result_low["data"]["opportunities"]) >= len(
            result_high["data"]["opportunities"]
        )

    @pytest.mark.asyncio
    async def test_invalid_model_probabilities(self):
        """Test handling of invalid model probabilities."""
        odds = {"home": 2.10, "draw": 3.40, "away": 3.60}

        # Probabilities don't sum to 1.0
        model_probs = {"home": 0.60, "draw": 0.25, "away": 0.25}  # Sum = 1.10

        result = await get_value_opportunities(odds, model_probs)

        data = result["data"]
        assert "error" in data
        assert len(data["opportunities"]) == 0

    @pytest.mark.asyncio
    async def test_kelly_stake_calculation(self):
        """Test Kelly stake calculation in opportunities."""
        odds = {"home": 2.00, "draw": 3.50, "away": 4.00}
        model_probs = {"home": 0.60, "draw": 0.25, "away": 0.15}

        result = await get_value_opportunities(odds, model_probs, confidence=80)

        opportunity = result["data"]["opportunities"][0]
        kelly = opportunity["kelly_stake"]

        # Check Kelly stake components
        assert kelly["kelly_percentage"] > 0
        assert kelly["fractional_kelly"] > 0
        assert kelly["stake"] > 0
        assert kelly["expected_value"] > 0

        # Fractional Kelly should be less than full Kelly
        assert kelly["fractional_kelly"] < kelly["kelly_percentage"]

    @pytest.mark.asyncio
    async def test_market_efficiency_score(self):
        """Test market efficiency score calculation."""
        odds = {"home": 2.05, "draw": 3.50, "away": 3.70}
        model_probs = {"home": 0.50, "draw": 0.30, "away": 0.20}

        result = await get_value_opportunities(odds, model_probs)

        # Should have efficiency score (based on overround)
        assert "market_efficiency_score" in result["data"]
        assert 0 <= result["data"]["market_efficiency_score"] <= 100
