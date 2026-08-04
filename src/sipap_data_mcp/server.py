"""SIPAP Data MCP Server - Sports data & odds intelligence.

Provides JSON-RPC 2.0 compliant MCP server for sports data access.
Wraps 43 data tools with MCP protocol for AI agent communication.
"""

import asyncio
from typing import Any

from sipap_mcp import MCPServer, mcp_tool  # type: ignore[import-untyped]

from sipap_data_mcp.cache.redis import RedisCache
from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools import (
    get_form_data,
    get_head_to_head,
    get_league_table,
    get_live_matches,
    get_match_details,
    get_match_odds,
    get_match_schedule,
    get_odds_movements,
    get_team_stats,
    query_history,
    search_fixtures,
    search_matches,
)
from sipap_data_mcp.tools import statistical
from sipap_data_mcp.tools import form


class SIPAPDataMCP(MCPServer):
    """SIPAP Data MCP Server.

    Provides JSON-RPC 2.0 compliant access to sports data via 43 MCP tools:
    - 5 match tools (schedule, details, live, search, search_fixtures)
    - 3 team tools (stats, standings, head-to-head)
    - 2 historical tools (query history, form data)
    - 2 odds tools (current odds, movements)
    - 24 statistical analysis tools (h2h, goals, halftime, combinations, specialized)
    - 7 form pattern tools (momentum, trajectory, consistency, venue, offensive, defensive, pressure)

    Example:
        ```python
        server = SIPAPDataMCP(
            db_host="localhost",
            db_port=5432,
            db_name="sipap",
            db_user="sipap_readonly",
            db_password="secret",
            redis_url="redis://localhost:6379/0"
        )

        await server._setup()

        # List all tools
        tools = server.list_tools()

        # Call a tool
        result = await server.call_tool(
            "get_match_schedule",
            {"date_from": "2026-07-05", "date_to": "2026-07-12"}
        )

        await server._cleanup()
        ```
    """

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        redis_url: str,
    ) -> None:
        """Initialize SIPAP Data MCP Server.

        Args:
            db_host: Aurora cluster endpoint
            db_port: Database port (typically 5432)
            db_name: Database name
            db_user: Database username
            db_password: Database password
            redis_url: Redis connection URL
        """
        super().__init__(
            name="sipap-data-mcp",
            version="1.0.0"
        )

        # Store connection parameters
        self._db_host = db_host
        self._db_port = db_port
        self._db_name = db_name
        self._db_user = db_user
        self._db_password = db_password
        self._redis_url = redis_url

        # Clients (initialized in _setup)
        self.db_client: AuroraDataClient | None = None
        self.cache: RedisCache | None = None

    async def _setup(self) -> None:
        """Initialize database and cache connections.

        Called automatically when server starts.
        Establishes connections to Aurora and Redis.
        """
        # Create database client
        self.db_client = AuroraDataClient(
            host=self._db_host,
            port=self._db_port,
            database=self._db_name,
            user=self._db_user,
            password=self._db_password,
        )

        # Create cache client
        self.cache = RedisCache(url=self._redis_url)

        # Connect to both
        await self.db_client.connect()
        await self.cache.connect()

    async def _cleanup(self) -> None:
        """Close database and cache connections.

        Called automatically when server shuts down.
        Ensures proper resource cleanup.
        """
        if self.db_client is not None:
            await self.db_client.close()
            self.db_client = None

        if self.cache is not None:
            await self.cache.close()
            self.cache = None

    def _ensure_connections(self) -> tuple[AuroraDataClient, RedisCache]:
        """Ensure connections are established.

        Returns:
            Tuple of (db_client, cache)

        Raises:
            RuntimeError: If connections not established
        """
        if self.db_client is None or self.cache is None:
            raise RuntimeError("Server not initialized. Call _setup() first.")
        return self.db_client, self.cache

    def _run_async(self, coro: Any) -> Any:
        """Run async coroutine synchronously.

        Uses existing event loop if available (Lambda warm start scenario),
        otherwise creates a new loop for standalone usage.

        Args:
            coro: Coroutine to run

        Returns:
            Result of coroutine
        """
        # Check if we're already in an async context (loop is running)
        try:
            running_loop = asyncio.get_running_loop()
            # We're in an async context (like pytest-asyncio)
            # Create a new thread with its own event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running loop, check if there's a set event loop (Lambda scenario)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    # Loop is closed, create new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(coro)
                else:
                    # Use existing loop (Lambda warm start)
                    return loop.run_until_complete(coro)
            except RuntimeError:
                # No event loop at all, use asyncio.run (creates new loop each time)
                return asyncio.run(coro)

    # ========================================================================
    # Match Tools (4)
    # ========================================================================

    @mcp_tool(
        description="Get match schedule for date range with optional filters",
        input_schema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date in ISO 8601 format (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "description": "End date in ISO 8601 format (YYYY-MM-DD)"
                },
                "status": {
                    "type": "string",
                    "description": "Match status filter (scheduled, live, finished)",
                    "default": "scheduled"
                },
                "league_id": {
                    "type": "string",
                    "description": "Optional league UUID filter"
                }
            },
            "required": ["date_from", "date_to"]
        }
    )
    def get_match_schedule(
        self,
        date_from: str,
        date_to: str,
        status: str = "scheduled",
        league_id: str | None = None,
    ) -> dict[str, Any]:
        """Get match schedule for specified date range.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            status: Match status filter
            league_id: Optional league UUID filter

        Returns:
            Dictionary with "matches" key containing list of matches
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_match_schedule(
            db_client=db_client,
            date_from=date_from,
            date_to=date_to,
            status=status,
            league_id=league_id)
        )

    @mcp_tool(
        description="Get detailed information for a specific match",
        input_schema={
            "type": "object",
            "properties": {
                "match_id": {
                    "type": "string",
                    "description": "Match UUID"
                }
            },
            "required": ["match_id"]
        }
    )
    def get_match_details(self, match_id: str) -> dict[str, Any]:
        """Get detailed information for a specific match.

        Args:
            match_id: Match UUID

        Returns:
            Dictionary with "match" key containing match details
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_match_details(db_client=db_client, match_id=match_id))

    @mcp_tool(
        description="Get all currently live matches",
        input_schema={
            "type": "object",
            "properties": {}
        }
    )
    def get_live_matches(self) -> dict[str, Any]:
        """Get all currently live matches.

        Returns:
            Dictionary with "matches" key containing list of live matches
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_live_matches(db_client=db_client))

    @mcp_tool(
        description="Search for matches by team name or other criteria",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                }
            },
            "required": ["query"]
        }
    )
    def search_matches(self, query: str) -> dict[str, Any]:
        """Search for matches by team name.

        Args:
            query: Search query string

        Returns:
            Dictionary with "matches" key containing matching matches
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(search_matches(db_client=db_client, query=query))

    @mcp_tool(
        description="Search for fixtures with flexible filtering (leagues, dates, odds availability)",
        input_schema={
            "type": "object",
            "properties": {
                "league_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of user-friendly league names (e.g., ['Premier League', 'LaLiga'])"
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date in ISO 8601 format (YYYY-MM-DD). Defaults to today."
                },
                "date_to": {
                    "type": "string",
                    "description": "End date in ISO 8601 format (YYYY-MM-DD). Defaults to today + 7 days."
                },
                "status": {
                    "type": "string",
                    "description": "Match status filter (scheduled, live, finished)",
                    "default": "scheduled"
                },
                "has_odds": {
                    "type": "boolean",
                    "description": "Only return matches with bookmaker odds available",
                    "default": True
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of fixtures to return",
                    "default": 100
                }
            },
            "required": []
        }
    )
    def search_fixtures(
        self,
        league_names: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str = "scheduled",
        has_odds: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Search for fixtures with flexible filtering.

        Designed for batch prediction requests like "20 odds in Premier League this weekend".
        Supports league name variations (EPL → Premier League), date ranges, and odds filtering.

        Args:
            league_names: List of user-friendly league names
            date_from: Start date (YYYY-MM-DD). Defaults to today.
            date_to: End date (YYYY-MM-DD). Defaults to today + 7 days.
            status: Match status filter. Default: "scheduled"
            has_odds: Only matches with odds. Default: True
            limit: Max fixtures to return. Default: 100

        Returns:
            Dictionary with "fixtures", "count", and "filters_applied" keys
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            search_fixtures(
                db_client=db_client,
                league_names=league_names,
                date_from=date_from,
                date_to=date_to,
                status=status,
                has_odds=has_odds,
                limit=limit,
            )
        )

    # ========================================================================
    # Team Tools (3)
    # ========================================================================

    @mcp_tool(
        description="Get team statistics for a season",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Team UUID"
                },
                "season": {
                    "type": "string",
                    "description": "Season (e.g., '2024-2025')"
                }
            },
            "required": ["team_id", "season"]
        }
    )
    def get_team_stats(self, team_id: str, season: str) -> dict[str, Any]:
        """Get team statistics for a season.

        Args:
            team_id: Team UUID
            season: Season (e.g., '2024-2025')

        Returns:
            Dictionary with team statistics
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_team_stats(
            db_client=db_client,
            team_id=team_id,
            season=season)
        )

    @mcp_tool(
        description="Get league standings/table",
        input_schema={
            "type": "object",
            "properties": {
                "league_id": {
                    "type": "string",
                    "description": "League UUID"
                },
                "season": {
                    "type": "string",
                    "description": "Season (e.g., '2024-2025')"
                }
            },
            "required": ["league_id", "season"]
        }
    )
    def get_league_table(self, league_id: str, season: str) -> dict[str, Any]:
        """Get league standings/table.

        Args:
            league_id: League UUID
            season: Season (e.g., '2024-2025')

        Returns:
            Dictionary with league standings
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_league_table(
            db_client=db_client,
            league_id=league_id,
            season=season)
        )

    @mcp_tool(
        description="Get head-to-head match history between two teams",
        input_schema={
            "type": "object",
            "properties": {
                "team1_id": {
                    "type": "string",
                    "description": "First team UUID"
                },
                "team2_id": {
                    "type": "string",
                    "description": "Second team UUID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of matches to return",
                    "default": 10
                }
            },
            "required": ["team1_id", "team2_id"]
        }
    )
    def get_head_to_head(
        self,
        team1_id: str,
        team2_id: str,
        limit: int = 10
    ) -> dict[str, Any]:
        """Get head-to-head match history.

        Args:
            team1_id: First team UUID
            team2_id: Second team UUID
            limit: Maximum number of matches

        Returns:
            Dictionary with H2H match history
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_head_to_head(
            db_client=db_client,
            team1_id=team1_id,
            team2_id=team2_id,
            limit=limit)
        )

    # ========================================================================
    # Historical Tools (2)
    # ========================================================================

    @mcp_tool(
        description="Query historical match data with filters",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Team UUID"
                },
                "league_id": {
                    "type": "string",
                    "description": "Optional league UUID filter"
                },
                "date_from": {
                    "type": "string",
                    "description": "Optional start date (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "description": "Optional end date (YYYY-MM-DD)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records",
                    "default": 20
                }
            },
            "required": ["team_id"]
        }
    )
    def query_history(
        self,
        team_id: str,
        league_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20
    ) -> dict[str, Any]:
        """Query historical match data.

        Args:
            team_id: Team UUID
            league_id: Optional league UUID filter
            date_from: Optional start date (YYYY-MM-DD)
            date_to: Optional end date (YYYY-MM-DD)
            limit: Maximum number of records

        Returns:
            Dictionary with historical match data
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(query_history(
            db_client=db_client,
            team_id=team_id,
            league_id=league_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit)
        )

    @mcp_tool(
        description="Get team form data (recent match results)",
        input_schema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Team UUID"
                },
                "num_matches": {
                    "type": "integer",
                    "description": "Number of recent matches",
                    "default": 5
                }
            },
            "required": ["team_id"]
        }
    )
    def get_form_data(
        self,
        team_id: str,
        num_matches: int = 5
    ) -> dict[str, Any]:
        """Get team form data (recent results).

        Args:
            team_id: Team UUID
            num_matches: Number of recent matches

        Returns:
            Dictionary with recent match results
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_form_data(
            db_client=db_client,
            team_id=team_id,
            num_matches=num_matches)
        )

    # ========================================================================
    # Odds Tools (2)
    # ========================================================================

    @mcp_tool(
        description="Get current betting odds for a match from multiple bookmakers",
        input_schema={
            "type": "object",
            "properties": {
                "match_id": {
                    "type": "string",
                    "description": "Match UUID"
                }
            },
            "required": ["match_id"]
        }
    )
    def get_match_odds(
        self,
        match_id: str
    ) -> dict[str, Any] | None:
        """Get current betting odds for a match.

        Args:
            match_id: Match UUID

        Returns:
            Dictionary with betting odds or None if no odds available
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_match_odds(
            db_client=db_client,
            match_id=match_id)
        )

    @mcp_tool(
        description="Track odds movements over time for a match",
        input_schema={
            "type": "object",
            "properties": {
                "match_id": {
                    "type": "string",
                    "description": "Match UUID"
                },
                "time_window": {
                    "type": "string",
                    "description": "Time window (1h, 6h, 12h, 24h, 48h, 7d)",
                    "default": "24h"
                }
            },
            "required": ["match_id"]
        }
    )
    def get_odds_movements(
        self,
        match_id: str,
        time_window: str = "24h"
    ) -> dict[str, Any] | None:
        """Get odds movement history.

        Args:
            match_id: Match UUID
            time_window: Time window for tracking movements

        Returns:
            Dictionary with odds movement history or None if no data available
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(get_odds_movements(
            db_client=db_client,
            match_id=match_id,
            time_window=time_window)
        )

    # ========================================================================
    # Statistical Analysis Tools - Phase 1: Core Tools (5)
    # ========================================================================

    @mcp_tool(
        description="Analyze head-to-head full-time results with recency weighting",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_full_time_result(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze head-to-head full-time results.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with H2H full-time result analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_full_time_result(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze total goals in h2h fixtures with over/under thresholds",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze total goals in h2h fixtures.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with H2H goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze both teams to score probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_bts(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze both teams to score probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with BTS probability analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_bts(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze home team goal-scoring capability (all home matches)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["team", "league"]
        }
    )
    def get_home_total_goals(
        self,
        team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze home team goal-scoring capability.

        Args:
            team: Team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with home team goal-scoring analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_home_total_goals(
                pool=db_client._pool,
                team=team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze away team goal-scoring capability (all away matches)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["team", "league"]
        }
    )
    def get_away_total_goals(
        self,
        team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze away team goal-scoring capability.

        Args:
            team: Team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with away team goal-scoring analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_away_total_goals(
                pool=db_client._pool,
                team=team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    # ========================================================================
    # Statistical Analysis Tools - Phase 2: Halftime Tools (5)
    # ========================================================================

    @mcp_tool(
        description="Analyze h2h halftime results with recency weighting",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_half_time_result(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze h2h halftime results.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with H2H halftime result analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_half_time_result(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze h2h second-half results with recency weighting",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_2nd_half_result(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze h2h second-half results.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with H2H second-half result analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_2nd_half_result(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze halftime/fulltime outcome combinations",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_ht_ft_outcome(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze halftime/fulltime outcome combinations.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with HT/FT outcome analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_ht_ft_outcome(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze halftime goals by team",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_half_time_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze halftime goals by team.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with halftime goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_half_time_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze second-half goals by team",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_2nd_half_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze second-half goals by team.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with second-half goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_2nd_half_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    # ========================================================================
    # Statistical Analysis Tools - Phase 3: Combination Markets (9)
    # ========================================================================

    @mcp_tool(
        description="Analyze double chance probability (Win OR Draw)",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_double_chance(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze double chance probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with double chance analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_double_chance(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze win OR total goals probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "goals_threshold": {"type": "number", "default": 2.5, "description": "Goals threshold (e.g., 2.5)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_win_or_total_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        goals_threshold: float = 2.5,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze win OR total goals probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            goals_threshold: Goals threshold
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with win OR total goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_win_or_total_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                goals_threshold=goals_threshold,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze win AND total goals probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "goals_threshold": {"type": "number", "default": 2.5, "description": "Goals threshold (e.g., 2.5)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_win_and_total_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        goals_threshold: float = 2.5,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze win AND total goals probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            goals_threshold: Goals threshold
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with win AND total goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_win_and_total_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                goals_threshold=goals_threshold,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze win OR both teams score probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_win_or_both_scores(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze win OR both teams score probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with win OR BTS analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_win_or_both_scores(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze win AND both teams score probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_win_and_both_scores(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze win AND both teams score probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with win AND BTS analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_win_and_both_scores(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze both teams score OR multi-goals probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "goals_threshold": {"type": "number", "default": 2.5, "description": "Goals threshold (e.g., 2.5)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_both_scores_or_multi_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        goals_threshold: float = 2.5,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze both teams score OR multi-goals probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            goals_threshold: Goals threshold
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with BTS OR multi-goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_both_scores_or_multi_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                goals_threshold=goals_threshold,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze no defeat AND total goals probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "goals_threshold": {"type": "number", "default": 2.5, "description": "Goals threshold (e.g., 2.5)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_no_defeat_and_total_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        goals_threshold: float = 2.5,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze no defeat AND total goals probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            goals_threshold: Goals threshold
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with no defeat AND total goals analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_no_defeat_and_total_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                goals_threshold=goals_threshold,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze avoid halftime defeat probability (Win OR Draw at HT)",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_avoid_halftime_defeat(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze avoid halftime defeat probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with avoid HT defeat analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_avoid_halftime_defeat(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze avoid 2nd-half defeat probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "perspective": {"type": "string", "enum": ["home", "away"], "default": "home", "description": "Perspective (home or away)"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_avoid_2nd_half_defeat(
        self,
        home_team: str,
        away_team: str,
        league: str,
        perspective: str = "home",
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze avoid 2nd-half defeat probability.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            perspective: Perspective (home or away)
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with avoid 2nd-half defeat analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_avoid_2nd_half_defeat(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                perspective=perspective,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    # ========================================================================
    # Statistical Analysis Tools - Phase 4: Specialized Analysis (5)
    # ========================================================================

    @mcp_tool(
        description="Analyze total goals range with percentiles",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_total_goals_range(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze total goals range with percentiles.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with total goals range analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_total_goals_range(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze which half home team wins (1st half, 2nd half, or both)",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_home_either_half_outcome(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze which half home team wins.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with home team either half outcome analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_home_either_half_outcome(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze which half away team wins (1st half, 2nd half, or both)",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_away_either_half_outcome(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze which half away team wins.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with away team either half outcome analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_away_either_half_outcome(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze probability that home team scores",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_home_to_score(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze probability that home team scores.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with home team to score analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_home_to_score(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze probability that away team scores",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_away_to_score(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze probability that away team scores.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League name
            seasons_back: Number of seasons to analyze
            current_form_matches: Number of recent matches for form analysis

        Returns:
            Dictionary with away team to score analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_away_to_score(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )
    # ========================================================================
    # Form Pattern Tools (7)
    # ========================================================================

    @mcp_tool(
        description="Detect consecutive winning/losing/drawing streaks to identify momentum",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 15, "description": "Number of recent matches to analyze"},
                "venue": {"type": "string", "enum": ["home", "away"], "description": "Optional venue filter"}
            },
            "required": ["team", "league"]
        }
    )
    def get_momentum_streak(
        self,
        team: str,
        league: str,
        match_limit: int = 15,
        venue: str | None = None
    ) -> dict[str, Any]:
        """Detect consecutive result streaks (winning/losing/drawing).

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            Dictionary with momentum streak analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_momentum_streak(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                venue=venue
            )
        )

    @mcp_tool(
        description="Compare recent vs previous form to identify improving/declining/stable patterns",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 10, "description": "Number of recent matches to analyze"},
                "venue": {"type": "string", "enum": ["home", "away"], "description": "Optional venue filter"}
            },
            "required": ["team", "league"]
        }
    )
    def get_form_trajectory(
        self,
        team: str,
        league: str,
        match_limit: int = 10,
        venue: str | None = None
    ) -> dict[str, Any]:
        """Analyze form trajectory (improving/declining/stable).

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            Dictionary with form trajectory analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_form_trajectory(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                venue=venue
            )
        )

    @mcp_tool(
        description="Measure form volatility and consistency (stable vs erratic)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 15, "description": "Number of recent matches to analyze"},
                "venue": {"type": "string", "enum": ["home", "away"], "description": "Optional venue filter"}
            },
            "required": ["team", "league"]
        }
    )
    def get_consistency_score(
        self,
        team: str,
        league: str,
        match_limit: int = 15,
        venue: str | None = None
    ) -> dict[str, Any]:
        """Analyze form consistency and volatility.

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            Dictionary with consistency score analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_consistency_score(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                venue=venue
            )
        )

    @mcp_tool(
        description="Analyze home vs away form differences to identify venue impact",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 15, "description": "Number of recent matches per venue"}
            },
            "required": ["team", "league"]
        }
    )
    def get_venue_form_split(
        self,
        team: str,
        league: str,
        match_limit: int = 15
    ) -> dict[str, Any]:
        """Analyze home vs away form differences.

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches per venue

        Returns:
            Dictionary with venue form split analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_venue_form_split(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit
            )
        )

    @mcp_tool(
        description="Analyze goals scored trajectory (increasing/decreasing/stable)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 10, "description": "Number of recent matches to analyze"},
                "venue": {"type": "string", "enum": ["home", "away"], "description": "Optional venue filter"}
            },
            "required": ["team", "league"]
        }
    )
    def get_goal_scoring_form_trend(
        self,
        team: str,
        league: str,
        match_limit: int = 10,
        venue: str | None = None
    ) -> dict[str, Any]:
        """Analyze goals scored trajectory (improving/declining).

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            Dictionary with goal scoring form trend analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_goal_scoring_form_trend(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                venue=venue
            )
        )

    @mcp_tool(
        description="Analyze goals conceded trajectory (tightening/leaking/stable)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 10, "description": "Number of recent matches to analyze"},
                "venue": {"type": "string", "enum": ["home", "away"], "description": "Optional venue filter"}
            },
            "required": ["team", "league"]
        }
    )
    def get_defensive_form_trend(
        self,
        team: str,
        league: str,
        match_limit: int = 10,
        venue: str | None = None
    ) -> dict[str, Any]:
        """Analyze goals conceded trajectory (tightening/leaking).

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            Dictionary with defensive form trend analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_defensive_form_trend(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                venue=venue
            )
        )

    @mcp_tool(
        description="Analyze form against strong opponents vs weaker opponents",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "match_limit": {"type": "integer", "default": 15, "description": "Number of recent matches to analyze"},
                "top_team_threshold": {"type": "number", "default": 2.0, "description": "Points per match threshold for strong teams"}
            },
            "required": ["team", "league"]
        }
    )
    def get_pressure_performance(
        self,
        team: str,
        league: str,
        match_limit: int = 15,
        top_team_threshold: float = 2.0
    ) -> dict[str, Any]:
        """Analyze form against strong opponents.

        Args:
            team: Team name
            league: League name
            match_limit: Number of recent matches to analyze
            top_team_threshold: Points per match threshold for strong teams

        Returns:
            Dictionary with pressure performance analysis
        """
        db_client, _ = self._ensure_connections()
        return self._run_async(
            form.get_pressure_performance(
                pool=db_client._pool,
                team=team,
                league=league,
                match_limit=match_limit,
                top_team_threshold=top_team_threshold
            )
        )
