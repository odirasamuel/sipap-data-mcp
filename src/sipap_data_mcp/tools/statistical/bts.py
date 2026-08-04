"""
Both teams to score (BTS) analysis tool.

Analyzes probability of both teams scoring at least one goal.
"""

from typing import Any
import asyncpg
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_bts(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Analyze probability of both teams scoring at least one goal.

    Args:
        pool: AsyncPG connection pool
        home_team: Home team name
        away_team: Away team name
        league: League/competition name
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)

    Returns:
        {
            "tool": "get_bts",
            "data": {
                "total_matches": int,
                "bts_occurrences": int,
                "bts_probability": float,
                "no_bts_occurrences": int,
                "no_bts_probability": float,
                "weighted_bts_probability": float,
                "current_form": {
                    "recent_matches": int,
                    "bts_occurrences": int,
                    "bts_probability": float
                },
                "breakdown": {
                    "home_scored_away_blanked": int,
                    "away_scored_home_blanked": int,
                    "both_scored": int,
                    "both_blanked": int
                }
            },
            "metadata": {...}
        }
    """
    # Get matches partitioned by recency
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool=pool,
        home_team=home_team,
        away_team=away_team,
        league=league,
        seasons_back=seasons_back,
        current_form_matches=current_form_matches
    )

    all_matches = matches_data["all_matches"]
    recent = matches_data["recent_matches"]
    last_season = matches_data["last_season"]
    older = matches_data["older_seasons"]

    if not all_matches:
        return {
            "tool": "get_bts",
            "data": {
                "total_matches": 0,
                "bts_occurrences": 0,
                "bts_probability": 0.0,
                "no_bts_occurrences": 0,
                "no_bts_probability": 0.0,
                "weighted_bts_probability": 0.0,
                "current_form": {"recent_matches": 0, "bts_occurrences": 0, "bts_probability": 0.0},
                "breakdown": {"home_scored_away_blanked": 0, "away_scored_home_blanked": 0, "both_scored": 0, "both_blanked": 0}
            },
            "metadata": {"seasons_analyzed": 0, "earliest_match": None, "latest_match": None, "data_quality": "low"}
        }

    # Helper to check if both teams scored
    def both_teams_scored(match: dict[str, Any]) -> bool:
        return match['home_score'] > 0 and match['away_score'] > 0

    # Calculate BTS statistics
    total_matches = len(all_matches)
    bts_occurrences = sum(1 for m in all_matches if both_teams_scored(m))
    no_bts_occurrences = total_matches - bts_occurrences

    bts_probability = bts_occurrences / total_matches if total_matches > 0 else 0.0
    no_bts_probability = no_bts_occurrences / total_matches if total_matches > 0 else 0.0

    # Breakdown of scoring patterns
    home_scored_away_blanked = sum(1 for m in all_matches if m['home_score'] > 0 and m['away_score'] == 0)
    away_scored_home_blanked = sum(1 for m in all_matches if m['away_score'] > 0 and m['home_score'] == 0)
    both_scored = bts_occurrences
    both_blanked = sum(1 for m in all_matches if m['home_score'] == 0 and m['away_score'] == 0)

    # Calculate weighted BTS probability
    weighted_bts_prob = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=both_teams_scored
    )

    # Current form analysis
    recent_bts_count = sum(1 for m in recent if both_teams_scored(m))
    recent_bts_prob = recent_bts_count / len(recent) if recent else 0.0

    current_form = {
        "recent_matches": len(recent),
        "bts_occurrences": recent_bts_count,
        "bts_probability": round(recent_bts_prob, 4)
    }

    # Assess data quality
    data_quality = DataQualityClassifier.assess(total_matches)

    return {
        "tool": "get_bts",
        "data": {
            "total_matches": total_matches,
            "bts_occurrences": bts_occurrences,
            "bts_probability": round(bts_probability, 4),
            "no_bts_occurrences": no_bts_occurrences,
            "no_bts_probability": round(no_bts_probability, 4),
            "weighted_bts_probability": weighted_bts_prob,
            "current_form": current_form,
            "breakdown": {
                "home_scored_away_blanked": home_scored_away_blanked,
                "away_scored_home_blanked": away_scored_home_blanked,
                "both_scored": both_scored,
                "both_blanked": both_blanked
            }
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "earliest_match": matches_data["earliest_match"].isoformat() if matches_data["earliest_match"] else None,
            "latest_match": matches_data["latest_match"].isoformat() if matches_data["latest_match"] else None,
            "data_quality": data_quality
        }
    }
