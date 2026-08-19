"""
Venue form split analysis tool.

Analyzes home vs away form differences to identify venue impact.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any

import asyncpg

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool


async def get_venue_form_split(
    pool: asyncpg.Pool | None,
    team: str | int,
    league: str | int,
    match_limit: int = 15,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze home vs away form differences.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        team: Team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        match_limit: Number of recent matches to analyze per venue (default: 15)
        api_client: Optional API-Football client (preferred)

    Returns:
        {
            "tool": "get_venue_form_split",
            "data": {
                "home_form": {
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "goals_scored": int,
                    "goals_conceded": int,
                    "form_score": float,  # 0-15 scale
                    "win_rate": float
                },
                "away_form": {
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "goals_scored": int,
                    "goals_conceded": int,
                    "form_score": float,  # 0-15 scale
                    "win_rate": float
                },
                "comparison": {
                    "points_differential": int,  # positive = home advantage
                    "form_score_differential": float,
                    "win_rate_differential": float,
                    "goals_scored_differential": float,
                    "venue_impact": "high" | "medium" | "low",
                    "stronger_venue": "home" | "away" | "neutral"
                },
                "venue_advantage_rating": int  # 0-100 scale
            },
            "metadata": {
                "home_matches_analyzed": int,
                "away_matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_venue_form_split(
        ...     pool=None, team=42, league=39, api_client=client
        ... )
        >>> print(result["data"]["comparison"]["stronger_venue"])
        "home"
    """
    # Determine team identifier for comparisons
    team_identifier: str | int
    if api_client is not None and isinstance(team, int):
        league_id = league if isinstance(league, int) else None
        home_matches = await BaseFormTool.get_recent_team_matches_api(
            api_client=api_client,
            team_id=team,
            league_id=league_id,
            match_limit=match_limit,
            venue="home",
        )
        away_matches = await BaseFormTool.get_recent_team_matches_api(
            api_client=api_client,
            team_id=team,
            league_id=league_id,
            match_limit=match_limit,
            venue="away",
        )
        team_identifier = team
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        home_matches = await BaseFormTool.get_recent_team_matches(
            pool=pool,
            team=str(team),
            league=str(league),
            match_limit=match_limit,
            venue="home",
        )
        away_matches = await BaseFormTool.get_recent_team_matches(
            pool=pool,
            team=str(team),
            league=str(league),
            match_limit=match_limit,
            venue="away",
        )
        team_identifier = str(team)

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    def analyze_venue(venue_matches: list[dict[str, Any]], _is_home_venue: bool) -> dict[str, Any]:
        """Analyze matches for a specific venue."""
        if not venue_matches:
            return {
                "points": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_scored": 0,
                "goals_conceded": 0,
                "form_score": 0.0,
                "win_rate": 0.0
            }

        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        for match in venue_matches:
            is_home = is_home_team(match)
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0

            if is_home:
                scored = home_score
                conceded = away_score
                if home_score > away_score:
                    wins += 1
                elif home_score == away_score:
                    draws += 1
                else:
                    losses += 1
            else:
                scored = away_score
                conceded = home_score
                if away_score > home_score:
                    wins += 1
                elif away_score == home_score:
                    draws += 1
                else:
                    losses += 1

            goals_scored += scored
            goals_conceded += conceded

        points = wins * 3 + draws

        # Form score calculation (max 15 points for 5 matches)
        # Scale to recent 5 matches if we have more
        recent_5 = venue_matches[:5]
        form_score_matches = recent_5 if len(recent_5) == 5 else venue_matches

        form_score_points = 0
        for match in form_score_matches:
            is_home = is_home_team(match)
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0

            if is_home:
                if home_score > away_score:
                    form_score_points += 3
                elif home_score == away_score:
                    form_score_points += 1
            else:
                if away_score > home_score:
                    form_score_points += 3
                elif away_score == home_score:
                    form_score_points += 1

        # Scale form score to 0-15 range
        max_form_points = len(form_score_matches) * 3
        form_score = (form_score_points / max_form_points * 15) if max_form_points > 0 else 0

        win_rate = wins / len(venue_matches) if venue_matches else 0

        return {
            "points": points,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "form_score": round(form_score, 2),
            "win_rate": round(win_rate, 3)
        }

    # Analyze both venues
    home_stats = analyze_venue(home_matches, True)
    away_stats = analyze_venue(away_matches, False)

    # Calculate differentials
    points_diff = home_stats["points"] - away_stats["points"]
    form_score_diff = home_stats["form_score"] - away_stats["form_score"]
    win_rate_diff = home_stats["win_rate"] - away_stats["win_rate"]

    home_goals_per_match = (
        home_stats["goals_scored"] / len(home_matches)
        if home_matches else 0
    )
    away_goals_per_match = (
        away_stats["goals_scored"] / len(away_matches)
        if away_matches else 0
    )
    goals_scored_diff = home_goals_per_match - away_goals_per_match

    # Determine venue impact
    # High impact: form score differential > 5 OR win rate differential > 0.3
    # Low impact: form score differential < 2 AND win rate differential < 0.15
    abs_form_diff = abs(form_score_diff)
    abs_win_rate_diff = abs(win_rate_diff)

    if abs_form_diff > 5 or abs_win_rate_diff > 0.3:
        venue_impact = "high"
    elif abs_form_diff > 2 or abs_win_rate_diff > 0.15:
        venue_impact = "medium"
    else:
        venue_impact = "low"

    # Determine stronger venue
    if form_score_diff > 2:
        stronger_venue = "home"
    elif form_score_diff < -2:
        stronger_venue = "away"
    else:
        stronger_venue = "neutral"

    # Calculate venue advantage rating (0-100)
    # Positive = home advantage, Negative = away advantage
    # Based on: form score differential (60%), win rate differential (40%)
    form_component = (form_score_diff / 15) * 60  # Normalize to -60 to +60
    win_rate_component = win_rate_diff * 40  # Normalize to -40 to +40

    venue_advantage_raw = form_component + win_rate_component
    # Convert to 0-100 scale (0 = strong away, 50 = neutral, 100 = strong home)
    venue_advantage_rating = int(min(100, max(0, 50 + venue_advantage_raw)))

    return {
        "tool": "get_venue_form_split",
        "data": {
            "home_form": home_stats,
            "away_form": away_stats,
            "comparison": {
                "points_differential": points_diff,
                "form_score_differential": round(form_score_diff, 2),
                "win_rate_differential": round(win_rate_diff, 3),
                "goals_scored_differential": round(goals_scored_diff, 2),
                "venue_impact": venue_impact,
                "stronger_venue": stronger_venue
            },
            "venue_advantage_rating": venue_advantage_rating
        },
        "metadata": {
            "home_matches_analyzed": len(home_matches),
            "away_matches_analyzed": len(away_matches)
        }
    }
