"""
Statistical analysis tools for AI agents.

Provides 24 granular tools for market-specific betting analysis:

Phase 1 - Core Tools (5):
- get_h2h_full_time_result: H2H full-time results
- get_h2h_goals: Total goals in h2h fixtures
- get_bts: Both teams to score
- get_home_total_goals: Home team goal-scoring capability
- get_away_total_goals: Away team goal-scoring capability

Phase 2 - Halftime/Second-Half Tools (5):
- get_h2h_half_time_result: H2H halftime results
- get_h2h_2nd_half_result: H2H second-half results
- get_ht_ft_outcome: Halftime/Fulltime combinations
- get_half_time_goals: Halftime goals by team
- get_2nd_half_goals: Second-half goals by team

Phase 3 - Combination Markets (8):
- get_double_chance: Win OR Draw probability
- get_win_or_total_goals: Win OR goals threshold
- get_win_and_total_goals: Win AND goals threshold
- get_win_or_both_scores: Win OR both teams score
- get_win_and_both_scores: Win AND both teams score
- get_both_scores_or_multi_goals: BTS OR goals
- get_no_defeat_and_total_goals: No defeat AND goals
- get_avoid_halftime_defeat: Avoid HT defeat (Win OR Draw at HT)
- get_avoid_2nd_half_defeat: Avoid 2H defeat

Phase 4 - Specialized Analysis (5):
- get_total_goals_range: Goal range percentiles
- get_home_either_half_outcome: Which half home team wins
- get_away_either_half_outcome: Which half away team wins
- get_home_to_score: Probability home team scores
- get_away_to_score: Probability away team scores

Infrastructure:
- RecencyWeightCalculator: 50/30/20 weighting algorithm
- DataQualityClassifier: high/medium/low classification
- BaseStatisticalTool: Common database patterns
"""

# Base infrastructure
from .base import (
    RecencyWeightCalculator,
    DataQualityClassifier,
    BaseStatisticalTool
)

# Phase 1: Core tools
from .h2h_full_time_result import get_h2h_full_time_result
from .h2h_goals import get_h2h_goals
from .bts import get_bts
from .team_total_goals import get_home_total_goals, get_away_total_goals

# Phase 2: Halftime/Second-half tools
from .halftime_analysis import (
    get_h2h_half_time_result,
    get_h2h_2nd_half_result,
    get_ht_ft_outcome,
    get_half_time_goals,
    get_2nd_half_goals
)

# Phase 3: Combination markets
from .combination_markets import (
    get_double_chance,
    get_win_or_total_goals,
    get_win_and_total_goals,
    get_win_or_both_scores,
    get_win_and_both_scores,
    get_both_scores_or_multi_goals,
    get_no_defeat_and_total_goals,
    get_avoid_halftime_defeat,
    get_avoid_2nd_half_defeat
)

# Phase 4: Specialized analysis
from .specialized_analysis import (
    get_total_goals_range,
    get_home_either_half_outcome,
    get_away_either_half_outcome,
    get_home_to_score,
    get_away_to_score
)

__all__ = [
    # Base infrastructure
    "RecencyWeightCalculator",
    "DataQualityClassifier",
    "BaseStatisticalTool",

    # Phase 1: Core tools (5)
    "get_h2h_full_time_result",
    "get_h2h_goals",
    "get_bts",
    "get_home_total_goals",
    "get_away_total_goals",

    # Phase 2: Halftime/Second-half (5)
    "get_h2h_half_time_result",
    "get_h2h_2nd_half_result",
    "get_ht_ft_outcome",
    "get_half_time_goals",
    "get_2nd_half_goals",

    # Phase 3: Combination markets (9)
    "get_double_chance",
    "get_win_or_total_goals",
    "get_win_and_total_goals",
    "get_win_or_both_scores",
    "get_win_and_both_scores",
    "get_both_scores_or_multi_goals",
    "get_no_defeat_and_total_goals",
    "get_avoid_halftime_defeat",
    "get_avoid_2nd_half_defeat",

    # Phase 4: Specialized (5)
    "get_total_goals_range",
    "get_home_either_half_outcome",
    "get_away_either_half_outcome",
    "get_home_to_score",
    "get_away_to_score",
]

# Total: 24 statistical tools + 3 base infrastructure classes
