"""MCP tools for sports data access.

Provides tools for:
- Match tools (schedule, details, live, search)
- Team tools (stats, standings, head-to-head)
- Historical tools (query history, form data)
- Odds tools (current odds, movements)
- News tools (news intelligence analysis)
- Injuries tools (player injuries for fixtures)
- Lineups tools (team lineups and formations)
"""

from sipap_data_mcp.tools.historical import (
    get_form_data,
    query_history,
)
from sipap_data_mcp.tools.injuries import (
    get_injuries,
)
from sipap_data_mcp.tools.lineups import (
    get_lineups,
)
from sipap_data_mcp.tools.matches import (
    get_live_matches,
    get_match_details,
    get_match_schedule,
    search_fixtures,
    search_matches,
)
from sipap_data_mcp.tools.news import (
    analyze_news_impact,
)
from sipap_data_mcp.tools.odds import (
    get_match_odds,
    get_odds_movements,
)
from sipap_data_mcp.tools.teams import (
    get_head_to_head,
    get_league_table,
    get_team_stats,
)

__all__ = [
    "analyze_news_impact",
    "get_form_data",
    "get_head_to_head",
    "get_injuries",
    "get_league_table",
    "get_lineups",
    "get_live_matches",
    "get_match_details",
    "get_match_odds",
    "get_match_schedule",
    "get_odds_movements",
    "get_team_stats",
    "query_history",
    "search_fixtures",
    "search_matches",
]
