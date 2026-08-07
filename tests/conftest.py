"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from dotenv import load_dotenv

# Load .env file for integration tests
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


@pytest.fixture
def mock_db_client():
    """Mock AuroraDataClient for unit tests."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=None)
    client.close = AsyncMock(return_value=None)
    client.get_matches = AsyncMock(return_value=[])
    client.get_match = AsyncMock(return_value=None)
    client.get_team_stats = AsyncMock(return_value={})
    client.get_league_table = AsyncMock(return_value=[])
    client.get_head_to_head = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests."""
    redis = MagicMock()
    redis.connect = AsyncMock(return_value=None)
    redis.close = AsyncMock(return_value=None)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()

    # Mock connection
    connection = MagicMock()
    connection.fetch = AsyncMock(return_value=[])
    connection.fetchrow = AsyncMock(return_value=None)
    connection.execute = AsyncMock(return_value="SELECT 1")

    # Mock pool.acquire() context manager
    acquire_context = MagicMock()
    acquire_context.__aenter__ = AsyncMock(return_value=connection)
    acquire_context.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acquire_context

    # Mock pool.close()
    pool.close = AsyncMock(return_value=None)

    return pool


@pytest.fixture(autouse=True)
def reset_module_state(monkeypatch):
    """Reset module-level state between tests.

    This fixture automatically runs before each test to ensure
    clean state and prevent test pollution.
    """
    # Clear any cached module-level clients
    import sys
    if 'sipap_data_mcp.tools' in sys.modules:
        for module_name in list(sys.modules.keys()):
            if module_name.startswith('sipap_data_mcp.tools'):
                del sys.modules[module_name]
