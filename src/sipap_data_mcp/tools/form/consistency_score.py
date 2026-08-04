"""
Consistency score analysis tool.

Measures form volatility and consistency using statistical analysis.
"""

from typing import Any, Literal

import asyncpg

from .base import BaseFormTool, ConsistencyAnalyzer


async def get_consistency_score(
    pool: asyncpg.Pool,
    team: str,
    league: str,
    match_limit: int = 15,
    venue: Literal["home", "away"] | None = None
) -> dict[str, Any]:
    """
    Analyze form consistency and volatility.

    Args:
        pool: AsyncPG connection pool
        team: Team name to analyze
        league: League/competition name
        match_limit: Number of recent matches to analyze (default: 15)
        venue: Optional venue filter ("home" or "away")

    Returns:
        {
            "tool": "get_consistency_score",
            "data": {
                "consistency_rating": int,  # 0-100 (higher = more consistent)
                "volatility": "low" | "medium" | "high",
                "pattern": "consistent" | "erratic" | "trending",
                "std_deviation": float,
                "result_distribution": {
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "dominant_result": "wins" | "draws" | "losses" | "mixed"
                },
                "points_per_match_avg": float,
                "reliability_assessment": str  # Human-readable assessment
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_consistency_score(
        ...     pool, "Arsenal", "Premier League", match_limit=10
        ... )
        >>> print(result["data"]["consistency_rating"])
        85
        >>> print(result["data"]["volatility"])
        "low"
    """
    # Get recent matches
    matches = await BaseFormTool.get_recent_team_matches(
        pool=pool,
        team=team,
        league=league,
        match_limit=match_limit,
        venue=venue
    )

    # Handle no data case
    if not matches:
        return {
            "tool": "get_consistency_score",
            "data": {
                "consistency_rating": 0,
                "volatility": "high",
                "pattern": "erratic",
                "std_deviation": 0.0,
                "result_distribution": {
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "dominant_result": "mixed"
                },
                "points_per_match_avg": 0.0,
                "reliability_assessment": "No data available"
            },
            "metadata": {
                "venue": venue or "all",
                "matches_analyzed": 0
            }
        }

    # Analyze consistency using ConsistencyAnalyzer
    consistency_analysis = ConsistencyAnalyzer.analyze(matches, team)

    # Count result distribution
    wins = 0
    draws = 0
    losses = 0
    total_points = 0

    for match in matches:
        is_home = match['home_team'] == team
        home_score = match['home_score']
        away_score = match['away_score']

        if is_home:
            if home_score > away_score:
                wins += 1
                total_points += 3
            elif home_score == away_score:
                draws += 1
                total_points += 1
            else:
                losses += 1
        else:
            if away_score > home_score:
                wins += 1
                total_points += 3
            elif away_score == home_score:
                draws += 1
                total_points += 1
            else:
                losses += 1

    # Determine dominant result
    results_map = {"wins": wins, "draws": draws, "losses": losses}
    max_result = max(results_map.values())
    dominant_results = [k for k, v in results_map.items() if v == max_result]

    if len(dominant_results) > 1 or max_result < len(matches) * 0.4:
        dominant_result = "mixed"
    else:
        dominant_result = dominant_results[0]

    # Calculate points per match average
    points_per_match = total_points / len(matches) if matches else 0.0

    # Generate reliability assessment
    if consistency_analysis["consistency_rating"] >= 80:
        reliability = "Highly predictable - consistent performance across matches"
    elif consistency_analysis["consistency_rating"] >= 60:
        reliability = "Moderately reliable - some variation in results"
    elif consistency_analysis["consistency_rating"] >= 40:
        reliability = "Unpredictable - significant fluctuation in form"
    else:
        reliability = "Highly volatile - unreliable form pattern"

    # Add context based on pattern
    if consistency_analysis["pattern"] == "consistent":
        if wins > losses:
            reliability += " (consistently strong)"
        elif losses > wins:
            reliability += " (consistently weak)"
        else:
            reliability += " (consistently balanced)"
    elif consistency_analysis["pattern"] == "trending":
        reliability += " (form is changing)"

    return {
        "tool": "get_consistency_score",
        "data": {
            "consistency_rating": consistency_analysis["consistency_rating"],
            "volatility": consistency_analysis["volatility"],
            "pattern": consistency_analysis["pattern"],
            "std_deviation": consistency_analysis["std_deviation"],
            "result_distribution": {
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "dominant_result": dominant_result
            },
            "points_per_match_avg": round(points_per_match, 2),
            "reliability_assessment": reliability
        },
        "metadata": {
            "venue": venue or "all",
            "matches_analyzed": len(matches)
        }
    }
