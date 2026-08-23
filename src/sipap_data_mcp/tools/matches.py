"""Match-related MCP tools for sports data access.

Provides tools for retrieving match schedules, details, live matches, and search.

REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.
All match data is fetched directly from API-Football with built-in caching via Redis.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.api.transformers import transform_fixtures

# League reference from sipap-common (ID-first architecture)
from sipap_common.data.league_reference import LEAGUE_REFERENCE

# Initialize logger for this module
logger = logging.getLogger(__name__)


def _convert_decimals_to_float(data: Any) -> Any:
    """Recursively convert Decimal objects to float for JSON serialization.

    Args:
        data: Any data structure (dict, list, Decimal, etc.)

    Returns:
        Same structure with Decimal values converted to float
    """
    if isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, dict):
        return {key: _convert_decimals_to_float(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_convert_decimals_to_float(item) for item in data]
    else:
        return data


def _map_status_to_api(status: str) -> str:
    """Map SIPAP status to API-Football status codes.

    Args:
        status: SIPAP status (scheduled, live, finished)

    Returns:
        API-Football status code(s)
    """
    status_map = {
        "scheduled": "NS",  # Not Started
        "live": "1H-2H-HT-ET-BT-P",  # All live statuses
        "finished": "FT",  # Full Time
    }
    return status_map.get(status, status)


def _derive_season_from_date(date_str: str) -> int:
    """Derive API-Football season year from a date string.

    European football seasons run Aug-May, so:
    - Aug-Dec: season = that year (e.g., Aug 2026 -> season 2026)
    - Jan-Jul: season = previous year (e.g., May 2027 -> season 2026)

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Season year (e.g., 2026)
    """
    date_obj = datetime.fromisoformat(date_str)
    if date_obj.month >= 8:  # Aug-Dec
        return date_obj.year
    else:  # Jan-Jul
        return date_obj.year - 1


async def get_match_schedule_api(
    api_client: APIFootballClient,
    date_from: str,
    date_to: str,
    status: str = "scheduled",
    league_id: int | None = None,
) -> dict[str, Any]:
    """Get match schedule using API-Football directly.

    Args:
        api_client: API-Football client instance
        date_from: Start date in ISO 8601 format (YYYY-MM-DD)
        date_to: End date in ISO 8601 format (YYYY-MM-DD)
        status: Match status filter (scheduled, live, finished)
        league_id: Optional API-Football league ID (e.g., 39 for Premier League)

    Returns:
        Dictionary with "matches" key containing list of matches
    """
    # Map status to API-Football format
    api_status = _map_status_to_api(status)

    # Derive season from date (required when filtering by league)
    season = _derive_season_from_date(date_from) if league_id else None

    # Call API-Football
    response = await api_client.get_fixtures(
        league=league_id,
        season=season,
        from_date=date_from,
        to_date=date_to,
        status=api_status,
    )

    # Transform response to MCP format
    matches = transform_fixtures(response)

    logger.info(f"get_match_schedule_api: {len(matches)} matches from API-Football")
    return {"matches": matches}


async def get_match_schedule(
    db_client: Any | None,  # DEPRECATED (2026-08-20): Database removed
    date_from: str,
    date_to: str,
    status: str = "scheduled",
    league_id: str | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get match schedule for specified date range.

    REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.

    Args:
        db_client: DEPRECATED - No longer used (database removed 2026-08-20)
        date_from: Start date in ISO 8601 format (YYYY-MM-DD)
        date_to: End date in ISO 8601 format (YYYY-MM-DD)
        status: Match status filter (scheduled, live, finished)
        league_id: Optional league filter (API-Football league ID as string)
        api_client: API-Football client (REQUIRED)

    Returns:
        Dictionary with "matches" key containing list of matches

    Raises:
        RuntimeError: If api_client is not provided

    Example:
        ```python
        result = await get_match_schedule(
            db_client=None,
            api_client=api,
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled"
        )
        # Returns: {"matches": [...]}
        ```
    """
    # API client is required (database removed 2026-08-20)
    if api_client is None:
        raise RuntimeError(
            "get_match_schedule requires api_client (database removed 2026-08-20)"
        )

    # Convert league_id to int if it looks like an API-Football ID
    api_league_id = None
    if league_id is not None:
        try:
            api_league_id = int(league_id)
        except ValueError:
            logger.warning(f"league_id '{league_id}' is not an integer, skipping league filter")

    return await get_match_schedule_api(
        api_client=api_client,
        date_from=date_from,
        date_to=date_to,
        status=status,
        league_id=api_league_id,
    )


async def get_match_details_api(
    api_client: APIFootballClient,
    fixture_id: int,
) -> dict[str, Any]:
    """Get match details using API-Football directly.

    Args:
        api_client: API-Football client instance
        fixture_id: API-Football fixture ID

    Returns:
        Dictionary with "match" key containing match details
    """
    response = await api_client.get_fixture_by_id(fixture_id)
    matches = transform_fixtures(response)

    if not matches:
        raise ValueError(f"Fixture not found: {fixture_id}")

    logger.info(f"get_match_details_api: found fixture {fixture_id}")
    return {"match": matches[0]}


async def get_match_details(
    db_client: Any | None,  # DEPRECATED (2026-08-20): Database removed
    match_id: str,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get detailed information for a specific match.

    REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.

    Args:
        db_client: DEPRECATED - No longer used (database removed 2026-08-20)
        match_id: API-Football fixture ID (integer or string representation)
        api_client: API-Football client (REQUIRED)

    Returns:
        Dictionary with "match" key containing match details

    Raises:
        RuntimeError: If api_client is not provided
        ValueError: If match_id is not a valid integer or match not found

    Example:
        ```python
        result = await get_match_details(
            db_client=None,
            api_client=api,
            match_id="1234567"
        )
        # Returns: {"match": {...}}
        ```
    """
    # API client is required (database removed 2026-08-20)
    if api_client is None:
        raise RuntimeError(
            "get_match_details requires api_client (database removed 2026-08-20)"
        )

    # Convert match_id to integer (API-Football fixture ID)
    try:
        fixture_id = int(match_id)
    except ValueError as e:
        raise ValueError(f"Invalid match ID: {match_id} (must be an API-Football fixture ID)") from e

    return await get_match_details_api(api_client, fixture_id)


async def get_live_matches_api(
    api_client: APIFootballClient,
) -> dict[str, Any]:
    """Get live matches using API-Football directly.

    Args:
        api_client: API-Football client instance

    Returns:
        Dictionary with "matches" key containing list of live matches
    """
    response = await api_client.get_live_fixtures()
    matches = transform_fixtures(response)

    logger.info(f"get_live_matches_api: {len(matches)} live matches from API-Football")
    return {"matches": matches}


async def get_live_matches(
    db_client: Any | None,  # DEPRECATED (2026-08-20): Database removed
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get all currently live matches.

    REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.
    API-Football provides real-time live match data.

    Args:
        db_client: DEPRECATED - No longer used (database removed 2026-08-20)
        api_client: API-Football client (REQUIRED)

    Returns:
        Dictionary with "matches" key containing list of live matches

    Raises:
        RuntimeError: If api_client is not provided

    Example:
        ```python
        result = await get_live_matches(db_client=None, api_client=api)
        # Returns: {"matches": [...]}
        ```
    """
    # API client is required (database removed 2026-08-20)
    if api_client is None:
        raise RuntimeError(
            "get_live_matches requires api_client (database removed 2026-08-20)"
        )

    return await get_live_matches_api(api_client)


async def search_matches_api(
    api_client: APIFootballClient,
    query: str,
    min_matches: int = 10,
    target_matches: int = 15,
) -> dict[str, Any]:
    """Search for matches using API-Football.

    Searches for teams matching the query and returns their recent completed fixtures.
    Includes pre-season, friendlies, and previous season matches if current season
    has fewer than min_matches completed.

    Args:
        api_client: API-Football client instance
        query: Search query string (team name)
        min_matches: Minimum matches desired (default: 10)
        target_matches: Target number of matches to return (default: 15)

    Returns:
        Dictionary with "matches" key containing list of matching matches
    """
    # First search for teams matching the query
    teams_response = await api_client.get_teams(search=query)
    teams = teams_response.get("response", [])

    if not teams:
        logger.info(f"search_matches_api: no teams found for '{query}'")
        return {"matches": [], "team_found": False, "team_id": None}

    # Get fixtures for the first matching team
    team_info = teams[0].get("team", {})
    team_id = team_info.get("id")
    team_name = team_info.get("name", query)

    if not team_id:
        logger.warning(f"search_matches_api: team found but no ID for '{query}'")
        return {"matches": [], "team_found": True, "team_id": None}

    logger.info(f"search_matches_api: found team '{team_name}' (ID: {team_id}) for query '{query}'")

    # Strategy: Get last N fixtures without season filter
    # This includes all competitions: league, cup, friendly, pre-season
    fixtures_response = await api_client.get_fixtures(
        team=team_id,
        last=target_matches,  # Get target number of completed fixtures
        status="FT",  # Only finished matches
    )

    matches = transform_fixtures(fixtures_response)
    logger.info(f"search_matches_api: {len(matches)} completed matches for '{team_name}'")

    # If we got fewer than min_matches with FT status, try without status filter
    # (in case some matches have different completion statuses like AET, PEN)
    if len(matches) < min_matches:
        logger.info(f"search_matches_api: only {len(matches)} matches, trying broader search")

        # Get more fixtures without status filter, then filter completed ones
        broader_response = await api_client.get_fixtures(
            team=team_id,
            last=target_matches * 2,  # Get more to filter from
        )

        all_fixtures = transform_fixtures(broader_response)

        # Filter to completed statuses (FT, AET, PEN, AWD, WO)
        completed_statuses = {"FT", "AET", "PEN", "AWD", "WO"}
        completed_matches = [
            m for m in all_fixtures
            if m.get("status") in completed_statuses
        ][:target_matches]

        if len(completed_matches) > len(matches):
            matches = completed_matches
            logger.info(f"search_matches_api: broader search found {len(matches)} completed matches")

    return {
        "matches": matches[:target_matches],
        "team_found": True,
        "team_id": team_id,
        "team_name": team_name,
    }


async def search_matches(
    db_client: Any | None,  # DEPRECATED (2026-08-20): Database removed
    query: str,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Search for matches by team name or other criteria.

    REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.
    API-Football search is team-based - finds teams matching the query
    and returns their recent fixtures.

    Args:
        db_client: DEPRECATED - No longer used (database removed 2026-08-20)
        query: Search query string (team name)
        api_client: API-Football client (REQUIRED)

    Returns:
        Dictionary with "matches" key containing list of matching matches

    Raises:
        RuntimeError: If api_client is not provided
        ValueError: If query is empty

    Example:
        ```python
        result = await search_matches(
            db_client=None,
            api_client=api,
            query="Arsenal"
        )
        # Returns: {"matches": [...]}
        ```
    """
    # Validate query
    if not query or query.strip() == "":
        raise ValueError("Query cannot be empty")

    # API client is required (database removed 2026-08-20)
    if api_client is None:
        raise RuntimeError(
            "search_matches requires api_client (database removed 2026-08-20)"
        )

    return await search_matches_api(api_client, query)


# League name mapping for user-friendly queries
# DEPRECATED: Old hardcoded mappings replaced with comprehensive mappings from sipap-common
# Kept for reference only. All league mapping logic now uses sipap-common.data module.
# LEAGUE_NAME_MAPPINGS = {...}  # Removed - see sipap-common/data/league_mappings.py


def map_league_name_to_id(league_name: str) -> str | None:
    """Map user-friendly league name to canonical name for database query.

    IMPORTANT: The database stores league names EXACTLY as they come from API-Football
    (e.g., "La Liga", "Premier League"), NOT slug format (e.g., "laliga", "premier-league").
    This function returns the canonical name for ILIKE matching in SQL queries.

    Uses comprehensive mappings from sipap-common covering 380 competitions across 77 countries.
    Supports:
    - Canonical competition names: "Premier League", "Cupa României", "Türkiye Kupası"
    - Country names: "romania" → resolves to first Romanian league in results
    - Aliases: "EPL", "Europa League", "romanian cup", "LaLiga", "Spanish LaLiga"

    Args:
        league_name: User-friendly league name (e.g., "Premier League", "EPL", "LaLiga")

    Returns:
        Canonical league name for database query, or None if not found

    Example:
        >>> map_league_name_to_id("Premier League")
        'Premier League'
        >>> map_league_name_to_id("EPL")
        'Premier League'
        >>> map_league_name_to_id("LaLiga")
        'La Liga'
        >>> map_league_name_to_id("Spanish LaLiga")
        'La Liga'
        >>> map_league_name_to_id("Unknown League")
        None
    """
    from sipap_common.data import find_league_matches

    # Find canonical league names using comprehensive mappings
    # This handles aliases like "LaLiga" → "La Liga", "EPL" → "Premier League"
    canonical_names = find_league_matches(league_name)

    if not canonical_names:
        logger.warning(f"No league match found for: '{league_name}'")
        return None

    # Return the first canonical name - this is what's stored in the database
    # Database stores league names exactly as API-Football provides them
    canonical_name = canonical_names[0]
    logger.debug(f"League mapping: '{league_name}' → '{canonical_name}'")
    return canonical_name


async def search_fixtures_api(
    api_client: APIFootballClient,
    league_ids: list[int] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str = "scheduled",
    limit: int = 100,
) -> dict[str, Any]:
    """Search for fixtures using API-Football directly.

    Args:
        api_client: API-Football client instance
        league_ids: List of API-Football league IDs
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        status: Match status (scheduled, live, finished)
        limit: Maximum fixtures to return

    Returns:
        Dictionary with fixtures, count, and filters_applied
    """
    # Apply date defaults
    if date_from is None:
        date_from = datetime.now(UTC).date().isoformat()
    if date_to is None:
        date_to = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()

    # Map status
    api_status = _map_status_to_api(status)

    all_fixtures: list[dict[str, Any]] = []

    # Derive season from date_from (required when filtering by league)
    season = _derive_season_from_date(date_from)

    if league_ids:
        # Query each league
        for league_id in league_ids:
            response = await api_client.get_fixtures(
                league=league_id,
                season=season,
                from_date=date_from,
                to_date=date_to,
                status=api_status,
            )
            fixtures = transform_fixtures(response)
            logger.info(f"search_fixtures_api: League {league_id} season {season} returned {len(fixtures)} fixtures")
            all_fixtures.extend(fixtures)
    else:
        # Get current season from today's year
        season = datetime.now().year

        # Without league filter, API-Football requires date parameter
        # Query by date range
        response = await api_client.get_fixtures(
            date=date_from,  # Get fixtures for start date
            status=api_status,
        )
        fixtures = transform_fixtures(response)
        all_fixtures.extend(fixtures)

        logger.info(f"search_fixtures_api: Date {date_from} returned {len(fixtures)} fixtures")

    # Apply limit
    limited_fixtures = all_fixtures[:limit]

    return {
        "fixtures": limited_fixtures,
        "count": len(limited_fixtures),
        "filters_applied": {
            "league_ids": league_ids,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "limit": limit,
            "source": "api_football",
        }
    }


async def search_fixtures(
    db_client: Any | None,  # DEPRECATED (2026-08-20): Database removed, kept for signature compatibility
    league_ids: list[int] | None = None,
    league_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str = "scheduled",
    has_odds: bool = True,
    limit: int = 100,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Search for fixtures with flexible filtering.

    REDESIGNED (2026-08-20): Database removed, uses API-Football exclusively.
    API-Football provides real-time fixture data with built-in caching.

    This tool provides advanced fixture search with:
    - League filtering by API-Football IDs (preferred) or user-friendly names
    - Date range filtering with sensible defaults (next 7 days if not specified)
    - Status filtering (scheduled, live, finished)
    - Result limit

    ID-FIRST ARCHITECTURE:
    Use league_ids (API-Football IDs) for unambiguous resolution.
    - league_ids: [140, 39] → La Liga (Spain), Premier League (England)
    - Eliminates string matching ambiguity (e.g., "Premier League" exists in multiple countries)

    Args:
        db_client: DEPRECATED - No longer used (database removed 2026-08-20)
        league_ids: List of API-Football league IDs (e.g., [140, 39] for La Liga, Premier League)
                   REQUIRED - Use IDs for unambiguous resolution.
        league_names: LEGACY - List of user-friendly league names. Converted to league_ids internally.
        date_from: Start date in ISO 8601 format (YYYY-MM-DD). Defaults to today.
        date_to: End date in ISO 8601 format (YYYY-MM-DD). Defaults to today + 7 days.
        status: Match status filter (scheduled, live, finished). Default: "scheduled"
        has_odds: DEPRECATED - No longer used (odds filtering done post-query if needed)
        limit: Maximum number of fixtures to return. Default: 100
        api_client: API-Football client (REQUIRED)

    Returns:
        Dictionary with:
        - "fixtures": List of fixture dictionaries matching filters
        - "count": Number of fixtures returned
        - "filters_applied": Dictionary showing what filters were used

    Raises:
        RuntimeError: If api_client is not provided

    Example:
        ```python
        result = await search_fixtures(
            db_client=None,
            api_client=api,
            league_ids=[140, 39],  # La Liga + Premier League
            date_from="2026-08-03",
            date_to="2026-08-10"
        )
        ```
    """
    logger.info(
        "search_fixtures called",
        extra={
            "league_ids": league_ids,
            "league_names": league_names,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "limit": limit,
            "api_client": "provided" if api_client else "not provided",
        }
    )

    # API client is now required (database removed 2026-08-20)
    if api_client is None:
        raise RuntimeError(
            "search_fixtures requires api_client (database removed 2026-08-20). "
            "Ensure API-Football client is initialized."
        )

    # Apply date defaults
    if date_from is None:
        date_from = datetime.now(UTC).date().isoformat()
    if date_to is None:
        date_to = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()

    logger.info(f"Date range after defaults: {date_from} to {date_to}")

    # Resolve league_ids from league_names if needed (LEGACY compatibility)
    resolved_league_ids: list[int] = []

    if league_ids:
        # PRIMARY PATH: Use API-Football IDs directly
        resolved_league_ids = league_ids
        logger.info(f"Using {len(resolved_league_ids)} API-Football league IDs: {resolved_league_ids}")

    elif league_names:
        # LEGACY PATH: Convert league names to IDs using sipap-common mappings
        logger.info(f"Converting {len(league_names)} league names to IDs")
        for name in league_names:
            canonical = map_league_name_to_id(name)
            if canonical:
                # Look up the ID from LEAGUE_REFERENCE
                for league in LEAGUE_REFERENCE:
                    if league["name"].lower() == canonical.lower():
                        resolved_league_ids.append(league["id"])
                        logger.debug(f"League name '{name}' → ID {league['id']}")
                        break
            else:
                logger.warning(f"Unknown league name: '{name}' (skipping)")

        if not resolved_league_ids:
            logger.warning(
                f"User requested leagues {league_names} but no valid IDs found. "
                f"Returning 0 fixtures."
            )
            return _convert_decimals_to_float({
                "fixtures": [],
                "count": 0,
                "filters_applied": {
                    "league_names": league_names,
                    "league_ids": None,
                    "date_from": date_from,
                    "date_to": date_to,
                    "status": status,
                    "limit": limit,
                    "error": "No valid league IDs resolved from names",
                }
            })

    else:
        # No league filter - query all supported leagues from LEAGUE_REFERENCE
        resolved_league_ids = [league["id"] for league in LEAGUE_REFERENCE]
        logger.info(f"No league filter - using all {len(resolved_league_ids)} leagues from LEAGUE_REFERENCE")

    # Call API-Football for fixtures
    result = await search_fixtures_api(
        api_client=api_client,
        league_ids=resolved_league_ids,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
    )

    fixtures = result.get("fixtures", [])
    logger.info(f"Found {len(fixtures)} fixtures via API-Football")

    # Return results with metadata
    return _convert_decimals_to_float({
        "fixtures": fixtures,
        "count": len(fixtures),
        "filters_applied": {
            "league_names": league_names,
            "league_ids": resolved_league_ids,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "limit": limit,
            "source": "api_football",
        }
    })
