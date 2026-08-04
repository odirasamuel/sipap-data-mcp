"""
Form pattern analysis tools.

Provides 7 specialized tools for analyzing recent form patterns:
1. get_momentum_streak: Detect winning/losing/drawing streaks
2. get_form_trajectory: Analyze improving/declining/stable patterns
3. get_consistency_score: Measure form volatility
4. get_venue_form_split: Analyze home vs away form differences
5. get_goal_scoring_form_trend: Analyze goals scored trajectory
6. get_defensive_form_trend: Analyze goals conceded trajectory
7. get_pressure_performance: Analyze form vs strong opponents

These tools complement the 24 statistical analysis tools by focusing on
recent form patterns (last 10-15 matches) rather than long-term historical data.
"""

from .consistency_score import get_consistency_score
from .defensive_form_trend import get_defensive_form_trend
from .form_trajectory import get_form_trajectory
from .goal_scoring_form_trend import get_goal_scoring_form_trend
from .momentum_streak import get_momentum_streak
from .pressure_performance import get_pressure_performance
from .venue_form_split import get_venue_form_split

__all__ = [
    "get_consistency_score",
    "get_defensive_form_trend",
    "get_form_trajectory",
    "get_goal_scoring_form_trend",
    "get_momentum_streak",
    "get_pressure_performance",
    "get_venue_form_split",
]
