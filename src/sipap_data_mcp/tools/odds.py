"""Odds intelligence MCP tools for sports betting analysis.

Provides tools for:
- Retrieving current betting odds from multiple bookmakers
- Tracking odds movements over time
- Identifying sharp money and steam moves

UPDATED: Now reads odds from matches.metadata JSONB where the odds updater stores them.
REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

import logging
from typing import Any

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.api.transformers import transform_odds
from sipap_data_mcp.database.aurora import AuroraDataClient

logger = logging.getLogger(__name__)


async def get_match_odds_api(
    api_client: APIFootballClient,
    fixture_id: int,
) -> dict[str, Any]:
    """Get betting odds using API-Football directly.

    Args:
        api_client: API-Football client instance
        fixture_id: API-Football fixture ID

    Returns:
        Dictionary with odds data including:
        - odds: List of bookmaker odds
        - fixture_id: The fixture ID
        - count: Number of bookmakers
    """
    response = await api_client.get_odds(fixture=fixture_id)
    odds = transform_odds(response)

    logger.info(f"get_match_odds_api: fixture {fixture_id}, {len(odds)} odds records")
    return {
        "fixture_id": fixture_id,
        "count": len(odds),
        "odds": odds,
    }


async def get_match_odds(
    db_client: AuroraDataClient,
    fixture_id: int,
    is_live: bool = False,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """Get betting odds for a match.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        db_client: Database client instance (fallback)
        fixture_id: API-Football fixture ID
        is_live: Whether to fetch live odds (default: False for pre-match)
        api_client: Optional API-Football client (preferred)

    Returns:
        Dictionary with odds data including:
        - odds: List of bookmaker odds
        - fixture_id: The fixture ID
        - count: Number of bookmakers

    Example:
        ```python
        result = await get_match_odds(
            db_client=client,
            fixture_id=1234567
        )
        # Returns:
        # {
        #   "fixture_id": 1234567,
        #   "count": 1,
        #   "odds": [
        #     {"bookmaker_name": "Best Odds", "market": "1X2", "home_odds": 1.85, ...}
        #   ]
        # }
        ```
    """
    # Use API client if available
    if api_client is not None:
        return await get_match_odds_api(
            api_client=api_client,
            fixture_id=fixture_id,
        )

    # Fallback to database
    logger.info(f"get_match_odds: using database fallback for fixture {fixture_id}")
    odds_list = await db_client.get_match_odds(fixture_id, is_live)

    return {
        "fixture_id": fixture_id,
        "count": len(odds_list),
        "odds": odds_list,
    }


async def get_odds_movements_api(
    api_client: APIFootballClient,
    fixture_id: int,
) -> dict[str, Any]:
    """Track odds movements using API-Football.

    Note: API-Football doesn't provide historical odds movements.
    This function returns current odds only. For historical tracking,
    implement a separate odds history storage in Redis.

    Args:
        api_client: API-Football client instance
        fixture_id: API-Football fixture ID

    Returns:
        Dictionary with current odds and empty movements
    """
    response = await api_client.get_odds(fixture=fixture_id)
    odds = transform_odds(response)

    # Extract current odds from the first bookmaker
    current_odds = {}
    if odds:
        first_odds = odds[0]
        current_odds = {
            "home": first_odds.get("home_odds"),
            "draw": first_odds.get("draw_odds"),
            "away": first_odds.get("away_odds"),
        }

    logger.info(f"get_odds_movements_api: fixture {fixture_id}")
    return {
        "fixture_id": fixture_id,
        "movements": [],  # API doesn't provide historical data
        "opening_odds": None,  # Would need historical storage
        "current_odds": current_odds,
        "movement_summary": None,
        "note": "Historical odds movements require Redis-based tracking",
    }


async def get_odds_movements(
    db_client: AuroraDataClient,
    fixture_id: int,
    time_window: str = "24h",
    api_client: APIFootballClient | None = None,
) -> dict[str, Any] | None:
    """Track odds movements over time for a match.

    REDESIGNED (2026-08-19): Uses API-Football for current odds when available.
    Note: API-Football doesn't provide historical odds movements.
    Full movement tracking requires Redis-based odds history storage.

    Args:
        db_client: Database client instance (fallback)
        fixture_id: API-Football fixture ID
        time_window: Time window for tracking movements (default: "24h")
                    Valid values: "1h", "6h", "12h", "24h", "48h", "7d"
        api_client: Optional API-Football client (preferred)

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

    # Use API client if available (returns current odds only)
    if api_client is not None:
        return await get_odds_movements_api(
            api_client=api_client,
            fixture_id=fixture_id,
        )

    # Fallback to database
    logger.info(f"get_odds_movements: using database fallback for fixture {fixture_id}")
    match_id = str(fixture_id)
    return await db_client.get_odds_movements(match_id, time_window)
