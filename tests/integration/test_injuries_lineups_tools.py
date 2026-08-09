"""Integration tests for injuries and lineups MCP tools.

Tests the complete flow: Aurora database → MCP tools → Tool output validation

Prerequisites:
- Aurora PostgreSQL deployed and accessible
- injuries and lineups tables exist (may be empty)
- Environment variables configured

Run with:
    pytest tests/integration/test_injuries_lineups_tools.py -v
"""

import os

import pytest

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools import get_injuries, get_lineups


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
async def aurora_client():
    """Create Aurora client connected to deployed database."""
    client = AuroraDataClient(
        host=os.getenv("AURORA_HOST", "sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com"),
        port=int(os.getenv("AURORA_PORT", "5432")),
        database=os.getenv("AURORA_DATABASE", "sipap_dev"),
        user=os.getenv("AURORA_USER", "sipap_admin"),
        password=os.getenv("AURORA_PASSWORD", ""),
    )

    await client.connect()
    yield client
    await client.close()


# ==============================================================================
# TEST SUITE - Injuries Tool
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestInjuriesTool:
    """Test get_injuries() MCP tool."""

    async def test_get_injuries_returns_correct_structure(self, aurora_client):
        """Verify get_injuries() returns correct data structure."""
        # Use a fixture_id that may or may not have injuries
        # Tool should handle both cases gracefully
        result = await get_injuries(
            db_client=aurora_client,
            fixture_id=1234567  # Sample fixture ID
        )

        # Verify structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "injuries" in result, "Result should have 'injuries' key"
        assert isinstance(result["injuries"], list), "Injuries should be a list"

    async def test_get_injuries_empty_fixture(self, aurora_client):
        """Verify get_injuries() handles fixtures with no injuries correctly."""
        result = await get_injuries(
            db_client=aurora_client,
            fixture_id=9999999  # Non-existent fixture
        )

        # Should return empty list, not error
        assert result["injuries"] == [], "Should return empty list for no injuries"

    async def test_get_injuries_data_structure(self, aurora_client):
        """Verify injury records have expected fields (if data exists)."""
        result = await get_injuries(
            db_client=aurora_client,
            fixture_id=1234567
        )

        injuries = result["injuries"]

        # If injuries exist, verify structure
        if len(injuries) > 0:
            first_injury = injuries[0]
            expected_fields = [
                "player_id",
                "player_name",
                "player_photo",
                "team_id",
                "team_name",
                "injury_type",
                "injury_reason",
                "expected_return_date"
            ]

            for field in expected_fields:
                assert field in first_injury, f"Injury record should have '{field}' field"


# ==============================================================================
# TEST SUITE - Lineups Tool
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestLineupsTool:
    """Test get_lineups() MCP tool."""

    async def test_get_lineups_returns_correct_structure(self, aurora_client):
        """Verify get_lineups() returns correct data structure."""
        result = await get_lineups(
            db_client=aurora_client,
            fixture_id=1234567  # Sample fixture ID
        )

        # Verify structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "lineups" in result, "Result should have 'lineups' key"

    async def test_get_lineups_not_available_yet(self, aurora_client):
        """Verify get_lineups() handles unavailable lineups correctly."""
        result = await get_lineups(
            db_client=aurora_client,
            fixture_id=9999999  # Non-existent fixture
        )

        # Should return None with message
        assert result["lineups"] is None, "Lineups should be None when not available"
        assert "message" in result, "Should include message when lineups not available"
        assert result["message"] == "Lineups not available yet"

    async def test_get_lineups_data_structure(self, aurora_client):
        """Verify lineup records have expected fields (if data exists)."""
        result = await get_lineups(
            db_client=aurora_client,
            fixture_id=1234567
        )

        lineups = result["lineups"]

        # If lineups exist, verify structure
        if lineups is not None:
            expected_fields = [
                "fixture_id",
                "home_team_lineup",
                "away_team_lineup"
            ]

            for field in expected_fields:
                assert field in lineups, f"Lineups record should have '{field}' field"

            # Verify lineup fields are JSONB (dicts)
            if lineups["home_team_lineup"] is not None:
                assert isinstance(lineups["home_team_lineup"], dict), \
                    "home_team_lineup should be a dictionary (JSONB)"

            if lineups["away_team_lineup"] is not None:
                assert isinstance(lineups["away_team_lineup"], dict), \
                    "away_team_lineup should be a dictionary (JSONB)"


# ==============================================================================
# TEST SUITE - Tool Integration with Database
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestToolsDatabaseIntegration:
    """Test that tools correctly integrate with Aurora database."""

    async def test_injuries_tool_uses_fixture_id(self, aurora_client):
        """Verify get_injuries() queries by fixture_id correctly."""
        # This confirms schema alignment - tool queries by fixture_id
        # which matches the verified schema (injuries.fixture_id INT NOT NULL)
        result = await get_injuries(
            db_client=aurora_client,
            fixture_id=1234567
        )

        # Should succeed without errors (schema aligned)
        assert "injuries" in result

    async def test_lineups_tool_uses_fixture_id(self, aurora_client):
        """Verify get_lineups() queries by fixture_id correctly."""
        # This confirms schema alignment - tool queries by fixture_id
        # which matches the verified schema (lineups.fixture_id INT UNIQUE)
        result = await get_lineups(
            db_client=aurora_client,
            fixture_id=1234567
        )

        # Should succeed without errors (schema aligned)
        assert "lineups" in result

    async def test_tools_handle_integer_fixture_ids(self, aurora_client):
        """Verify tools work with integer fixture IDs from API-Football."""
        # Phase 3 uses integer IDs from API-Football, not UUIDs
        fixture_ids = [1234567, 7654321, 9999999]

        for fixture_id in fixture_ids:
            # Both tools should handle integer IDs without errors
            injuries_result = await get_injuries(
                db_client=aurora_client,
                fixture_id=fixture_id
            )
            lineups_result = await get_lineups(
                db_client=aurora_client,
                fixture_id=fixture_id
            )

            assert "injuries" in injuries_result
            assert "lineups" in lineups_result
