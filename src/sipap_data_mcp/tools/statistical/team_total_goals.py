"""
Team total goals analysis tools.

Analyzes home and away team goal-scoring capabilities.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any, Literal
import asyncpg
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_home_total_goals(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze home team's goal-scoring capability (all home matches).

    Args:
        pool: AsyncPG connection pool
        team: Team name
        league: League/competition name
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)

    Returns:
        {
            "tool": "get_home_total_goals",
            "data": {
                "total_matches": int,
                "total_goals_scored": int,
                "average_goals_per_match": float,
                "minimum_goals_capability": float,  # 25th percentile
                "scoring_probabilities": {
                    "0_goals": float,
                    "1_goal": float,
                    "2_goals": float,
                    "3_goals": float,
                    "4+_goals": float
                },
                "over_thresholds": {
                    "over_0.5": float,
                    "over_1.5": float,
                    "over_2.5": float
                },
                "weighted_average_goals": float,
                "current_form": {
                    "recent_home_matches": int,
                    "average_goals": float,
                    "over_1.5_probability": float
                }
            },
            "metadata": {...}
        }
    """
    return await _get_team_total_goals(
        pool=pool,
        team=team,
        venue="home",
        league=league,
        seasons_back=seasons_back,
        current_form_matches=current_form_matches,
        api_client=api_client,
    )


async def get_away_total_goals(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze away team's goal-scoring capability (all away matches).

    Args:
        pool: AsyncPG connection pool
        team: Team name
        league: League/competition name
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)

    Returns:
        Same structure as get_home_total_goals, but for away matches
    """
    return await _get_team_total_goals(
        pool=pool,
        team=team,
        venue="away",
        league=league,
        seasons_back=seasons_back,
        current_form_matches=current_form_matches,
        api_client=api_client,
    )


async def _get_team_total_goals(
    pool: asyncpg.Pool | None,
    team: str | int,
    venue: Literal["home", "away"],
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Internal implementation for team goal analysis.

    Args:
        pool: AsyncPG connection pool
        team: Team name
        venue: "home" or "away"
        league: League/competition name
        seasons_back: Historical seasons to analyze
        current_form_matches: Recent matches for current form

    Returns:
        Structured goal analysis data
    """
    tool_name = f"get_{venue}_total_goals"

    # Use API client if available
    if api_client is not None and isinstance(team, int):
        league_id = league if isinstance(league, int) else None
        matches_data = await BaseStatisticalTool.get_team_matches_api(
            api_client=api_client,
            team_id=team,
            venue=venue,
            league_id=league_id,
            current_form_matches=current_form_matches,
        )
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        matches_data = await BaseStatisticalTool.get_team_matches(
            pool=pool,
            team=str(team),
            venue=venue,
            league=str(league),
            seasons_back=seasons_back,
            current_form_matches=current_form_matches,
        )

    all_matches = matches_data["all_matches"]
    recent = matches_data["recent_matches"]
    last_season = matches_data["last_season"]
    older = matches_data["older_seasons"]

    if not all_matches:
        return {
            "tool": tool_name,
            "data": {
                "total_matches": 0,
                "total_goals_scored": 0,
                "average_goals_per_match": 0.0,
                "minimum_goals_capability": 0.0,
                "scoring_probabilities": {},
                "over_thresholds": {},
                "weighted_average_goals": 0.0,
                "current_form": {"recent_home_matches" if venue == "home" else "recent_away_matches": 0, "average_goals": 0.0, "over_1.5_probability": 0.0}
            },
            "metadata": {"seasons_analyzed": 0, "earliest_match": None, "latest_match": None, "data_quality": "low"}
        }

    # Helper to get team's goals scored (handles both DB and API responses)
    def get_goals_scored(match: dict[str, Any]) -> int:
        if venue == "home":
            return match.get('home_score', 0) or 0
        else:
            return match.get('away_score', 0) or 0

    # Calculate total goals
    total_matches = len(all_matches)
    total_goals_scored = sum(get_goals_scored(m) for m in all_matches)
    average_goals = total_goals_scored / total_matches if total_matches > 0 else 0.0

    # Calculate scoring probabilities (0, 1, 2, 3, 4+ goals)
    goals_0 = sum(1 for m in all_matches if get_goals_scored(m) == 0)
    goals_1 = sum(1 for m in all_matches if get_goals_scored(m) == 1)
    goals_2 = sum(1 for m in all_matches if get_goals_scored(m) == 2)
    goals_3 = sum(1 for m in all_matches if get_goals_scored(m) == 3)
    goals_4_plus = sum(1 for m in all_matches if get_goals_scored(m) >= 4)

    scoring_probabilities = {
        "0_goals": round(goals_0 / total_matches, 4) if total_matches > 0 else 0.0,
        "1_goal": round(goals_1 / total_matches, 4) if total_matches > 0 else 0.0,
        "2_goals": round(goals_2 / total_matches, 4) if total_matches > 0 else 0.0,
        "3_goals": round(goals_3 / total_matches, 4) if total_matches > 0 else 0.0,
        "4+_goals": round(goals_4_plus / total_matches, 4) if total_matches > 0 else 0.0
    }

    # Calculate over thresholds
    over_0_5_count = sum(1 for m in all_matches if get_goals_scored(m) > 0.5)
    over_1_5_count = sum(1 for m in all_matches if get_goals_scored(m) > 1.5)
    over_2_5_count = sum(1 for m in all_matches if get_goals_scored(m) > 2.5)

    over_thresholds = {
        "over_0.5": round(over_0_5_count / total_matches, 4) if total_matches > 0 else 0.0,
        "over_1.5": round(over_1_5_count / total_matches, 4) if total_matches > 0 else 0.0,
        "over_2.5": round(over_2_5_count / total_matches, 4) if total_matches > 0 else 0.0
    }

    # Calculate minimum goals capability (25th percentile)
    goals_sorted = sorted([get_goals_scored(m) for m in all_matches])
    percentile_25_index = int(len(goals_sorted) * 0.25)
    minimum_goals_capability = goals_sorted[percentile_25_index] if goals_sorted else 0.0

    # Calculate weighted average goals with recency bias
    def get_avg_goals(matches: list[dict[str, Any]]) -> float:
        if not matches:
            return 0.0
        total = sum(get_goals_scored(m) for m in matches)
        return total / len(matches)

    recent_avg = get_avg_goals(recent)
    last_season_avg = get_avg_goals(last_season)
    older_avg = get_avg_goals(older)

    weighted_avg = (
        recent_avg * 0.50 +
        last_season_avg * 0.30 +
        older_avg * 0.20
    )

    # Current form analysis
    recent_goals = sum(get_goals_scored(m) for m in recent)
    recent_avg_goals = recent_goals / len(recent) if recent else 0.0
    recent_over_1_5_count = sum(1 for m in recent if get_goals_scored(m) > 1.5)
    recent_over_1_5_prob = recent_over_1_5_count / len(recent) if recent else 0.0

    current_form = {
        f"recent_{venue}_matches": len(recent),
        "average_goals": round(recent_avg_goals, 2),
        "over_1.5_probability": round(recent_over_1_5_prob, 4)
    }

    # Assess data quality
    data_quality = DataQualityClassifier.assess(total_matches)

    return {
        "tool": tool_name,
        "data": {
            "total_matches": total_matches,
            "total_goals_scored": total_goals_scored,
            "average_goals_per_match": round(average_goals, 2),
            "minimum_goals_capability": round(minimum_goals_capability, 2),
            "scoring_probabilities": scoring_probabilities,
            "over_thresholds": over_thresholds,
            "weighted_average_goals": round(weighted_avg, 2),
            "current_form": current_form
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "earliest_match": matches_data["earliest_match"].isoformat() if matches_data["earliest_match"] else None,
            "latest_match": matches_data["latest_match"].isoformat() if matches_data["latest_match"] else None,
            "data_quality": data_quality
        }
    }
