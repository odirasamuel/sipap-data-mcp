"""TypedDict data models for SIPAP sports data.

Provides structured type definitions for:
- Match data (matches, fixtures)
- Team data (stats, standings)
- Odds data (betting odds)
- League data (standings, tables)
"""

from sipap_data_mcp.models.models import (
    HomeAwayRecord,
    LeagueStanding,
    Match,
    MatchMetadata,
    OddsData,
    TeamStats,
)

__all__ = [
    "HomeAwayRecord",
    "LeagueStanding",
    "Match",
    "MatchMetadata",
    "OddsData",
    "TeamStats",
]
