"""Odds intelligence MCP tools for sports betting analysis.

Provides tools for:
- Retrieving current betting odds from multiple bookmakers
- Tracking odds movements over time
- Identifying sharp money and steam moves

UPDATED for Phase 3: Now uses integer fixture IDs from API-Football.
"""

from typing import Any

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_match_odds(
    db_client: AuroraDataClient,
    fixture_id: int,
    is_live: bool = False,
) -> dict[str, Any]:
    """Get betting odds for a match from multiple bookmakers.

    UPDATED for Phase 3: Now accepts integer fixture ID from API-Football
    and queries dedicated odds table (not JSONB).

    Args:
        db_client: Database client instance
        fixture_id: API-Football fixture ID
        is_live: Whether to fetch live odds (default: False for pre-match)

    Returns:
        Dictionary with odds data including:
        - odds: List of odds records from different bookmakers
        - fixture_id: The fixture ID
        - count: Number of bookmaker odds available

    Example:
        ```python
        result = await get_match_odds(
            db_client=client,
            fixture_id=1234567
        )
        # Returns:
        # {
        #   "fixture_id": 1234567,
        #   "count": 15,
        #   "odds": [
        #     {"bookmaker_name": "Bet365", "market": "1X2", "home_odds": 1.85, ...},
        #     ...
        #   ]
        # }
        ```
    """
    # Query odds from dedicated odds table
    odds_list = await db_client.get_match_odds(fixture_id, is_live)

    return {
        "fixture_id": fixture_id,
        "count": len(odds_list),
        "odds": odds_list,
    }


async def get_odds_movements(
    db_client: AuroraDataClient,
    fixture_id: int,
    time_window: str = "24h",
) -> dict[str, Any] | None:
    """Track odds movements over time for a match.

    NOTE: This function will be updated in a future phase to query the odds table
    with created_at timestamps instead of using the old JSONB schema.

    Args:
        db_client: Database client instance
        fixture_id: API-Football fixture ID
        time_window: Time window for tracking movements (default: "24h")
                    Valid values: "1h", "6h", "12h", "24h", "48h", "7d"

    Returns:
        Dictionary with odds movement data including:
        - movements: List of odds changes over time
        - opening_odds: Initial odds
        - current_odds: Latest odds
        - movement_summary: Net change in odds
        Returns None if no movements data available

    Raises:
        ValueError: If time_window is invalid

    Example:
        ```python
        result = await get_odds_movements(
            db_client=client,
            fixture_id=1234567,
            time_window="24h"
        )
        # Returns:
        # {
        #   "movements": [{"timestamp": "...", "home_odds": 2.10, ...}],
        #   "opening_odds": {"home": 2.10, "draw": 3.40, "away": 3.60},
        #   "current_odds": {"home": 2.00, "draw": 3.50, "away": 3.80},
        #   "movement_summary": {"home": -0.10, "draw": +0.10, "away": +0.20}
        # }
        ```
    """
    # Validate time_window
    valid_windows = ["1h", "6h", "12h", "24h", "48h", "7d"]
    if time_window not in valid_windows:
        raise ValueError(
            f"Invalid time_window '{time_window}': "
            f"Must be one of {', '.join(valid_windows)}"
        )

    # NOTE: get_odds_movements() still uses old match_id (str) parameter
    # This will be updated in a future phase to work with Phase 3 schema
    # For now, convert fixture_id to string to maintain compatibility
    match_id = str(fixture_id)
    return await db_client.get_odds_movements(match_id, time_window)
