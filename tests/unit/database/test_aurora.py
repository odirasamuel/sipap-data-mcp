"""Unit tests for AuroraDataClient.

Following TDD methodology: Tests written BEFORE implementation.
These tests define the expected behavior of the database client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from tests.fixtures.matches import SAMPLE_MATCH


class TestAuroraDataClient:
    """Tests for AuroraDataClient database operations."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_asyncpg_pool):
        """Test successful connection to Aurora database."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock asyncpg.create_pool to return our mock pool
        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            # Act
            await client.connect()

            # Assert
            assert client._pool is not None
            assert client._pool == mock_asyncpg_pool

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_get_matches_returns_list(self, mock_asyncpg_pool):
        """Test get_matches returns list of matches from database."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock database response (asyncpg.Record objects)
        # Create a mock that behaves like a dict when passed to dict()
        mock_record = MagicMock()
        mock_record.items.return_value = SAMPLE_MATCH.items()
        mock_record.keys.return_value = SAMPLE_MATCH.keys()
        mock_record.values.return_value = SAMPLE_MATCH.values()
        mock_record.__iter__ = lambda self: iter(SAMPLE_MATCH.keys())
        mock_record.__getitem__ = lambda self, key: SAMPLE_MATCH[key]

        mock_records = [mock_record]
        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=mock_records)

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            matches = await client.get_matches(
                date_from="2026-07-05",
                date_to="2026-07-12",
                status="scheduled"
            )

            # Assert
            assert isinstance(matches, list)
            assert len(matches) == 1
            assert matches[0]["home_team"] == "Arsenal"
            assert matches[0]["away_team"] == "Chelsea"

            # Verify query was called with correct parameters
            connection.fetch.assert_called_once()
            call_args = connection.fetch.call_args[0]
            assert "2026-07-05" in call_args
            assert "2026-07-12" in call_args
            assert "scheduled" in call_args

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_get_matches_with_invalid_date_raises_error(self, mock_asyncpg_pool):
        """Test get_matches with invalid date format raises ValueError."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act & Assert
            with pytest.raises(ValueError, match="Invalid date format"):
                await client.get_matches(
                    date_from="invalid-date",
                    date_to="2026-07-12",
                    status="scheduled"
                )

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_get_matches_with_league_filter(self, mock_asyncpg_pool):
        """Test get_matches with league_id filter."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Create a mock that behaves like a dict
        mock_record = MagicMock()
        mock_record.items.return_value = SAMPLE_MATCH.items()
        mock_record.keys.return_value = SAMPLE_MATCH.keys()
        mock_record.values.return_value = SAMPLE_MATCH.values()
        mock_record.__iter__ = lambda self: iter(SAMPLE_MATCH.keys())
        mock_record.__getitem__ = lambda self, key: SAMPLE_MATCH[key]

        mock_records = [mock_record]
        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=mock_records)

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            matches = await client.get_matches(
                date_from="2026-07-05",
                date_to="2026-07-12",
                league_id="league-uuid-1",
                status="scheduled"
            )

            # Assert
            assert len(matches) == 1
            connection.fetch.assert_called_once()

            # Verify league_id was passed to query
            call_args = connection.fetch.call_args[0]
            assert "league-uuid-1" in call_args

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, mock_asyncpg_pool):
        """Test handling of connection pool exhaustion."""
        import asyncio

        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock pool.acquire() to raise TimeoutError
        acquire_context = MagicMock()
        acquire_context.__aenter__ = AsyncMock(
            side_effect=TimeoutError("Pool exhausted")
        )
        mock_asyncpg_pool.acquire.return_value = acquire_context

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act & Assert
            with pytest.raises(asyncio.TimeoutError):
                await client.get_matches(
                    date_from="2026-07-05",
                    date_to="2026-07-12",
                    status="scheduled"
                )

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self, mock_asyncpg_pool):
        """Test handling of query timeout (>5s)."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock connection.fetch() to raise QueryTimeoutError
        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(
            side_effect=asyncpg.exceptions.QueryCanceledError("Query timeout")
        )

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act & Assert
            with pytest.raises(asyncpg.exceptions.QueryCanceledError):
                await client.get_matches(
                    date_from="2026-07-05",
                    date_to="2026-07-12",
                    status="scheduled"
                )

            # Cleanup
            await client.close()

    @pytest.mark.asyncio
    async def test_close_connection_pool(self, mock_asyncpg_pool):
        """Test closing connection pool releases resources."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()
            assert client._pool is not None

            # Act
            await client.close()

            # Assert
            mock_asyncpg_pool.close.assert_called_once()
            assert client._pool is None
