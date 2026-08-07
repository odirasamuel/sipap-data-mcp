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
            # Dates are converted to datetime.date objects
            import datetime
            assert datetime.date(2026, 7, 5) in call_args
            assert datetime.date(2026, 7, 12) in call_args
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

    # ================================================================================
    # Phase 3 Schema Method Tests (API-Football Integration)
    # ================================================================================

    @pytest.mark.asyncio
    async def test_get_standings(self, mock_asyncpg_pool):
        """Test get_standings returns league standings from Phase 3 table."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock standings data
        mock_record = MagicMock()
        mock_standing = {
            "team_id": 50,
            "team_name": "Manchester City",
            "rank": 1,
            "points": 90,
            "played": 38,
            "wins": 28,
            "draws": 6,
            "losses": 4,
            "goals_for": 95,
            "goals_against": 33,
            "goal_difference": 62,
            "form": "WWDWW",
        }
        mock_record.items.return_value = mock_standing.items()
        mock_record.keys.return_value = mock_standing.keys()
        mock_record.values.return_value = mock_standing.values()
        mock_record.__iter__ = lambda self: iter(mock_standing.keys())
        mock_record.__getitem__ = lambda self, key: mock_standing[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=[mock_record])

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            standings = await client.get_standings(league_id=39, season="2024")

            # Assert
            assert isinstance(standings, list)
            assert len(standings) == 1
            assert standings[0]["team_name"] == "Manchester City"
            assert standings[0]["rank"] == 1
            assert standings[0]["points"] == 90

            # Verify query was called with correct parameters
            connection.fetch.assert_called_once()
            call_args = connection.fetch.call_args[0]
            assert 39 in call_args  # league_id
            assert "2024" in call_args  # season

            await client.close()

    @pytest.mark.asyncio
    async def test_get_team_statistics(self, mock_asyncpg_pool):
        """Test get_team_statistics returns team stats from Phase 3 table."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock team statistics data
        mock_record = MagicMock()
        mock_stats = {
            "team_id": 50,
            "league_id": 39,
            "season": "2024",
            "total_played": 38,
            "home_wins": 15,
            "away_goals_for": 40,
        }
        mock_record.items.return_value = mock_stats.items()
        mock_record.keys.return_value = mock_stats.keys()
        mock_record.values.return_value = mock_stats.values()
        mock_record.__iter__ = lambda self: iter(mock_stats.keys())
        mock_record.__getitem__ = lambda self, key: mock_stats[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetchrow = AsyncMock(return_value=mock_record)

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            stats = await client.get_team_statistics(
                team_id=50, league_id=39, season="2024"
            )

            # Assert
            assert stats is not None
            assert stats["team_id"] == 50
            assert stats["total_played"] == 38
            assert stats["home_wins"] == 15

            # Verify query was called
            connection.fetchrow.assert_called_once()

            await client.close()

    @pytest.mark.asyncio
    async def test_get_injuries(self, mock_asyncpg_pool):
        """Test get_injuries returns player injuries for a fixture."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock injury data
        mock_record = MagicMock()
        mock_injury = {
            "player_id": 123,
            "player_name": "Bukayo Saka",
            "team_id": 42,
            "injury_type": "Muscle",
            "injury_reason": "Hamstring",
        }
        mock_record.items.return_value = mock_injury.items()
        mock_record.keys.return_value = mock_injury.keys()
        mock_record.values.return_value = mock_injury.values()
        mock_record.__iter__ = lambda self: iter(mock_injury.keys())
        mock_record.__getitem__ = lambda self, key: mock_injury[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=[mock_record])

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            injuries = await client.get_injuries(fixture_id=1234567)

            # Assert
            assert isinstance(injuries, list)
            assert len(injuries) == 1
            assert injuries[0]["player_name"] == "Bukayo Saka"
            assert injuries[0]["injury_type"] == "Muscle"

            await client.close()

    @pytest.mark.asyncio
    async def test_get_lineups(self, mock_asyncpg_pool):
        """Test get_lineups returns team lineups for a fixture."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock lineups data
        mock_record = MagicMock()
        mock_lineups = {
            "fixture_id": 1234567,
            "home_team_lineup": {"formation": "4-3-3", "startXI": []},
            "away_team_lineup": {"formation": "4-2-3-1", "startXI": []},
        }
        mock_record.items.return_value = mock_lineups.items()
        mock_record.keys.return_value = mock_lineups.keys()
        mock_record.values.return_value = mock_lineups.values()
        mock_record.__iter__ = lambda self: iter(mock_lineups.keys())
        mock_record.__getitem__ = lambda self, key: mock_lineups[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetchrow = AsyncMock(return_value=mock_record)

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            lineups = await client.get_lineups(fixture_id=1234567)

            # Assert
            assert lineups is not None
            assert lineups["fixture_id"] == 1234567
            assert lineups["home_team_lineup"]["formation"] == "4-3-3"
            assert lineups["away_team_lineup"]["formation"] == "4-2-3-1"

            await client.close()

    @pytest.mark.asyncio
    async def test_get_head_to_head_stats(self, mock_asyncpg_pool):
        """Test get_head_to_head_stats returns H2H statistics."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock H2H data
        mock_record = MagicMock()
        mock_h2h = {
            "team_1_id": 42,
            "team_2_id": 50,
            "team_1_wins": 5,
            "team_2_wins": 3,
            "draws": 2,
            "last_10_matches": [],
        }
        mock_record.items.return_value = mock_h2h.items()
        mock_record.keys.return_value = mock_h2h.keys()
        mock_record.values.return_value = mock_h2h.values()
        mock_record.__iter__ = lambda self: iter(mock_h2h.keys())
        mock_record.__getitem__ = lambda self, key: mock_h2h[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetchrow = AsyncMock(return_value=mock_record)

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            h2h = await client.get_head_to_head_stats(team_1_id=50, team_2_id=42)

            # Assert
            assert h2h is not None
            assert h2h["team_1_id"] == 42  # Auto-swapped (min)
            assert h2h["team_2_id"] == 50  # Auto-swapped (max)
            assert h2h["team_1_wins"] == 5
            assert h2h["draws"] == 2

            # Verify correct ordering in query
            call_args = connection.fetchrow.call_args[0]
            assert 42 in call_args  # min(50, 42)
            assert 50 in call_args  # max(50, 42)

            await client.close()

    @pytest.mark.asyncio
    async def test_get_teams_metadata(self, mock_asyncpg_pool):
        """Test get_teams_metadata returns metadata for multiple teams."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock metadata
        mock_record = MagicMock()
        mock_metadata = {
            "team_id": 50,
            "team_name": "Manchester City",
            "team_logo": "https://example.com/mancity.png",
            "team_code": "MCI",
            "country": "England",
        }
        mock_record.items.return_value = mock_metadata.items()
        mock_record.keys.return_value = mock_metadata.keys()
        mock_record.values.return_value = mock_metadata.values()
        mock_record.__iter__ = lambda self: iter(mock_metadata.keys())
        mock_record.__getitem__ = lambda self, key: mock_metadata[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=[mock_record])

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            metadata = await client.get_teams_metadata(team_ids=[50, 42])

            # Assert
            assert isinstance(metadata, list)
            assert len(metadata) == 1
            assert metadata[0]["team_name"] == "Manchester City"
            assert metadata[0]["team_code"] == "MCI"

            await client.close()

    @pytest.mark.asyncio
    async def test_get_match_odds_phase3(self, mock_asyncpg_pool):
        """Test get_match_odds returns odds from Phase 3 dedicated table."""
        from sipap_data_mcp.database.aurora import AuroraDataClient

        # Arrange
        client = AuroraDataClient(
            host="localhost",
            port=5432,
            database="sipap_test",
            user="sipap",
            password="test_password"
        )

        # Mock odds data
        mock_record = MagicMock()
        mock_odds = {
            "fixture_id": 1234567,
            "bookmaker_id": 8,
            "bookmaker_name": "Bet365",
            "market": "1X2",
            "home_odds": 1.85,
            "draw_odds": 3.40,
            "away_odds": 4.20,
            "is_live": False,
        }
        mock_record.items.return_value = mock_odds.items()
        mock_record.keys.return_value = mock_odds.keys()
        mock_record.values.return_value = mock_odds.values()
        mock_record.__iter__ = lambda self: iter(mock_odds.keys())
        mock_record.__getitem__ = lambda self, key: mock_odds[key]

        connection = mock_asyncpg_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=[mock_record])

        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_asyncpg_pool)):
            await client.connect()

            # Act
            odds = await client.get_match_odds(fixture_id=1234567)

            # Assert
            assert isinstance(odds, list)
            assert len(odds) == 1
            assert odds[0]["bookmaker_name"] == "Bet365"
            assert odds[0]["market"] == "1X2"
            assert odds[0]["home_odds"] == 1.85

            # Verify query was called with correct parameters
            call_args = connection.fetch.call_args[0]
            assert 1234567 in call_args  # fixture_id
            assert False in call_args  # is_live

            await client.close()
