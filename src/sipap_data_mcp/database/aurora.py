"""Aurora PostgreSQL database client for sports data access.

This module provides async database access to SIPAP's normalized sports data schema.
Implements connection pooling, query timeout handling, and proper resource cleanup.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

# Initialize logger for this module
logger = logging.getLogger(__name__)


class AuroraDataClient:
    """Async client for Aurora PostgreSQL database operations.

    Provides read-only access to sports data (matches, teams, leagues, odds).
    Implements connection pooling for efficient resource usage.

    Example:
        ```python
        client = AuroraDataClient(
            host="sipap-aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
            port=5432,
            database="sipap",
            user="sipap_readonly",
            password="secret"
        )

        await client.connect()

        matches = await client.get_matches(
            date_from="2026-07-05",
            date_to="2026-07-12",
            status="scheduled"
        )

        await client.close()
        ```

    Attributes:
        _pool: asyncpg connection pool (None until connect() called)
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> None:
        """Initialize Aurora database client.

        Args:
            host: Aurora cluster endpoint
            port: Database port (typically 5432)
            database: Database name
            user: Database username
            password: Database password
        """
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Create database connection pool.

        Establishes connection pool with:
        - Min connections: 2
        - Max connections: 10
        - Query timeout: 5 seconds
        - Pool acquire timeout: 30 seconds

        Raises:
            asyncpg.PostgresError: If connection fails
        """
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password,
            # ssl=False - Disabled SSL for Lambda → RDS within VPC (already encrypted at network level)
            min_size=2,
            max_size=10,
            command_timeout=5.0,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close database connection pool and release resources.

        Should be called when client is no longer needed to prevent
        connection leaks.
        """
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def get_matches(
        self,
        date_from: str,
        date_to: str,
        status: str,
        league_id: str | None = None,
        has_odds: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve matches from database within date range.

        Args:
            date_from: Start date in ISO 8601 format (YYYY-MM-DD)
            date_to: End date in ISO 8601 format (YYYY-MM-DD)
            status: Match status filter (scheduled, live, finished)
            league_id: Optional league name filter (e.g., "allsvenskan", "premier-league")
                      Note: Named league_id for backward compatibility, but accepts names
            has_odds: Only include matches with odds available (default: False)

        Returns:
            List of match dictionaries with keys:
            - id, external_id, scheduled_at, status
            - home_team, away_team, home_team_id, away_team_id
            - league, league_id
            - home_score, away_score, metadata

        Raises:
            ValueError: If date_from or date_to are invalid ISO 8601 dates
            RuntimeError: If client not connected
            asyncio.TimeoutError: If pool is exhausted
            asyncpg.QueryCanceledError: If query exceeds 5s timeout

        Example:
            ```python
            # Get all matches
            matches = await client.get_matches(
                date_from="2026-07-05",
                date_to="2026-07-12",
                status="scheduled",
                league_id="550e8400-e29b-41d4-a716-446655440000"
            )

            # Get only matches with odds
            matches_with_odds = await client.get_matches(
                date_from="2026-07-05",
                date_to="2026-07-12",
                status="scheduled",
                has_odds=True
            )
            ```
        """
        # Validate inputs
        self._validate_dates(date_from, date_to)
        self._ensure_connected()

        # Build query and parameters
        query, params = self._build_matches_query(
            date_from=date_from,
            date_to=date_to,
            status=status,
            league_id=league_id,
            has_odds=has_odds,
        )

        # DEBUG: Log query parameters
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"get_matches() - date_from={date_from}, date_to={date_to}, "
            f"status={status}, league_id={league_id}, has_odds={has_odds}, "
            f"params={params}"
        )

        # Execute query
        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, *params)
            logger.info(f"get_matches() - returned {len(records)} records")

        # Convert asyncpg.Record to JSON-serializable dict
        return [self._record_to_dict(record) for record in records]

    def _record_to_dict(self, record: asyncpg.Record) -> dict[str, Any]:
        """Convert asyncpg.Record to JSON-serializable dict.

        Handles type conversions:
        - UUID objects → strings
        - datetime objects → ISO strings
        - Decimal objects → floats
        - All other types → as-is

        Args:
            record: asyncpg.Record from database query

        Returns:
            JSON-serializable dictionary
        """
        result: dict[str, Any] = {}
        for key, value in dict(record).items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key] = float(value)
            else:
                result[key] = value
        return result

    def _parse_date(self, date_str: str) -> date:
        """Parse ISO 8601 date string to datetime.date object.

        Args:
            date_str: Date string in ISO 8601 format (YYYY-MM-DD)

        Returns:
            datetime.date object

        Raises:
            ValueError: If date string is not valid ISO 8601 format
        """
        try:
            return datetime.fromisoformat(date_str).date()
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{date_str}': "
                f"Expected ISO 8601 format (YYYY-MM-DD)"
            ) from e

    def _validate_dates(self, date_from: str, date_to: str) -> None:
        """Validate date formats are ISO 8601 compliant.

        Args:
            date_from: Start date string
            date_to: End date string

        Raises:
            ValueError: If either date is not valid ISO 8601 format
        """
        self._parse_date(date_from)  # Validates format
        self._parse_date(date_to)  # Validates format

    def _ensure_connected(self) -> None:
        """Verify client is connected to database.

        Raises:
            RuntimeError: If client not connected
        """
        if self._pool is None:
            raise RuntimeError(
                "Client not connected. Call connect() before using database operations."
            )

    def _build_matches_query(
        self,
        date_from: str,
        date_to: str,
        status: str,
        league_id: str | None,
        has_odds: bool = False,
    ) -> tuple[str, tuple[Any, ...]]:
        """Build SQL query and parameters for matches retrieval.

        Args:
            date_from: Start date in ISO 8601 format
            date_to: End date in ISO 8601 format
            status: Match status filter
            league_id: Optional league name filter (e.g., "allsvenskan", "premier-league")
            has_odds: Only include matches with odds available (checks metadata)

        Returns:
            Tuple of (query string, parameters tuple)
        """
        # Base SELECT clause with odds and team API IDs from metadata JSONB
        # Reads from matches.metadata->'odds'->'best_odds' where odds updater stores them
        # Also reads team API IDs from metadata for team_statistics lookup
        select_clause = """
            SELECT
                m.id, m.external_id, m.scheduled_at, m.status,
                m.home_team, m.away_team,
                m.home_team_id, m.away_team_id,
                -- Team API-Football IDs from metadata (for team_statistics lookup)
                (m.metadata->>'home_team_api_id')::text as home_team_external_id,
                (m.metadata->>'away_team_api_id')::text as away_team_external_id,
                m.league, m.league_id,
                m.home_score, m.away_score, m.metadata,
                -- Extract odds from metadata JSONB
                (m.metadata->'odds'->'best_odds'->>'home')::float as best_home_odds,
                (m.metadata->'odds'->'best_odds'->>'draw')::float as best_draw_odds,
                (m.metadata->'odds'->'best_odds'->>'away')::float as best_away_odds,
                CASE WHEN m.metadata->'odds'->'best_odds' IS NOT NULL THEN 1 ELSE 0 END as bookmakers_count
            FROM matches m
        """

        # Build WHERE clause and parameters
        params: tuple[Any, ...]  # Allow mixed types (date, str, etc.)

        # Base WHERE conditions (use table alias m.)
        # Convert ISO date strings to datetime.date for asyncpg
        # IMPORTANT: Cast scheduled_at to date for comparison to include entire day
        # Without ::date cast, "scheduled_at <= '2026-08-10'" means "<= 2026-08-10 00:00:00"
        # which excludes matches at 15:30, 20:00, etc. on that date
        where_conditions = [
            "m.scheduled_at::date >= $1",
            "m.scheduled_at::date <= $2",
            "m.status IN ('NS', 'scheduled')",  # Support both API-Football 'NS' and legacy 'scheduled'
        ]
        base_params: list[Any] = [
            self._parse_date(date_from),  # Convert to datetime.date
            self._parse_date(date_to),  # Convert to datetime.date
        ]

        # Add league filter if specified
        # Note: league_id parameter now accepts league names (e.g., "allsvenskan")
        # because batch-scraper stores denormalized league names in m.league column
        # Use ILIKE for case-insensitive matching (allsvenskan matches Allsvenskan)
        if league_id is not None:
            where_conditions.append(f"m.league ILIKE ${len(base_params) + 1}")
            base_params.append(league_id)

        # Add odds filter if requested (checks metadata JSONB)
        if has_odds:
            where_conditions.append("m.metadata->'odds'->'best_odds' IS NOT NULL")

        where_clause = f"""
            WHERE {' AND '.join(where_conditions)}
            ORDER BY m.scheduled_at ASC
        """
        params = tuple(base_params)

        # Log the built query for debugging
        full_query = select_clause + where_clause
        logger.debug(f"Built SQL query: {full_query}")
        logger.debug(f"Query parameters: {params}")

        return (full_query, params)

    async def get_match(self, match_id: str) -> dict[str, Any] | None:
        """Retrieve a single match by ID.

        Args:
            match_id: Match UUID

        Returns:
            Match dictionary or None if not found

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            match = await client.get_match(
                match_id="550e8400-e29b-41d4-a716-446655440000"
            )
            ```
        """
        self._ensure_connected()

        # Query with team API IDs from metadata (primary) or teams table (fallback)
        # The metadata contains home_team_api_id and away_team_api_id from API-Football
        # This allows team_statistics lookup without requiring teams.external_id to be populated
        query = """
            SELECT
                m.id, m.external_id, m.scheduled_at, m.status,
                m.home_team, m.away_team,
                m.home_team_id, m.away_team_id,
                COALESCE(
                    (m.metadata->>'home_team_api_id')::text,
                    ht.external_id
                ) AS home_team_external_id,
                COALESCE(
                    (m.metadata->>'away_team_api_id')::text,
                    at.external_id
                ) AS away_team_external_id,
                m.league, m.league_id,
                m.home_score, m.away_score, m.metadata
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.id
            LEFT JOIN teams at ON m.away_team_id = at.id
            WHERE m.id = $1
        """

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, match_id)

        if record is None:
            return None

        return self._record_to_dict(record)

    async def search_matches(self, query: str) -> list[dict[str, Any]]:
        """Search for matches by team name or other criteria.

        Args:
            query: Search query string

        Returns:
            List of match dictionaries

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            matches = await client.search_matches(query="Arsenal")
            ```
        """
        self._ensure_connected()

        # Search by team name (home or away) using denormalized columns
        search_query = """
            SELECT
                m.id, m.external_id, m.scheduled_at, m.status,
                m.home_team, m.away_team,
                m.home_team_id, m.away_team_id,
                m.league, m.league_id,
                m.home_score, m.away_score, m.metadata
            FROM matches m
            WHERE m.home_team ILIKE $1
               OR m.away_team ILIKE $1
            ORDER BY m.scheduled_at DESC
            LIMIT 100
        """

        # Add wildcards for partial matching
        search_term = f"%{query}%"

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(search_query, search_term)

        return [self._record_to_dict(record) for record in records]

    async def get_team_stats(
        self,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any] | None:
        """Retrieve team statistics for a specific season.

        UPDATED: Now queries team_statistics table (Phase 3 schema).
        OLD: Queried team_stats table with UUID
        NEW: Queries team_statistics table with integer IDs from API-Football

        Args:
            team_id: API-Football team ID (e.g., 50 for Manchester City)
            league_id: API-Football league ID (e.g., 39 for Premier League)
            season: Season year as string (e.g., "2024" for 2024-2025 season)

        Returns:
            Team statistics dictionary with home/away/total splits, or None if not found

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            stats = await client.get_team_stats(
                team_id=50,
                league_id=39,
                season="2024"
            )
            ```
        """
        return await self.get_team_statistics(team_id, league_id, season)

    async def get_league_table(
        self,
        league_id: int,
        season: str,
    ) -> list[dict[str, Any]]:
        """Retrieve league table/standings for a specific season.

        UPDATED: Now queries standings table (Phase 3 schema).
        OLD: Queried league_standings table with UUID, computed from matches on-the-fly
        NEW: Queries pre-computed standings table with integer IDs (faster, more accurate)

        Args:
            league_id: API-Football league ID (e.g., 39 for Premier League)
            season: Season year as string (e.g., "2024" for 2024-2025 season)

        Returns:
            List of team standings sorted by rank (1st place first)

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            standings = await client.get_league_table(
                league_id=39,
                season="2024"
            )
            ```
        """
        return await self.get_standings(league_id, season)

    async def get_head_to_head(
        self,
        home_team_id: int,
        away_team_id: int,
    ) -> dict[str, Any]:
        """Retrieve head-to-head statistics between two teams.

        UPDATED: Now queries head_to_head table (Phase 3 schema).
        OLD: Queried matches table with complex logic:
             WHERE (home = A AND away = B) OR (home = B AND away = A)
        NEW: Queries pre-computed head_to_head table (faster, includes last 10 matches)

        Args:
            home_team_id: API-Football home team ID (e.g., 50 for Manchester City)
            away_team_id: API-Football away team ID (e.g., 42 for Arsenal)

        Returns:
            Head-to-head statistics dictionary with:
            - team_1_id, team_2_id (auto-ordered: team_1_id < team_2_id)
            - last_10_matches (JSONB array of recent matches)
            - team_1_wins, team_2_wins, draws
            Returns empty structure if no H2H history exists.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            h2h = await client.get_head_to_head(
                home_team_id=50,  # Man City
                away_team_id=42   # Arsenal
            )
            # Returns: {
            #   "team_1_id": 42, "team_2_id": 50,
            #   "team_1_wins": 5, "team_2_wins": 3, "draws": 2,
            #   "last_10_matches": [...]
            # }
            ```
        """
        h2h_stats = await self.get_head_to_head_stats(home_team_id, away_team_id)

        if not h2h_stats:
            # Return empty structure if no H2H data
            return {
                'team_1_id': min(home_team_id, away_team_id),
                'team_2_id': max(home_team_id, away_team_id),
                'last_10_matches': [],
                'team_1_wins': 0,
                'team_2_wins': 0,
                'draws': 0,
            }

        return h2h_stats

    async def query_match_history(
        self,
        team_id: str,
        league_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query historical match data for a team.

        Args:
            team_id: Team UUID
            league_id: Optional league UUID filter
            date_from: Optional start date in ISO 8601 format
            date_to: Optional end date in ISO 8601 format
            limit: Maximum number of matches to return

        Returns:
            List of finished matches ordered by date (most recent first)

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            matches = await client.query_match_history(
                team_id="team-uuid-1",
                date_from="2026-01-01",
                date_to="2026-06-30",
                limit=50
            )
            ```
        """
        self._ensure_connected()

        # Build query dynamically based on filters
        # Note: This method expects team_id but data is denormalized - will return empty until foreign keys populated
        query_parts = [
            """
            SELECT
                m.id, m.external_id, m.scheduled_at, m.status,
                m.home_team, m.away_team,
                m.home_team_id, m.away_team_id,
                m.league, m.league_id,
                m.home_score, m.away_score, m.metadata
            FROM matches m
            WHERE m.status = 'finished'
              AND (m.home_team_id = $1 OR m.away_team_id = $1)
            """
        ]

        params: list[Any] = [team_id]
        param_idx = 2

        # Add league filter if provided
        if league_id is not None:
            query_parts.append(f"  AND m.league_id = ${param_idx}")
            params.append(league_id)
            param_idx += 1

        # Add date range filters if provided (convert ISO strings to date objects)
        if date_from is not None:
            query_parts.append(f"  AND m.scheduled_at >= ${param_idx}")
            params.append(self._parse_date(date_from))  # Convert to datetime.date
            param_idx += 1

        if date_to is not None:
            query_parts.append(f"  AND m.scheduled_at <= ${param_idx}")
            params.append(self._parse_date(date_to))  # Convert to datetime.date
            param_idx += 1

        # Order by most recent first and apply limit
        query_parts.append("ORDER BY m.scheduled_at DESC")
        query_parts.append(f"LIMIT ${param_idx}")
        params.append(limit)

        query = "\n".join(query_parts)

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, *params)

        return [self._record_to_dict(record) for record in records]

    async def get_match_odds(
        self,
        fixture_id: int,
        is_live: bool = False,
    ) -> list[dict[str, Any]]:
        """Get betting odds for a match from matches.metadata JSONB.

        Reads odds from matches.metadata->'odds'->'best_odds' where the
        odds updater stores aggregated best odds across all bookmakers.

        Args:
            fixture_id: API-Football fixture ID (stored as external_id in matches)
            is_live: Whether to fetch live odds (default: False for pre-match)
                     Note: Live odds not currently supported in metadata storage

        Returns:
            List with single odds record containing best odds. Each record contains:
            fixture_id, bookmaker_id, bookmaker_name, market, home_odds,
            draw_odds, away_odds, is_live, updated_at.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            odds = await client.get_match_odds(fixture_id=1234567)
            # Returns: [
            #   {
            #     "fixture_id": 1234567,
            #     "bookmaker_id": 0,
            #     "bookmaker_name": "Best Odds",
            #     "market": "1X2",
            #     "home_odds": 1.85,
            #     "draw_odds": 3.40,
            #     "away_odds": 4.20,
            #     "is_live": false,
            #     "updated_at": "2026-08-16T13:39:48"
            #   }
            # ]
            ```
        """
        self._ensure_connected()

        # Query matches.metadata for odds (where odds updater stores them)
        query = """
            SELECT
                external_id,
                metadata->'odds'->'best_odds'->>'home' as home_odds,
                metadata->'odds'->'best_odds'->>'draw' as draw_odds,
                metadata->'odds'->'best_odds'->>'away' as away_odds,
                metadata->'odds'->>'updated_at' as updated_at
            FROM matches
            WHERE external_id = $1
              AND metadata->'odds'->'best_odds' IS NOT NULL
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, str(fixture_id))

        if not row:
            return []

        # Convert to expected format (list of odds records)
        home_odds = float(row['home_odds']) if row['home_odds'] else None
        draw_odds = float(row['draw_odds']) if row['draw_odds'] else None
        away_odds = float(row['away_odds']) if row['away_odds'] else None

        return [{
            'fixture_id': fixture_id,
            'bookmaker_id': 0,
            'bookmaker_name': 'Best Odds',
            'market': '1X2',
            'home_odds': home_odds,
            'draw_odds': draw_odds,
            'away_odds': away_odds,
            'is_live': is_live,
            'updated_at': row['updated_at'],
        }]

    async def get_odds_movements(
        self,
        match_id: str,
        time_window: str = "24h",
    ) -> dict[str, Any] | None:
        """Get odds movements over time for a match.

        Args:
            match_id: Match UUID
            time_window: Time window (1h, 6h, 12h, 24h, 48h, 7d)

        Returns:
            Dictionary with movement data (movements, opening_odds, current_odds)
            or None if no movements available

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            movements = await client.get_odds_movements("match-uuid-1", "24h")
            # Returns: {"movements": [...], "opening_odds": {...}, ...}
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                id AS match_id,
                metadata->'odds_history' AS odds_history
            FROM matches
            WHERE id = $1
              AND metadata ? 'odds_history'
        """

        assert self._pool is not None
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, match_id)

        if record is None or record["odds_history"] is None:
            return None

        # Parse odds history from JSONB
        odds_history = dict(record["odds_history"])

        return {
            "match_id": record["match_id"],
            "time_window": time_window,
            "movements": odds_history.get("movements", []),
            "opening_odds": odds_history.get("opening_odds", {}),
            "current_odds": odds_history.get("current_odds", {}),
            "movement_summary": odds_history.get("movement_summary", {}),
        }

    # ================================================================================
    # Phase 3 Schema Methods (API-Football Integration)
    # ================================================================================
    # These methods query dedicated Phase 3 tables populated by sipap-batch-scraper
    # jobs. They replace JSONB queries with proper relational schema for better
    # performance and data integrity.

    async def get_standings(
        self,
        league_id: int,
        season: str,
    ) -> list[dict[str, Any]]:
        """Retrieve league standings from standings table.

        Args:
            league_id: API-Football league ID (e.g., 39 for Premier League)
            season: Season year as string (e.g., "2024" for 2024-2025 season)

        Returns:
            List of standings records ordered by rank (1st place first).
            Each record contains: team_id, team_name, rank, points, played,
            wins, draws, losses, goals_for, goals_against, goal_difference,
            form, home/away splits.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            standings = await client.get_standings(
                league_id=39,  # Premier League
                season="2024"
            )
            # Returns: [{"rank": 1, "team_name": "Arsenal", ...}, ...]
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                team_id, team_name, rank, points, played,
                wins, draws, losses, goals_for, goals_against,
                goal_difference, form,
                home_played, home_wins, home_draws, home_losses,
                away_played, away_wins, away_draws, away_losses
            FROM standings
            WHERE league_id = $1 AND season = $2
            ORDER BY rank ASC
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, league_id, season)

        return [self._record_to_dict(row) for row in rows]

    async def get_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any] | None:
        """Retrieve team statistics from team_statistics table.

        Returns comprehensive team statistics with home/away/total splits (27 columns).

        Args:
            team_id: API-Football team ID (e.g., 50 for Manchester City)
            league_id: API-Football league ID (e.g., 39 for Premier League)
            season: Season year as string (e.g., "2024")

        Returns:
            Team statistics record with form and detailed splits, or None if not found.
            Includes: total_*, home_*, away_* columns for matches, wins, goals, etc.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            stats = await client.get_team_statistics(
                team_id=50,
                league_id=39,
                season="2024"
            )
            # Returns: {"total_played": 38, "home_wins": 15, ...}
            ```
        """
        self._ensure_connected()

        query = """
            SELECT * FROM team_statistics
            WHERE team_id = $1 AND league_id = $2 AND season = $3
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, team_id, league_id, season)

        if not row:
            return None

        # Convert to dict and map column names to expected format
        stats = self._record_to_dict(row)

        # Map database column names (matches_played_*) to expected format (total_*)
        # Database schema: matches_played_home, wins_total, etc.
        # Expected format: home_played, total_wins, etc.
        column_mapping = {
            # Home stats
            "matches_played_home": "home_played",
            # Away stats
            "matches_played_away": "away_played",
            # Total stats
            "matches_played_total": "total_played",
            "wins_total": "total_wins",
            "draws_total": "total_draws",
            "losses_total": "total_losses",
            "goals_for_total": "total_goals_for",
            "goals_against_total": "total_goals_against",
        }

        # Apply column name mapping
        mapped_stats = {}
        for db_col, expected_col in column_mapping.items():
            if db_col in stats:
                mapped_stats[expected_col] = stats[db_col]

        # Keep all other columns as-is (id, team_id, league_id, season, home_*, away_*, clean_sheets_*, etc.)
        for key, value in stats.items():
            if key not in column_mapping:
                mapped_stats[key] = value

        return mapped_stats

    async def get_injuries(
        self,
        fixture_id: int,
    ) -> list[dict[str, Any]]:
        """Retrieve player injuries for a specific fixture.

        Args:
            fixture_id: API-Football fixture ID

        Returns:
            List of injury records for the fixture. Each record contains:
            player_id, player_name, player_photo, team_id, team_name,
            injury_type, injury_reason, expected_return_date.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            injuries = await client.get_injuries(fixture_id=1234567)
            # Returns: [{"player_name": "Bukayo Saka", "injury_type": "Muscle", ...}, ...]
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                player_id, player_name, player_photo,
                team_id, team_name,
                injury_type, injury_reason, expected_return_date
            FROM injuries
            WHERE fixture_id = $1
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, fixture_id)

        return [self._record_to_dict(row) for row in rows]

    async def get_lineups(
        self,
        fixture_id: int,
    ) -> dict[str, Any] | None:
        """Retrieve team lineups for a specific fixture.

        Args:
            fixture_id: API-Football fixture ID

        Returns:
            Dictionary with fixture_id, home_team_lineup (JSONB), away_team_lineup (JSONB),
            or None if lineups not available yet.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            lineups = await client.get_lineups(fixture_id=1234567)
            # Returns: {
            #   "fixture_id": 1234567,
            #   "home_team_lineup": {"formation": "4-3-3", "startXI": [...], ...},
            #   "away_team_lineup": {"formation": "4-2-3-1", "startXI": [...], ...}
            # }
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                fixture_id,
                home_team_lineup,
                away_team_lineup
            FROM lineups
            WHERE fixture_id = $1
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, fixture_id)

        return self._record_to_dict(row) if row else None

    async def get_head_to_head_stats(
        self,
        team_1_id: int,
        team_2_id: int,
    ) -> dict[str, Any] | None:
        """Retrieve head-to-head statistics between two teams.

        Automatically orders team IDs (team_1_id < team_2_id) to match database constraint.

        Args:
            team_1_id: API-Football team ID (e.g., 50 for Manchester City)
            team_2_id: API-Football team ID (e.g., 42 for Arsenal)

        Returns:
            H2H statistics record with:
            - team_1_id, team_2_id (ordered: team_1_id < team_2_id)
            - last_10_matches (JSONB array of recent matches)
            - team_1_wins, team_2_wins, draws
            Returns None if no H2H history exists.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            h2h = await client.get_head_to_head_stats(
                team_1_id=50,  # Man City
                team_2_id=42   # Arsenal
            )
            # Returns: {
            #   "team_1_id": 42, "team_2_id": 50,  # Auto-swapped for ordering
            #   "team_1_wins": 5, "team_2_wins": 3, "draws": 2,
            #   "last_10_matches": [...]
            # }
            ```
        """
        self._ensure_connected()

        # Ensure correct ordering (team_1_id < team_2_id to match constraint)
        team_a = min(team_1_id, team_2_id)
        team_b = max(team_1_id, team_2_id)

        query = """
            SELECT
                team_1_id, team_2_id,
                last_10_matches,
                team_1_wins, team_2_wins, draws
            FROM head_to_head
            WHERE team_1_id = $1 AND team_2_id = $2
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, team_a, team_b)

        return self._record_to_dict(row) if row else None

    async def get_teams_metadata(
        self,
        team_ids: list[int],
    ) -> list[dict[str, Any]]:
        """Retrieve team metadata for multiple teams.

        Args:
            team_ids: List of API-Football team IDs (e.g., [50, 42, 40])

        Returns:
            List of team metadata records. Each record contains:
            team_id, team_name, team_logo, team_code, country,
            founded, venue_name, venue_capacity.

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            metadata = await client.get_teams_metadata(team_ids=[50, 42, 40])
            # Returns: [
            #   {"team_id": 50, "team_name": "Manchester City", "team_logo": "...", ...},
            #   {"team_id": 42, "team_name": "Arsenal", ...},
            #   ...
            # ]
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                team_id, team_name, team_logo, team_code,
                country, founded, venue_name, venue_capacity
            FROM teams_metadata
            WHERE team_id = ANY($1::int[])
        """

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, team_ids)

        return [self._record_to_dict(row) for row in rows]

    async def get_matches_by_external_league_id(
        self,
        external_league_id: str,
        date_from: str,
        date_to: str,
        status: str,
        has_odds: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve matches by API-Football league ID.

        ID-FIRST ARCHITECTURE: Uses API-Football league ID for unambiguous resolution.
        This eliminates string matching ambiguity (e.g., "Premier League" exists in
        multiple countries: England=39, Wales=113, Belarus=117).

        The external_league_id maps to the leagues.external_id column, which stores
        API-Football competition IDs.

        Args:
            external_league_id: API-Football league ID (e.g., "140" for La Liga, "39" for Premier League England)
            date_from: Start date in ISO 8601 format (YYYY-MM-DD)
            date_to: End date in ISO 8601 format (YYYY-MM-DD)
            status: Match status filter (scheduled, live, finished, NS)
            has_odds: Only include matches with odds available (default: False)

        Returns:
            List of match dictionaries with keys:
            - id, external_id, scheduled_at, status
            - home_team, away_team, home_team_id, away_team_id
            - league, league_id, league_external_id
            - home_score, away_score, metadata
            - best_home_odds, best_draw_odds, best_away_odds, bookmakers_count

        Raises:
            ValueError: If date_from or date_to are invalid ISO 8601 dates
            RuntimeError: If client not connected

        Example:
            ```python
            # Get La Liga matches (ID 140)
            matches = await client.get_matches_by_external_league_id(
                external_league_id="140",
                date_from="2026-08-15",
                date_to="2026-08-22",
                status="NS"
            )

            # Get Premier League England matches (ID 39) with odds
            matches = await client.get_matches_by_external_league_id(
                external_league_id="39",
                date_from="2026-08-15",
                date_to="2026-08-22",
                status="NS",
                has_odds=True
            )
            ```
        """
        # Validate inputs
        self._validate_dates(date_from, date_to)
        self._ensure_connected()

        # Build SELECT clause with league join
        # Reads odds from matches.metadata->'odds'->'best_odds' where odds updater stores them
        select_clause = """
            SELECT
                m.id, m.external_id, m.scheduled_at, m.status,
                m.home_team, m.away_team,
                m.home_team_id, m.away_team_id,
                m.league, m.league_id,
                l.external_id AS league_external_id,
                m.home_score, m.away_score, m.metadata,
                -- Extract odds from metadata JSONB
                (m.metadata->'odds'->'best_odds'->>'home')::float as best_home_odds,
                (m.metadata->'odds'->'best_odds'->>'draw')::float as best_draw_odds,
                (m.metadata->'odds'->'best_odds'->>'away')::float as best_away_odds,
                CASE WHEN m.metadata->'odds'->'best_odds' IS NOT NULL THEN 1 ELSE 0 END as bookmakers_count
            FROM matches m
            JOIN leagues l ON m.league_id = l.id
        """

        # Build WHERE clause
        # Support both 'NS' (API-Football) and 'scheduled' status codes
        status_condition = "m.status IN ('NS', 'scheduled')" if status in ("NS", "scheduled") else "m.status = $4"

        base_params: list[Any] = [
            self._parse_date(date_from),
            self._parse_date(date_to),
            external_league_id,
        ]

        where_conditions = [
            "m.scheduled_at::date >= $1",
            "m.scheduled_at::date <= $2",
            "l.external_id = $3",  # Use external_id from leagues table
            status_condition,
        ]

        if status not in ("NS", "scheduled"):
            base_params.append(status)

        # Add odds filter if requested (checks metadata JSONB)
        if has_odds:
            where_conditions.append("m.metadata->'odds'->'best_odds' IS NOT NULL")

        full_query = f"""
            {select_clause}
            WHERE {' AND '.join(where_conditions)}
            ORDER BY m.scheduled_at ASC
        """

        # Log query for debugging
        logger.info(
            f"get_matches_by_external_league_id() - external_league_id={external_league_id}, "
            f"date_from={date_from}, date_to={date_to}, status={status}, has_odds={has_odds}"
        )
        logger.debug(f"Query: {full_query}")
        logger.debug(f"Params: {base_params}")

        # Execute query
        assert self._pool is not None
        async with self._pool.acquire() as connection:
            records = await connection.fetch(full_query, *base_params)
            logger.info(f"get_matches_by_external_league_id() - returned {len(records)} records")

        return [self._record_to_dict(record) for record in records]
