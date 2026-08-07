"""Team-related MCP tools for sports data access.

Provides tools for retrieving team statistics, league tables, and head-to-head data.

UPDATED for Phase 3: Now uses integer IDs from API-Football instead of UUIDs.
"""

import re
from typing import Any

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_team_stats(
    db_client: AuroraDataClient,
    team_id: int,
    league_id: int,
    season: str,
) -> dict[str, Any]:
    """Get team statistics for a specific season.

    UPDATED for Phase 3: Now accepts integer IDs from API-Football.

    Args:
        db_client: Database client instance
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)

    Returns:
        Dictionary with "stats" key containing team statistics

    Raises:
        ValueError: If season format is invalid or team stats not found

    Example:
        ```python
        result = await get_team_stats(
            db_client=client,
            team_id=50,
            league_id=39,
            season="2024"
        )
        # Returns: {"stats": {...}}
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Query database
    stats = await db_client.get_team_stats(
        team_id=team_id, league_id=league_id, season=season
    )

    if stats is None:
        raise ValueError(
            f"Team stats not found for team {team_id} in league {league_id}, season {season}"
        )

    return {"stats": stats}


async def get_league_table(
    db_client: AuroraDataClient,
    league_id: int,
    season: str,
) -> dict[str, Any]:
    """Get league standings/table for a specific season.

    UPDATED for Phase 3: Now accepts integer league ID from API-Football.

    Args:
        db_client: Database client instance
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)

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
        # Returns: {"standings": [{"rank": 1, ...}, {"rank": 2, ...}, ...]}
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Query database
    standings = await db_client.get_league_table(league_id=league_id, season=season)

    return {"standings": standings}


async def get_head_to_head(
    db_client: AuroraDataClient,
    home_team_id: int,
    away_team_id: int,
) -> dict[str, Any]:
    """Get head-to-head statistics between two teams.

    UPDATED for Phase 3: Now accepts integer team IDs from API-Football.

    Args:
        db_client: Database client instance
        home_team_id: API-Football home team ID (e.g., 50 for Manchester City)
        away_team_id: API-Football away team ID (e.g., 42 for Arsenal)

    Returns:
        Dictionary with "head_to_head" key containing:
        - team_1_id, team_2_id (auto-ordered: team_1_id < team_2_id)
        - last_10_matches (JSONB array of recent matches)
        - team_1_wins, team_2_wins, draws

    Raises:
        ValueError: If both teams are the same

    Example:
        ```python
        result = await get_head_to_head(
            db_client=client,
            home_team_id=50,
            away_team_id=42
        )
        # Returns: {"head_to_head": {...}}
        ```
    """
    # Check if both teams are the same
    if home_team_id == away_team_id:
        raise ValueError("Cannot compare team with itself")

    # Query database
    h2h_data = await db_client.get_head_to_head(
        home_team_id=home_team_id,
        away_team_id=away_team_id
    )

    return {"head_to_head": h2h_data}
