"""API clients for external sports data providers.

This module provides async clients for fetching sports data directly from
external APIs with intelligent caching.
"""

from sipap_data_mcp.api.football_client import APIFootballClient, CacheTTL
from sipap_data_mcp.api.transformers import (
    calculate_form_from_fixtures,
    transform_fixture,
    transform_fixtures,
    transform_h2h,
    transform_odds,
    transform_standings,
    transform_team_statistics,
)

__all__ = [
    "APIFootballClient",
    "CacheTTL",
    "calculate_form_from_fixtures",
    "transform_fixture",
    "transform_fixtures",
    "transform_h2h",
    "transform_odds",
    "transform_standings",
    "transform_team_statistics",
]
