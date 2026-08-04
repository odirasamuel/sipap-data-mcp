"""
Value opportunities analysis tool.

Identifies +EV betting opportunities by comparing model probabilities to market odds.
This is the core mission of SIPAP - finding bets where our model says the probability
is higher than what the market implies.
"""

from typing import Any

from .base import ExpectedValueCalculator, ImpliedProbabilityCalculator, OddsValidator


async def get_value_opportunities(
    odds_data: dict[str, Any],
    model_probabilities: dict[str, float],
    confidence: int = 70,
    market_type: str = "h2h",
    min_ev_threshold: float = 5.0
) -> dict[str, Any]:
    """
    Identify +EV betting opportunities by comparing model vs market.

    Calculates Expected Value (EV) for each outcome by comparing our model's
    probability estimate to the market's implied probability from odds.

    Args:
        odds_data: Dictionary with odds for each outcome
            For h2h: {"home": 2.10, "draw": 3.40, "away": 3.60}
        model_probabilities: Our model's probability estimates
            For h2h: {"home": 0.60, "draw": 0.25, "away": 0.15}
        confidence: Model confidence rating (0-100)
        market_type: Type of market ("h2h", "totals", "btts")
        min_ev_threshold: Minimum EV% to be considered an opportunity (default: 5%)

    Returns:
        {
            "tool": "get_value_opportunities",
            "data": {
                "opportunities": [
                    {
                        "outcome": "home",
                        "odds": 2.10,
                        "model_probability": 0.60,
                        "market_probability": 0.454,  # After margin removal
                        "edge": 0.146,  # Model - Market
                        "expected_value": 26.0,  # EV percentage
                        "value_rating": 82,  # 0-100 composite rating
                        "kelly_stake": {
                            "kelly_percentage": 15.2,
                            "fractional_kelly": 3.8,  # Quarter Kelly
                            "stake": 38.0,  # Per 1000 bankroll
                            "expected_value": 26.0
                        }
                    }
                ],
                "best_opportunity": {
                    "outcome": "home",
                    "expected_value": 26.0,
                    "value_rating": 82
                },
                "market_efficiency_score": 95
            },
            "metadata": {
                "confidence": 70,
                "min_ev_threshold": 5.0,
                "opportunities_found": 1
            }
        }

    Example:
        >>> odds = {"home": 2.10, "draw": 3.40, "away": 3.60}
        >>> model = {"home": 0.60, "draw": 0.25, "away": 0.15}
        >>> result = await get_value_opportunities(odds, model, confidence=80)
        >>> print(result["data"]["best_opportunity"]["expected_value"])
        26.0
    """
    # Validate inputs
    if market_type == "h2h" and not OddsValidator.validate_h2h_odds(odds_data):
        return _empty_response(market_type, "Invalid odds data")

    # Validate model probabilities sum to ~1.0
    model_sum = sum(model_probabilities.values())
    if not (0.95 <= model_sum <= 1.05):
        return _empty_response(
            market_type,
            f"Model probabilities must sum to 1.0 (got {model_sum:.3f})"
        )

    # Calculate market implied probabilities (with margin removed)
    calculator = ImpliedProbabilityCalculator()
    implied_probs = {
        outcome: calculator.decimal_to_probability(odds)
        for outcome, odds in odds_data.items()
    }
    market_probs = calculator.remove_overround(implied_probs)

    # Calculate overround for efficiency score
    overround = calculator.calculate_overround(implied_probs)
    market_efficiency = _calculate_market_efficiency(overround)

    # Analyze each outcome for value opportunities
    opportunities = []
    ev_calc = ExpectedValueCalculator()

    for outcome in odds_data:
        model_prob = model_probabilities.get(outcome, 0.0)
        market_prob = market_probs.get(outcome, 0.0)
        odds = odds_data[outcome]

        # Calculate edge and EV
        edge = model_prob - market_prob
        ev = ev_calc.calculate_ev(model_prob, odds)

        # Only include if meets minimum EV threshold
        if ev >= min_ev_threshold:
            # Calculate Kelly stake
            kelly = ev_calc.calculate_kelly_stake(
                model_probability=model_prob,
                market_odds=odds,
                bankroll=1000.0,  # Per 1000 units
                kelly_fraction=0.25  # Quarter Kelly for safety
            )

            # Calculate composite value rating
            value_rating = ev_calc.calculate_value_rating(ev, confidence)

            opportunities.append({
                "outcome": outcome,
                "odds": round(odds, 2),
                "model_probability": round(model_prob, 3),
                "market_probability": round(market_prob, 3),
                "edge": round(edge, 3),
                "expected_value": round(ev, 2),
                "value_rating": value_rating,
                "kelly_stake": kelly
            })

    # Sort opportunities by value rating (descending)
    opportunities.sort(key=lambda x: x["value_rating"], reverse=True)

    # Identify best opportunity
    best_opportunity = None
    if opportunities:
        best = opportunities[0]
        best_opportunity = {
            "outcome": best["outcome"],
            "expected_value": best["expected_value"],
            "value_rating": best["value_rating"]
        }

    return {
        "tool": "get_value_opportunities",
        "data": {
            "opportunities": opportunities,
            "best_opportunity": best_opportunity,
            "market_efficiency_score": market_efficiency
        },
        "metadata": {
            "confidence": confidence,
            "min_ev_threshold": min_ev_threshold,
            "opportunities_found": len(opportunities)
        }
    }


def _calculate_market_efficiency(overround: float) -> int:
    """
    Calculate market efficiency score from overround.

    Args:
        overround: Overround percentage

    Returns:
        Efficiency score (0-100)
    """
    if overround < 3.0:
        return 95 + int((3.0 - overround) * 2)
    if overround < 5.0:
        return 85 + int((5.0 - overround) * 5)
    if overround < 8.0:
        return 70 + int((8.0 - overround) * 5)
    if overround < 12.0:
        return 50 + int((12.0 - overround) * 5)
    return max(0, int(50 - (overround - 12.0) * 3))


def _empty_response(_market_type: str, error: str) -> dict[str, Any]:
    """Return empty response for invalid/missing data."""
    return {
        "tool": "get_value_opportunities",
        "data": {
            "opportunities": [],
            "best_opportunity": None,
            "market_efficiency_score": 0,
            "error": error
        },
        "metadata": {
            "confidence": 0,
            "min_ev_threshold": 0.0,
            "opportunities_found": 0
        }
    }
