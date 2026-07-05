"""Team-related MCP tools for sports data access.

Provides tools for retrieving team statistics, league tables, and head-to-head data.
"""

import re
from typing import Any
from uuid import UUID

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_team_stats(
    db_client: AuroraDataClient,
    team_id: str,
    season: str,
) -> dict[str, Any]:
    """Get team statistics for a specific season.

    Args:
        db_client: Database client instance
        team_id: Team UUID
        season: Season in format "YYYY-YYYY" (e.g., "2024-2025")

    Returns:
        Dictionary with "stats" key containing team statistics

    Raises:
        ValueError: If team_id is not a valid UUID, season format is invalid,
                   or team stats not found

    Example:
        ```python
        result = await get_team_stats(
            db_client=client,
            team_id="550e8400-e29b-41d4-a716-446655440000",
            season="2024-2025"
        )
        # Returns: {"stats": {...}}
        ```
    """
    # Validate UUID format
    try:
        UUID(team_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID: {team_id}") from e

    # Validate season format (YYYY-YYYY)
    if not re.match(r"^\d{4}-\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY-YYYY (e.g., 2024-2025)"
        )

    # Query database
    stats = await db_client.get_team_stats(team_id=team_id, season=season)

    if stats is None:
        raise ValueError(f"Team stats not found for team {team_id} in season {season}")

    return {"stats": stats}


async def get_league_table(
    db_client: AuroraDataClient,
    league_id: str,
    season: str,
) -> dict[str, Any]:
    """Get league standings/table for a specific season.

    Args:
        db_client: Database client instance
        league_id: League UUID
        season: Season in format "YYYY-YYYY" (e.g., "2024-2025")

    Returns:
        Dictionary with "standings" key containing list of team standings
        sorted by position

    Raises:
        ValueError: If league_id is not a valid UUID or season format is invalid

    Example:
        ```python
        result = await get_league_table(
            db_client=client,
            league_id="550e8400-e29b-41d4-a716-446655440000",
            season="2024-2025"
        )
        # Returns: {"standings": [{position: 1, ...}, {position: 2, ...}, ...]}
        ```
    """
    # Validate UUID format
    try:
        UUID(league_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID: {league_id}") from e

    # Validate season format (YYYY-YYYY)
    if not re.match(r"^\d{4}-\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY-YYYY (e.g., 2024-2025)"
        )

    # Query database
    standings = await db_client.get_league_table(league_id=league_id, season=season)

    return {"standings": standings}


async def get_head_to_head(
    db_client: AuroraDataClient,
    team1_id: str,
    team2_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Get head-to-head statistics between two teams.

    Args:
        db_client: Database client instance
        team1_id: First team UUID
        team2_id: Second team UUID
        limit: Maximum number of recent matches to include (default: 10)

    Returns:
        Dictionary with "head_to_head" key containing:
        - team1_id, team2_id
        - team1_name, team2_name
        - total_matches, team1_wins, team2_wins, draws
        - recent_matches (list of recent match results)

    Raises:
        ValueError: If either team_id is not a valid UUID or both teams are the same

    Example:
        ```python
        result = await get_head_to_head(
            db_client=client,
            team1_id="550e8400-e29b-41d4-a716-446655440000",
            team2_id="550e8400-e29b-41d4-a716-446655440001",
            limit=5
        )
        # Returns: {"head_to_head": {...}}
        ```
    """
    # Validate UUID formats
    try:
        UUID(team1_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for team1_id: {team1_id}") from e

    try:
        UUID(team2_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for team2_id: {team2_id}") from e

    # Check if both teams are the same
    if team1_id == team2_id:
        raise ValueError("Cannot compare team with itself")

    # Query database
    h2h_data = await db_client.get_head_to_head(
        team1_id=team1_id,
        team2_id=team2_id,
        limit=limit
    )

    return {"head_to_head": h2h_data}
