"""API-Football client for direct API access with intelligent caching.

This client replaces Aurora database queries with direct API-Football calls,
providing fresher data and eliminating database inconsistency issues.

API Documentation: https://www.api-football.com/documentation-v3
Base URL: https://v3.football.api-sports.io
Auth: x-apisports-key header
"""

import logging
from typing import Any

import aiohttp

from sipap_data_mcp.cache.redis import RedisCache

logger = logging.getLogger(__name__)


# Cache TTL constants (in seconds)
class CacheTTL:
    """Cache TTL values by data volatility tier."""

    REALTIME = 300  # 5 minutes - live matches, odds
    SESSION = 3600  # 1 hour - match details, schedule
    DAILY = 21600  # 6 hours - team stats, standings, form
    HISTORICAL = 86400  # 24 hours - H2H, historical queries


class APIFootballClient:
    """Async client for API-Football with Redis caching.

    Provides direct access to API-Football endpoints with tiered caching:
    - Tier 1 (5 min): Live data, odds
    - Tier 2 (1 hr): Match details, schedule
    - Tier 3 (6 hr): Team stats, standings, form
    - Tier 4 (24 hr): H2H, historical data

    Example:
        ```python
        cache = RedisCache(url="redis://localhost:6379/0")
        await cache.connect()

        client = APIFootballClient(
            api_key="your-api-key",
            cache=cache
        )
        await client.connect()

        # Get fixtures for a league
        fixtures = await client.get_fixtures(
            league=140,
            season=2026,
            date="2026-08-19"
        )

        await client.close()
        ```
    """

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str, cache: RedisCache) -> None:
        """Initialize API-Football client.

        Args:
            api_key: API-Football API key (x-apisports-key)
            cache: Redis cache instance for response caching
        """
        self._api_key = api_key
        self._cache = cache
        self._session: aiohttp.ClientSession | None = None

    async def connect(self) -> None:
        """Create HTTP session for API requests."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"x-apisports-key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=30),
            )
            logger.info("API-Football client session created")

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("API-Football client session closed")

    def _ensure_connected(self) -> aiohttp.ClientSession:
        """Ensure session is connected.

        Returns:
            Active aiohttp session

        Raises:
            RuntimeError: If session not connected
        """
        if self._session is None or self._session.closed:
            raise RuntimeError(
                "API-Football client not connected. Call connect() first."
            )
        return self._session

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        cache_ttl: int = CacheTTL.SESSION,
        cache_key: str | None = None,
    ) -> dict[str, Any]:
        """Make cached API request.

        Args:
            endpoint: API endpoint (e.g., "fixtures", "standings")
            params: Query parameters
            cache_ttl: Cache time-to-live in seconds
            cache_key: Custom cache key (auto-generated if None)

        Returns:
            API response data

        Raises:
            RuntimeError: If session not connected
            aiohttp.ClientError: If API request fails
        """
        session = self._ensure_connected()

        # Generate cache key if not provided
        if cache_key is None:
            param_str = ":".join(
                f"{k}={v}" for k, v in sorted((params or {}).items())
            )
            cache_key = f"sipap:api:{endpoint}:{param_str}"

        # Check cache first
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        # Make API request
        url = f"{self.BASE_URL}/{endpoint}"
        logger.info(f"API request: {url} params={params}")

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data: dict[str, Any] = await response.json()

        # Log API usage (rate limits)
        if "errors" in data and data["errors"]:
            logger.warning(f"API errors: {data['errors']}")
            # Don't cache errors
            return data

        # Cache successful response
        results_count = data.get("results", 0)
        if results_count > 0:
            await self._cache.set(cache_key, data, ttl=cache_ttl)
            logger.debug(f"Cached {results_count} results: {cache_key}")

        return data

    # =========================================================================
    # Fixture Endpoints
    # =========================================================================

    async def get_fixtures(
        self,
        fixture_id: int | None = None,
        league: int | None = None,
        season: int | None = None,
        team: int | None = None,
        date: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        status: str | None = None,
        live: str | None = None,
        last: int | None = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Get fixtures (matches) with flexible filtering.

        API: GET /fixtures

        Args:
            fixture_id: Specific fixture ID
            league: League ID (e.g., 39 for Premier League)
            season: Season year (e.g., 2026)
            team: Team ID
            date: Specific date (YYYY-MM-DD)
            from_date: Start date for range
            to_date: End date for range
            status: Status filter (NS, 1H, 2H, HT, FT, etc.)
            live: "all" for all live matches
            last: Last N fixtures for a team
            timezone: Timezone (default: UTC)

        Returns:
            API response with fixtures in "response" key

        Example:
            ```python
            # Get today's Premier League fixtures
            fixtures = await client.get_fixtures(
                league=39,
                season=2026,
                date="2026-08-19"
            )

            # Get live matches
            live = await client.get_fixtures(live="all")

            # Get team's last 10 matches
            team_fixtures = await client.get_fixtures(
                team=50,  # Man City
                last=10
            )
            ```
        """
        params: dict[str, Any] = {"timezone": timezone}

        if fixture_id is not None:
            params["id"] = fixture_id
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if team is not None:
            params["team"] = team
        if date is not None:
            params["date"] = date
        if from_date is not None:
            params["from"] = from_date
        if to_date is not None:
            params["to"] = to_date
        if status is not None:
            params["status"] = status
        if live is not None:
            params["live"] = live
        if last is not None:
            params["last"] = last

        # Determine TTL based on request type
        ttl = CacheTTL.SESSION
        if live is not None:
            ttl = CacheTTL.REALTIME
        elif status in ("FT", "finished"):
            ttl = CacheTTL.HISTORICAL

        return await self._request("fixtures", params, cache_ttl=ttl)

    async def get_fixture_by_id(self, fixture_id: int) -> dict[str, Any]:
        """Get a specific fixture by ID.

        Args:
            fixture_id: API-Football fixture ID

        Returns:
            API response with single fixture
        """
        return await self.get_fixtures(fixture_id=fixture_id)

    async def get_live_fixtures(self) -> dict[str, Any]:
        """Get all currently live fixtures.

        Returns:
            API response with live fixtures
        """
        return await self.get_fixtures(live="all")

    async def get_h2h(
        self,
        team1_id: int,
        team2_id: int,
        last: int = 20,
    ) -> dict[str, Any]:
        """Get head-to-head fixtures between two teams.

        API: GET /fixtures/headtohead

        Args:
            team1_id: First team ID
            team2_id: Second team ID
            last: Number of recent matches (default: 20)

        Returns:
            API response with H2H fixtures

        Example:
            ```python
            h2h = await client.get_h2h(
                team1_id=50,  # Man City
                team2_id=42,  # Arsenal
                last=10
            )
            ```
        """
        params = {"h2h": f"{team1_id}-{team2_id}", "last": last}
        return await self._request(
            "fixtures/headtohead",
            params,
            cache_ttl=CacheTTL.HISTORICAL,
        )

    async def get_fixture_statistics(
        self,
        fixture_id: int,
        team: int | None = None,
    ) -> dict[str, Any]:
        """Get statistics for a fixture.

        API: GET /fixtures/statistics

        Args:
            fixture_id: Fixture ID
            team: Optional team ID filter

        Returns:
            API response with match statistics
        """
        params: dict[str, Any] = {"fixture": fixture_id}
        if team is not None:
            params["team"] = team
        return await self._request(
            "fixtures/statistics",
            params,
            cache_ttl=CacheTTL.SESSION,
        )

    async def get_fixture_events(
        self,
        fixture_id: int,
        team: int | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """Get events (goals, cards, subs) for a fixture.

        API: GET /fixtures/events

        Args:
            fixture_id: Fixture ID
            team: Optional team ID filter
            event_type: Optional event type (Goal, Card, Subst, Var)

        Returns:
            API response with match events
        """
        params: dict[str, Any] = {"fixture": fixture_id}
        if team is not None:
            params["team"] = team
        if event_type is not None:
            params["type"] = event_type
        return await self._request(
            "fixtures/events",
            params,
            cache_ttl=CacheTTL.SESSION,
        )

    async def get_fixture_lineups(self, fixture_id: int) -> dict[str, Any]:
        """Get lineups for a fixture.

        API: GET /fixtures/lineups

        Args:
            fixture_id: Fixture ID

        Returns:
            API response with team lineups
        """
        return await self._request(
            "fixtures/lineups",
            {"fixture": fixture_id},
            cache_ttl=CacheTTL.SESSION,
        )

    # =========================================================================
    # Team Endpoints
    # =========================================================================

    async def get_teams(
        self,
        team_id: int | None = None,
        league: int | None = None,
        season: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Get team information.

        API: GET /teams

        Args:
            team_id: Specific team ID
            league: League ID
            season: Season year
            search: Search by team name (min 3 chars)

        Returns:
            API response with team data
        """
        params: dict[str, Any] = {}
        if team_id is not None:
            params["id"] = team_id
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if search is not None:
            params["search"] = search
        return await self._request(
            "teams",
            params,
            cache_ttl=CacheTTL.HISTORICAL,
        )

    async def get_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: int,
    ) -> dict[str, Any]:
        """Get team statistics for a season.

        API: GET /teams/statistics

        Args:
            team_id: Team ID
            league_id: League ID
            season: Season year

        Returns:
            API response with comprehensive team stats

        Example:
            ```python
            stats = await client.get_team_statistics(
                team_id=50,  # Man City
                league_id=39,  # Premier League
                season=2026
            )
            ```
        """
        params = {"team": team_id, "league": league_id, "season": season}
        return await self._request(
            "teams/statistics",
            params,
            cache_ttl=CacheTTL.DAILY,
        )

    async def get_team_seasons(self, team_id: int) -> dict[str, Any]:
        """Get available seasons for a team.

        API: GET /teams/seasons

        Args:
            team_id: Team ID

        Returns:
            API response with available seasons
        """
        return await self._request(
            "teams/seasons",
            {"team": team_id},
            cache_ttl=CacheTTL.HISTORICAL,
        )

    # =========================================================================
    # League Endpoints
    # =========================================================================

    async def get_standings(
        self,
        league_id: int,
        season: int,
        team: int | None = None,
    ) -> dict[str, Any]:
        """Get league standings/table.

        API: GET /standings

        Args:
            league_id: League ID
            season: Season year
            team: Optional team ID filter

        Returns:
            API response with standings

        Example:
            ```python
            standings = await client.get_standings(
                league_id=39,  # Premier League
                season=2026
            )
            ```
        """
        params: dict[str, Any] = {"league": league_id, "season": season}
        if team is not None:
            params["team"] = team
        return await self._request(
            "standings",
            params,
            cache_ttl=CacheTTL.DAILY,
        )

    async def get_leagues(
        self,
        league_id: int | None = None,
        name: str | None = None,
        country: str | None = None,
        season: int | None = None,
        league_type: str | None = None,
    ) -> dict[str, Any]:
        """Get league information.

        API: GET /leagues

        Args:
            league_id: Specific league ID
            name: League name search
            country: Country name
            season: Season year
            league_type: "league" or "cup"

        Returns:
            API response with league data
        """
        params: dict[str, Any] = {}
        if league_id is not None:
            params["id"] = league_id
        if name is not None:
            params["name"] = name
        if country is not None:
            params["country"] = country
        if season is not None:
            params["season"] = season
        if league_type is not None:
            params["type"] = league_type
        return await self._request(
            "leagues",
            params,
            cache_ttl=CacheTTL.HISTORICAL,
        )

    # =========================================================================
    # Odds Endpoints
    # =========================================================================

    async def get_odds(
        self,
        fixture_id: int | None = None,
        league: int | None = None,
        season: int | None = None,
        date: str | None = None,
        bookmaker: int | None = None,
        bet: int | None = None,
    ) -> dict[str, Any]:
        """Get betting odds.

        API: GET /odds

        Args:
            fixture_id: Specific fixture ID
            league: League ID
            season: Season year
            date: Specific date
            bookmaker: Bookmaker ID
            bet: Bet type ID (1 = Match Winner)

        Returns:
            API response with odds data

        Example:
            ```python
            odds = await client.get_odds(fixture_id=1234567)
            ```
        """
        params: dict[str, Any] = {}
        if fixture_id is not None:
            params["fixture"] = fixture_id
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if date is not None:
            params["date"] = date
        if bookmaker is not None:
            params["bookmaker"] = bookmaker
        if bet is not None:
            params["bet"] = bet
        return await self._request(
            "odds",
            params,
            cache_ttl=CacheTTL.REALTIME,
        )

    # =========================================================================
    # Other Endpoints
    # =========================================================================

    async def get_injuries(
        self,
        fixture_id: int | None = None,
        league: int | None = None,
        season: int | None = None,
        team: int | None = None,
    ) -> dict[str, Any]:
        """Get injury information.

        API: GET /injuries

        Args:
            fixture_id: Fixture ID
            league: League ID
            season: Season year
            team: Team ID

        Returns:
            API response with injury data
        """
        params: dict[str, Any] = {}
        if fixture_id is not None:
            params["fixture"] = fixture_id
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if team is not None:
            params["team"] = team
        return await self._request(
            "injuries",
            params,
            cache_ttl=CacheTTL.DAILY,
        )

    async def get_predictions(self, fixture_id: int) -> dict[str, Any]:
        """Get predictions for a fixture.

        API: GET /predictions

        Args:
            fixture_id: Fixture ID

        Returns:
            API response with prediction data
        """
        return await self._request(
            "predictions",
            {"fixture": fixture_id},
            cache_ttl=CacheTTL.HISTORICAL,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def resolve_team_id(
        self,
        team_name: str,
        league_id: int,
        season: int | None = None,
    ) -> int | None:
        """Resolve team name to API-Football team ID.

        Performs fuzzy matching against teams in the specified league.
        Results are cached for 30 days.

        Args:
            team_name: Team name to search for
            league_id: League ID to search within
            season: Season year (default: current year)

        Returns:
            Team ID if found, None otherwise

        Example:
            ```python
            team_id = await client.resolve_team_id(
                team_name="Man City",
                league_id=39  # Premier League
            )
            # Returns: 50
            ```
        """
        if season is None:
            from datetime import datetime
            season = datetime.now().year

        # Check cache first
        cache_key = f"sipap:team_resolve:{league_id}:{team_name.lower()}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return int(cached.get("team_id")) if cached.get("team_id") else None

        # Fetch teams in league
        teams_data = await self.get_teams(league=league_id, season=season)
        teams = teams_data.get("response", [])

        # Normalize search term
        search_lower = team_name.lower().strip()

        # Try exact match first, then partial
        for team_info in teams:
            team = team_info.get("team", {})
            team_name_api = team.get("name", "")

            # Exact match
            if team_name_api.lower() == search_lower:
                team_id = team.get("id")
                await self._cache.set(
                    cache_key,
                    {"team_id": team_id},
                    ttl=86400 * 30,  # 30 days
                )
                return team_id

        # Partial match
        for team_info in teams:
            team = team_info.get("team", {})
            team_name_api = team.get("name", "")

            if search_lower in team_name_api.lower() or team_name_api.lower() in search_lower:
                team_id = team.get("id")
                await self._cache.set(
                    cache_key,
                    {"team_id": team_id},
                    ttl=86400 * 30,  # 30 days
                )
                return team_id

        # Not found
        logger.warning(f"Team '{team_name}' not found in league {league_id}")
        return None
