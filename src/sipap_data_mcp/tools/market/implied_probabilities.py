"""
Implied probabilities analysis tool.

Converts betting odds to implied probabilities and removes bookmaker overround.
"""

from typing import Any

from .base import ImpliedProbabilityCalculator, OddsValidator


async def get_implied_probabilities(
    odds_data: dict[str, Any],
    market_type: str = "h2h"
) -> dict[str, Any]:
    """
    Convert betting odds to implied probabilities with overround removal.

    Takes raw odds and converts them to probabilities, then removes the
    bookmaker margin (overround) to get true probability estimates.

    Args:
        odds_data: Dictionary with odds for each outcome
            For h2h: {"home": 2.10, "draw": 3.40, "away": 3.60}
            For totals: {"over": 1.95, "under": 1.95}
            For btts: {"yes": 1.80, "no": 2.05}
        market_type: Type of market ("h2h", "totals", "btts")

    Returns:
        {
            "tool": "get_implied_probabilities",
            "data": {
                "market_type": str,
                "odds": {
                    "home": 2.10,
                    "draw": 3.40,
                    "away": 3.60
                },
                "implied_probabilities": {
                    "home": 0.476,  # Raw implied probability
                    "draw": 0.294,
                    "away": 0.278
                },
                "overround": 4.8,  # Bookmaker margin %
                "true_probabilities": {
                    "home": 0.454,  # After margin removal
                    "draw": 0.281,
                    "away": 0.265
                },
                "efficiency_rating": 95  # Lower overround = higher rating
            },
            "metadata": {
                "outcomes": ["home", "draw", "away"],
                "total_probability": 1.000
            }
        }

    Example:
        >>> odds = {"home": 2.10, "draw": 3.40, "away": 3.60}
        >>> result = await get_implied_probabilities(odds, "h2h")
        >>> print(result["data"]["true_probabilities"]["home"])
        0.454
    """
    # Validate odds data
    if market_type == "h2h" and not OddsValidator.validate_h2h_odds(odds_data):
        return _empty_response(market_type, "Invalid h2h odds data")
    if market_type == "totals" and not OddsValidator.validate_totals_odds(odds_data):
        return _empty_response(market_type, "Invalid totals odds data")

    # Calculate implied probabilities
    calculator = ImpliedProbabilityCalculator()
    implied_probs = {
        outcome: calculator.decimal_to_probability(odds)
        for outcome, odds in odds_data.items()
    }

    # Calculate overround
    overround = calculator.calculate_overround(implied_probs)

    # Remove overround to get true probabilities
    true_probs = calculator.remove_overround(implied_probs)

    # Calculate efficiency rating (0-100)
    # Lower overround = higher efficiency
    # Typical overround: 3-10%, excellent: <5%, poor: >10%
    efficiency_rating = _calculate_efficiency_rating(overround)

    return {
        "tool": "get_implied_probabilities",
        "data": {
            "market_type": market_type,
            "odds": odds_data,
            "implied_probabilities": {
                k: round(v, 3) for k, v in implied_probs.items()
            },
            "overround": round(overround, 2),
            "true_probabilities": {
                k: round(v, 3) for k, v in true_probs.items()
            },
            "efficiency_rating": efficiency_rating
        },
        "metadata": {
            "outcomes": list(odds_data.keys()),
            "total_probability": round(sum(true_probs.values()), 3)
        }
    }


def _calculate_efficiency_rating(overround: float) -> int:
    """
    Calculate market efficiency rating from overround.

    Lower overround = higher efficiency (bookmaker margin is lower).

    Args:
        overround: Overround percentage

    Returns:
        Efficiency rating (0-100)

    Rating scale:
    - 95-100: Excellent (overround <3%)
    - 85-94: Very good (overround 3-5%)
    - 70-84: Good (overround 5-8%)
    - 50-69: Average (overround 8-12%)
    - 0-49: Poor (overround >12%)
    """
    if overround < 3.0:
        return 95 + int((3.0 - overround) * 2)  # 95-100
    if overround < 5.0:
        return 85 + int((5.0 - overround) * 5)  # 85-94
    if overround < 8.0:
        return 70 + int((8.0 - overround) * 5)  # 70-84
    if overround < 12.0:
        return 50 + int((12.0 - overround) * 5)  # 50-69
    return max(0, int(50 - (overround - 12.0) * 3))  # 0-49


def _empty_response(market_type: str, error: str) -> dict[str, Any]:
    """Return empty response for invalid/missing data."""
    return {
        "tool": "get_implied_probabilities",
        "data": {
            "market_type": market_type,
            "odds": {},
            "implied_probabilities": {},
            "overround": 0.0,
            "true_probabilities": {},
            "efficiency_rating": 0,
            "error": error
        },
        "metadata": {
            "outcomes": [],
            "total_probability": 0.0
        }
    }
