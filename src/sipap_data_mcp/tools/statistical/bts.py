"""
Both teams to score (BTS) analysis tool.

Analyzes probability of both teams scoring at least one goal.

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


async def _calculate_form_btts_probability(
    api_client: APIFootballClient,
    home_team_id: int,
    away_team_id: int,
) -> dict[str, Any]:
    """Calculate theoretical BTTS from team form.

    P(BTTS) ≈ P(Home scores at home) × P(Away scores away)

    Args:
        api_client: API-Football client
        home_team_id: Home team ID
        away_team_id: Away team ID

    Returns:
        Dict with home_scores_probability, away_scores_probability,
        btts_probability, and match counts
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

    # Calculate scoring probabilities
    home_matches = home_form["recent_matches"]
    away_matches = away_form["recent_matches"]

    home_scores_prob = (
        sum(1 for m in home_matches if (m.get("home_score") or 0) > 0) / len(home_matches)
        if home_matches else 0.5
    )

    away_scores_prob = (
        sum(1 for m in away_matches if (m.get("away_score") or 0) > 0) / len(away_matches)
        if away_matches else 0.5
    )

    # Theoretical BTTS probability
    btts_probability = home_scores_prob * away_scores_prob

    logger.info(
        f"Form BTTS: home_scores={home_scores_prob:.2f} ({len(home_matches)} matches), "
        f"away_scores={away_scores_prob:.2f} ({len(away_matches)} matches), "
        f"btts={btts_probability:.2f}"
    )

    return {
        "home_scores_probability": round(home_scores_prob, 4),
        "away_scores_probability": round(away_scores_prob, 4),
        "btts_probability": round(btts_probability, 4),
        "home_matches_analyzed": len(home_matches),
        "away_matches_analyzed": len(away_matches),
    }


async def get_bts(
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
    Analyze probability of both teams scoring at least one goal.

    When blend_with_form=True and api_client is provided:
    - Fetches home team's recent home matches
    - Fetches away team's recent away matches
    - Calculates P(Home scores at home) × P(Away scores away)
    - Blends H2H BTTS with theoretical form-based BTTS

    Args:
        pool: AsyncPG connection pool (can be None if api_client provided)
        home_team: Home team name or API-Football team ID
        away_team: Away team name or API-Football team ID
        league: League/competition name or ID
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)
        api_client: API-Football client for direct API access
        blend_with_form: Whether to blend H2H with team form (default: True)

    Returns:
        {
            "tool": "get_bts",
            "data": {
                "total_matches": int,
                "bts_occurrences": int,
                "bts_probability": float,  # Raw H2H probability
                "no_bts_occurrences": int,
                "no_bts_probability": float,
                "weighted_bts_probability": float,  # Recency-weighted H2H
                "blended_bts_probability": float,  # H2H + Form blended (NEW)
                "h2h_breakdown": {...},  # Weighting breakdown (NEW)
                "form_data": {...},  # Team form analysis (NEW)
                "confidence": {...},  # Confidence with adjustments (NEW)
                "current_form": {...},
                "breakdown": {...}
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
            "tool": "get_bts",
            "data": {
                "total_matches": 0,
                "bts_occurrences": 0,
                "bts_probability": 0.0,
                "no_bts_occurrences": 0,
                "no_bts_probability": 0.0,
                "weighted_bts_probability": 0.0,
                "blended_bts_probability": 0.0,
                "h2h_breakdown": {},
                "form_data": None,
                "confidence": {"final_confidence": 0.0, "adjustments": ["No data"]},
                "current_form": {"recent_matches": 0, "bts_occurrences": 0, "bts_probability": 0.0},
                "breakdown": {"home_scored_away_blanked": 0, "away_scored_home_blanked": 0, "both_scored": 0, "both_blanked": 0}
            },
            "metadata": {"seasons_analyzed": 0, "earliest_match": None, "latest_match": None, "data_quality": "low"}
        }

    # Helper to get scores safely (handles both DB and API responses)
    def get_scores(match: dict[str, Any]) -> tuple[int, int]:
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0
        return home_score, away_score

    # Helper to check if both teams scored
    def both_teams_scored(match: dict[str, Any]) -> bool:
        home_score, away_score = get_scores(match)
        return home_score > 0 and away_score > 0

    # Calculate BTS statistics
    total_matches = len(all_matches)
    bts_occurrences = sum(1 for m in all_matches if both_teams_scored(m))
    no_bts_occurrences = total_matches - bts_occurrences

    bts_probability = bts_occurrences / total_matches if total_matches > 0 else 0.0
    no_bts_probability = no_bts_occurrences / total_matches if total_matches > 0 else 0.0

    # Breakdown of scoring patterns
    home_scored_away_blanked = sum(1 for m in all_matches if get_scores(m)[0] > 0 and get_scores(m)[1] == 0)
    away_scored_home_blanked = sum(1 for m in all_matches if get_scores(m)[1] > 0 and get_scores(m)[0] == 0)
    both_scored = bts_occurrences
    both_blanked = sum(1 for m in all_matches if get_scores(m)[0] == 0 and get_scores(m)[1] == 0)

    # Calculate weighted BTS probability with breakdown
    weighted_bts_prob, h2h_breakdown = RecencyWeightCalculator.calculate(
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

    # Assess data quality with market-specific thresholds
    data_quality = DataQualityClassifier.assess(total_matches, market="BTTS")

    # Team form blending
    form_data = None
    blended_prob = weighted_bts_prob

    if blend_with_form and api_client is not None and isinstance(home_team, int) and isinstance(away_team, int):
        try:
            form_data = await _calculate_form_btts_probability(
                api_client=api_client,
                home_team_id=home_team,
                away_team_id=away_team,
            )

            # Blend H2H with form
            # Weight H2H more when we have more H2H data
            h2h_weight = 0.6 if total_matches >= 8 else 0.4
            form_weight = 1 - h2h_weight

            blended_prob = round(
                weighted_bts_prob * h2h_weight + form_data["btts_probability"] * form_weight,
                4
            )

            logger.info(
                f"Blended BTTS: h2h={weighted_bts_prob:.2f} (weight={h2h_weight}), "
                f"form={form_data['btts_probability']:.2f} (weight={form_weight}), "
                f"blended={blended_prob:.2f}"
            )
        except Exception as e:
            logger.warning(f"Failed to calculate form BTTS: {e}")
            # Continue with H2H only
            blended_prob = weighted_bts_prob

    # Calculate confidence with penalties
    confidence_data = calculate_final_confidence(
        base_confidence=blended_prob,
        h2h_prob=weighted_bts_prob,
        form_prob=form_data["btts_probability"] if form_data else None,
        data_quality=data_quality,
    )

    return {
        "tool": "get_bts",
        "data": {
            "total_matches": total_matches,
            "bts_occurrences": bts_occurrences,
            "bts_probability": round(bts_probability, 4),
            "no_bts_occurrences": no_bts_occurrences,
            "no_bts_probability": round(no_bts_probability, 4),
            "weighted_bts_probability": weighted_bts_prob,
            "blended_bts_probability": blended_prob,
            "h2h_breakdown": h2h_breakdown,
            "form_data": form_data,
            "confidence": confidence_data,
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
