"""
Halftime and second-half analysis tools.

Provides 5 tools for analyzing halftime results, second-half performance,
and HT/FT combinations.

NOTE: These tools require halftime data in metadata->>'halftime_home_score'
      and metadata->>'halftime_away_score' (DB) or score.halftime (API).
      Tools will gracefully degrade if halftime data is missing.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
IMPROVED (2026-08-29): Updated weighting algorithm with sample guards and breakdown.
"""

from typing import Any
# asyncpg removed (2026-08-20) - database removed
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_h2h_half_time_result(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze head-to-head half-time result record.

    Returns win/draw/loss at halftime with recency-weighted probabilities.
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

    # Filter matches with halftime data (handles both DB and API formats)
    def has_ht_data(m: dict) -> bool:
        # Transformed API format: ht_home_score/ht_away_score at top level
        if m.get('ht_home_score') is not None and m.get('ht_away_score') is not None:
            return True
        # Raw API format: score.halftime.home/away
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return ht.get('home') is not None and ht.get('away') is not None
        # DB format: metadata->halftime_home_score/halftime_away_score
        if m.get('metadata'):
            return ('halftime_home_score' in m['metadata'] and
                    'halftime_away_score' in m['metadata'])
        return False

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_h2h_half_time_result",
            "data": {
                "total_matches": 0,
                "home_leading_ht": 0,
                "draw_ht": 0,
                "away_leading_ht": 0,
                "home_leading_ht_probability": 0.0,
                "draw_ht_probability": 0.0,
                "away_leading_ht_probability": 0.0,
                "weighted_probabilities": {"home_leading_ht": 0.0, "draw_ht": 0.0, "away_leading_ht": 0.0},
                "h2h_breakdown": {},
                "current_form": {"recent_matches": 0, "home_leading_ht": 0, "home_leading_ht_probability": 0.0}
            },
            "metadata": {"seasons_analyzed": 0, "halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores(match: dict) -> tuple[int, int]:
        """Get halftime scores from match (handles both DB and API formats)."""
        # Transformed API format
        if match.get('ht_home_score') is not None:
            return (match.get('ht_home_score', 0) or 0, match.get('ht_away_score', 0) or 0)
        # Raw API format
        if match.get('score') and match['score'].get('halftime'):
            ht = match['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if match.get('metadata'):
            return (
                int(match['metadata'].get('halftime_home_score', 0)),
                int(match['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def get_ht_result(match: dict) -> str:
        """Get halftime result from home team perspective."""
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier
        ht_home, ht_away = get_ht_scores(match)

        if is_home:
            if ht_home > ht_away:
                return 'home_leading'
            elif ht_home < ht_away:
                return 'away_leading'
            else:
                return 'draw'
        else:
            if ht_away > ht_home:
                return 'home_leading'
            elif ht_away < ht_home:
                return 'away_leading'
            else:
                return 'draw'

    total = len(matches_with_ht)
    home_leading = sum(1 for m in matches_with_ht if get_ht_result(m) == 'home_leading')
    draw = sum(1 for m in matches_with_ht if get_ht_result(m) == 'draw')
    away_leading = sum(1 for m in matches_with_ht if get_ht_result(m) == 'away_leading')

    # Partition with HT data for weighting
    recent_ht = [m for m in recent if has_ht_data(m)]
    last_season_ht = [m for m in last_season if has_ht_data(m)]
    older_ht = [m for m in older if has_ht_data(m)]

    # Updated to use tuple return
    weighted_home, breakdown_home = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_ht_result(m) == 'home_leading'
    )

    weighted_draw, breakdown_draw = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_ht_result(m) == 'draw'
    )

    weighted_away, breakdown_away = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_ht_result(m) == 'away_leading'
    )

    h2h_breakdown = {
        "home_leading_ht": breakdown_home,
        "draw_ht": breakdown_draw,
        "away_leading_ht": breakdown_away,
    }

    # Current form
    recent_home_leading = sum(1 for m in recent_ht if get_ht_result(m) == 'home_leading')

    # Data quality based on HT coverage with market-specific thresholds
    ht_coverage = (len(matches_with_ht) / len(all_matches)) if all_matches else 0.0
    data_quality = DataQualityClassifier.assess(len(matches_with_ht), market="HT_1X2")

    return {
        "tool": "get_h2h_half_time_result",
        "data": {
            "total_matches": total,
            "home_leading_ht": home_leading,
            "draw_ht": draw,
            "away_leading_ht": away_leading,
            "home_leading_ht_probability": round(home_leading / total, 4) if total > 0 else 0.0,
            "draw_ht_probability": round(draw / total, 4) if total > 0 else 0.0,
            "away_leading_ht_probability": round(away_leading / total, 4) if total > 0 else 0.0,
            "weighted_probabilities": {
                "home_leading_ht": weighted_home,
                "draw_ht": weighted_draw,
                "away_leading_ht": weighted_away
            },
            "h2h_breakdown": h2h_breakdown,
            "current_form": {
                "recent_matches": len(recent_ht),
                "home_leading_ht": recent_home_leading,
                "home_leading_ht_probability": round(recent_home_leading / len(recent_ht), 4) if recent_ht else 0.0
            }
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(ht_coverage, 2),
            "data_quality": data_quality,
            "current_football_season": matches_data.get("current_football_season"),
        }
    }


async def get_h2h_2nd_half_result(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze head-to-head second-half result record.

    Calculates second-half goals: FT_score - HT_score
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

    # Filter matches with halftime data (handles both DB and API formats)
    def has_ht_data(m: dict) -> bool:
        # Transformed API format: ht_home_score/ht_away_score at top level
        if m.get('ht_home_score') is not None and m.get('ht_away_score') is not None:
            return True
        # Raw API format: score.halftime.home/away
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return ht.get('home') is not None and ht.get('away') is not None
        # DB format: metadata->halftime_home_score/halftime_away_score
        if m.get('metadata'):
            return ('halftime_home_score' in m['metadata'] and
                    'halftime_away_score' in m['metadata'])
        return False

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_h2h_2nd_half_result",
            "data": {
                "total_matches": 0,
                "home_wins_2h": 0,
                "draws_2h": 0,
                "away_wins_2h": 0,
                "home_win_2h_probability": 0.0,
                "draw_2h_probability": 0.0,
                "away_win_2h_probability": 0.0,
                "weighted_probabilities": {"home_win_2h": 0.0, "draw_2h": 0.0, "away_win_2h": 0.0},
                "h2h_breakdown": {}
            },
            "metadata": {"seasons_analyzed": 0, "halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores(match: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if match.get('ht_home_score') is not None:
            return (match.get('ht_home_score', 0) or 0, match.get('ht_away_score', 0) or 0)
        # Raw API format
        if match.get('score') and match['score'].get('halftime'):
            ht = match['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if match.get('metadata'):
            return (
                int(match['metadata'].get('halftime_home_score', 0)),
                int(match['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def get_2h_result(match: dict) -> str:
        """Calculate second-half result from home team perspective."""
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier

        ft_home = match.get('home_score', 0) or 0
        ft_away = match.get('away_score', 0) or 0
        ht_home, ht_away = get_ht_scores(match)

        # Second half goals
        goals_2h_home = ft_home - ht_home
        goals_2h_away = ft_away - ht_away

        if is_home:
            if goals_2h_home > goals_2h_away:
                return 'home_win'
            elif goals_2h_home < goals_2h_away:
                return 'away_win'
            else:
                return 'draw'
        else:
            if goals_2h_away > goals_2h_home:
                return 'home_win'
            elif goals_2h_away < goals_2h_home:
                return 'away_win'
            else:
                return 'draw'

    total = len(matches_with_ht)
    home_wins = sum(1 for m in matches_with_ht if get_2h_result(m) == 'home_win')
    draws = sum(1 for m in matches_with_ht if get_2h_result(m) == 'draw')
    away_wins = sum(1 for m in matches_with_ht if get_2h_result(m) == 'away_win')

    # Partition
    recent_ht = [m for m in recent if has_ht_data(m)]
    last_season_ht = [m for m in last_season if has_ht_data(m)]
    older_ht = [m for m in older if has_ht_data(m)]

    # Updated to use tuple return
    weighted_home, breakdown_home = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_2h_result(m) == 'home_win'
    )

    weighted_draw, breakdown_draw = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_2h_result(m) == 'draw'
    )

    weighted_away, breakdown_away = RecencyWeightCalculator.calculate(
        recent_ht, last_season_ht, older_ht,
        lambda m: get_2h_result(m) == 'away_win'
    )

    h2h_breakdown = {
        "home_win_2h": breakdown_home,
        "draw_2h": breakdown_draw,
        "away_win_2h": breakdown_away,
    }

    ht_coverage = (len(matches_with_ht) / len(all_matches)) if all_matches else 0.0
    data_quality = DataQualityClassifier.assess(len(matches_with_ht), market="HT_1X2")

    return {
        "tool": "get_h2h_2nd_half_result",
        "data": {
            "total_matches": total,
            "home_wins_2h": home_wins,
            "draws_2h": draws,
            "away_wins_2h": away_wins,
            "home_win_2h_probability": round(home_wins / total, 4) if total > 0 else 0.0,
            "draw_2h_probability": round(draws / total, 4) if total > 0 else 0.0,
            "away_win_2h_probability": round(away_wins / total, 4) if total > 0 else 0.0,
            "weighted_probabilities": {
                "home_win_2h": weighted_home,
                "draw_2h": weighted_draw,
                "away_win_2h": weighted_away
            },
            "h2h_breakdown": h2h_breakdown
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(ht_coverage, 2),
            "data_quality": data_quality,
            "current_football_season": matches_data.get("current_football_season"),
        }
    }


async def get_ht_ft_outcome(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze halftime/fulltime result combinations.

    Returns all 9 possible combinations (HT: Home/Draw/Away × FT: Home/Draw/Away).
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

    def has_ht_data(m: dict) -> bool:
        # Transformed API format: ht_home_score/ht_away_score at top level
        if m.get('ht_home_score') is not None and m.get('ht_away_score') is not None:
            return True
        # Raw API format: score.halftime.home/away
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return ht.get('home') is not None and ht.get('away') is not None
        # DB format: metadata->halftime_home_score/halftime_away_score
        if m.get('metadata'):
            return ('halftime_home_score' in m['metadata'] and
                    'halftime_away_score' in m['metadata'])
        return False

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_ht_ft_outcome",
            "data": {"total_matches": 0, "outcomes": [], "most_likely": None},
            "metadata": {"seasons_analyzed": 0, "halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores(match: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if match.get('ht_home_score') is not None:
            return (match.get('ht_home_score', 0) or 0, match.get('ht_away_score', 0) or 0)
        # Raw API format
        if match.get('score') and match['score'].get('halftime'):
            ht = match['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if match.get('metadata'):
            return (
                int(match['metadata'].get('halftime_home_score', 0)),
                int(match['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def get_ht_ft_combo(match: dict) -> tuple[str, str]:
        """Get (HT_result, FT_result) combination."""
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier

        # HT result
        ht_home, ht_away = get_ht_scores(match)

        # FT result
        ft_home = match.get('home_score', 0) or 0
        ft_away = match.get('away_score', 0) or 0

        if is_home:
            ht = 'Home' if ht_home > ht_away else ('Draw' if ht_home == ht_away else 'Away')
            ft = 'Home' if ft_home > ft_away else ('Draw' if ft_home == ft_away else 'Away')
        else:
            # Flip perspective
            ht = 'Home' if ht_away > ht_home else ('Draw' if ht_away == ht_home else 'Away')
            ft = 'Home' if ft_away > ft_home else ('Draw' if ft_away == ft_home else 'Away')

        return (ht, ft)

    # Count all 9 combinations
    combos = {}
    for m in matches_with_ht:
        combo = get_ht_ft_combo(m)
        key = f"{combo[0]}/{combo[1]}"
        combos[key] = combos.get(key, 0) + 1

    total = len(matches_with_ht)

    outcomes = [
        {
            "halftime": ht,
            "fulltime": ft,
            "count": combos.get(f"{ht}/{ft}", 0),
            "probability": round(combos.get(f"{ht}/{ft}", 0) / total, 4) if total > 0 else 0.0
        }
        for ht in ["Home", "Draw", "Away"]
        for ft in ["Home", "Draw", "Away"]
    ]

    # Find most likely
    most_likely_combo = max(outcomes, key=lambda x: x["probability"]) if outcomes else None

    return {
        "tool": "get_ht_ft_outcome",
        "data": {
            "total_matches": total,
            "outcomes": sorted(outcomes, key=lambda x: x["probability"], reverse=True),
            "most_likely": most_likely_combo
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total, market="HT_1X2"),
            "current_football_season": matches_data.get("current_football_season"),
        }
    }


async def get_half_time_goals(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Analyze halftime goals scored by each team."""
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

    def has_ht_data(m: dict) -> bool:
        # Transformed API format: ht_home_score/ht_away_score at top level
        if m.get('ht_home_score') is not None and m.get('ht_away_score') is not None:
            return True
        # Raw API format: score.halftime.home/away
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return ht.get('home') is not None and ht.get('away') is not None
        # DB format: metadata->halftime_home_score/halftime_away_score
        if m.get('metadata'):
            return ('halftime_home_score' in m['metadata'] and
                    'halftime_away_score' in m['metadata'])
        return False

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_half_time_goals",
            "data": {"total_matches": 0, "home_ht_goals": {}, "away_ht_goals": {}, "total_ht_goals": {}},
            "metadata": {"seasons_analyzed": 0, "halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores_raw(match: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if match.get('ht_home_score') is not None:
            return (match.get('ht_home_score', 0) or 0, match.get('ht_away_score', 0) or 0)
        # Raw API format
        if match.get('score') and match['score'].get('halftime'):
            ht = match['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if match.get('metadata'):
            return (
                int(match['metadata'].get('halftime_home_score', 0)),
                int(match['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def get_ht_goals(match: dict) -> tuple[int, int]:
        """Get (home_ht_goals, away_ht_goals) from actual team perspective."""
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier
        ht_home_actual, ht_away_actual = get_ht_scores_raw(match)

        if is_home:
            return (ht_home_actual, ht_away_actual)
        else:
            return (ht_away_actual, ht_home_actual)

    total = len(matches_with_ht)

    # Home team HT goals
    home_ht_total = sum(get_ht_goals(m)[0] for m in matches_with_ht)
    home_ht_avg = home_ht_total / total if total > 0 else 0.0

    home_0_goals = sum(1 for m in matches_with_ht if get_ht_goals(m)[0] == 0)
    home_1_goal = sum(1 for m in matches_with_ht if get_ht_goals(m)[0] == 1)
    home_2plus_goals = sum(1 for m in matches_with_ht if get_ht_goals(m)[0] >= 2)

    # Away team HT goals
    away_ht_total = sum(get_ht_goals(m)[1] for m in matches_with_ht)
    away_ht_avg = away_ht_total / total if total > 0 else 0.0

    away_0_goals = sum(1 for m in matches_with_ht if get_ht_goals(m)[1] == 0)
    away_1_goal = sum(1 for m in matches_with_ht if get_ht_goals(m)[1] == 1)
    away_2plus_goals = sum(1 for m in matches_with_ht if get_ht_goals(m)[1] >= 2)

    # Total HT goals
    total_ht_goals = home_ht_total + away_ht_total
    total_ht_avg = total_ht_goals / total if total > 0 else 0.0

    over_1_5_ht = sum(1 for m in matches_with_ht if (get_ht_goals(m)[0] + get_ht_goals(m)[1]) > 1.5)

    return {
        "tool": "get_half_time_goals",
        "data": {
            "total_matches": total,
            "home_ht_goals": {
                "total": home_ht_total,
                "average": round(home_ht_avg, 2),
                "probabilities": {
                    "0_goals": round(home_0_goals / total, 4) if total > 0 else 0.0,
                    "1_goal": round(home_1_goal / total, 4) if total > 0 else 0.0,
                    "2+_goals": round(home_2plus_goals / total, 4) if total > 0 else 0.0
                },
                "over_0.5": round((total - home_0_goals) / total, 4) if total > 0 else 0.0
            },
            "away_ht_goals": {
                "total": away_ht_total,
                "average": round(away_ht_avg, 2),
                "probabilities": {
                    "0_goals": round(away_0_goals / total, 4) if total > 0 else 0.0,
                    "1_goal": round(away_1_goal / total, 4) if total > 0 else 0.0,
                    "2+_goals": round(away_2plus_goals / total, 4) if total > 0 else 0.0
                },
                "over_0.5": round((total - away_0_goals) / total, 4) if total > 0 else 0.0
            },
            "total_ht_goals": {
                "average": round(total_ht_avg, 2),
                "over_1.5": round(over_1_5_ht / total, 4) if total > 0 else 0.0
            }
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total, market="HT_OU1.5"),
            "current_football_season": matches_data.get("current_football_season"),
        }
    }


async def get_2nd_half_goals(
    pool: Any,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Analyze second-half goals scored by each team (FT - HT)."""
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

    def has_ht_data(m: dict) -> bool:
        # Transformed API format: ht_home_score/ht_away_score at top level
        if m.get('ht_home_score') is not None and m.get('ht_away_score') is not None:
            return True
        # Raw API format: score.halftime.home/away
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return ht.get('home') is not None and ht.get('away') is not None
        # DB format: metadata->halftime_home_score/halftime_away_score
        if m.get('metadata'):
            return ('halftime_home_score' in m['metadata'] and
                    'halftime_away_score' in m['metadata'])
        return False

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_2nd_half_goals",
            "data": {"total_matches": 0, "home_2h_goals": {}, "away_2h_goals": {}, "total_2h_goals": {}},
            "metadata": {"seasons_analyzed": 0, "halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores_raw(match: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if match.get('ht_home_score') is not None:
            return (match.get('ht_home_score', 0) or 0, match.get('ht_away_score', 0) or 0)
        # Raw API format
        if match.get('score') and match['score'].get('halftime'):
            ht = match['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if match.get('metadata'):
            return (
                int(match['metadata'].get('halftime_home_score', 0)),
                int(match['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def get_2h_goals(match: dict) -> tuple[int, int]:
        """Get (home_2h_goals, away_2h_goals)."""
        if isinstance(home_team_identifier, int):
            is_home = match.get('home_team_id') == home_team_identifier
        else:
            is_home = match.get('home_team') == home_team_identifier

        ft_home_actual = match.get('home_score', 0) or 0
        ft_away_actual = match.get('away_score', 0) or 0
        ht_home_actual, ht_away_actual = get_ht_scores_raw(match)

        goals_2h_home_actual = ft_home_actual - ht_home_actual
        goals_2h_away_actual = ft_away_actual - ht_away_actual

        if is_home:
            return (goals_2h_home_actual, goals_2h_away_actual)
        else:
            return (goals_2h_away_actual, goals_2h_home_actual)

    total = len(matches_with_ht)

    # Home team 2H goals
    home_2h_total = sum(get_2h_goals(m)[0] for m in matches_with_ht)
    home_2h_avg = home_2h_total / total if total > 0 else 0.0

    # Away team 2H goals
    away_2h_total = sum(get_2h_goals(m)[1] for m in matches_with_ht)
    away_2h_avg = away_2h_total / total if total > 0 else 0.0

    # Total 2H goals
    total_2h_goals = home_2h_total + away_2h_total
    total_2h_avg = total_2h_goals / total if total > 0 else 0.0

    over_1_5_2h = sum(1 for m in matches_with_ht if (get_2h_goals(m)[0] + get_2h_goals(m)[1]) > 1.5)

    return {
        "tool": "get_2nd_half_goals",
        "data": {
            "total_matches": total,
            "home_2h_goals": {
                "total": home_2h_total,
                "average": round(home_2h_avg, 2)
            },
            "away_2h_goals": {
                "total": away_2h_total,
                "average": round(away_2h_avg, 2)
            },
            "total_2h_goals": {
                "average": round(total_2h_avg, 2),
                "over_1.5": round(over_1_5_2h / total, 4) if total > 0 else 0.0
            }
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total, market="HT_OU1.5"),
            "current_football_season": matches_data.get("current_football_season"),
        }
    }
