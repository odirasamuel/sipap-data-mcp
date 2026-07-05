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
    ) -> list[dict[str, Any]]:
        """Retrieve matches from database within date range.

        Args:
            date_from: Start date in ISO 8601 format (YYYY-MM-DD)
            date_to: End date in ISO 8601 format (YYYY-MM-DD)
            status: Match status filter (scheduled, live, finished)
            league_id: Optional league UUID filter

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
            matches = await client.get_matches(
                date_from="2026-07-05",
                date_to="2026-07-12",
                status="scheduled",
                league_id="550e8400-e29b-41d4-a716-446655440000"
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
    ) -> tuple[str, tuple[str, ...]]  :
        """Build SQL query and parameters for matches retrieval.

        Args:
            date_from: Start date in ISO 8601 format
            date_to: End date in ISO 8601 format
            status: Match status filter
            league_id: Optional league UUID filter

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
        if league_id is not None:
            where_clause = """
                WHERE scheduled_at >= $1
                  AND scheduled_at <= $2
                  AND status = $3
                  AND league_id = $4
                ORDER BY scheduled_at ASC
            """
            params = (date_from, date_to, status, league_id)
        else:
            where_clause = """
                WHERE scheduled_at >= $1
                  AND scheduled_at <= $2
                  AND status = $3
                ORDER BY scheduled_at ASC
            """
            params = (date_from, date_to, status)

        return (select_clause + where_clause, params)
