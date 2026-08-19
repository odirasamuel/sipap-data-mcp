"""
Momentum streak analysis tool.

Detects consecutive winning/losing/drawing streaks to identify momentum patterns.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from datetime import datetime
from typing import Any, Literal

import asyncpg

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool


def _format_date(date_value: Any) -> str:
    """Format a date value to 'Mon DD' format."""
    if date_value is None:
        return "N/A"
    if isinstance(date_value, str):
        # Parse ISO format string
        try:
            dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            return dt.strftime('%b %d')
        except ValueError:
            return date_value[:10] if len(date_value) >= 10 else date_value
    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%b %d')
    return str(date_value)


def _to_isoformat(date_value: Any) -> str | None:
    """Convert a date value to ISO format string."""
    if date_value is None:
        return None
    if isinstance(date_value, str):
        return date_value
    if hasattr(date_value, 'isoformat'):
        return date_value.isoformat()
    return str(date_value)


async def get_momentum_streak(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    match_limit: int = 15,
    venue: Literal["home", "away"] | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Detect consecutive result streaks (winning/losing/drawing).

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        team: Team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        match_limit: Number of recent matches to analyze (default: 15)
        venue: Optional venue filter ("home" or "away")
        api_client: Optional API-Football client (preferred)

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
        ...     pool=None, team=42, league=39, match_limit=10, api_client=client
        ... )
        >>> print(result["data"]["current_streak"]["type"])
        "winning"
    """
    # Use API client if available
    if api_client is not None and isinstance(team, int):
        league_id = league if isinstance(league, int) else None
        matches = await BaseFormTool.get_recent_team_matches_api(
            api_client=api_client,
            team_id=team,
            league_id=league_id,
            match_limit=match_limit,
            venue=venue,
        )
        # For API matches, use team_id for comparison
        team_identifier = team
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        matches = await BaseFormTool.get_recent_team_matches(
            pool=pool,
            team=str(team),
            league=str(league),
            match_limit=match_limit,
            venue=venue,
        )
        team_identifier = str(team)

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

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        # Support both team name and team ID comparisons
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    def get_result(match: dict[str, Any]) -> Literal["win", "draw", "loss"]:
        """Determine result from team's perspective."""
        is_home = is_home_team(match)
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0

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
        is_home = is_home_team(match)
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0
        if is_home:
            return home_score, away_score
        return away_score, home_score

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
    streak_start_str = _format_date(longest_streak_start)
    streak_end_str = _format_date(longest_streak_end)
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
            "earliest_match": _to_isoformat(matches[-1]['scheduled_at']) if matches else None,
            "latest_match": _to_isoformat(matches[0]['scheduled_at']) if matches else None
        }
    }
