"""Odds intelligence MCP tools for sports betting analysis.

Provides tools for:
- Retrieving current betting odds from multiple bookmakers
- Tracking odds movements over time
- Identifying sharp money and steam moves
"""

from typing import Any
from uuid import UUID

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_match_odds(
    db_client: AuroraDataClient,
    match_id: str,
) -> dict[str, Any] | None:
    """Get betting odds for a match from multiple bookmakers.

    Args:
        db_client: Database client instance
        match_id: Match UUID

    Returns:
        Dictionary with odds data including:
        - bookmakers: List of bookmaker odds
        - best_odds: Best available odds for each outcome
        - average_odds: Average odds across all bookmakers
        Returns None if no odds data available

    Raises:
        ValueError: If match_id is not a valid UUID

    Example:
        ```python
        result = await get_match_odds(
            db_client=client,
            match_id="550e8400-e29b-41d4-a716-446655440000"
        )
        # Returns:
        # {
        #   "bookmakers": [{"bookmaker": "Bet365", "home_odds": 2.10, ...}],
        #   "best_odds": {"home": {"odds": 2.15, "bookmaker": "William Hill"}},
        #   "average_odds": {"home": 2.125, "draw": 3.35, "away": 3.55}
        # }
        ```
    """
    # Validate match UUID
    try:
        UUID(match_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for match_id: {match_id}") from e

    # Query match odds from database
    return await db_client.get_match_odds(match_id)


async def get_odds_movements(
    db_client: AuroraDataClient,
    match_id: str,
    time_window: str = "24h",
) -> dict[str, Any] | None:
    """Track odds movements over time for a match.

    Args:
        db_client: Database client instance
        match_id: Match UUID
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
        ValueError: If match_id is not a valid UUID or time_window is invalid

    Example:
        ```python
        result = await get_odds_movements(
            db_client=client,
            match_id="550e8400-e29b-41d4-a716-446655440000",
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
    # Validate match UUID
    try:
        UUID(match_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID for match_id: {match_id}") from e

    # Validate time_window
    valid_windows = ["1h", "6h", "12h", "24h", "48h", "7d"]
    if time_window not in valid_windows:
        raise ValueError(
            f"Invalid time_window '{time_window}': "
            f"Must be one of {', '.join(valid_windows)}"
        )

    # Query odds movements from database
    return await db_client.get_odds_movements(match_id, time_window)
