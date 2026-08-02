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


# League name mapping for user-friendly queries
LEAGUE_NAME_MAPPINGS = {
    # Premier League variations
    "premier league": "premier-league",
    "epl": "premier-league",
    "english premier league": "premier-league",
    "england": "premier-league",

    # LaLiga variations
    "laliga": "laliga",
    "la liga": "laliga",
    "spanish league": "laliga",
    "spain": "laliga",

    # Serie A variations
    "serie a": "serie-a",
    "italian league": "serie-a",
    "italy": "serie-a",

    # Bundesliga variations
    "bundesliga": "bundesliga",
    "german league": "bundesliga",
    "germany": "bundesliga",

    # Ligue 1 variations
    "ligue 1": "ligue-1",
    "french league": "ligue-1",
    "france": "ligue-1",

    # Other leagues
    "eredivisie": "eredivisie",
    "netherlands": "eredivisie",
    "dutch league": "eredivisie",
    "liga portugal": "liga-portugal",
    "portuguese league": "liga-portugal",
    "portugal": "liga-portugal",
    "scottish premiership": "scottish-premiership",
    "scotland": "scottish-premiership",
    "super lig": "super-lig",
    "turkish league": "super-lig",
    "turkey": "super-lig",
    "belgian pro league": "belgian-pro-league",
    "belgium": "belgian-pro-league",
}


def map_league_name_to_id(league_name: str) -> str | None:
    """Map user-friendly league name to database league ID.

    Args:
        league_name: User-friendly league name (e.g., "Premier League", "EPL")

    Returns:
        League ID string or None if not found

    Example:
        >>> map_league_name_to_id("Premier League")
        "premier-league"
        >>> map_league_name_to_id("EPL")
        "premier-league"
        >>> map_league_name_to_id("Unknown League")
        None
    """
    return LEAGUE_NAME_MAPPINGS.get(league_name.lower().strip())


async def search_fixtures(
    db_client: AuroraDataClient,
    league_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str = "scheduled",
    has_odds: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    """Search for fixtures with flexible filtering.

    This tool provides advanced fixture search with:
    - League filtering by user-friendly names (e.g., "Premier League", "EPL")
    - Date range filtering with sensible defaults (next 7 days if not specified)
    - Status filtering (scheduled, live, finished)
    - Odds availability filtering (only matches with bookmaker odds)
    - Result limit

    Designed for batch prediction requests like "20 odds in Premier League this weekend".

    Args:
        db_client: Database client instance
        league_names: List of user-friendly league names (e.g., ["Premier League", "LaLiga"])
                     Maps variations like "EPL" → "premier-league", "Spain" → "laliga"
        date_from: Start date in ISO 8601 format (YYYY-MM-DD). Defaults to today.
        date_to: End date in ISO 8601 format (YYYY-MM-DD). Defaults to today + 7 days.
        status: Match status filter (scheduled, live, finished). Default: "scheduled"
        has_odds: Only return matches with bookmaker odds available. Default: True
        limit: Maximum number of fixtures to return. Default: 100

    Returns:
        Dictionary with:
        - "fixtures": List of fixture dictionaries matching filters
        - "count": Number of fixtures returned
        - "filters_applied": Dictionary showing what filters were used

    Raises:
        ValueError: If date format is invalid
        RuntimeError: If database connection fails

    Example:
        ```python
        # Basic: Get scheduled fixtures with odds for next 7 days
        result = await search_fixtures(db_client=client)
        # Returns: {"fixtures": [...], "count": 45, "filters_applied": {...}}

        # With league filter: Premier League and LaLiga
        result = await search_fixtures(
            db_client=client,
            league_names=["Premier League", "LaLiga"],
            date_from="2026-08-03",
            date_to="2026-08-10"
        )

        # All fixtures (including without odds)
        result = await search_fixtures(
            db_client=client,
            has_odds=False,
            limit=50
        )
        ```
    """
    # Apply date defaults
    if date_from is None:
        date_from = datetime.now(UTC).date().isoformat()
    if date_to is None:
        date_to = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()

    # Map league names to IDs
    league_ids: list[str] | None = None
    if league_names:
        league_ids = []
        for name in league_names:
            league_id = map_league_name_to_id(name)
            if league_id:
                league_ids.append(league_id)
            # Silently skip unknown leagues (don't fail the whole query)

    # Query database for each league (if specified) or all leagues
    # The has_odds filtering is now done at the database level via SQL WHERE clause
    all_fixtures: list[dict[str, Any]] = []

    if league_ids:
        # Query each league separately
        for league_id in league_ids:
            fixtures = await db_client.get_matches(
                date_from=date_from,
                date_to=date_to,
                status=status,
                league_id=league_id,
                has_odds=has_odds,  # Database-level filtering
            )
            all_fixtures.extend(fixtures)
    else:
        # Query all leagues
        fixtures = await db_client.get_matches(
            date_from=date_from,
            date_to=date_to,
            status=status,
            league_id=None,
            has_odds=has_odds,  # Database-level filtering
        )
        all_fixtures = fixtures

    # Apply limit
    limited_fixtures = all_fixtures[:limit]

    # Return results with metadata
    return {
        "fixtures": limited_fixtures,
        "count": len(limited_fixtures),
        "filters_applied": {
            "league_names": league_names,
            "league_ids": league_ids,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "has_odds": has_odds,
            "limit": limit,
        }
    }
