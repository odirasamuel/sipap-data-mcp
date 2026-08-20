"""
Head-to-head full-time result analysis tool.

Analyzes win/draw/loss record between two teams with recency weighting.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any
import asyncpg
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_h2h_full_time_result(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze head-to-head full-time result record.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        home_team: Home team name (for DB) or API-Football team ID (for API)
        away_team: Away team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        seasons_back: Historical seasons to analyze (default: 6)
        current_form_matches: Recent matches for current form (default: 10)
        api_client: Optional API-Football client (preferred)

    Returns:
        {
            "tool": "get_h2h_full_time_result",
            "data": {
                "total_matches": int,
                "home_wins": int,
                "draws": int,
                "away_wins": int,
                "home_win_probability": float,
                "draw_probability": float,
                "away_win_probability": float,
                "weighted_probabilities": {
                    "home_win": float,
                    "draw": float,
                    "away_win": float
                },
                "current_form": {
                    "recent_matches": int,
                    "home_wins": int,
                    "draws": int,
                    "away_wins": int,
                    "home_win_probability": float
                },
                "by_season": [
                    {
                        "season": str,
                        "matches": int,
                        "home_wins": int,
                        "draws": int,
                        "away_wins": int
                    },
                    ...
                ]
            },
            "metadata": {
                "seasons_analyzed": int,
                "earliest_match": str,
                "latest_match": str,
                "data_quality": "high" | "medium" | "low"
            }
        }

    Example:
        >>> result = await get_h2h_full_time_result(
        ...     pool, "Arsenal", "Chelsea", "Premier League"
        ... )
        >>> print(result["data"]["weighted_probabilities"]["home_win"])
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
                "data_quality": "low"
            }
        }

    # Helper to determine result from home team perspective
    def get_result(match: dict[str, Any]) -> str:
        """
        Returns 'home_win', 'draw', or 'away_win' from home team perspective.

        Accounts for reversed fixtures (home_team might be away in this match).
        """
        # Check if our "home team" is actually playing at home in this match
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier

        home_score = match['home_score']
        away_score = match['away_score']

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

    # Count results in all matches
    total_matches = len(all_matches)
    home_wins = sum(1 for m in all_matches if get_result(m) == 'home_win')
    draws = sum(1 for m in all_matches if get_result(m) == 'draw')
    away_wins = sum(1 for m in all_matches if get_result(m) == 'away_win')

    # Calculate base probabilities
    home_win_prob = home_wins / total_matches if total_matches > 0 else 0.0
    draw_prob = draws / total_matches if total_matches > 0 else 0.0
    away_win_prob = away_wins / total_matches if total_matches > 0 else 0.0

    # Calculate weighted probabilities with recency bias
    weighted_home_win = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'home_win'
    )

    weighted_draw = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'draw'
    )

    weighted_away_win = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=lambda m: get_result(m) == 'away_win'
    )

    # Current form analysis (recent matches only)
    recent_home_wins = sum(1 for m in recent if get_result(m) == 'home_win')
    recent_draws = sum(1 for m in recent if get_result(m) == 'draw')
    recent_away_wins = sum(1 for m in recent if get_result(m) == 'away_win')

    current_form = {
        "recent_matches": len(recent),
        "home_wins": recent_home_wins,
        "draws": recent_draws,
        "away_wins": recent_away_wins,
        "home_win_probability": round(recent_home_wins / len(recent), 4) if recent else 0.0
    }

    # Group by season
    by_season = []
    unique_seasons = sorted(set(m['season_year'] for m in all_matches), reverse=True)

    for year in unique_seasons:
        season_matches = [m for m in all_matches if m['season_year'] == year]
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

    # Assess data quality
    data_quality = DataQualityClassifier.assess(total_matches)

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
            "data_quality": data_quality
        }
    }
