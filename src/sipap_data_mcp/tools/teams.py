"""Team-related MCP tools for sports data access.

Provides tools for retrieving team statistics, league tables, and head-to-head data.

UPDATED for Phase 3: Now uses integer IDs from API-Football instead of UUIDs.
UPDATED: Added fallback logic for empty team stats (computes from recent matches).
REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

import logging
import re
from typing import Any

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.api.transformers import (
    transform_h2h,
    transform_standings,
    transform_team_statistics,
)
from sipap_data_mcp.database.aurora import AuroraDataClient

logger = logging.getLogger(__name__)


async def get_team_stats_api(
    api_client: APIFootballClient,
    team_id: int,
    league_id: int,
    season: int,
    min_matches: int = 10,
) -> dict[str, Any]:
    """Get team statistics using API-Football directly.

    If the current season has fewer than min_matches played, also fetches
    the previous season's stats and last 15 completed fixtures across all
    competitions for comprehensive analysis.

    Args:
        api_client: API-Football client instance
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year (e.g., 2026)
        min_matches: Minimum matches threshold (default: 10)

    Returns:
        Dictionary with "stats" key containing team statistics,
        plus "previous_season_stats" and "recent_fixtures" if current season
        has fewer than min_matches.
    """
    from sipap_data_mcp.api.transformers import transform_fixtures

    # Get current season stats
    response = await api_client.get_team_statistics(
        team_id=team_id,
        league_id=league_id,
        season=season,
    )

    stats = transform_team_statistics(response)

    if not stats:
        logger.warning(f"No stats found for team {team_id} in league {league_id} season {season}")
        stats = {}

    # Check if current season has enough matches
    current_matches_played = stats.get("total_played", 0) if stats else 0

    result: dict[str, Any] = {"stats": stats}

    if current_matches_played < min_matches:
        logger.info(
            f"get_team_stats_api: team {team_id} has only {current_matches_played} matches "
            f"in season {season}, fetching supplementary data"
        )

        # Fetch previous season stats
        previous_season = season - 1
        prev_response = await api_client.get_team_statistics(
            team_id=team_id,
            league_id=league_id,
            season=previous_season,
        )
        prev_stats = transform_team_statistics(prev_response)

        if prev_stats:
            result["previous_season_stats"] = prev_stats
            result["previous_season"] = previous_season
            logger.info(f"get_team_stats_api: included previous season {previous_season} stats")

        # Fetch last 15 completed fixtures across all competitions
        fixtures_response = await api_client.get_fixtures(
            team=team_id,
            last=15,
            status="FT",
        )
        recent_fixtures = transform_fixtures(fixtures_response)

        if recent_fixtures:
            result["recent_fixtures"] = recent_fixtures
            result["recent_fixtures_count"] = len(recent_fixtures)
            logger.info(f"get_team_stats_api: included {len(recent_fixtures)} recent fixtures")

        result["data_note"] = (
            f"Current season ({season}) has only {current_matches_played} matches. "
            f"Previous season stats and last 15 fixtures included for comprehensive analysis."
        )

    logger.info(f"get_team_stats_api: team {team_id}, league {league_id}, season {season}")
    return result


async def get_team_stats(
    db_client: AuroraDataClient,
    team_id: int,
    league_id: int,
    season: str,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get team statistics for a specific season.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with "stats" key containing team statistics.

    Raises:
        ValueError: If season format is invalid

    Example:
        ```python
        result = await get_team_stats(
            db_client=client,
            team_id=50,
            league_id=39,
            season="2024"
        )
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Use API client if available
    if api_client is not None:
        return await get_team_stats_api(
            api_client=api_client,
            team_id=team_id,
            league_id=league_id,
            season=int(season),
        )

    # Fallback to database
    logger.info(f"get_team_stats: using database fallback for team {team_id}")
    stats = await db_client.get_team_stats(
        team_id=team_id, league_id=league_id, season=season
    )

    if stats is not None:
        return {"stats": stats}

    # FALLBACK: team_statistics is empty - compute from recent matches
    return await _compute_stats_from_matches(db_client, team_id)


async def _compute_stats_from_matches(
    db_client: AuroraDataClient,
    team_id: int,
    num_matches: int = 15,
) -> dict[str, Any]:
    """Compute team statistics from recent finished matches.

    Fallback logic when team_statistics table is empty.

    Args:
        db_client: Database client instance
        team_id: API-Football team ID
        num_matches: Number of recent matches to analyze (default: 15)

    Returns:
        Dictionary with computed statistics including:
        - total_played, total_wins, total_draws, total_losses
        - total_goals_for, total_goals_against, goal_difference
        - form (string like "WWDLW")
        - points (3 per win, 1 per draw)
        - computed_from_matches: True (indicates this is computed, not from team_statistics)
    """
    # Query last N finished matches for this team
    matches = await db_client.query_match_history_by_api_team_id(
        team_api_id=team_id,
        limit=num_matches,
    )

    if not matches:
        # No matches found - return empty stats structure
        return {
            "stats": {
                "total_played": 0,
                "total_wins": 0,
                "total_draws": 0,
                "total_losses": 0,
                "total_goals_for": 0,
                "total_goals_against": 0,
                "goal_difference": 0,
                "form": "",
                "points": 0,
                "computed_from_matches": True,
                "num_matches": 0,
            }
        }

    # Compute form and stats from matches
    form_letters = []
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for match in matches:
        home_team_api_id = match.get("home_team_api_id")
        home_score = match.get("home_score")
        away_score = match.get("away_score")

        # Skip matches without scores
        if home_score is None or away_score is None:
            continue

        is_home = home_team_api_id == team_id

        if is_home:
            team_goals = home_score
            opponent_goals = away_score
        else:
            team_goals = away_score
            opponent_goals = home_score

        goals_for += team_goals
        goals_against += opponent_goals

        # Determine result
        if team_goals > opponent_goals:
            form_letters.append("W")
            wins += 1
        elif team_goals < opponent_goals:
            form_letters.append("L")
            losses += 1
        else:
            form_letters.append("D")
            draws += 1

    # Calculate points (3 per win, 1 per draw)
    points = (wins * 3) + draws

    return {
        "stats": {
            "total_played": len(form_letters),
            "total_wins": wins,
            "total_draws": draws,
            "total_losses": losses,
            "total_goals_for": goals_for,
            "total_goals_against": goals_against,
            "goal_difference": goals_for - goals_against,
            "form": "".join(form_letters[:5]),  # Last 5 for form string
            "points": points,
            "computed_from_matches": True,
            "num_matches": len(matches),
        }
    }


async def get_league_table_api(
    api_client: APIFootballClient,
    league_id: int,
    season: int,
) -> dict[str, Any]:
    """Get league standings using API-Football directly.

    Args:
        api_client: API-Football client instance
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year (e.g., 2026)

    Returns:
        Dictionary with "standings" key containing list of team standings
    """
    response = await api_client.get_standings(
        league_id=league_id,
        season=season,
    )

    standings = transform_standings(response)

    logger.info(f"get_league_table_api: league {league_id} season {season}, {len(standings)} teams")
    return {"standings": standings}


async def get_league_table(
    db_client: AuroraDataClient,
    league_id: int,
    season: str,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get league standings/table for a specific season.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with "standings" key containing list of team standings
        sorted by rank (1st place first)

    Raises:
        ValueError: If season format is invalid

    Example:
        ```python
        result = await get_league_table(
            db_client=client,
            league_id=39,
            season="2024"
        )
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Use API client if available
    if api_client is not None:
        return await get_league_table_api(
            api_client=api_client,
            league_id=league_id,
            season=int(season),
        )

    # Fallback to database
    logger.info(f"get_league_table: using database fallback for league {league_id}")
    standings = await db_client.get_league_table(league_id=league_id, season=season)

    return {"standings": standings}


async def get_head_to_head_api(
    api_client: APIFootballClient,
    home_team_id: int,
    away_team_id: int,
    last: int = 20,
) -> dict[str, Any]:
    """Get head-to-head statistics using API-Football directly.

    Args:
        api_client: API-Football client instance
        home_team_id: API-Football home team ID
        away_team_id: API-Football away team ID
        last: Number of recent H2H matches (default: 20)

    Returns:
        Dictionary with "head_to_head" and "summary" keys
    """
    response = await api_client.get_h2h(
        team1_id=home_team_id,
        team2_id=away_team_id,
        last=last,
    )

    h2h_data = transform_h2h(response)

    logger.info(f"get_head_to_head_api: {home_team_id} vs {away_team_id}, {len(h2h_data.get('head_to_head', []))} matches")
    return h2h_data


async def get_head_to_head(
    db_client: AuroraDataClient,
    home_team_id: int,
    away_team_id: int,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get head-to-head statistics between two teams.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        home_team_id: API-Football home team ID (e.g., 50 for Manchester City)
        away_team_id: API-Football away team ID (e.g., 42 for Arsenal)
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with "head_to_head" key containing H2H statistics

    Raises:
        ValueError: If both teams are the same

    Example:
        ```python
        result = await get_head_to_head(
            db_client=client,
            home_team_id=50,
            away_team_id=42
        )
        ```
    """
    # Check if both teams are the same
    if home_team_id == away_team_id:
        raise ValueError("Cannot compare team with itself")

    # Use API client if available
    if api_client is not None:
        return await get_head_to_head_api(
            api_client=api_client,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )

    # Fallback to database
    logger.info(f"get_head_to_head: using database fallback for {home_team_id} vs {away_team_id}")
    h2h_data = await db_client.get_head_to_head(
        home_team_id=home_team_id,
        away_team_id=away_team_id
    )

    return {"head_to_head": h2h_data}
