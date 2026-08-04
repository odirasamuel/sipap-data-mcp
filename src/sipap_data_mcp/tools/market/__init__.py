"""
Market intelligence tools for betting odds analysis.

Provides 2 core tools:
- get_implied_probabilities: Convert odds to probabilities, remove overround
- get_value_opportunities: Identify +EV betting opportunities

These tools enable the Market Agent to detect positive expected value (+EV)
opportunities by comparing model probabilities to market-implied probabilities.
"""

from .implied_probabilities import get_implied_probabilities
from .value_opportunities import get_value_opportunities

__all__ = [
    "get_implied_probabilities",
    "get_value_opportunities",
]
