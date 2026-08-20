"""
Specialized analysis tools.

Provides 5 specialized tools for advanced betting markets:
- Goal range analysis (percentiles)
- Half dominance analysis (which half each team tends to win)
- Team to score probabilities

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any
import asyncpg
from sipap_data_mcp.api.football_client import APIFootballClient
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_total_goals_range(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Determine the typical goal range for this fixture.

    Returns percentiles (25th, 50th, 75th) and most common range.
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
            "tool": "get_total_goals_range",
            "data": {"total_matches": 0, "most_common_range": None, "percentiles": {}, "weighted_probabilities": {}},
            "metadata": {"data_quality": "low"}
        }

    def get_total(m: dict) -> int:
        home_score = m.get('home_score', 0) or 0
        away_score = m.get('away_score', 0) or 0
        return home_score + away_score

    total_goals = sorted([get_total(m) for m in all_matches])

    # Calculate percentiles
    p25_idx = int(len(total_goals) * 0.25)
    p50_idx = int(len(total_goals) * 0.50)
    p75_idx = int(len(total_goals) * 0.75)

    percentiles = {
        "25th": total_goals[p25_idx],
        "50th": total_goals[p50_idx],  # Median
        "75th": total_goals[p75_idx]
    }

    # Determine most common range (group by 0-1, 2-3, 4-5, 6+)
    range_0_1 = sum(1 for g in total_goals if 0 <= g <= 1)
    range_2_3 = sum(1 for g in total_goals if 2 <= g <= 3)
    range_4_5 = sum(1 for g in total_goals if 4 <= g <= 5)
    range_6_plus = sum(1 for g in total_goals if g >= 6)

    ranges = {
        "0-1": range_0_1,
        "2-3": range_2_3,
        "4-5": range_4_5,
        "6+": range_6_plus
    }

    most_common_key = max(ranges, key=ranges.get)
    most_common_range = {
        "range": most_common_key,
        "occurrences": ranges[most_common_key],
        "probability": round(ranges[most_common_key] / len(all_matches), 4)
    }

    # Calculate weighted probabilities for each range with recency bias
    weighted_range_probs = {}
    for range_key in ranges:
        low, high = (0, 1) if range_key == "0-1" else (2, 3) if range_key == "2-3" else (4, 5) if range_key == "4-5" else (6, 100)

        def in_range(m: dict) -> bool:
            total = get_total(m)
            if range_key == "6+":
                return total >= low
            return low <= total <= high

        weighted_prob = RecencyWeightCalculator.calculate(
            recent_matches=recent,
            last_season=last_season,
            older_seasons=older,
            condition_fn=in_range
        )
        weighted_range_probs[range_key] = weighted_prob

    return {
        "tool": "get_total_goals_range",
        "data": {
            "total_matches": len(all_matches),
            "goal_distribution": ranges,
            "most_common_range": most_common_range,
            "percentiles": percentiles,
            "weighted_probabilities": weighted_range_probs  # Recency weighted (50/30/20) for each range
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(len(all_matches))
        }
    }


async def get_home_either_half_outcome(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Determine which half the home team tends to win (1H vs 2H tendency).

    Requires halftime data.
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

    # Get partitioned matches with halftime data
    recent_with_ht = [m for m in matches_data["recent_matches"] if has_ht_data(m)]
    last_season_with_ht = [m for m in matches_data["last_season"] if has_ht_data(m)]
    older_with_ht = [m for m in matches_data["older_seasons"] if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_home_either_half_outcome",
            "data": {"total_matches": 0, "tendency": None, "probabilities": {}, "weighted_probabilities": {}},
            "metadata": {"halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores(m: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if m.get('ht_home_score') is not None:
            return (m.get('ht_home_score', 0) or 0, m.get('ht_away_score', 0) or 0)
        # Raw API format
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if m.get('metadata'):
            return (
                int(m['metadata'].get('halftime_home_score', 0)),
                int(m['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def check_half_wins(m: dict) -> dict:
        """Check which halves home team won from their perspective."""
        if isinstance(home_team_identifier, int):
            is_home_actual = m.get('home_team_id') == home_team_identifier
        else:
            is_home_actual = m.get('home_team') == home_team_identifier

        ht_home, ht_away = get_ht_scores(m)
        ft_home = m.get('home_score', 0) or 0
        ft_away = m.get('away_score', 0) or 0

        # Second half goals
        goals_2h_home = ft_home - ht_home
        goals_2h_away = ft_away - ht_away

        if is_home_actual:
            first_half_win = ht_home > ht_away
            second_half_win = goals_2h_home > goals_2h_away
        else:
            first_half_win = ht_away > ht_home
            second_half_win = goals_2h_away > goals_2h_home

        return {"first_half_win": first_half_win, "second_half_win": second_half_win}

    first_half_wins = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"])
    second_half_wins = sum(1 for m in matches_with_ht if check_half_wins(m)["second_half_win"])
    both_halves = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"] and check_half_wins(m)["second_half_win"])
    either_half = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"] or check_half_wins(m)["second_half_win"])

    total = len(matches_with_ht)

    tendency = "second_half" if second_half_wins > first_half_wins else "first_half"

    # Calculate weighted probabilities with recency bias
    weighted_win_first_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"]
    )

    weighted_win_second_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["second_half_win"]
    )

    weighted_win_either_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"] or check_half_wins(m)["second_half_win"]
    )

    weighted_win_both_halves = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"] and check_half_wins(m)["second_half_win"]
    )

    return {
        "tool": "get_home_either_half_outcome",
        "data": {
            "total_matches": total,
            "first_half_wins": first_half_wins,
            "second_half_wins": second_half_wins,
            "probabilities": {
                "win_first_half": round(first_half_wins / total, 4) if total > 0 else 0.0,
                "win_second_half": round(second_half_wins / total, 4) if total > 0 else 0.0,
                "win_either_half": round(either_half / total, 4) if total > 0 else 0.0,
                "win_both_halves": round(both_halves / total, 4) if total > 0 else 0.0
            },
            "weighted_probabilities": {  # Recency weighted (50/30/20)
                "win_first_half": weighted_win_first_half,
                "win_second_half": weighted_win_second_half,
                "win_either_half": weighted_win_either_half,
                "win_both_halves": weighted_win_both_halves
            },
            "tendency": tendency
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_away_either_half_outcome(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Determine which half the away team tends to win (1H vs 2H tendency).

    Requires halftime data. Gracefully degrades if halftime data is missing.
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

    # Get partitioned matches with halftime data
    recent_with_ht = [m for m in matches_data["recent_matches"] if has_ht_data(m)]
    last_season_with_ht = [m for m in matches_data["last_season"] if has_ht_data(m)]
    older_with_ht = [m for m in matches_data["older_seasons"] if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_away_either_half_outcome",
            "data": {"total_matches": 0, "tendency": None, "probabilities": {}, "weighted_probabilities": {}},
            "metadata": {"halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_scores(m: dict) -> tuple[int, int]:
        """Get halftime scores (handles both DB and API formats)."""
        # Transformed API format
        if m.get('ht_home_score') is not None:
            return (m.get('ht_home_score', 0) or 0, m.get('ht_away_score', 0) or 0)
        # Raw API format
        if m.get('score') and m['score'].get('halftime'):
            ht = m['score']['halftime']
            return (ht.get('home', 0) or 0, ht.get('away', 0) or 0)
        # DB format
        if m.get('metadata'):
            return (
                int(m['metadata'].get('halftime_home_score', 0)),
                int(m['metadata'].get('halftime_away_score', 0))
            )
        return (0, 0)

    def check_half_wins(m: dict) -> dict:
        """Check which halves away team won from their perspective."""
        if isinstance(home_team_identifier, int):
            is_home_actual = m.get('home_team_id') == home_team_identifier
        else:
            is_home_actual = m.get('home_team') == home_team_identifier

        ht_home, ht_away = get_ht_scores(m)
        ft_home = m.get('home_score', 0) or 0
        ft_away = m.get('away_score', 0) or 0

        # Second half goals
        goals_2h_home = ft_home - ht_home
        goals_2h_away = ft_away - ht_away

        if is_home_actual:
            # Away team is the actual away team
            first_half_win = ht_away > ht_home
            second_half_win = goals_2h_away > goals_2h_home
        else:
            # Away team is the actual home team (reversed fixture)
            first_half_win = ht_home > ht_away
            second_half_win = goals_2h_home > goals_2h_away

        return {"first_half_win": first_half_win, "second_half_win": second_half_win}

    first_half_wins = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"])
    second_half_wins = sum(1 for m in matches_with_ht if check_half_wins(m)["second_half_win"])
    both_halves = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"] and check_half_wins(m)["second_half_win"])
    either_half = sum(1 for m in matches_with_ht if check_half_wins(m)["first_half_win"] or check_half_wins(m)["second_half_win"])

    total = len(matches_with_ht)

    tendency = "second_half" if second_half_wins > first_half_wins else "first_half"

    # Calculate weighted probabilities with recency bias
    weighted_win_first_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"]
    )

    weighted_win_second_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["second_half_win"]
    )

    weighted_win_either_half = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"] or check_half_wins(m)["second_half_win"]
    )

    weighted_win_both_halves = RecencyWeightCalculator.calculate(
        recent_matches=recent_with_ht,
        last_season=last_season_with_ht,
        older_seasons=older_with_ht,
        condition_fn=lambda m: check_half_wins(m)["first_half_win"] and check_half_wins(m)["second_half_win"]
    )

    return {
        "tool": "get_away_either_half_outcome",
        "data": {
            "total_matches": total,
            "first_half_wins": first_half_wins,
            "second_half_wins": second_half_wins,
            "probabilities": {
                "win_first_half": round(first_half_wins / total, 4) if total > 0 else 0.0,
                "win_second_half": round(second_half_wins / total, 4) if total > 0 else 0.0,
                "win_either_half": round(either_half / total, 4) if total > 0 else 0.0,
                "win_both_halves": round(both_halves / total, 4) if total > 0 else 0.0
            },
            "weighted_probabilities": {  # Recency weighted (50/30/20)
                "win_first_half": weighted_win_first_half,
                "win_second_half": weighted_win_second_half,
                "win_either_half": weighted_win_either_half,
                "win_both_halves": weighted_win_both_halves
            },
            "tendency": tendency
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_home_to_score(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Probability that home team scores at least one goal."""
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

    if not all_matches:
        return {
            "tool": "get_home_to_score",
            "data": {"total_matches": 0, "home_to_score_probability": 0.0, "weighted_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def home_scores(m: dict) -> bool:
        if isinstance(home_team_identifier, int):
            is_home_actual = m.get('home_team_id') == home_team_identifier
        else:
            is_home_actual = m.get('home_team') == home_team_identifier
        home_score = m.get('home_score', 0) or 0
        away_score = m.get('away_score', 0) or 0
        if is_home_actual:
            return home_score > 0
        else:
            return away_score > 0

    home_scored = sum(1 for m in all_matches if home_scores(m))
    total = len(all_matches)

    # Calculate weighted probability with recency bias
    weighted_prob = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=home_scores
    )

    return {
        "tool": "get_home_to_score",
        "data": {
            "total_matches": total,
            "home_scored": home_scored,
            "home_blanked": total - home_scored,
            "home_to_score_probability": round(home_scored / total, 4) if total > 0 else 0.0,
            "weighted_probability": weighted_prob  # Recency weighted (50/30/20)
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_away_to_score(
    pool: asyncpg.Pool | None,
    home_team: str | int,
    away_team: str | int,
    league: str | int,
    seasons_back: int = 6,
    current_form_matches: int = 10,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Probability that away team scores at least one goal."""
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

    if not all_matches:
        return {
            "tool": "get_away_to_score",
            "data": {"total_matches": 0, "away_to_score_probability": 0.0, "weighted_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def away_scores(m: dict) -> bool:
        if isinstance(home_team_identifier, int):
            is_home_actual = m.get('home_team_id') == home_team_identifier
        else:
            is_home_actual = m.get('home_team') == home_team_identifier
        home_score = m.get('home_score', 0) or 0
        away_score = m.get('away_score', 0) or 0
        if is_home_actual:
            return away_score > 0
        else:
            return home_score > 0

    away_scored = sum(1 for m in all_matches if away_scores(m))
    total = len(all_matches)

    # Calculate weighted probability with recency bias
    weighted_prob = RecencyWeightCalculator.calculate(
        recent_matches=recent,
        last_season=last_season,
        older_seasons=older,
        condition_fn=away_scores
    )

    return {
        "tool": "get_away_to_score",
        "data": {
            "total_matches": total,
            "away_scored": away_scored,
            "away_blanked": total - away_scored,
            "away_to_score_probability": round(away_scored / total, 4) if total > 0 else 0.0,
            "weighted_probability": weighted_prob  # Recency weighted (50/30/20)
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }
