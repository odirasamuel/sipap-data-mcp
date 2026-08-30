"""
Head-to-head full-time result analysis tool.

Analyzes win/draw/loss record between two teams with recency weighting.

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


async def _calculate_form_1x2_probability(
    api_client: APIFootballClient,
    home_team_id: int,
    away_team_id: int,
) -> dict[str, Any]:
    """Calculate theoretical 1X2 probabilities from team form.

    Uses recent home form for home team and away form for away team.

    Args:
        api_client: API-Football client
        home_team_id: Home team ID
        away_team_id: Away team ID

    Returns:
        Dict with home_win_probability, draw_probability, away_win_probability,
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

    # Home team win rate at home
    home_wins_at_home = sum(
        1 for m in home_matches
        if (m.get("home_score") or 0) > (m.get("away_score") or 0)
    )
    home_draws_at_home = sum(
        1 for m in home_matches
        if (m.get("home_score") or 0) == (m.get("away_score") or 0)
        and m.get("home_score") is not None
    )
    home_win_rate = home_wins_at_home / len(home_matches) if home_matches else 0.33
    home_draw_rate = home_draws_at_home / len(home_matches) if home_matches else 0.33

    # Away team win rate away
    away_wins_away = sum(
        1 for m in away_matches
        if (m.get("away_score") or 0) > (m.get("home_score") or 0)
    )
    away_draws_away = sum(
        1 for m in away_matches
        if (m.get("away_score") or 0) == (m.get("home_score") or 0)
        and m.get("away_score") is not None
    )
    away_win_rate = away_wins_away / len(away_matches) if away_matches else 0.33
    away_draw_rate = away_draws_away / len(away_matches) if away_matches else 0.33

    # Theoretical probabilities
    # Home wins when home team wins at home AND away team loses away
    # This is a simplification - real models would be more sophisticated
    form_home_win = home_win_rate * (1 - away_win_rate)
    form_away_win = away_win_rate * (1 - home_win_rate)

    # Draw is more complex - average of both draw rates
    form_draw = (home_draw_rate + away_draw_rate) / 2

    # Normalize to sum to 1.0
    total = form_home_win + form_draw + form_away_win
    if total > 0:
        form_home_win /= total
        form_draw /= total
        form_away_win /= total
    else:
        form_home_win = form_draw = form_away_win = 0.33

    logger.info(
        f"Form 1X2: home_win={form_home_win:.2f} ({len(home_matches)} home matches), "
        f"draw={form_draw:.2f}, away_win={form_away_win:.2f} ({len(away_matches)} away matches)"
    )

    return {
        "home_win_probability": round(form_home_win, 4),
        "draw_probability": round(form_draw, 4),
        "away_win_probability": round(form_away_win, 4),
        "home_matches_analyzed": len(home_matches),
        "away_matches_analyzed": len(away_matches),
        "home_win_rate_at_home": round(home_win_rate, 4),
        "away_win_rate_away": round(away_win_rate, 4),
    }


async def get_h2h_full_time_result(
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
    Analyze head-to-head full-time result record.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.
    IMPROVED (2026-08-29): Added team form blending, adaptive weighting.

    When blend_with_form=True and api_client is provided:
    - Fetches home team's recent home matches
    - Fetches away team's recent away matches
    - Calculates form-based 1X2 probabilities
    - Blends H2H with form-based probabilities

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        home_team: Home team name (for DB) or API-Football team ID (for API)
        away_team: Away team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)
        api_client: Optional API-Football client (preferred)
        blend_with_form: Whether to blend H2H with team form (default: True)

    Returns:
        {
            "tool": "get_h2h_full_time_result",
            "data": {
                "total_matches": int,
                "home_wins": int,
                "draws": int,
                "away_wins": int,
                "home_win_probability": float,  # Raw H2H probability
                "draw_probability": float,
                "away_win_probability": float,
                "weighted_probabilities": {...},  # Recency-weighted H2H
                "blended_probabilities": {...},  # H2H + Form blended (NEW)
                "h2h_breakdown": {...},  # Weighting breakdown (NEW)
                "form_data": {...},  # Team form analysis (NEW)
                "confidence": {...},  # Confidence with adjustments (NEW)
                "current_form": {...},
                "by_season": [...]
            },
            "metadata": {...}
        }

    Example:
        >>> result = await get_h2h_full_time_result(
        ...     pool, "Arsenal", "Chelsea", "Premier League"
        ... )
        >>> print(result["data"]["blended_probabilities"]["home_win"])
        0.4200
    """
    # Use API client if available
    if api_client is not None and isinstance(home_team, int) and isinstance(away_team, int):
        matches_data = await BaseStatisticalTool.get_h2h_matches_api(
            api_client=api_client,
            home_team_id=home_team,
            away_team_id=away_team,
            current_form_matches=current_form_matches,
        )
        home_team_identifier: str | int = home_team
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
        home_team_identifier = str(home_team)

    all_matches = matches_data["all_matches"]
    recent = matches_data["recent_matches"]
    last_season = matches_data["last_season"]
    older = matches_data["older_seasons"]

    # Handle no data case
    if not all_matches:
        return {
            "tool": "get_h2h_full_time_result",
            "data": {
                "total_matches": 0,
                "home_wins": 0,
                "draws": 0,
                "away_wins": 0,
                "home_win_probability": 0.0,
                "draw_probability": 0.0,
                "away_win_probability": 0.0,
                "weighted_probabilities": {
                    "home_win": 0.0,
                    "draw": 0.0,
                    "away_win": 0.0
                },
                "blended_probabilities": {
                    "home_win": 0.0,
                    "draw": 0.0,
                    "away_win": 0.0
                },
                "h2h_breakdown": {},
                "form_data": None,
                "confidence": {"final_confidence": 0.0, "adjustments": ["No data"]},
                "current_form": {
                    "recent_matches": 0,
                    "home_wins": 0,
                    "draws": 0,
                    "away_wins": 0,
                    "home_win_probability": 0.0
                },
                "by_season": []
            },
            "metadata": {
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None,
                "data_quality": "low",
                "blend_applied": False,
            }
        }

    # Helper to determine result from home team perspective
    def get_result(match: dict[str, Any]) -> str | None:
        """
        Returns 'home_win', 'draw', or 'away_win' from home team perspective.
        Returns None if scores are not available (e.g., upcoming matches).

        Accounts for reversed fixtures (home_team might be away in this match).
        """
        # Check if our "home team" is actually playing at home in this match
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier

        home_score = match.get('home_score')
        away_score = match.get('away_score')

        # Skip matches without scores (upcoming or cancelled)
        if home_score is None or away_score is None:
            return None

        if is_home:
            # Our home team is actually home in this match
            if home_score > away_score:
                return 'home_win'
            elif home_score < away_score:
                return 'away_win'
            else:
                return 'draw'
        else:
            # Our home team is actually away in this match (reversed fixture)
            # So we flip the perspective
            if away_score > home_score:
                return 'home_win'
            elif away_score < home_score:
                return 'away_win'
            else:
                return 'draw'

    # Filter to only matches with valid results (exclude upcoming/cancelled)
    valid_matches = [m for m in all_matches if get_result(m) is not None]
    valid_recent = [m for m in recent if get_result(m) is not None]

    # Count results in valid matches only
    total_matches = len(valid_matches)
    home_wins = sum(1 for m in valid_matches if get_result(m) == 'home_win')
    draws = sum(1 for m in valid_matches if get_result(m) == 'draw')
    away_wins = sum(1 for m in valid_matches if get_result(m) == 'away_win')

    # Calculate base probabilities
    home_win_prob = home_wins / total_matches if total_matches > 0 else 0.0
    draw_prob = draws / total_matches if total_matches > 0 else 0.0
    away_win_prob = away_wins / total_matches if total_matches > 0 else 0.0

    # Calculate weighted probabilities with recency bias (now returns tuple)
    weighted_home_win, h2h_breakdown_home = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'home_win'
    )

    weighted_draw, h2h_breakdown_draw = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'draw'
    )

    weighted_away_win, h2h_breakdown_away = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'away_win'
    )

    # Combined breakdown
    h2h_breakdown = {
        "home_win": h2h_breakdown_home,
        "draw": h2h_breakdown_draw,
        "away_win": h2h_breakdown_away,
    }

    # Current form analysis (recent matches with valid results only)
    recent_home_wins = sum(1 for m in valid_recent if get_result(m) == 'home_win')
    recent_draws = sum(1 for m in valid_recent if get_result(m) == 'draw')
    recent_away_wins = sum(1 for m in valid_recent if get_result(m) == 'away_win')

    current_form = {
        "recent_matches": len(valid_recent),
        "home_wins": recent_home_wins,
        "draws": recent_draws,
        "away_wins": recent_away_wins,
        "home_win_probability": round(recent_home_wins / len(valid_recent), 4) if valid_recent else 0.0
    }

    # Group by season (using football_season if available)
    by_season = []
    season_key = 'football_season' if all_matches and 'football_season' in all_matches[0] else 'season_year'
    unique_seasons = sorted(set(m.get(season_key) for m in all_matches if m.get(season_key)), reverse=True)

    for year in unique_seasons:
        season_matches = [m for m in all_matches if m.get(season_key) == year]
        season_home_wins = sum(1 for m in season_matches if get_result(m) == 'home_win')
        season_draws = sum(1 for m in season_matches if get_result(m) == 'draw')
        season_away_wins = sum(1 for m in season_matches if get_result(m) == 'away_win')

        by_season.append({
            "season": f"{int(year)}-{int(year)+1}",
            "matches": len(season_matches),
            "home_wins": season_home_wins,
            "draws": season_draws,
            "away_wins": season_away_wins
        })

    # Assess data quality with market-specific thresholds
    data_quality = DataQualityClassifier.assess(total_matches, market="1X2")

    # Team form blending
    form_data = None
    blended_home_win = weighted_home_win
    blended_draw = weighted_draw
    blended_away_win = weighted_away_win

    if blend_with_form and api_client is not None and isinstance(home_team, int) and isinstance(away_team, int):
        try:
            form_data = await _calculate_form_1x2_probability(
                api_client=api_client,
                home_team_id=home_team,
                away_team_id=away_team,
            )

            # Blend H2H with form
            # Weight H2H more when we have more H2H data
            h2h_weight = 0.6 if total_matches >= 8 else 0.4
            form_weight = 1 - h2h_weight

            blended_home_win = round(
                weighted_home_win * h2h_weight + form_data["home_win_probability"] * form_weight,
                4
            )
            blended_draw = round(
                weighted_draw * h2h_weight + form_data["draw_probability"] * form_weight,
                4
            )
            blended_away_win = round(
                weighted_away_win * h2h_weight + form_data["away_win_probability"] * form_weight,
                4
            )

            logger.info(
                f"Blended 1X2: h2h_home={weighted_home_win:.2f}, form_home={form_data['home_win_probability']:.2f}, "
                f"blended_home={blended_home_win:.2f} (h2h_weight={h2h_weight})"
            )
        except Exception as e:
            logger.warning(f"Failed to calculate form 1X2: {e}")
            # Continue with H2H only

    # Calculate confidence with penalties
    # Use the maximum probability as the "predicted" outcome
    max_prob = max(blended_home_win, blended_draw, blended_away_win)
    max_h2h = max(weighted_home_win, weighted_draw, weighted_away_win)
    max_form = None
    if form_data:
        max_form = max(
            form_data["home_win_probability"],
            form_data["draw_probability"],
            form_data["away_win_probability"]
        )

    confidence_data = calculate_final_confidence(
        base_confidence=max_prob,
        h2h_prob=max_h2h,
        form_prob=max_form,
        data_quality=data_quality,
    )

    return {
        "tool": "get_h2h_full_time_result",
        "data": {
            "total_matches": total_matches,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "home_win_probability": round(home_win_prob, 4),
            "draw_probability": round(draw_prob, 4),
            "away_win_probability": round(away_win_prob, 4),
            "weighted_probabilities": {
                "home_win": weighted_home_win,
                "draw": weighted_draw,
                "away_win": weighted_away_win
            },
            "blended_probabilities": {
                "home_win": blended_home_win,
                "draw": blended_draw,
                "away_win": blended_away_win
            },
            "h2h_breakdown": h2h_breakdown,
            "form_data": form_data,
            "confidence": confidence_data,
            "current_form": current_form,
            "by_season": by_season
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
