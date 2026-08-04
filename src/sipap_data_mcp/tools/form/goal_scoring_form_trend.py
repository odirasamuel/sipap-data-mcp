"""
Goal scoring form trend analysis tool.

Analyzes goals scored trajectory to identify offensive form patterns.
"""

from typing import Any, Literal

import asyncpg

from .base import BaseFormTool


async def get_goal_scoring_form_trend(
    pool: asyncpg.Pool,
    team: str,
    league: str,
    match_limit: int = 10,
    venue: Literal["home", "away"] | None = None
) -> dict[str, Any]:
    """
    Analyze goals scored trajectory (improving/declining).

    Args:
        pool: AsyncPG connection pool
        team: Team name to analyze
        league: League/competition name
        match_limit: Number of recent matches to analyze (default: 10)
        venue: Optional venue filter ("home" or "away")

    Returns:
        {
            "tool": "get_goal_scoring_form_trend",
            "data": {
                "trend": "increasing" | "decreasing" | "stable",
                "last_5": {
                    "goals_scored": int,
                    "avg_per_match": float,
                    "highest_in_match": int,
                    "matches_2plus_goals": int
                },
                "previous_5": {
                    "goals_scored": int,
                    "avg_per_match": float,
                    "highest_in_match": int,
                    "matches_2plus_goals": int
                },
                "comparison": {
                    "goals_change": int,
                    "avg_change": float,
                    "percentage_change": float
                },
                "highest_scoring_streak": int,  # Consecutive matches with 2+ goals
                "offensive_rating": int  # 0-100 scale
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_goal_scoring_form_trend(
        ...     pool, "Arsenal", "Premier League"
        ... )
        >>> print(result["data"]["trend"])
        "increasing"
        >>> print(result["data"]["comparison"]["avg_change"])
        0.8
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
            "tool": "get_goal_scoring_form_trend",
            "data": {
                "trend": "stable",
                "last_5": {
                    "goals_scored": 0,
                    "avg_per_match": 0.0,
                    "highest_in_match": 0,
                    "matches_2plus_goals": 0
                },
                "previous_5": {
                    "goals_scored": 0,
                    "avg_per_match": 0.0,
                    "highest_in_match": 0,
                    "matches_2plus_goals": 0
                },
                "comparison": {
                    "goals_change": 0,
                    "avg_change": 0.0,
                    "percentage_change": 0.0
                },
                "highest_scoring_streak": 0,
                "offensive_rating": 0
            },
            "metadata": {
                "venue": venue or "all",
                "matches_analyzed": 0
            }
        }

    # Split into last 5 and previous 5
    last_5 = matches[:5]
    previous_5 = matches[5:10] if len(matches) > 5 else []

    def analyze_goals(period_matches: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze goals scored in a period."""
        if not period_matches:
            return {
                "goals_scored": 0,
                "avg_per_match": 0.0,
                "highest_in_match": 0,
                "matches_2plus_goals": 0
            }

        goals_scored = []
        for match in period_matches:
            is_home = match['home_team'] == team
            scored = match['home_score'] if is_home else match['away_score']
            goals_scored.append(scored)

        total_goals = sum(goals_scored)
        avg = total_goals / len(period_matches)
        highest = max(goals_scored) if goals_scored else 0
        matches_2plus = sum(1 for g in goals_scored if g >= 2)

        return {
            "goals_scored": total_goals,
            "avg_per_match": round(avg, 2),
            "highest_in_match": highest,
            "matches_2plus_goals": matches_2plus
        }

    # Analyze both periods
    last_5_stats = analyze_goals(last_5)
    previous_5_stats = analyze_goals(previous_5)

    # Calculate comparison
    goals_change = last_5_stats["goals_scored"] - previous_5_stats["goals_scored"]
    avg_change = last_5_stats["avg_per_match"] - previous_5_stats["avg_per_match"]
    percentage_change = (
        (avg_change / previous_5_stats["avg_per_match"] * 100)
        if previous_5_stats["avg_per_match"] > 0 else 0.0
    )

    # Determine trend
    if avg_change > 0.5:
        trend = "increasing"
    elif avg_change < -0.5:
        trend = "decreasing"
    else:
        trend = "stable"

    # Find highest scoring streak (consecutive matches with 2+ goals)
    current_streak = 0
    max_streak = 0

    for match in matches:
        is_home = match['home_team'] == team
        scored = match['home_score'] if is_home else match['away_score']

        if scored >= 2:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    # Calculate offensive rating (0-100)
    # Based on: recent avg goals (50%), trend (30%), 2+ goals frequency (20%)

    # Recent avg component (50%)
    # 2.5+ goals per match = excellent (100%), 0 = poor (0%)
    avg_component = min(100, (last_5_stats["avg_per_match"] / 2.5) * 100) * 0.50

    # Trend component (30%)
    if trend == "increasing":
        trend_component = 100 * 0.30
    elif trend == "decreasing":
        trend_component = 0 * 0.30
    else:
        trend_component = 50 * 0.30

    # 2+ goals frequency component (20%)
    freq_pct = (
        last_5_stats["matches_2plus_goals"] / len(last_5) * 100 if last_5 else 0
    )
    freq_component = freq_pct * 0.20

    offensive_rating = int(avg_component + trend_component + freq_component)

    return {
        "tool": "get_goal_scoring_form_trend",
        "data": {
            "trend": trend,
            "last_5": last_5_stats,
            "previous_5": previous_5_stats,
            "comparison": {
                "goals_change": goals_change,
                "avg_change": round(avg_change, 2),
                "percentage_change": round(percentage_change, 1)
            },
            "highest_scoring_streak": max_streak,
            "offensive_rating": offensive_rating
        },
        "metadata": {
            "venue": venue or "all",
            "matches_analyzed": len(matches)
        }
    }
