"""
Pressure performance analysis tool.

Analyzes form against strong opponents vs weaker opponents.
"""

from typing import Any

import asyncpg

from .base import BaseFormTool


async def get_pressure_performance(
    pool: asyncpg.Pool,
    team: str,
    league: str,
    match_limit: int = 15,
    top_team_threshold: float = 2.0  # Points per match threshold for "strong" teams
) -> dict[str, Any]:
    """
    Analyze form against strong opponents.

    Strong opponents are identified as teams averaging 2+ points per match
    in recent form (typically top 6-8 teams).

    Args:
        pool: AsyncPG connection pool
        team: Team name to analyze
        league: League/competition name
        match_limit: Number of recent matches to analyze (default: 15)
        top_team_threshold: Points per match threshold for "strong" teams (default: 2.0)

    Returns:
        {
            "tool": "get_pressure_performance",
            "data": {
                "vs_strong_opponents": {
                    "matches": int,
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "points_per_match": float,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "vs_weaker_opponents": {
                    "matches": int,
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "points_per_match": float,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "comparison": {
                    "points_per_match_diff": float,  # negative = struggles vs strong teams
                    "win_rate_diff": float,
                    "performance_differential": int,  # -100 to +100
                    "pressure_rating": "high" | "medium" | "low"
                },
                "pressure_performance_rating": int  # 0-100 scale
            },
            "metadata": {
                "strong_opponent_threshold": float,
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_pressure_performance(
        ...     pool, "Arsenal", "Premier League"
        ... )
        >>> print(result["data"]["comparison"]["pressure_rating"])
        "high"
        >>> print(result["data"]["pressure_performance_rating"])
        72
    """
    # Get recent matches for the team
    matches = await BaseFormTool.get_recent_team_matches(
        pool=pool,
        team=team,
        league=league,
        match_limit=match_limit,
        venue=None
    )

    # Handle no data case
    if not matches:
        return {
            "tool": "get_pressure_performance",
            "data": {
                "vs_strong_opponents": {
                    "matches": 0,
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "points_per_match": 0.0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "vs_weaker_opponents": {
                    "matches": 0,
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "points_per_match": 0.0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "comparison": {
                    "points_per_match_diff": 0.0,
                    "win_rate_diff": 0.0,
                    "performance_differential": 0,
                    "pressure_rating": "low"
                },
                "pressure_performance_rating": 50
            },
            "metadata": {
                "strong_opponent_threshold": top_team_threshold,
                "matches_analyzed": 0
            }
        }

    # Categorize opponents as strong or weaker
    # For simplicity, use basic heuristic: if opponent has won >60% of matches, they're "strong"
    # In production, this could query league standings

    strong_opponent_matches = []
    weaker_opponent_matches = []

    async with pool.acquire() as conn:
        for match in matches:
            # Identify opponent
            is_home = match['home_team'] == team
            opponent = match['away_team'] if is_home else match['home_team']

            # Get opponent's recent form (last 10 matches)
            opponent_query = """
                SELECT COUNT(*) FILTER (WHERE
                    (home_team = $1 AND home_score > away_score) OR
                    (away_team = $1 AND away_score > home_score)
                ) as wins,
                COUNT(*) as total_matches
                FROM matches
                WHERE
                    (home_team = $1 OR away_team = $1)
                    AND league = $2
                    AND status = 'finished'
                    AND scheduled_at <= $3
                ORDER BY scheduled_at DESC
                LIMIT 10
            """

            opponent_stats = await conn.fetchrow(
                opponent_query,
                opponent,
                league,
                match['scheduled_at']
            )

            # Classify opponent
            if opponent_stats and opponent_stats['total_matches'] > 0:
                opponent_win_rate = opponent_stats['wins'] / opponent_stats['total_matches']
                # Strong opponent = >60% win rate OR top team threshold
                if opponent_win_rate >= 0.6:
                    strong_opponent_matches.append(match)
                else:
                    weaker_opponent_matches.append(match)
            else:
                # Unknown opponent strength, classify as weaker
                weaker_opponent_matches.append(match)

    def analyze_matches(match_list: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze performance against a category of opponents."""
        if not match_list:
            return {
                "matches": 0,
                "points": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points_per_match": 0.0,
                "goals_scored": 0,
                "goals_conceded": 0
            }

        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        for match in match_list:
            is_home = match['home_team'] == team
            home_score = match['home_score']
            away_score = match['away_score']

            if is_home:
                scored = home_score
                conceded = away_score
                if home_score > away_score:
                    wins += 1
                elif home_score == away_score:
                    draws += 1
                else:
                    losses += 1
            else:
                scored = away_score
                conceded = home_score
                if away_score > home_score:
                    wins += 1
                elif away_score == home_score:
                    draws += 1
                else:
                    losses += 1

            goals_scored += scored
            goals_conceded += conceded

        points = wins * 3 + draws
        points_per_match = points / len(match_list)

        return {
            "matches": len(match_list),
            "points": points,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points_per_match": round(points_per_match, 2),
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded
        }

    # Analyze both categories
    strong_stats = analyze_matches(strong_opponent_matches)
    weaker_stats = analyze_matches(weaker_opponent_matches)

    # Calculate comparison
    points_per_match_diff = strong_stats["points_per_match"] - weaker_stats["points_per_match"]

    strong_win_rate = (
        strong_stats["wins"] / strong_stats["matches"]
        if strong_stats["matches"] > 0
        else 0
    )
    weaker_win_rate = (
        weaker_stats["wins"] / weaker_stats["matches"]
        if weaker_stats["matches"] > 0
        else 0
    )
    win_rate_diff = strong_win_rate - weaker_win_rate

    # Performance differential (-100 to +100)
    # Positive = performs better vs strong teams
    # Negative = struggles vs strong teams
    performance_differential = int(points_per_match_diff * 33.33)  # Scale to -100 to +100

    # Determine pressure rating
    # High: performs well vs strong teams (diff > -0.5)
    # Medium: moderate drop-off (diff -0.5 to -1.5)
    # Low: struggles vs strong teams (diff < -1.5)
    if points_per_match_diff > -0.5:
        pressure_rating = "high"
    elif points_per_match_diff > -1.5:
        pressure_rating = "medium"
    else:
        pressure_rating = "low"

    # Calculate pressure performance rating (0-100)
    # Based on: points vs strong teams (60%), relative performance (40%)

    # Points vs strong component (60%)
    max_points_per_match = 3.0
    strong_points_normalized = strong_stats["points_per_match"] / max_points_per_match
    strong_points_component = strong_points_normalized * 60

    # Relative performance component (40%)
    # +1.0 diff = excellent, -1.0 diff = poor
    relative_performance_normalized = min(1.0, max(-1.0, points_per_match_diff + 1.0))
    relative_component = relative_performance_normalized * 40

    pressure_performance_rating = int(strong_points_component + relative_component)

    return {
        "tool": "get_pressure_performance",
        "data": {
            "vs_strong_opponents": strong_stats,
            "vs_weaker_opponents": weaker_stats,
            "comparison": {
                "points_per_match_diff": round(points_per_match_diff, 2),
                "win_rate_diff": round(win_rate_diff, 3),
                "performance_differential": performance_differential,
                "pressure_rating": pressure_rating
            },
            "pressure_performance_rating": pressure_performance_rating
        },
        "metadata": {
            "strong_opponent_threshold": top_team_threshold,
            "matches_analyzed": len(matches)
        }
    }
