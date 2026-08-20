"""Odds intelligence MCP tools for sports betting analysis.

Provides tools for:
- Retrieving current betting odds from multiple bookmakers
- Tracking odds movements over time
- Identifying sharp money and steam moves
- Fetching odds for specific markets (BTTS, Over/Under, Double Chance, etc.)

UPDATED: Now reads odds from matches.metadata JSONB where the odds updater stores them.
REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
EXTENDED (2026-08-19): Multi-market odds support for accumulator building.
"""

from __future__ import annotations

import logging
from typing import Any

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.api.transformers import transform_odds, transform_odds_for_market
# Database removed (2026-08-20) - import removed

logger = logging.getLogger(__name__)


# Import bet_mappings from sipap-master if available
# This allows the odds tool to use market code mappings
def _get_bet_mapping(market_code: str) -> dict[str, Any] | None:
    """Get bet mapping for a market code.

    Attempts to import from sipap-master bet_mappings module.
    Returns a dict representation of the BetMapping for this tool to use.

    Args:
        market_code: SIPAP market code (e.g., "1X2", "BTTS", "OU2.5")

    Returns:
        Dict with bet_id, outcome_mapping, line (or None if not found)
    """
    try:
        # Try to import from sipap-master
        from sipap.sports.soccer.bet_mappings import get_bet_mapping

        mapping = get_bet_mapping(market_code)
        if mapping is None:
            return None

        return {
            "market_code": mapping.market_code,
            "bet_id": mapping.bet_id,
            "outcome_mapping": mapping.outcome_mapping,
            "line": mapping.line,
        }
    except ImportError:
        # Fallback: Define common mappings inline for standalone operation
        logger.debug("bet_mappings not available, using inline fallbacks")
        return _get_inline_bet_mapping(market_code)


def _get_inline_bet_mapping(market_code: str) -> dict[str, Any] | None:
    """Inline fallback mappings for common markets.

    Used when sipap-master is not installed or importable.
    """
    inline_mappings: dict[str, dict[str, Any]] = {
        "1X2": {
            "market_code": "1X2",
            "bet_id": 1,
            "outcome_mapping": {
                "Home Win": "Home",
                "Draw": "Draw",
                "Away Win": "Away",
            },
            "line": None,
        },
        "BTTS": {
            "market_code": "BTTS",
            "bet_id": 8,
            "outcome_mapping": {"Yes": "Yes", "No": "No"},
            "line": None,
        },
        "DC": {
            "market_code": "DC",
            "bet_id": 12,
            "outcome_mapping": {
                "1X": "Home/Draw",
                "12": "Home/Away",
                "X2": "Draw/Away",
            },
            "line": None,
        },
        "DNB": {
            "market_code": "DNB",
            "bet_id": 10,
            "outcome_mapping": {"Home Win": "Home", "Away Win": "Away"},
            "line": None,
        },
        "OU0.5": {
            "market_code": "OU0.5",
            "bet_id": 5,
            "outcome_mapping": {"Over 0.5": "Over 0.5", "Under 0.5": "Under 0.5"},
            "line": 0.5,
        },
        "OU1.5": {
            "market_code": "OU1.5",
            "bet_id": 5,
            "outcome_mapping": {"Over 1.5": "Over 1.5", "Under 1.5": "Under 1.5"},
            "line": 1.5,
        },
        "OU2.5": {
            "market_code": "OU2.5",
            "bet_id": 5,
            "outcome_mapping": {"Over 2.5": "Over 2.5", "Under 2.5": "Under 2.5"},
            "line": 2.5,
        },
        "OU3.5": {
            "market_code": "OU3.5",
            "bet_id": 5,
            "outcome_mapping": {"Over 3.5": "Over 3.5", "Under 3.5": "Under 3.5"},
            "line": 3.5,
        },
        "OU4.5": {
            "market_code": "OU4.5",
            "bet_id": 5,
            "outcome_mapping": {"Over 4.5": "Over 4.5", "Under 4.5": "Under 4.5"},
            "line": 4.5,
        },
        "HT_1X2": {
            "market_code": "HT_1X2",
            "bet_id": 13,
            "outcome_mapping": {"1HT": "Home", "XHT": "Draw", "2HT": "Away"},
            "line": None,
        },
    }
    return inline_mappings.get(market_code)


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
    response = await api_client.get_odds(fixture_id=fixture_id)
    odds_data = transform_odds(response, fixture_id)

    logger.info(f"get_match_odds_api: fixture {fixture_id}, {odds_data.get('count', 0)} odds records")
    return odds_data


async def get_match_odds(
    db_client: Any | None,
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
    response = await api_client.get_odds(fixture_id=fixture_id)
    odds_data = transform_odds(response, fixture_id)
    odds_list = odds_data.get("odds", [])

    # Extract current odds from the first bookmaker
    current_odds = {}
    if odds_list:
        first_odds = odds_list[0]
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
    db_client: Any | None,
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


async def get_market_odds(
    api_client: APIFootballClient,
    fixture_id: int,
    market_code: str,
    outcome: str,
) -> dict[str, Any]:
    """Fetch bookmaker odds for a specific market and outcome.

    This function enables fetching odds for any supported market type,
    not just 1X2. It maps SIPAP market codes to API-Football bet IDs
    and extracts odds for the specified outcome.

    Args:
        api_client: API-Football client instance
        fixture_id: API-Football fixture ID
        market_code: SIPAP market code (e.g., "BTTS", "OU2.5", "DC", "HT_1X2")
        outcome: The specific outcome (e.g., "Yes", "Over 2.5", "1X", "Home Win")

    Returns:
        Dictionary with:
        - fixture_id: The fixture ID
        - market_code: The requested market code
        - outcome: The requested outcome
        - best_odds: Highest odds found (0.0 if not available)
        - bookmaker: Name of bookmaker with best odds (None if not found)
        - all_odds: List of all bookmaker odds for this outcome

    Raises:
        ValueError: If market_code is not supported/mapped

    Example:
        ```python
        # Get BTTS Yes odds
        result = await get_market_odds(
            api_client=client,
            fixture_id=1234567,
            market_code="BTTS",
            outcome="Yes"
        )
        # Returns:
        # {
        #   "fixture_id": 1234567,
        #   "market_code": "BTTS",
        #   "outcome": "Yes",
        #   "best_odds": 1.85,
        #   "bookmaker": "Bet365",
        #   "all_odds": [{"bookmaker": "Bet365", "odds": 1.85}, ...]
        # }

        # Get Over 2.5 odds
        result = await get_market_odds(
            api_client=client,
            fixture_id=1234567,
            market_code="OU2.5",
            outcome="Over 2.5"
        )
        ```
    """
    # Get bet mapping for this market code
    mapping = _get_bet_mapping(market_code)
    if mapping is None:
        raise ValueError(
            f"No mapping found for market code '{market_code}'. "
            f"Supported markets include: 1X2, BTTS, DC, DNB, OU0.5-OU4.5, HT_1X2"
        )

    bet_id = mapping["bet_id"]
    outcome_mapping = mapping["outcome_mapping"]
    line = mapping.get("line")

    # Map SIPAP outcome to API-Football outcome value
    api_outcome = outcome_mapping.get(outcome)
    if api_outcome is None:
        # Try using outcome directly (might already be in API format)
        api_outcome = outcome
        logger.debug(f"Outcome '{outcome}' not in mapping, using directly")

    # Fetch odds from API-Football with bet type filter
    response = await api_client.get_odds(fixture_id=fixture_id, bet=bet_id)

    # Transform response for the specific market and outcome
    odds_data = transform_odds_for_market(
        api_response=response,
        fixture_id=fixture_id,
        bet_id=bet_id,
        target_outcome=api_outcome,
        line=line,
    )

    logger.info(
        f"get_market_odds: fixture {fixture_id}, market {market_code}, "
        f"outcome {outcome} → best odds {odds_data['best_odds']} "
        f"from {odds_data['best_bookmaker']}"
    )

    return {
        "fixture_id": fixture_id,
        "market_code": market_code,
        "outcome": outcome,
        "best_odds": odds_data["best_odds"],
        "bookmaker": odds_data["best_bookmaker"],
        "all_odds": odds_data["all_odds"],
    }


async def get_top_markets_with_odds(
    api_client: APIFootballClient,
    fixture_id: int,
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fetch odds for a list of markets and attach them to each market.

    This is a convenience function for the MarketEvaluator to fetch odds
    for multiple top markets at once.

    Args:
        api_client: API-Football client instance
        fixture_id: API-Football fixture ID
        markets: List of market dicts with at least 'market_code' and 'best_outcome'

    Returns:
        Same markets list with 'odds' and 'bookmaker' fields added to each

    Example:
        ```python
        top_markets = [
            {"market_code": "BTTS", "best_outcome": "Yes", "probability": 0.72},
            {"market_code": "OU2.5", "best_outcome": "Over 2.5", "probability": 0.68},
        ]

        enriched = await get_top_markets_with_odds(
            api_client=client,
            fixture_id=1234567,
            markets=top_markets
        )
        # Returns:
        # [
        #   {"market_code": "BTTS", "best_outcome": "Yes", "probability": 0.72,
        #    "odds": 1.85, "bookmaker": "Bet365"},
        #   ...
        # ]
        ```
    """
    import asyncio

    async def fetch_and_attach(market: dict[str, Any]) -> dict[str, Any]:
        """Fetch odds for a single market and attach to the dict."""
        market_code = market.get("market_code", "")
        outcome = market.get("best_outcome", "")

        if not market_code or not outcome:
            return {**market, "odds": None, "bookmaker": None}

        try:
            odds_data = await get_market_odds(
                api_client=api_client,
                fixture_id=fixture_id,
                market_code=market_code,
                outcome=outcome,
            )
            return {
                **market,
                "odds": odds_data["best_odds"] if odds_data["best_odds"] > 0 else None,
                "bookmaker": odds_data["bookmaker"],
            }
        except ValueError as e:
            # Market not supported
            logger.warning(f"Could not fetch odds for {market_code}: {e}")
            return {**market, "odds": None, "bookmaker": None}
        except Exception as e:
            # API or network error
            logger.error(f"Error fetching odds for {market_code}: {e}")
            return {**market, "odds": None, "bookmaker": None}

    # Fetch all odds in parallel
    results = await asyncio.gather(*[fetch_and_attach(m) for m in markets])
    return list(results)
