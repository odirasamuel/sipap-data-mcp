"""
Momentum streak analysis tool.

Detects consecutive winning/losing/drawing streaks to identify momentum patterns.
"""

from typing import Any, Literal

import asyncpg

from .base import BaseFormTool


async def get_momentum_streak(
    pool: asyncpg.Pool,
    team: str,
    league: str,
    match_limit: int = 15,
    venue: Literal["home", "away"] | None = None
) -> dict[str, Any]:
    """
    Detect consecutive result streaks (winning/losing/drawing).

    Args:
        pool: AsyncPG connection pool
        team: Team name to analyze
        league: League/competition name
        match_limit: Number of recent matches to analyze (default: 15)
        venue: Optional venue filter ("home" or "away")

    Returns:
        {
            "tool": "get_momentum_streak",
            "data": {
                "current_streak": {
                    "type": "winning" | "losing" | "drawing" | "mixed",
                    "length": int,
                    "points": int,
                    "goals_scored_avg": float,
                    "goals_conceded_avg": float
                },
                "longest_streak": {
                    "type": "winning" | "losing" | "drawing",
                    "length": int,
                    "period": str,  # e.g., "Mar 1 - Mar 22"
                    "points": int
                },
                "recent_form": {
                    "matches_analyzed": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "points": int
                },
                "momentum_rating": int  # 0-100 scale
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "earliest_match": str,
                "latest_match": str
            }
        }

    Example:
        >>> result = await get_momentum_streak(
        ...     pool, "Arsenal", "Premier League", match_limit=10
        ... )
        >>> print(result["data"]["current_streak"]["type"])
        "winning"
        >>> print(result["data"]["current_streak"]["length"])
        5
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
            "tool": "get_momentum_streak",
            "data": {
                "current_streak": {
                    "type": "mixed",
                    "length": 0,
                    "points": 0,
                    "goals_scored_avg": 0.0,
                    "goals_conceded_avg": 0.0
                },
                "longest_streak": {
                    "type": "mixed",
                    "length": 0,
                    "period": "N/A",
                    "points": 0
                },
                "recent_form": {
                    "matches_analyzed": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "points": 0
                },
                "momentum_rating": 0
            },
            "metadata": {
                "venue": venue or "all",
                "earliest_match": None,
                "latest_match": None
            }
        }

    def get_result(match: dict[str, Any]) -> Literal["win", "draw", "loss"]:
        """Determine result from team's perspective."""
        is_home = match['home_team'] == team
        home_score = match['home_score']
        away_score = match['away_score']

        if is_home:
            if home_score > away_score:
                return "win"
            if home_score == away_score:
                return "draw"
            return "loss"
        if away_score > home_score:
            return "win"
        if away_score == home_score:
            return "draw"
        return "loss"

    def get_goals(match: dict[str, Any]) -> tuple[int, int]:
        """Get goals scored and conceded from team's perspective."""
        is_home = match['home_team'] == team
        if is_home:
            return match['home_score'], match['away_score']
        return match['away_score'], match['home_score']

    # Analyze match results
    results = [get_result(m) for m in matches]

    # Count overall stats
    wins = results.count("win")
    draws = results.count("draw")
    losses = results.count("loss")
    total_points = wins * 3 + draws

    # Detect current streak (most recent consecutive results)
    current_streak_type = results[0] if results else "mixed"
    current_streak_length = 1
    current_streak_matches = [matches[0]]

    for i in range(1, len(results)):
        if results[i] == current_streak_type:
            current_streak_length += 1
            current_streak_matches.append(matches[i])
        else:
            break

    # If only 1 match or different results, it's mixed
    if current_streak_length == 1 and len(results) > 1:
        current_streak_type = "mixed"

    # Calculate current streak stats
    current_streak_points = (
        current_streak_length * 3 if current_streak_type == "win"
        else current_streak_length if current_streak_type == "draw"
        else 0
    )

    current_streak_goals_scored = []
    current_streak_goals_conceded = []
    for match in current_streak_matches:
        scored, conceded = get_goals(match)
        current_streak_goals_scored.append(scored)
        current_streak_goals_conceded.append(conceded)

    current_goals_scored_avg = (
        sum(current_streak_goals_scored) / len(current_streak_goals_scored)
        if current_streak_goals_scored else 0.0
    )
    current_goals_conceded_avg = (
        sum(current_streak_goals_conceded) / len(current_streak_goals_conceded)
        if current_streak_goals_conceded else 0.0
    )

    # Find longest streak in recent matches
    longest_streak_type = current_streak_type
    longest_streak_length = current_streak_length
    longest_streak_start_idx = 0

    temp_streak_type = None
    temp_streak_length = 0
    temp_start_idx = 0

    for i, result in enumerate(results):
        if result == temp_streak_type:
            temp_streak_length += 1
        else:
            temp_streak_type = result
            temp_streak_length = 1
            temp_start_idx = i

        # temp_streak_type is always win/draw/loss (never mixed) from results
        if temp_streak_length > longest_streak_length:
            longest_streak_length = temp_streak_length
            longest_streak_type = temp_streak_type
            longest_streak_start_idx = temp_start_idx

    # Get longest streak period
    longest_streak_start = matches[longest_streak_start_idx]['scheduled_at']
    end_idx = min(
        longest_streak_start_idx + longest_streak_length - 1,
        len(matches) - 1
    )
    longest_streak_end = matches[end_idx]['scheduled_at']
    streak_start_str = longest_streak_start.strftime('%b %d')
    streak_end_str = longest_streak_end.strftime('%b %d')
    longest_streak_period = f"{streak_start_str} - {streak_end_str}"
    longest_streak_points = (
        longest_streak_length * 3 if longest_streak_type == "win"
        else longest_streak_length if longest_streak_type == "draw"
        else 0
    )

    # Calculate momentum rating (0-100)
    # Based on: current streak (40%), recent win rate (30%), recent points (30%)
    streak_bonus = {
        "win": 100,
        "draw": 50,
        "loss": 0,
        "mixed": 25
    }
    streak_val = streak_bonus.get(current_streak_type, 0)
    streak_normalized = min(current_streak_length, 5) / 5
    streak_component = (streak_val * streak_normalized) * 0.40

    win_rate = wins / len(results) if results else 0
    win_rate_component = win_rate * 100 * 0.30

    max_points = len(results) * 3
    points_rate = total_points / max_points if max_points > 0 else 0
    points_component = points_rate * 100 * 0.30

    momentum_rating = int(streak_component + win_rate_component + points_component)

    # Format streak type for output
    streak_type_map = {
        "win": "winning",
        "draw": "drawing",
        "loss": "losing",
        "mixed": "mixed"
    }

    return {
        "tool": "get_momentum_streak",
        "data": {
            "current_streak": {
                "type": streak_type_map[current_streak_type],
                "length": current_streak_length,
                "points": current_streak_points,
                "goals_scored_avg": round(current_goals_scored_avg, 2),
                "goals_conceded_avg": round(current_goals_conceded_avg, 2)
            },
            "longest_streak": {
                "type": streak_type_map[longest_streak_type],
                "length": longest_streak_length,
                "period": longest_streak_period,
                "points": longest_streak_points
            },
            "recent_form": {
                "matches_analyzed": len(matches),
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "points": total_points
            },
            "momentum_rating": momentum_rating
        },
        "metadata": {
            "venue": venue or "all",
            "earliest_match": matches[-1]['scheduled_at'].isoformat() if matches else None,
            "latest_match": matches[0]['scheduled_at'].isoformat() if matches else None
        }
    }
