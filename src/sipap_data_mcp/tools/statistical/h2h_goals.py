"""
Head-to-head goals analysis tool.

Analyzes total goals produced in h2h fixtures with over/under thresholds.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any
import asyncpg
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_h2h_goals(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze total goals produced in head-to-head fixtures.

    Args:
        pool: AsyncPG connection pool
        home_team: Home team name
        away_team: Away team name
        league: League/competition name
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)

    Returns:
        {
            "tool": "get_h2h_goals",
            "data": {
                "total_matches": int,
                "total_goals": int,
                "average_goals_per_match": float,
                "over_thresholds": {
                    "over_0.5": {"count": int, "probability": float},
                    "over_1.5": {"count": int, "probability": float},
                    "over_2.5": {"count": int, "probability": float},
                    "over_3.5": {"count": int, "probability": float},
                    "over_4.5": {"count": int, "probability": float}
                },
                "under_thresholds": {
                    "under_1.5": {"count": int, "probability": float},
                    "under_2.5": {"count": int, "probability": float},
                    "under_3.5": {"count": int, "probability": float}
                },
                "weighted_probabilities": {
                    "over_2.5": float,
                    "under_2.5": float
                },
                "current_form": {
                    "recent_matches": int,
                    "average_goals": float,
                    "over_2.5_probability": float
                }
            },
            "metadata": {...}
        }
    """
    # Use API client if available
    if api_client is not None and isinstance(home_team, int) and isinstance(away_team, int):
        matches_data = await BaseStatisticalTool.get_h2h_matches_api(
            api_client=api_client,
            home_team_id=home_team,
            away_team_id=away_team,
            current_form_matches=current_form_matches,
        )
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        matches_data = await BaseStatisticalTool.get_h2h_matches(
            pool=pool,
            home_team=str(home_team),
            away_team=str(away_team),
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
            "tool": "get_h2h_goals",
            "data": {
                "total_matches": 0,
                "total_goals": 0,
                "average_goals_per_match": 0.0,
                "over_thresholds": {},
                "under_thresholds": {},
                "weighted_probabilities": {"over_2.5": 0.0, "under_2.5": 0.0},
                "current_form": {"recent_matches": 0, "average_goals": 0.0, "over_2.5_probability": 0.0}
            },
            "metadata": {
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None,
                "data_quality": "low"
            }
        }

    # Helper to get total goals (handles both DB and API responses)
    def get_total_goals(match: dict[str, Any]) -> int:
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0
        return home_score + away_score

    # Calculate total goals
    total_matches = len(all_matches)
    total_goals = sum(get_total_goals(m) for m in all_matches)
    average_goals = total_goals / total_matches if total_matches > 0 else 0.0

    # Calculate over/under thresholds
    thresholds = [0.5, 1.5, 2.5, 3.5, 4.5]
    over_thresholds = {}
    under_thresholds = {}

    for threshold in thresholds:
        over_count = sum(1 for m in all_matches if get_total_goals(m) > threshold)
        over_thresholds[f"over_{threshold}"] = {
            "count": over_count,
            "probability": round(over_count / total_matches, 4)
        }

        if threshold >= 1.5:  # Under 0.5 doesn't make sense
            under_count = sum(1 for m in all_matches if get_total_goals(m) < threshold)
            under_thresholds[f"under_{threshold}"] = {
                "count": under_count,
                "probability": round(under_count / total_matches, 4)
            }

    # Calculate weighted probability for over 2.5 (most common market)
    weighted_over_2_5 = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_total_goals(m) > 2.5
    )

    weighted_under_2_5 = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_total_goals(m) < 2.5
    )

    # Current form analysis
    recent_total_goals = sum(get_total_goals(m) for m in recent)
    recent_avg_goals = recent_total_goals / len(recent) if recent else 0.0
    recent_over_2_5_count = sum(1 for m in recent if get_total_goals(m) > 2.5)
    recent_over_2_5_prob = recent_over_2_5_count / len(recent) if recent else 0.0

    current_form = {
        "recent_matches": len(recent),
        "average_goals": round(recent_avg_goals, 2),
        "over_2.5_probability": round(recent_over_2_5_prob, 4)
    }

    # Assess data quality
    data_quality = DataQualityClassifier.assess(total_matches)

    return {
        "tool": "get_h2h_goals",
        "data": {
            "total_matches": total_matches,
            "total_goals": total_goals,
            "average_goals_per_match": round(average_goals, 2),
            "over_thresholds": over_thresholds,
            "under_thresholds": under_thresholds,
            "weighted_probabilities": {
                "over_2.5": weighted_over_2_5,
                "under_2.5": weighted_under_2_5
            },
            "current_form": current_form
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "earliest_match": (
                matches_data["earliest_match"].isoformat()
                if hasattr(matches_data["earliest_match"], "isoformat")
                else matches_data["earliest_match"]
            ) if matches_data["earliest_match"] else None,
            "latest_match": (
                matches_data["latest_match"].isoformat()
                if hasattr(matches_data["latest_match"], "isoformat")
                else matches_data["latest_match"]
            ) if matches_data["latest_match"] else None,
            "data_quality": data_quality
        }
    }
