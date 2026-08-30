"""
Head-to-head goals analysis tool.

Analyzes total goals produced in h2h fixtures with over/under thresholds.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
IMPROVED (2026-08-29): Added team form blending, adaptive weighting, confidence penalties.
"""

import logging
from typing import Any
# asyncpg removed (2026-08-20) - database removed
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import (
    BaseStatisticalTool,
    RecencyWeightCalculator,
    DataQualityClassifier,
    calculate_final_confidence,
)

logger = logging.getLogger(__name__)


async def _calculate_form_goals_probability(
    api_client: APIFootballClient,
    home_team_id: int,
    away_team_id: int,
    threshold: float = 2.5,
) -> dict[str, Any]:
    """Calculate theoretical Over/Under probabilities from team form.

    Uses average goals scored + conceded by each team in their venue.

    Args:
        api_client: API-Football client
        home_team_id: Home team ID
        away_team_id: Away team ID
        threshold: Goal threshold (default 2.5)

    Returns:
        Dict with over_probability, under_probability, expected_goals,
        and match counts
    """
    # Get home team's recent home matches
    home_form = await BaseStatisticalTool.get_team_matches_api(
        api_client=api_client,
        team_id=home_team_id,
        venue="home",
        current_form_matches=10,
    )

    # Get away team's recent away matches
    away_form = await BaseStatisticalTool.get_team_matches_api(
        api_client=api_client,
        team_id=away_team_id,
        venue="away",
        current_form_matches=10,
    )

    home_matches = home_form["recent_matches"]
    away_matches = away_form["recent_matches"]

    # Home team average goals at home (scored + conceded)
    home_goals_scored = sum(m.get("home_score") or 0 for m in home_matches)
    home_goals_conceded = sum(m.get("away_score") or 0 for m in home_matches)
    home_avg_total = (home_goals_scored + home_goals_conceded) / len(home_matches) if home_matches else 2.5

    # Away team average goals away (scored + conceded)
    away_goals_scored = sum(m.get("away_score") or 0 for m in away_matches)
    away_goals_conceded = sum(m.get("home_score") or 0 for m in away_matches)
    away_avg_total = (away_goals_scored + away_goals_conceded) / len(away_matches) if away_matches else 2.5

    # Expected goals is average of both averages
    expected_goals = (home_avg_total + away_avg_total) / 2

    # Count matches above/below threshold
    home_over_count = sum(1 for m in home_matches if ((m.get("home_score") or 0) + (m.get("away_score") or 0)) > threshold)
    away_over_count = sum(1 for m in away_matches if ((m.get("home_score") or 0) + (m.get("away_score") or 0)) > threshold)

    home_over_rate = home_over_count / len(home_matches) if home_matches else 0.5
    away_over_rate = away_over_count / len(away_matches) if away_matches else 0.5

    # Theoretical over probability (average of both rates)
    over_probability = (home_over_rate + away_over_rate) / 2
    under_probability = 1 - over_probability

    logger.info(
        f"Form Goals: home_avg_total={home_avg_total:.2f} ({len(home_matches)} home matches), "
        f"away_avg_total={away_avg_total:.2f} ({len(away_matches)} away matches), "
        f"expected={expected_goals:.2f}, over_{threshold}={over_probability:.2f}"
    )

    return {
        "over_probability": round(over_probability, 4),
        "under_probability": round(under_probability, 4),
        "expected_goals": round(expected_goals, 2),
        "home_avg_total_goals": round(home_avg_total, 2),
        "away_avg_total_goals": round(away_avg_total, 2),
        "home_matches_analyzed": len(home_matches),
        "away_matches_analyzed": len(away_matches),
    }


async def get_h2h_goals(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
    blend_with_form: bool = True,
) -> dict[str, Any]:
    """
    Analyze total goals produced in head-to-head fixtures.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.
    IMPROVED (2026-08-29): Added team form blending, adaptive weighting.

    When blend_with_form=True and api_client is provided:
    - Fetches home team's recent home matches
    - Fetches away team's recent away matches
    - Calculates form-based expected goals and over/under probabilities
    - Blends H2H with form-based probabilities

    Args:
        pool: AsyncPG connection pool
        home_team: Home team name
        away_team: Away team name
        league: League/competition name
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)
        api_client: Optional API-Football client (preferred)
        blend_with_form: Whether to blend H2H with team form (default: True)

    Returns:
        {
            "tool": "get_h2h_goals",
            "data": {
                "total_matches": int,
                "total_goals": int,
                "average_goals_per_match": float,
                "over_thresholds": {...},
                "under_thresholds": {...},
                "weighted_probabilities": {...},  # Recency-weighted H2H
                "blended_probabilities": {...},  # H2H + Form blended (NEW)
                "h2h_breakdown": {...},  # Weighting breakdown (NEW)
                "form_data": {...},  # Team form analysis (NEW)
                "confidence": {...},  # Confidence with adjustments (NEW)
                "current_form": {...}
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
                "blended_probabilities": {"over_2.5": 0.0, "under_2.5": 0.0},
                "h2h_breakdown": {},
                "form_data": None,
                "confidence": {"final_confidence": 0.0, "adjustments": ["No data"]},
                "current_form": {"recent_matches": 0, "average_goals": 0.0, "over_2.5_probability": 0.0}
            },
            "metadata": {
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None,
                "data_quality": "low",
                "blend_applied": False,
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

    # Calculate weighted probability for over 2.5 (most common market) - now returns tuple
    weighted_over_2_5, h2h_breakdown_over = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_total_goals(m) > 2.5
    )

    weighted_under_2_5, h2h_breakdown_under = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_total_goals(m) < 2.5
    )

    h2h_breakdown = {
        "over_2.5": h2h_breakdown_over,
        "under_2.5": h2h_breakdown_under,
    }

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

    # Assess data quality with market-specific thresholds
    data_quality = DataQualityClassifier.assess(total_matches, market="OU2.5")

    # Team form blending
    form_data = None
    blended_over_2_5 = weighted_over_2_5
    blended_under_2_5 = weighted_under_2_5

    if blend_with_form and api_client is not None and isinstance(home_team, int) and isinstance(away_team, int):
        try:
            form_data = await _calculate_form_goals_probability(
                api_client=api_client,
                home_team_id=home_team,
                away_team_id=away_team,
                threshold=2.5,
            )

            # Blend H2H with form
            # Weight H2H more when we have more H2H data
            h2h_weight = 0.6 if total_matches >= 8 else 0.4
            form_weight = 1 - h2h_weight

            blended_over_2_5 = round(
                weighted_over_2_5 * h2h_weight + form_data["over_probability"] * form_weight,
                4
            )
            blended_under_2_5 = round(
                weighted_under_2_5 * h2h_weight + form_data["under_probability"] * form_weight,
                4
            )

            logger.info(
                f"Blended Goals: h2h_over={weighted_over_2_5:.2f}, form_over={form_data['over_probability']:.2f}, "
                f"blended_over={blended_over_2_5:.2f} (h2h_weight={h2h_weight})"
            )
        except Exception as e:
            logger.warning(f"Failed to calculate form goals: {e}")
            # Continue with H2H only

    # Calculate confidence with penalties
    # Use the primary prediction (over or under based on higher probability)
    if blended_over_2_5 >= blended_under_2_5:
        base_conf = blended_over_2_5
        h2h_prob = weighted_over_2_5
        form_prob = form_data["over_probability"] if form_data else None
    else:
        base_conf = blended_under_2_5
        h2h_prob = weighted_under_2_5
        form_prob = form_data["under_probability"] if form_data else None

    confidence_data = calculate_final_confidence(
        base_confidence=base_conf,
        h2h_prob=h2h_prob,
        form_prob=form_prob,
        data_quality=data_quality,
    )

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
            "blended_probabilities": {
                "over_2.5": blended_over_2_5,
                "under_2.5": blended_under_2_5
            },
            "h2h_breakdown": h2h_breakdown,
            "form_data": form_data,
            "confidence": confidence_data,
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
            "data_quality": data_quality,
            "blend_applied": blend_with_form and form_data is not None,
            "current_football_season": matches_data.get("current_football_season"),
        }
    }
