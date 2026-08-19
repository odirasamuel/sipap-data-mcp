"""
Form trajectory analysis tool.

Compares recent vs previous form to identify improving/declining/stable patterns.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any, Literal

import asyncpg

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool, FormTrendCalculator


async def get_form_trajectory(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    match_limit: int = 10,
    venue: Literal["home", "away"] | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze form trajectory (improving/declining/stable).

    Compares last 5 matches vs previous 5 matches to identify trends.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        team: Team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        match_limit: Number of recent matches to analyze (default: 10)
        venue: Optional venue filter ("home" or "away")
        api_client: Optional API-Football client (preferred)

    Returns:
        {
            "tool": "get_form_trajectory",
            "data": {
                "trajectory": "improving" | "declining" | "stable",
                "last_5": {
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "previous_5": {
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "comparison": {
                    "points_change": int,
                    "points_percentage_change": float,
                    "goals_scored_change": float,
                    "goals_conceded_change": float,
                    "win_rate_change": float
                },
                "trajectory_rating": int  # 0-100 scale
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_form_trajectory(
        ...     pool=None, team=42, league=39, api_client=client
        ... )
        >>> print(result["data"]["trajectory"])
        "improving"
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
        team_identifier: str | int = team
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
            "tool": "get_form_trajectory",
            "data": {
                "trajectory": "stable",
                "last_5": {
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "previous_5": {
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "comparison": {
                    "points_change": 0,
                    "points_percentage_change": 0.0,
                    "goals_scored_change": 0.0,
                    "goals_conceded_change": 0.0,
                    "win_rate_change": 0.0
                },
                "trajectory_rating": 50
            },
            "metadata": {
                "venue": venue or "all",
                "matches_analyzed": 0
            }
        }

    # Split into last 5 and previous 5
    last_5 = matches[:5]
    previous_5 = matches[5:10] if len(matches) > 5 else []

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    def analyze_period(period_matches: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze a period of matches."""
        if not period_matches:
            return {
                "points": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_scored": 0,
                "goals_conceded": 0
            }

        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        for match in period_matches:
            is_home = is_home_team(match)
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0

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

        return {
            "points": points,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded
        }

    # Analyze both periods
    last_5_stats = analyze_period(last_5)
    previous_5_stats = analyze_period(previous_5)

    # Calculate comparison metrics
    points_change = last_5_stats["points"] - previous_5_stats["points"]
    points_percentage = (
        (points_change / previous_5_stats["points"] * 100)
        if previous_5_stats["points"] > 0 else 0.0
    )

    last_5_goals_avg = last_5_stats["goals_scored"] / len(last_5) if last_5 else 0
    previous_5_goals_avg = (
        previous_5_stats["goals_scored"] / len(previous_5)
        if previous_5 else 0
    )
    goals_scored_change = last_5_goals_avg - previous_5_goals_avg

    last_5_conceded_avg = last_5_stats["goals_conceded"] / len(last_5) if last_5 else 0
    previous_5_conceded_avg = (
        previous_5_stats["goals_conceded"] / len(previous_5)
        if previous_5 else 0
    )
    goals_conceded_change = last_5_conceded_avg - previous_5_conceded_avg

    last_5_win_rate = last_5_stats["wins"] / len(last_5) if last_5 else 0
    previous_5_win_rate = (
        previous_5_stats["wins"] / len(previous_5)
        if previous_5 else 0
    )
    win_rate_change = (last_5_win_rate - previous_5_win_rate) * 100

    # Determine trajectory using FormTrendCalculator
    trend_analysis = FormTrendCalculator.analyze(
        last_5_stats["points"],
        previous_5_stats["points"]
    )
    trajectory = trend_analysis["trend"]

    # Calculate trajectory rating (0-100)
    # Based on: points trend (40%), goals scored trend (30%), goals conceded trend (30%)
    # Improving: positive change, Declining: negative change, Stable: minimal change

    # Points component (40%)
    max_points = 15  # 5 matches * 3 points
    points_normalized = last_5_stats["points"] / max_points if max_points > 0 else 0
    points_component = points_normalized * 40

    # Goals scored component (30%)
    # Positive change is good
    goals_scored_component = min(30, max(0, (goals_scored_change + 1) * 15))

    # Goals conceded component (30%)
    # Negative change is good (fewer goals conceded)
    goals_conceded_component = min(30, max(0, (-goals_conceded_change + 1) * 15))

    trajectory_rating = int(points_component + goals_scored_component + goals_conceded_component)

    return {
        "tool": "get_form_trajectory",
        "data": {
            "trajectory": trajectory,
            "last_5": last_5_stats,
            "previous_5": previous_5_stats,
            "comparison": {
                "points_change": points_change,
                "points_percentage_change": round(points_percentage, 1),
                "goals_scored_change": round(goals_scored_change, 2),
                "goals_conceded_change": round(goals_conceded_change, 2),
                "win_rate_change": round(win_rate_change, 1)
            },
            "trajectory_rating": trajectory_rating
        },
        "metadata": {
            "venue": venue or "all",
            "matches_analyzed": len(matches)
        }
    }
