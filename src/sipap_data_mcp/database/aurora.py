"""Aurora PostgreSQL database client for sports data access.

This module provides async database access to SIPAP's normalized sports data schema.
Implements connection pooling, query timeout handling, and proper resource cleanup.
"""

from datetime import datetime
from typing import Any

import asyncpg


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
            ssl='require',  # Aurora requires SSL connections
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
            league_id: Optional league UUID filter
            has_odds: Only include matches with odds available (default: False)

        Returns:
            List of match dictionaries with keys:
            - id, external_id, scheduled_at, status
            - home_team, away_team, home_team_id, away_team_id
            - league, league_id, sport, venue
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

        # Execute query
        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, *params)

        # Convert asyncpg.Record to dict
        return [dict(record) for record in records]

    def _validate_dates(self, date_from: str, date_to: str) -> None:
        """Validate date formats are ISO 8601 compliant.

        Args:
            date_from: Start date string
            date_to: End date string

        Raises:
            ValueError: If either date is not valid ISO 8601 format
        """
        try:
            datetime.fromisoformat(date_from)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format for date_from '{date_from}': "
                f"Expected ISO 8601 format (YYYY-MM-DD)"
            ) from e

        try:
            datetime.fromisoformat(date_to)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format for date_to '{date_to}': "
                f"Expected ISO 8601 format (YYYY-MM-DD)"
            ) from e

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
    ) -> tuple[str, tuple[str, ...]]  :
        """Build SQL query and parameters for matches retrieval.

        Args:
            date_from: Start date in ISO 8601 format
            date_to: End date in ISO 8601 format
            status: Match status filter
            league_id: Optional league UUID filter
            has_odds: Only include matches with odds available (checks metadata->'odds')

        Returns:
            Tuple of (query string, parameters tuple)
        """
        # Base SELECT clause
        select_clause = """
            SELECT
                id, external_id, scheduled_at, status,
                home_team, away_team, home_team_id, away_team_id,
                league, league_id, sport, venue,
                home_score, away_score, metadata
            FROM matches
        """

        # Build WHERE clause and parameters
        params: tuple[str, ...]  # Explicitly type to allow variable-length tuples

        # Base WHERE conditions
        where_conditions = [
            "scheduled_at >= $1",
            "scheduled_at <= $2",
            "status = $3",
        ]
        base_params = [date_from, date_to, status]

        # Add league filter if specified
        if league_id is not None:
            where_conditions.append(f"league_id = ${len(base_params) + 1}")
            base_params.append(league_id)

        # Add odds filter if requested (uses PostgreSQL JSONB ? operator)
        if has_odds:
            where_conditions.append("metadata ? 'odds'")

        where_clause = f"""
            WHERE {' AND '.join(where_conditions)}
            ORDER BY scheduled_at ASC
        """
        params = tuple(base_params)

        return (select_clause + where_clause, params)

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

        query = """
            SELECT
                id, external_id, scheduled_at, status,
                home_team, away_team, home_team_id, away_team_id,
                league, league_id, sport, venue,
                home_score, away_score, metadata
            FROM matches
            WHERE id = $1
        """

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, match_id)

        if record is None:
            return None

        return dict(record)

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

        # Search by team name (home or away)
        search_query = """
            SELECT
                id, external_id, scheduled_at, status,
                home_team, away_team, home_team_id, away_team_id,
                league, league_id, sport, venue,
                home_score, away_score, metadata
            FROM matches
            WHERE home_team ILIKE $1
               OR away_team ILIKE $1
            ORDER BY scheduled_at DESC
            LIMIT 100
        """

        # Add wildcards for partial matching
        search_term = f"%{query}%"

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(search_query, search_term)

        return [dict(record) for record in records]

    async def get_team_stats(
        self,
        team_id: str,
        season: str,
    ) -> dict[str, Any] | None:
        """Retrieve team statistics for a specific season.

        Args:
            team_id: Team UUID
            season: Season in format "YYYY-YYYY"

        Returns:
            Team statistics dictionary or None if not found

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            stats = await client.get_team_stats(
                team_id="team-uuid-1",
                season="2024-2025"
            )
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                team_id, team_name, season,
                matches_played, wins, draws, losses,
                goals_scored, goals_conceded, goal_difference,
                points, form, home_record, away_record
            FROM team_stats
            WHERE team_id = $1 AND season = $2
        """

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, team_id, season)

        if record is None:
            return None

        return dict(record)

    async def get_league_table(
        self,
        league_id: str,
        season: str,
    ) -> list[dict[str, Any]]:
        """Retrieve league table/standings for a specific season.

        Args:
            league_id: League UUID
            season: Season in format "YYYY-YYYY"

        Returns:
            List of team standings sorted by position

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            standings = await client.get_league_table(
                league_id="league-uuid-1",
                season="2024-2025"
            )
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                position, team_name, team_id,
                matches_played, wins, draws, losses,
                goals_scored, goals_conceded, goal_difference,
                points, form
            FROM league_standings
            WHERE league_id = $1 AND season = $2
            ORDER BY position ASC
        """

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, league_id, season)

        return [dict(record) for record in records]

    async def get_head_to_head(
        self,
        team1_id: str,
        team2_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Retrieve head-to-head statistics between two teams.

        Args:
            team1_id: First team UUID
            team2_id: Second team UUID
            limit: Maximum number of recent matches to include

        Returns:
            Head-to-head statistics dictionary with:
            - team1_id, team2_id
            - team1_name, team2_name
            - total_matches, team1_wins, team2_wins, draws
            - recent_matches

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            h2h = await client.get_head_to_head(
                team1_id="team-uuid-1",
                team2_id="team-uuid-2",
                limit=10
            )
            ```
        """
        self._ensure_connected()

        # Get team names
        team_names_query = """
            SELECT id, name FROM teams WHERE id = $1 OR id = $2
        """

        # Get historical matches between these teams
        matches_query = """
            SELECT
                id, scheduled_at, home_team, away_team,
                home_team_id, away_team_id,
                home_score, away_score, status
            FROM matches
            WHERE (home_team_id = $1 AND away_team_id = $2)
               OR (home_team_id = $2 AND away_team_id = $1)
            AND status = 'finished'
            ORDER BY scheduled_at DESC
            LIMIT $3
        """

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            # Get team names
            team_records = await connection.fetch(team_names_query, team1_id, team2_id)
            teams_dict = {str(record["id"]): record["name"] for record in team_records}

            team1_name = teams_dict.get(team1_id, "Unknown Team")
            team2_name = teams_dict.get(team2_id, "Unknown Team")

            # Get historical matches
            match_records = await connection.fetch(matches_query, team1_id, team2_id, limit)

        # Calculate statistics
        total_matches = len(match_records)
        team1_wins = 0
        team2_wins = 0
        draws = 0
        recent_matches = []

        for record in match_records:
            match_dict = dict(record)
            recent_matches.append(match_dict)

            # Determine winner
            if match_dict["home_team_id"] == team1_id:
                # Team1 is home
                if match_dict["home_score"] > match_dict["away_score"]:
                    team1_wins += 1
                elif match_dict["home_score"] < match_dict["away_score"]:
                    team2_wins += 1
                else:
                    draws += 1
            else:
                # Team1 is away
                if match_dict["away_score"] > match_dict["home_score"]:
                    team1_wins += 1
                elif match_dict["away_score"] < match_dict["home_score"]:
                    team2_wins += 1
                else:
                    draws += 1

        return {
            "team1_id": team1_id,
            "team2_id": team2_id,
            "team1_name": team1_name,
            "team2_name": team2_name,
            "total_matches": total_matches,
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "draws": draws,
            "recent_matches": recent_matches,
        }

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
        query_parts = [
            """
            SELECT
                id, external_id, scheduled_at, status,
                home_team, away_team, home_team_id, away_team_id,
                league, league_id, sport, venue,
                home_score, away_score, metadata
            FROM matches
            WHERE status = 'finished'
              AND (home_team_id = $1 OR away_team_id = $1)
            """
        ]

        params: list[Any] = [team_id]
        param_idx = 2

        # Add league filter if provided
        if league_id is not None:
            query_parts.append(f"  AND league_id = ${param_idx}")
            params.append(league_id)
            param_idx += 1

        # Add date range filters if provided
        if date_from is not None:
            query_parts.append(f"  AND scheduled_at >= ${param_idx}")
            params.append(date_from)
            param_idx += 1

        if date_to is not None:
            query_parts.append(f"  AND scheduled_at <= ${param_idx}")
            params.append(date_to)
            param_idx += 1

        # Order by most recent first and apply limit
        query_parts.append("ORDER BY scheduled_at DESC")
        query_parts.append(f"LIMIT ${param_idx}")
        params.append(limit)

        query = "\n".join(query_parts)

        assert self._pool is not None  # Type narrowing for mypy
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, *params)

        return [dict(record) for record in records]

    async def get_match_odds(
        self,
        match_id: str,
    ) -> dict[str, Any] | None:
        """Get betting odds for a match from multiple bookmakers.

        Args:
            match_id: Match UUID

        Returns:
            Dictionary with odds data (bookmakers, best_odds, average_odds)
            or None if no odds available

        Raises:
            RuntimeError: If client not connected

        Example:
            ```python
            odds = await client.get_match_odds("match-uuid-1")
            # Returns: {"bookmakers": [...], "best_odds": {...}, ...}
            ```
        """
        self._ensure_connected()

        query = """
            SELECT
                id AS match_id,
                metadata->'odds' AS odds_data
            FROM matches
            WHERE id = $1
              AND metadata ? 'odds'
        """

        assert self._pool is not None
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, match_id)

        if record is None or record["odds_data"] is None:
            return None

        # Parse odds data from JSONB
        odds_data = dict(record["odds_data"])

        return {
            "match_id": record["match_id"],
            "bookmakers": odds_data.get("bookmakers", []),
            "best_odds": odds_data.get("best_odds", {}),
            "average_odds": odds_data.get("average_odds", {}),
        }

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
