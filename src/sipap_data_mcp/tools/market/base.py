"""
Base classes and utilities for market intelligence analysis tools.

Provides:
- ImpliedProbabilityCalculator: Convert odds to probabilities, remove overround
- ExpectedValueCalculator: Calculate EV from model vs market probabilities
- OddsFormat: Handle different odds formats (decimal, fractional, american)
"""

from typing import Any


class ImpliedProbabilityCalculator:
    """
    Calculate implied probabilities from betting odds.

    Handles:
    - Converting decimal odds to implied probabilities
    - Removing bookmaker overround (margin) to get true probabilities
    - Supporting multiple market types (h2h, totals, btts, etc.)
    """

    @staticmethod
    def decimal_to_probability(odds: float) -> float:
        """
        Convert decimal odds to implied probability.

        Args:
            odds: Decimal odds (e.g., 2.10)

        Returns:
            Implied probability as decimal (0-1)

        Example:
            >>> ImpliedProbabilityCalculator.decimal_to_probability(2.00)
            0.50
            >>> ImpliedProbabilityCalculator.decimal_to_probability(4.00)
            0.25
        """
        if odds <= 1.0:
            return 0.0
        return 1.0 / odds

    @staticmethod
    def remove_overround(probabilities: dict[str, float]) -> dict[str, float]:
        """
        Remove bookmaker overround (margin) to get true probabilities.

        The sum of implied probabilities from odds is always > 100% (overround).
        This normalizes them to sum to 100%.

        Args:
            probabilities: Dict of outcome -> implied probability

        Returns:
            Dict of outcome -> true probability (sum = 1.0)

        Example:
            >>> probs = {"home": 0.48, "draw": 0.30, "away": 0.28}  # sum = 1.06
            >>> ImpliedProbabilityCalculator.remove_overround(probs)
            {"home": 0.453, "draw": 0.283, "away": 0.264}  # sum = 1.0
        """
        total = sum(probabilities.values())

        if total <= 0:
            # Return uniform distribution if invalid
            num_outcomes = len(probabilities)
            return dict.fromkeys(probabilities, 1.0 / num_outcomes)

        # Normalize by dividing by total
        return {
            outcome: prob / total
            for outcome, prob in probabilities.items()
        }

    @staticmethod
    def calculate_overround(probabilities: dict[str, float]) -> float:
        """
        Calculate bookmaker overround (margin) percentage.

        Args:
            probabilities: Dict of outcome -> implied probability

        Returns:
            Overround as percentage (e.g., 6.0 for 6%)

        Example:
            >>> probs = {"home": 0.48, "draw": 0.30, "away": 0.28}
            >>> ImpliedProbabilityCalculator.calculate_overround(probs)
            6.0
        """
        total = sum(probabilities.values())
        return (total - 1.0) * 100


class ExpectedValueCalculator:
    """
    Calculate Expected Value (EV) from model vs market probabilities.

    EV = (Model Probability * Decimal Odds) - 1
    Positive EV = Value opportunity
    Negative EV = No value
    """

    @staticmethod
    def calculate_ev(
        model_probability: float,
        market_odds: float
    ) -> float:
        """
        Calculate Expected Value (EV) percentage.

        Args:
            model_probability: Our model's probability estimate (0-1)
            market_odds: Market decimal odds

        Returns:
            EV as percentage (-100 to +inf)

        Example:
            >>> ExpectedValueCalculator.calculate_ev(0.60, 2.00)
            20.0  # +20% EV (60% probability at 2.00 odds)

            >>> ExpectedValueCalculator.calculate_ev(0.40, 2.00)
            -20.0  # -20% EV (40% probability at 2.00 odds)
        """
        if market_odds <= 1.0:
            return -100.0

        ev = (model_probability * market_odds) - 1.0
        return ev * 100

    @staticmethod
    def calculate_kelly_stake(
        model_probability: float,
        market_odds: float,
        bankroll: float = 100.0,
        kelly_fraction: float = 0.25
    ) -> dict[str, Any]:
        """
        Calculate optimal stake using Kelly Criterion.

        Kelly % = (p * odds - 1) / (odds - 1)
        Where p = model probability

        Args:
            model_probability: Our model's probability estimate (0-1)
            market_odds: Market decimal odds
            bankroll: Total bankroll (default: 100 units)
            kelly_fraction: Fraction of full Kelly (default: 0.25 = quarter Kelly)

        Returns:
            Dict with stake size, kelly percentage, and EV

        Example:
            >>> ExpectedValueCalculator.calculate_kelly_stake(0.60, 2.00, 1000)
            {
                "kelly_percentage": 20.0,
                "fractional_kelly": 5.0,  # 25% of 20%
                "stake": 50.0,  # 5% of 1000
                "expected_value": 20.0
            }
        """
        ev = ExpectedValueCalculator.calculate_ev(model_probability, market_odds)

        # No bet if negative EV
        if ev <= 0:
            return {
                "kelly_percentage": 0.0,
                "fractional_kelly": 0.0,
                "stake": 0.0,
                "expected_value": ev
            }

        # Full Kelly percentage
        # Kelly = (p * b - q) / b, where b = odds - 1, q = 1 - p
        b = market_odds - 1
        q = 1 - model_probability
        kelly_pct = (model_probability * b - q) / b * 100

        # Apply Kelly fraction (e.g., quarter Kelly)
        fractional_kelly = kelly_pct * kelly_fraction

        # Calculate stake
        stake = bankroll * (fractional_kelly / 100)

        return {
            "kelly_percentage": round(kelly_pct, 2),
            "fractional_kelly": round(fractional_kelly, 2),
            "stake": round(stake, 2),
            "expected_value": round(ev, 2)
        }

    @staticmethod
    def calculate_value_rating(
        expected_value: float,
        confidence: float
    ) -> int:
        """
        Calculate a 0-100 value rating from EV and confidence.

        Combines:
        - Expected Value (70% weight) - how much edge
        - Confidence (30% weight) - how sure we are

        Args:
            expected_value: EV percentage (-100 to +100)
            confidence: Model confidence (0-100)

        Returns:
            Value rating (0-100)

        Example:
            >>> ExpectedValueCalculator.calculate_value_rating(15.0, 80)
            81  # High EV + high confidence = strong value
        """
        # Normalize EV to 0-100 scale (assume max useful EV is +30%)
        ev_normalized = min(100, max(0, (expected_value + 10) / 40 * 100))

        # Combine with 70/30 weighting
        value_rating = (ev_normalized * 0.70) + (confidence * 0.30)

        return int(value_rating)


class OddsValidator:
    """Validate odds data and formats."""

    @staticmethod
    def is_valid_decimal_odds(odds: float) -> bool:
        """
        Check if decimal odds are valid.

        Args:
            odds: Decimal odds value

        Returns:
            True if valid (>= 1.01), False otherwise
        """
        return odds >= 1.01

    @staticmethod
    def validate_h2h_odds(odds: dict[str, float]) -> bool:
        """
        Validate head-to-head odds have all required outcomes.

        Args:
            odds: Dict with home, draw, away odds

        Returns:
            True if all outcomes present and valid
        """
        required = ["home", "draw", "away"]
        return (
            all(outcome in odds for outcome in required) and
            all(OddsValidator.is_valid_decimal_odds(odds[outcome]) for outcome in required)
        )

    @staticmethod
    def validate_totals_odds(odds: dict[str, float]) -> bool:
        """
        Validate totals (over/under) odds.

        Args:
            odds: Dict with over, under odds

        Returns:
            True if both outcomes present and valid
        """
        required = ["over", "under"]
        return (
            all(outcome in odds for outcome in required) and
            all(OddsValidator.is_valid_decimal_odds(odds[outcome]) for outcome in required)
        )
