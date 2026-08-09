"""Lineups-related MCP tools for sports data access.

Provides tools for retrieving team lineups (starting XI and substitutes) for fixtures.

UPDATED for Phase 3: Now uses integer fixture IDs from API-Football.
"""

from typing import Any

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_lineups(
    db_client: AuroraDataClient,
    fixture_id: int,
) -> dict[str, Any]:
    """Get team lineups (starting XI and substitutes) for a specific fixture.

    Retrieves confirmed lineups for both home and away teams. Lineups are
    typically announced 60-90 minutes before kickoff.

    Args:
        db_client: Database client instance
        fixture_id: API-Football fixture ID (e.g., 1234567)

    Returns:
        Dictionary with "lineups" key containing:
        - fixture_id: The fixture ID
        - home_team_lineup: JSONB object with home team lineup
          (formation, startXI, substitutes, coach)
        - away_team_lineup: JSONB object with away team lineup
          (formation, startXI, substitutes, coach)

        If lineups not yet announced, returns:
        - lineups: None
        - message: "Lineups not available yet"

    Example:
        ```python
        result = await get_lineups(
            db_client=client,
            fixture_id=1234567
        )
        # Returns: {
        #   "lineups": {
        #     "fixture_id": 1234567,
        #     "home_team_lineup": {
        #       "formation": "4-3-3",
        #       "startXI": [
        #         {"player_id": 123, "player_name": "Player Name", "number": 1, "pos": "G"},
        #         ...
        #       ],
        #       "substitutes": [...],
        #       "coach": {"id": 456, "name": "Coach Name"}
        #     },
        #     "away_team_lineup": {
        #       "formation": "4-2-3-1",
        #       ...
        #     }
        #   }
        # }
        #
        # Or if not available yet:
        # {
        #   "lineups": None,
        #   "message": "Lineups not available yet"
        # }
        ```
    """
    # Query database
    lineups = await db_client.get_lineups(fixture_id)

    if lineups is None:
        return {
            "lineups": None,
            "message": "Lineups not available yet"
        }

    return {"lineups": lineups}
