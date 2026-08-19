"""
Defensive form trend analysis tool.

Analyzes goals conceded trajectory to identify defensive form patterns.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any, Literal

import asyncpg

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool


async def get_defensive_form_trend(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    match_limit: int = 10,
    venue: Literal["home", "away"] | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze goals conceded trajectory (tightening/leaking).

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
            "tool": "get_defensive_form_trend",
            "data": {
                "trend": "tightening" | "leaking" | "stable",
                "last_5": {
                    "goals_conceded": int,
                    "avg_per_match": float,
                    "worst_in_match": int,
                    "clean_sheets": int
                },
                "previous_5": {
                    "goals_conceded": int,
                    "avg_per_match": float,
                    "worst_in_match": int,
                    "clean_sheets": int
                },
                "comparison": {
                    "goals_change": int,  # negative = improvement
                    "avg_change": float,  # negative = improvement
                    "percentage_change": float,
                    "clean_sheets_change": int
                },
                "clean_sheet_streak": int,  # Current consecutive clean sheets
                "defensive_rating": int  # 0-100 scale
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_defensive_form_trend(
        ...     pool=None, team=42, league=39, api_client=client
        ... )
        >>> print(result["data"]["trend"])
        "tightening"
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

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    # Handle no data case
    if not matches:
        return {
            "tool": "get_defensive_form_trend",
            "data": {
                "trend": "stable",
                "last_5": {
                    "goals_conceded": 0,
                    "avg_per_match": 0.0,
                    "worst_in_match": 0,
                    "clean_sheets": 0
                },
                "previous_5": {
                    "goals_conceded": 0,
                    "avg_per_match": 0.0,
                    "worst_in_match": 0,
                    "clean_sheets": 0
                },
                "comparison": {
                    "goals_change": 0,
                    "avg_change": 0.0,
                    "percentage_change": 0.0,
                    "clean_sheets_change": 0
                },
                "clean_sheet_streak": 0,
                "defensive_rating": 0
            },
            "metadata": {
                "venue": venue or "all",
                "matches_analyzed": 0
            }
        }

    # Split into last 5 and previous 5
    last_5 = matches[:5]
    previous_5 = matches[5:10] if len(matches) > 5 else []

    def analyze_defense(period_matches: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze goals conceded in a period."""
        if not period_matches:
            return {
                "goals_conceded": 0,
                "avg_per_match": 0.0,
                "worst_in_match": 0,
                "clean_sheets": 0
            }

        goals_conceded = []
        clean_sheets = 0

        for match in period_matches:
            is_home = is_home_team(match)
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0
            conceded = away_score if is_home else home_score
            goals_conceded.append(conceded)

            if conceded == 0:
                clean_sheets += 1

        total_conceded = sum(goals_conceded)
        avg = total_conceded / len(period_matches)
        worst = max(goals_conceded) if goals_conceded else 0

        return {
            "goals_conceded": total_conceded,
            "avg_per_match": round(avg, 2),
            "worst_in_match": worst,
            "clean_sheets": clean_sheets
        }

    # Analyze both periods
    last_5_stats = analyze_defense(last_5)
    previous_5_stats = analyze_defense(previous_5)

    # Calculate comparison
    goals_change = last_5_stats["goals_conceded"] - previous_5_stats["goals_conceded"]
    avg_change = last_5_stats["avg_per_match"] - previous_5_stats["avg_per_match"]
    percentage_change = (
        (avg_change / previous_5_stats["avg_per_match"] * 100)
        if previous_5_stats["avg_per_match"] > 0 else 0.0
    )
    clean_sheets_change = last_5_stats["clean_sheets"] - previous_5_stats["clean_sheets"]

    # Determine trend (negative change = improvement)
    if avg_change < -0.3:
        trend = "tightening"
    elif avg_change > 0.3:
        trend = "leaking"
    else:
        trend = "stable"

    # Find current clean sheet streak
    clean_sheet_streak = 0
    for match in matches:
        is_home = is_home_team(match)
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0
        conceded = away_score if is_home else home_score

        if conceded == 0:
            clean_sheet_streak += 1
        else:
            break

    # Calculate defensive rating (0-100)
    # Based on: recent avg conceded (50%), trend (30%), clean sheets (20%)

    # Recent avg component (50%) - inverse (lower conceded = higher rating)
    # 0 conceded = excellent (100%), 3+ conceded = poor (0%)
    avg_conceded_rating = max(0, 100 - (last_5_stats["avg_per_match"] / 3.0 * 100))
    avg_component = avg_conceded_rating * 0.50

    # Trend component (30%)
    if trend == "tightening":
        trend_component = 100 * 0.30
    elif trend == "leaking":
        trend_component = 0 * 0.30
    else:
        trend_component = 50 * 0.30

    # Clean sheets component (20%)
    clean_sheet_rate = last_5_stats["clean_sheets"] / len(last_5) if last_5 else 0
    clean_sheet_component = clean_sheet_rate * 100 * 0.20

    defensive_rating = int(avg_component + trend_component + clean_sheet_component)

    return {
        "tool": "get_defensive_form_trend",
        "data": {
            "trend": trend,
            "last_5": last_5_stats,
            "previous_5": previous_5_stats,
            "comparison": {
                "goals_change": goals_change,
                "avg_change": round(avg_change, 2),
                "percentage_change": round(percentage_change, 1),
                "clean_sheets_change": clean_sheets_change
            },
            "clean_sheet_streak": clean_sheet_streak,
            "defensive_rating": defensive_rating
        },
        "metadata": {
            "venue": venue or "all",
            "matches_analyzed": len(matches)
        }
    }
