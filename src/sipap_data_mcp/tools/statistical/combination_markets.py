"""
Combination market analysis tools.

Implements 8 tools for analyzing combination bets using OR and AND logic:
- Double chance (Win OR Draw)
- OR combinations (Win OR Goals, Win OR BTS, BTS OR Goals)
- AND combinations (Win AND Goals, Win AND BTS, No Defeat AND Goals)
- Avoidance markets (Avoid HT/2H defeat)
"""

from typing import Any
import asyncpg
from .base import BaseStatisticalTool, RecencyWeightCalculator, DataQualityClassifier


async def get_double_chance(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Analyze probability of not losing (Win OR Draw).

    Args:
        perspective: "home" or "away" - which team's perspective
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]
    recent = matches_data["recent_matches"]
    last_season = matches_data["last_season"]
    older = matches_data["older_seasons"]

    if not all_matches:
        return {
            "tool": "get_double_chance",
            "data": {"total_matches": 0, "perspective": perspective, "double_chance_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def get_result(m: dict) -> str:
        is_home = m['home_team'] == home_team
        if is_home:
            if m['home_score'] > m['away_score']:
                return 'home_win'
            elif m['home_score'] < m['away_score']:
                return 'away_win'
            else:
                return 'draw'
        else:
            if m['away_score'] > m['home_score']:
                return 'home_win'
            elif m['away_score'] < m['home_score']:
                return 'away_win'
            else:
                return 'draw'

    total = len(all_matches)
    home_wins = sum(1 for m in all_matches if get_result(m) == 'home_win')
    draws = sum(1 for m in all_matches if get_result(m) == 'draw')
    away_wins = sum(1 for m in all_matches if get_result(m) == 'away_win')

    if perspective == "home":
        dc_count = home_wins + draws  # Home win OR Draw
    else:
        dc_count = away_wins + draws  # Away win OR Draw

    dc_prob = dc_count / total if total > 0 else 0.0

    # Weighted probability
    if perspective == "home":
        weighted = RecencyWeightCalculator.calculate(
            recent, last_season, older,
            lambda m: get_result(m) in ['home_win', 'draw']
        )
    else:
        weighted = RecencyWeightCalculator.calculate(
            recent, last_season, older,
            lambda m: get_result(m) in ['away_win', 'draw']
        )

    return {
        "tool": "get_double_chance",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "outcomes": {"home_win": home_wins, "draw": draws, "away_win": away_wins},
            "double_chance_count": dc_count,
            "double_chance_probability": round(dc_prob, 4),
            "weighted_probability": weighted
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_win_or_total_goals(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    goals_threshold: float = 2.5,
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Team wins OR fixture produces X+ goals (OR logic).

    Formula: P(A OR B) = P(A) + P(B) - P(A AND B)
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_win_or_total_goals",
            "data": {"total_matches": 0, "or_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def team_wins(m: dict) -> bool:
        is_home = m['home_team'] == home_team
        if perspective == "home":
            if is_home:
                return m['home_score'] > m['away_score']
            else:
                return m['away_score'] > m['home_score']
        else:
            if is_home:
                return m['home_score'] < m['away_score']
            else:
                return m['away_score'] < m['home_score']

    def over_goals(m: dict) -> bool:
        return (m['home_score'] + m['away_score']) > goals_threshold

    total = len(all_matches)
    win_only = sum(1 for m in all_matches if team_wins(m) and not over_goals(m))
    goals_only = sum(1 for m in all_matches if over_goals(m) and not team_wins(m))
    both = sum(1 for m in all_matches if team_wins(m) and over_goals(m))
    neither = sum(1 for m in all_matches if not team_wins(m) and not over_goals(m))

    or_count = win_only + goals_only + both
    or_prob = or_count / total if total > 0 else 0.0

    return {
        "tool": "get_win_or_total_goals",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "goals_threshold": goals_threshold,
            "conditions": {
                "team_win": {"count": win_only + both, "probability": round((win_only + both) / total, 4) if total > 0 else 0.0},
                "over_goals": {"count": goals_only + both, "probability": round((goals_only + both) / total, 4) if total > 0 else 0.0}
            },
            "breakdown": {"win_only": win_only, "goals_only": goals_only, "both": both, "neither": neither},
            "or_logic": {"count": or_count, "probability": round(or_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_win_and_total_goals(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    goals_threshold: float = 2.5,
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Team wins AND fixture produces X+ goals (AND logic).

    Uses actual co-occurrence count (not assuming independence).
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_win_and_total_goals",
            "data": {"total_matches": 0, "and_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def team_wins(m: dict) -> bool:
        is_home = m['home_team'] == home_team
        if perspective == "home":
            if is_home:
                return m['home_score'] > m['away_score']
            else:
                return m['away_score'] > m['home_score']
        else:
            if is_home:
                return m['home_score'] < m['away_score']
            else:
                return m['away_score'] < m['home_score']

    def over_goals(m: dict) -> bool:
        return (m['home_score'] + m['away_score']) > goals_threshold

    total = len(all_matches)
    both_true = sum(1 for m in all_matches if team_wins(m) and over_goals(m))

    and_prob = both_true / total if total > 0 else 0.0

    return {
        "tool": "get_win_and_total_goals",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "goals_threshold": goals_threshold,
            "conditions": {
                "team_win": {"count": sum(1 for m in all_matches if team_wins(m))},
                "over_goals": {"count": sum(1 for m in all_matches if over_goals(m))}
            },
            "and_logic": {"count": both_true, "probability": round(and_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


# Implement remaining 5 combination tools using the same patterns...
# For brevity, I'll provide stubs that follow the same structure

async def get_win_or_both_scores(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Team wins OR both teams score (OR logic).

    Formula: P(A OR B) = P(A) + P(B) - P(A AND B)
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_win_or_both_scores",
            "data": {"total_matches": 0, "or_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def team_wins(m: dict) -> bool:
        is_home = m['home_team'] == home_team
        if perspective == "home":
            if is_home:
                return m['home_score'] > m['away_score']
            else:
                return m['away_score'] > m['home_score']
        else:
            if is_home:
                return m['home_score'] < m['away_score']
            else:
                return m['away_score'] < m['home_score']

    def both_teams_score(m: dict) -> bool:
        return m['home_score'] > 0 and m['away_score'] > 0

    total = len(all_matches)
    win_only = sum(1 for m in all_matches if team_wins(m) and not both_teams_score(m))
    bts_only = sum(1 for m in all_matches if both_teams_score(m) and not team_wins(m))
    both = sum(1 for m in all_matches if team_wins(m) and both_teams_score(m))
    neither = sum(1 for m in all_matches if not team_wins(m) and not both_teams_score(m))

    or_count = win_only + bts_only + both
    or_prob = or_count / total if total > 0 else 0.0

    return {
        "tool": "get_win_or_both_scores",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "conditions": {
                "team_win": {"count": win_only + both, "probability": round((win_only + both) / total, 4) if total > 0 else 0.0},
                "both_teams_score": {"count": bts_only + both, "probability": round((bts_only + both) / total, 4) if total > 0 else 0.0}
            },
            "breakdown": {"win_only": win_only, "bts_only": bts_only, "both": both, "neither": neither},
            "or_logic": {"count": or_count, "probability": round(or_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_win_and_both_scores(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Team wins AND both teams score (AND logic).

    Uses actual co-occurrence count (not assuming independence).
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_win_and_both_scores",
            "data": {"total_matches": 0, "and_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def team_wins(m: dict) -> bool:
        is_home = m['home_team'] == home_team
        if perspective == "home":
            if is_home:
                return m['home_score'] > m['away_score']
            else:
                return m['away_score'] > m['home_score']
        else:
            if is_home:
                return m['home_score'] < m['away_score']
            else:
                return m['away_score'] < m['home_score']

    def both_teams_score(m: dict) -> bool:
        return m['home_score'] > 0 and m['away_score'] > 0

    total = len(all_matches)
    both_true = sum(1 for m in all_matches if team_wins(m) and both_teams_score(m))

    and_prob = both_true / total if total > 0 else 0.0

    return {
        "tool": "get_win_and_both_scores",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "conditions": {
                "team_win": {"count": sum(1 for m in all_matches if team_wins(m))},
                "both_teams_score": {"count": sum(1 for m in all_matches if both_teams_score(m))}
            },
            "and_logic": {"count": both_true, "probability": round(and_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_both_scores_or_multi_goals(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    goals_threshold: float = 2.5,
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Both teams score OR fixture produces X+ goals (OR logic).

    Formula: P(A OR B) = P(A) + P(B) - P(A AND B)
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_both_scores_or_multi_goals",
            "data": {"total_matches": 0, "or_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def both_teams_score(m: dict) -> bool:
        return m['home_score'] > 0 and m['away_score'] > 0

    def over_goals(m: dict) -> bool:
        return (m['home_score'] + m['away_score']) > goals_threshold

    total = len(all_matches)
    bts_only = sum(1 for m in all_matches if both_teams_score(m) and not over_goals(m))
    goals_only = sum(1 for m in all_matches if over_goals(m) and not both_teams_score(m))
    both = sum(1 for m in all_matches if both_teams_score(m) and over_goals(m))
    neither = sum(1 for m in all_matches if not both_teams_score(m) and not over_goals(m))

    or_count = bts_only + goals_only + both
    or_prob = or_count / total if total > 0 else 0.0

    return {
        "tool": "get_both_scores_or_multi_goals",
        "data": {
            "total_matches": total,
            "goals_threshold": goals_threshold,
            "conditions": {
                "both_teams_score": {"count": bts_only + both, "probability": round((bts_only + both) / total, 4) if total > 0 else 0.0},
                "over_goals": {"count": goals_only + both, "probability": round((goals_only + both) / total, 4) if total > 0 else 0.0}
            },
            "breakdown": {"bts_only": bts_only, "goals_only": goals_only, "both": both, "neither": neither},
            "or_logic": {"count": or_count, "probability": round(or_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_no_defeat_and_total_goals(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    goals_threshold: float = 2.5,
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Team avoids defeat (Win OR Draw) AND fixture produces X+ goals (AND logic).

    Uses actual co-occurrence count (not assuming independence).
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    if not all_matches:
        return {
            "tool": "get_no_defeat_and_total_goals",
            "data": {"total_matches": 0, "and_probability": 0.0},
            "metadata": {"data_quality": "low"}
        }

    def get_result(m: dict) -> str:
        is_home = m['home_team'] == home_team
        if is_home:
            if m['home_score'] > m['away_score']:
                return 'home_win'
            elif m['home_score'] < m['away_score']:
                return 'away_win'
            else:
                return 'draw'
        else:
            if m['away_score'] > m['home_score']:
                return 'home_win'
            elif m['away_score'] < m['home_score']:
                return 'away_win'
            else:
                return 'draw'

    def team_avoids_defeat(m: dict) -> bool:
        result = get_result(m)
        if perspective == "home":
            return result in ['home_win', 'draw']
        else:
            return result in ['away_win', 'draw']

    def over_goals(m: dict) -> bool:
        return (m['home_score'] + m['away_score']) > goals_threshold

    total = len(all_matches)
    both_true = sum(1 for m in all_matches if team_avoids_defeat(m) and over_goals(m))

    and_prob = both_true / total if total > 0 else 0.0

    return {
        "tool": "get_no_defeat_and_total_goals",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "goals_threshold": goals_threshold,
            "conditions": {
                "team_avoids_defeat": {"count": sum(1 for m in all_matches if team_avoids_defeat(m))},
                "over_goals": {"count": sum(1 for m in all_matches if over_goals(m))}
            },
            "and_logic": {"count": both_true, "probability": round(and_prob, 4)}
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_avoid_halftime_defeat(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Probability of avoiding defeat at halftime (leading OR drawing at HT).

    Requires halftime data. Gracefully degrades if halftime data is missing.
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    # Filter matches with halftime data
    def has_ht_data(m: dict) -> bool:
        return (m.get('metadata') and
                'halftime_home_score' in m['metadata'] and
                'halftime_away_score' in m['metadata'])

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_avoid_halftime_defeat",
            "data": {"total_matches": 0, "perspective": perspective, "avoid_defeat_probability": 0.0},
            "metadata": {"halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_ht_result(m: dict) -> str:
        """Get halftime result from team's perspective."""
        is_home_actual = m['home_team'] == home_team
        ht_home = int(m['metadata']['halftime_home_score'])
        ht_away = int(m['metadata']['halftime_away_score'])

        if is_home_actual:
            if ht_home > ht_away:
                return 'home_win'
            elif ht_home < ht_away:
                return 'away_win'
            else:
                return 'draw'
        else:
            if ht_away > ht_home:
                return 'home_win'
            elif ht_away < ht_home:
                return 'away_win'
            else:
                return 'draw'

    total = len(matches_with_ht)
    ht_home_wins = sum(1 for m in matches_with_ht if get_ht_result(m) == 'home_win')
    ht_draws = sum(1 for m in matches_with_ht if get_ht_result(m) == 'draw')
    ht_away_wins = sum(1 for m in matches_with_ht if get_ht_result(m) == 'away_win')

    if perspective == "home":
        avoid_defeat_count = ht_home_wins + ht_draws  # Home win OR Draw at HT
    else:
        avoid_defeat_count = ht_away_wins + ht_draws  # Away win OR Draw at HT

    avoid_defeat_prob = avoid_defeat_count / total if total > 0 else 0.0

    return {
        "tool": "get_avoid_halftime_defeat",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "halftime_outcomes": {"home_win": ht_home_wins, "draw": ht_draws, "away_win": ht_away_wins},
            "avoid_defeat_count": avoid_defeat_count,
            "avoid_defeat_probability": round(avoid_defeat_prob, 4)
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total)
        }
    }


async def get_avoid_2nd_half_defeat(
    pool: asyncpg.Pool,
    home_team: str,
    away_team: str,
    league: str,
    perspective: str = "home",
    seasons_back: int = 6,
    current_form_matches: int = 10
) -> dict[str, Any]:
    """
    Probability of avoiding defeat in second-half (winning OR drawing in 2H).

    Requires halftime data. Gracefully degrades if halftime data is missing.
    """
    matches_data = await BaseStatisticalTool.get_h2h_matches(
        pool, home_team, away_team, league, seasons_back, current_form_matches
    )

    all_matches = matches_data["all_matches"]

    # Filter matches with halftime data
    def has_ht_data(m: dict) -> bool:
        return (m.get('metadata') and
                'halftime_home_score' in m['metadata'] and
                'halftime_away_score' in m['metadata'])

    matches_with_ht = [m for m in all_matches if has_ht_data(m)]

    if not matches_with_ht:
        return {
            "tool": "get_avoid_2nd_half_defeat",
            "data": {"total_matches": 0, "perspective": perspective, "avoid_defeat_probability": 0.0},
            "metadata": {"halftime_data_coverage": 0.0, "data_quality": "low"}
        }

    def get_2h_result(m: dict) -> str:
        """Get second-half result from team's perspective."""
        is_home_actual = m['home_team'] == home_team

        ht_home = int(m['metadata']['halftime_home_score'])
        ht_away = int(m['metadata']['halftime_away_score'])
        ft_home = m['home_score']
        ft_away = m['away_score']

        # Calculate second-half goals
        goals_2h_home = ft_home - ht_home
        goals_2h_away = ft_away - ht_away

        if is_home_actual:
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
    second_half_home_wins = sum(1 for m in matches_with_ht if get_2h_result(m) == 'home_win')
    second_half_draws = sum(1 for m in matches_with_ht if get_2h_result(m) == 'draw')
    second_half_away_wins = sum(1 for m in matches_with_ht if get_2h_result(m) == 'away_win')

    if perspective == "home":
        avoid_defeat_count = second_half_home_wins + second_half_draws  # Home win OR Draw in 2H
    else:
        avoid_defeat_count = second_half_away_wins + second_half_draws  # Away win OR Draw in 2H

    avoid_defeat_prob = avoid_defeat_count / total if total > 0 else 0.0

    return {
        "tool": "get_avoid_2nd_half_defeat",
        "data": {
            "total_matches": total,
            "perspective": perspective,
            "second_half_outcomes": {"home_win": second_half_home_wins, "draw": second_half_draws, "away_win": second_half_away_wins},
            "avoid_defeat_count": avoid_defeat_count,
            "avoid_defeat_probability": round(avoid_defeat_prob, 4)
        },
        "metadata": {
            "seasons_analyzed": matches_data["seasons_analyzed"],
            "halftime_data_coverage": round(len(matches_with_ht) / len(all_matches), 2) if all_matches else 0.0,
            "data_quality": DataQualityClassifier.assess(total)
        }
    }
