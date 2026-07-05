"""Match-related MCP tools for sports data access.

Provides tools for retrieving match schedules, details, live matches, and search.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_match_schedule(
    db_client: AuroraDataClient,
    date_from: str,
    date_to: str,
    status: str = "scheduled",
    league_id: str | None = None,
) -> dict[str, Any]:
    """Get match schedule for specified date range.

    Args:
        db_client: Database client instance
        date_from: Start date in ISO 8601 format (YYYY-MM-DD)
        date_to: End date in ISO 8601 format (YYYY-MM-DD)
        status: Match status filter (scheduled, live, finished)
        league_id: Optional league UUID filter

    Returns:
        Dictionary with "matches" key containing list of matches

    Raises:
        ValueError: If date format is invalid
        RuntimeError: If database connection fails

    Example:
        ```python
        result = await get_match_schedule(
            db_client=client,
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled"
        )
        # Returns: {"matches": [...]}
        ```
    """
    # Query database
    matches = await db_client.get_matches(
        date_from=date_from,
        date_to=date_to,
        status=status,
        league_id=league_id
    )

    return {"matches": matches}


async def get_match_details(
    db_client: AuroraDataClient,
    match_id: str,
) -> dict[str, Any]:
    """Get detailed information for a specific match.

    Args:
        db_client: Database client instance
        match_id: Match UUID

    Returns:
        Dictionary with "match" key containing match details

    Raises:
        ValueError: If match_id is not a valid UUID or match not found

    Example:
        ```python
        result = await get_match_details(
            db_client=client,
            match_id="550e8400-e29b-41d4-a716-446655440000"
        )
        # Returns: {"match": {...}}
        ```
    """
    # Validate UUID format
    try:
        UUID(match_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID: {match_id}") from e

    # Query database for single match
    match = await db_client.get_match(match_id=match_id)

    if match is None:
        raise ValueError(f"Match not found: {match_id}")

    return {"match": match}


async def get_live_matches(
    db_client: AuroraDataClient,
) -> dict[str, Any]:
    """Get all currently live matches.

    Args:
        db_client: Database client instance

    Returns:
        Dictionary with "matches" key containing list of live matches

    Example:
        ```python
        result = await get_live_matches(db_client=client)
        # Returns: {"matches": [...]}
        ```
    """
    # Get today's date range (live matches should be today)
    now = datetime.now(UTC)
    date_from = now.date().isoformat()
    date_to = (now.date() + timedelta(days=1)).isoformat()

    # Query database for live matches
    matches = await db_client.get_matches(
        date_from=date_from,
        date_to=date_to,
        status="live",
        league_id=None
    )

    return {"matches": matches}


async def search_matches(
    db_client: AuroraDataClient,
    query: str,
) -> dict[str, Any]:
    """Search for matches by team name or other criteria.

    Args:
        db_client: Database client instance
        query: Search query string

    Returns:
        Dictionary with "matches" key containing list of matching matches

    Raises:
        ValueError: If query is empty

    Example:
        ```python
        result = await search_matches(
            db_client=client,
            query="Arsenal"
        )
        # Returns: {"matches": [...]}
        ```
    """
    # Validate query
    if not query or query.strip() == "":
        raise ValueError("Query cannot be empty")

    # Query database
    matches = await db_client.search_matches(query=query)

    return {"matches": matches}
