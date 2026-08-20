"""Historical data MCP tools for sports intelligence.

Provides tools for querying historical match data and calculating team form.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.api.transformers import calculate_form_from_fixtures, transform_fixtures
# Database removed (2026-08-20) - import removed

logger = logging.getLogger(__name__)


async def query_history_api(
    api_client: APIFootballClient,
    team_id: int,
    league_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Query historical match data using API-Football directly.

    Args:
        api_client: API-Football client instance
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: Optional API-Football league ID filter
        date_from: Optional start date (YYYY-MM-DD)
        date_to: Optional end date (YYYY-MM-DD)
        limit: Maximum number of matches to return (default: 20)

    Returns:
        Dictionary with "matches" key containing list of historical matches
    """
    params: dict[str, Any] = {
        "team": team_id,
        "status": "FT",  # Only finished matches for history
        "last": limit,
    }

    if league_id is not None:
        params["league"] = league_id

    if date_from is not None:
        params["from"] = date_from

    if date_to is not None:
        params["to"] = date_to

    response = await api_client.get_fixtures(**params)
    matches = transform_fixtures(response)

    logger.info(
        f"query_history_api: team {team_id}, league {league_id}, "
        f"dates {date_from} to {date_to}, found {len(matches)} matches"
    )
    return {"matches": matches}


async def get_form_data_api(
    api_client: APIFootballClient,
    team_id: int,
    num_matches: int = 5,
    league_id: int | None = None,
) -> dict[str, Any]:
    """Calculate team form using API-Football directly.

    Args:
        api_client: API-Football client instance
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        num_matches: Number of recent matches to analyze (default: 5)
        league_id: Optional league ID to filter by

    Returns:
        Dictionary with form data:
        - form: String of results like "WWDLW" (most recent first)
        - wins: Number of wins
        - draws: Number of draws
        - losses: Number of losses
        - points: Total points (3 per win, 1 per draw)
        - goals_for: Total goals scored
        - goals_against: Total goals conceded
    """
    params: dict[str, Any] = {
        "team": team_id,
        "status": "FT",  # Only finished matches
        "last": num_matches,
    }

    if league_id is not None:
        params["league"] = league_id

    response = await api_client.get_fixtures(**params)
    fixtures = transform_fixtures(response)
    form_data = calculate_form_from_fixtures(fixtures, team_id)

    logger.info(f"get_form_data_api: team {team_id}, form '{form_data.get('form', '')}'")
    return form_data


async def query_history(
    db_client: Any | None,
    team_id: int,
    league_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Query historical match data with flexible filters.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: Optional API-Football league ID filter
        date_from: Optional start date (ISO 8601 format)
        date_to: Optional end date (ISO 8601 format)
        limit: Maximum number of matches to return (default: 20)
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with "matches" key containing list of historical matches

    Raises:
        ValueError: If date formats are invalid

    Example:
        ```python
        result = await query_history(
            db_client=client,
            team_id=50,  # Manchester City
            date_from="2026-01-01",
            date_to="2026-06-30",
            limit=50
        )
        # Returns: {"matches": [{...}, {...}, ...]}
        ```
    """
    # Validate date formats if provided
    if date_from is not None:
        try:
            datetime.fromisoformat(date_from)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format for date_from '{date_from}': "
                f"Expected ISO 8601 format (YYYY-MM-DD)"
            ) from e

    if date_to is not None:
        try:
            datetime.fromisoformat(date_to)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format for date_to '{date_to}': "
                f"Expected ISO 8601 format (YYYY-MM-DD)"
            ) from e

    # Use API client if available
    if api_client is not None:
        return await query_history_api(
            api_client=api_client,
            team_id=team_id,
            league_id=league_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    # Fallback to database
    logger.info(f"query_history: using database fallback for team {team_id}")
    matches = await db_client.query_match_history(
        team_id=str(team_id),
        league_id=str(league_id) if league_id else None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    return {"matches": matches}


async def get_form_data(
    db_client: Any | None,
    team_id: int,
    num_matches: int = 5,
    league_id: int | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Calculate team form from recent match results.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        num_matches: Number of recent matches to analyze (default: 5)
        league_id: Optional league ID to filter by
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with form data:
        - form: String of results like "WWDLW" (most recent first)
        - wins: Number of wins
        - draws: Number of draws
        - losses: Number of losses
        - points: Total points (3 per win, 1 per draw)
        - goals_for: Total goals scored
        - goals_against: Total goals conceded

    Example:
        ```python
        result = await get_form_data(
            db_client=client,
            team_id=50,  # Manchester City
            num_matches=10
        )
        # Returns: {"form": "WWDLW", "wins": 3, ...}
        ```
    """
    # Use API client if available
    if api_client is not None:
        return await get_form_data_api(
            api_client=api_client,
            team_id=team_id,
            num_matches=num_matches,
            league_id=league_id,
        )

    # Fallback to database
    logger.info(f"get_form_data: using database fallback for team {team_id}")

    # Query recent matches
    matches = await db_client.query_match_history(
        team_id=str(team_id),
        league_id=str(league_id) if league_id else None,
        date_from=None,
        date_to=None,
        limit=num_matches,
    )

    # Calculate form
    form_letters = []
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for match in matches:
        # Determine if team was home or away
        is_home = str(match.get("home_team_id")) == str(team_id) or match.get("home_team_api_id") == team_id

        home_score = match.get("home_score", 0) or 0
        away_score = match.get("away_score", 0) or 0

        if is_home:
            goals_for += home_score
            goals_against += away_score
        else:
            goals_for += away_score
            goals_against += home_score

        # Calculate result from team's perspective
        if home_score == away_score:
            form_letters.append("D")
            draws += 1
        elif (is_home and home_score > away_score) or (not is_home and away_score > home_score):
            form_letters.append("W")
            wins += 1
        else:
            form_letters.append("L")
            losses += 1

    # Calculate points (3 for win, 1 for draw, 0 for loss)
    points = (wins * 3) + draws

    return {
        "form": "".join(form_letters),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": points,
        "goals_for": goals_for,
        "goals_against": goals_against,
    }
