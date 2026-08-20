"""Injuries-related MCP tools for sports data access.

Provides tools for retrieving player injury information for fixtures.

UPDATED for Phase 3: Now uses integer fixture IDs from API-Football.
"""

from typing import Any

# Database removed (2026-08-20) - import removed


async def get_injuries(
    db_client: Any | None,
    fixture_id: int,
) -> dict[str, Any]:
    """Get player injuries for a specific fixture.

    Retrieves injury information for players from both teams in a fixture.
    Returns injuries reported for the match, including injury type, reason,
    and expected return date.

    Args:
        db_client: Database client instance
        fixture_id: API-Football fixture ID (e.g., 1234567)

    Returns:
        Dictionary with "injuries" key containing list of injury records.
        Each injury record includes:
        - player_id: API-Football player ID
        - player_name: Player's full name
        - player_photo: URL to player photo
        - team_id: API-Football team ID
        - team_name: Team name
        - injury_type: Type of injury (e.g., "Muscle Injury", "Knee Injury")
        - injury_reason: Reason/description of injury
        - expected_return_date: Expected return date (ISO format) or None

        Returns empty list if no injuries reported for the fixture.

    Example:
        ```python
        result = await get_injuries(
            db_client=client,
            fixture_id=1234567
        )
        # Returns: {
        #   "injuries": [
        #     {
        #       "player_name": "Bukayo Saka",
        #       "team_name": "Arsenal",
        #       "injury_type": "Muscle Injury",
        #       "injury_reason": "Hamstring",
        #       "expected_return_date": "2026-08-15"
        #     },
        #     ...
        #   ]
        # }
        ```
    """
    # Query database
    injuries = await db_client.get_injuries(fixture_id)

    return {"injuries": injuries}
