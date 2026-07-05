"""Historical data MCP tools for sports intelligence.

Provides tools for querying historical match data and calculating team form.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sipap_data_mcp.database.aurora import AuroraDataClient


async def query_history(
    db_client: AuroraDataClient,
    team_id: str,
    league_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Query historical match data with flexible filters.

    Args:
        db_client: Database client instance
        team_id: Team UUID
        league_id: Optional league UUID filter
        date_from: Optional start date (ISO 8601 format)
        date_to: Optional end date (ISO 8601 format)
        limit: Maximum number of matches to return (default: 20)

    Returns:
        Dictionary with "matches" key containing list of historical matches

    Raises:
        ValueError: If team_id or league_id are not valid UUIDs,
                   or if date formats are invalid

    Example:
        ```python
        result = await query_history(
            db_client=client,
            team_id="550e8400-e29b-41d4-a716-446655440000",
            date_from="2026-01-01",
            date_to="2026-06-30",
            limit=50
        )
        # Returns: {"matches": [{...}, {...}, ...]}
        ```
    """
    # Validate team UUID
    try:
        UUID(team_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for team_id: {team_id}") from e

    # Validate league UUID if provided
    if league_id is not None:
        try:
            UUID(league_id)
        except ValueError as e:
            raise ValueError(f"Invalid UUID for league_id: {league_id}") from e

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

    # Query historical matches
    matches = await db_client.query_match_history(
        team_id=team_id,
        league_id=league_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    return {"matches": matches}


async def get_form_data(
    db_client: AuroraDataClient,
    team_id: str,
    num_matches: int = 5,
) -> dict[str, Any]:
    """Calculate team form from recent match results.

    Args:
        db_client: Database client instance
        team_id: Team UUID
        num_matches: Number of recent matches to analyze (default: 5)

    Returns:
        Dictionary with form data:
        - form: List of results ["W", "D", "L"] (most recent first)
        - wins: Number of wins
        - draws: Number of draws
        - losses: Number of losses
        - points: Total points (3 per win, 1 per draw)

    Raises:
        ValueError: If team_id is not a valid UUID

    Example:
        ```python
        result = await get_form_data(
            db_client=client,
            team_id="550e8400-e29b-41d4-a716-446655440000",
            num_matches=10
        )
        # Returns: {"form": ["W", "W", "D", "L", "W"], "wins": 3, ...}
        ```
    """
    # Validate team UUID
    try:
        UUID(team_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for team_id: {team_id}") from e

    # Query recent matches
    matches = await db_client.query_match_history(
        team_id=team_id,
        league_id=None,
        date_from=None,
        date_to=None,
        limit=num_matches,
    )

    # Calculate form
    form = []
    wins = 0
    draws = 0
    losses = 0

    for match in matches:
        # Determine if team was home or away
        is_home = match["home_team_id"] == team_id

        home_score = match["home_score"]
        away_score = match["away_score"]

        # Calculate result from team's perspective
        if home_score == away_score:
            form.append("D")
            draws += 1
        elif (is_home and home_score > away_score) or (not is_home and away_score > home_score):
            form.append("W")
            wins += 1
        else:
            form.append("L")
            losses += 1

    # Calculate points (3 for win, 1 for draw, 0 for loss)
    points = (wins * 3) + (draws * 1)

    return {
        "form": form,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": points,
    }
