"""MCP tools for sports data access.

Provides tools for:
- Match tools (schedule, details, live, search)
- Team tools (stats, standings, head-to-head)
"""

from sipap_data_mcp.tools.matches import (
    get_live_matches,
    get_match_details,
    get_match_schedule,
    search_matches,
)
from sipap_data_mcp.tools.teams import (
    get_head_to_head,
    get_league_table,
    get_team_stats,
)

__all__ = [
    "get_head_to_head",
    "get_league_table",
    "get_live_matches",
    "get_match_details",
    "get_match_schedule",
    "get_team_stats",
    "search_matches",
]
