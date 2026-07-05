"""Tests for SIPAP Data MCP Server.

Tests the MCP server implementation including:
- Server initialization and lifecycle
- Tool registration and listing
- Tool execution via JSON-RPC 2.0
- Error handling
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestSIPAPDataMCPServer:
    """Test suite for SIPAPDataMCP server class."""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test server can be instantiated."""
        from sipap_data_mcp.server import SIPAPDataMCP

        server = SIPAPDataMCP(
            db_host="localhost",
            db_port=5432,
            db_name="test_db",
            db_user="test_user",
            db_password="test_pass",
            redis_url="redis://localhost:6379/0"
        )

        assert server.name == "sipap-data-mcp"
        assert server.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_server_setup_connections(self):
        """Test server establishes database and cache connections."""
        from sipap_data_mcp.server import SIPAPDataMCP

        with patch("sipap_data_mcp.server.AuroraDataClient") as mock_db:
            with patch("sipap_data_mcp.server.RedisCache") as mock_cache:
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_cache_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                mock_cache.return_value = mock_cache_instance

                server = SIPAPDataMCP(
                    db_host="localhost",
                    db_port=5432,
                    db_name="test_db",
                    db_user="test_user",
                    db_password="test_pass",
                    redis_url="redis://localhost:6379/0"
                )

                await server._setup()

                # Verify connections were established
                mock_db_instance.connect.assert_called_once()
                mock_cache_instance.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_cleanup_connections(self):
        """Test server closes database and cache connections."""
        from sipap_data_mcp.server import SIPAPDataMCP

        with patch("sipap_data_mcp.server.AuroraDataClient") as mock_db:
            with patch("sipap_data_mcp.server.RedisCache") as mock_cache:
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_cache_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                mock_cache.return_value = mock_cache_instance

                server = SIPAPDataMCP(
                    db_host="localhost",
                    db_port=5432,
                    db_name="test_db",
                    db_user="test_user",
                    db_password="test_pass",
                    redis_url="redis://localhost:6379/0"
                )

                await server._setup()
                await server._cleanup()

                # Verify connections were closed
                mock_db_instance.close.assert_called_once()
                mock_cache_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_tools(self):
        """Test tools/list returns all 11 registered tools."""
        from sipap_data_mcp.server import SIPAPDataMCP

        server = SIPAPDataMCP(
            db_host="localhost",
            db_port=5432,
            db_name="test_db",
            db_user="test_user",
            db_password="test_pass",
            redis_url="redis://localhost:6379/0"
        )

        # Get tools list
        tools = server.list_tools()

        # Should return 11 tools
        assert len(tools) == 11

        # Verify tool names
        tool_names = [tool["name"] for tool in tools]
        expected_tools = [
            "get_match_schedule",
            "get_match_details",
            "get_live_matches",
            "search_matches",
            "get_team_stats",
            "get_league_table",
            "get_head_to_head",
            "query_history",
            "get_form_data",
            "get_match_odds",
            "get_odds_movements",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Tool {expected} not found in tools list"

    @pytest.mark.asyncio
    async def test_tool_has_json_schema(self):
        """Test each tool has a valid JSON Schema."""
        from sipap_data_mcp.server import SIPAPDataMCP

        server = SIPAPDataMCP(
            db_host="localhost",
            db_port=5432,
            db_name="test_db",
            db_user="test_user",
            db_password="test_pass",
            redis_url="redis://localhost:6379/0"
        )

        tools = server.list_tools()

        # Check first tool (get_match_schedule)
        tool = next(t for t in tools if t["name"] == "get_match_schedule")

        assert "inputSchema" in tool
        assert "type" in tool["inputSchema"]
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]
        assert "date_from" in tool["inputSchema"]["properties"]
        assert "date_to" in tool["inputSchema"]["properties"]

    @pytest.mark.asyncio
    async def test_call_get_match_schedule(self):
        """Test calling get_match_schedule tool via JSON-RPC 2.0."""
        from sipap_data_mcp.server import SIPAPDataMCP

        with patch("sipap_data_mcp.server.AuroraDataClient") as mock_db:
            with patch("sipap_data_mcp.server.RedisCache") as mock_cache:
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_cache_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                mock_cache.return_value = mock_cache_instance

                # Mock database response
                mock_db_instance.get_matches.return_value = [
                    {
                        "match_id": "550e8400-e29b-41d4-a716-446655440000",
                        "home_team": "Arsenal",
                        "away_team": "Chelsea",
                        "date": "2026-07-12",
                    }
                ]

                # Mock cache miss
                mock_cache_instance.get.return_value = None

                server = SIPAPDataMCP(
                    db_host="localhost",
                    db_port=5432,
                    db_name="test_db",
                    db_user="test_user",
                    db_password="test_pass",
                    redis_url="redis://localhost:6379/0"
                )

                await server._setup()

                # Create JSON-RPC 2.0 request
                request = {
                    "jsonrpc": "2.0",
                    "id": "test-1",
                    "method": "tools/call",
                    "params": {
                        "name": "get_match_schedule",
                        "arguments": {
                            "date_from": "2026-07-05",
                            "date_to": "2026-07-12",
                            "status": "scheduled"
                        }
                    }
                }

                # Call tool via handle_request
                response = server.handle_request(request)

                # Verify JSON-RPC response structure
                assert response["jsonrpc"] == "2.0"
                assert response["id"] == "test-1"
                assert "result" in response

                # Extract actual result from content array
                content = response["result"]["content"]
                assert len(content) == 1
                result_text = content[0]["text"]
                result = json.loads(result_text)

                # Verify result structure
                assert "matches" in result
                assert len(result["matches"]) == 1
                assert result["matches"][0]["home_team"] == "Arsenal"

                await server._cleanup()

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool_raises_error(self):
        """Test calling non-existent tool returns JSON-RPC error."""
        from sipap_data_mcp.server import SIPAPDataMCP

        server = SIPAPDataMCP(
            db_host="localhost",
            db_port=5432,
            db_name="test_db",
            db_user="test_user",
            db_password="test_pass",
            redis_url="redis://localhost:6379/0"
        )

        # Create JSON-RPC request for non-existent tool
        request = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            }
        }

        response = server.handle_request(request)

        # Should return JSON-RPC error
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-1"
        assert "error" in response
        # Protocol handler treats nonexistent tool as invalid param (-32602)
        assert response["error"]["code"] == -32602
        assert "Tool not found" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_invalid_params_raises_error(self):
        """Test calling tool with invalid parameters returns JSON-RPC error."""
        from sipap_data_mcp.server import SIPAPDataMCP

        with patch("sipap_data_mcp.server.AuroraDataClient") as mock_db:
            with patch("sipap_data_mcp.server.RedisCache") as mock_cache:
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_cache_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                mock_cache.return_value = mock_cache_instance

                server = SIPAPDataMCP(
                    db_host="localhost",
                    db_port=5432,
                    db_name="test_db",
                    db_user="test_user",
                    db_password="test_pass",
                    redis_url="redis://localhost:6379/0"
                )

                await server._setup()

                # Missing required parameters
                request = {
                    "jsonrpc": "2.0",
                    "id": "test-1",
                    "method": "tools/call",
                    "params": {
                        "name": "get_match_schedule",
                        "arguments": {}  # Missing date_from, date_to
                    }
                }

                response = server.handle_request(request)

                # Should return JSON-RPC error
                assert response["jsonrpc"] == "2.0"
                assert response["id"] == "test-1"
                assert "error" in response

                await server._cleanup()

    @pytest.mark.asyncio
    async def test_all_tools_callable(self):
        """Test all 11 tools are callable."""
        from sipap_data_mcp.server import SIPAPDataMCP

        with patch("sipap_data_mcp.server.AuroraDataClient") as mock_db:
            with patch("sipap_data_mcp.server.RedisCache") as mock_cache:
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_cache_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                mock_cache.return_value = mock_cache_instance

                # Mock all database methods
                mock_db_instance.get_matches.return_value = []
                mock_db_instance.get_match.return_value = None
                mock_db_instance.search_matches.return_value = []
                mock_db_instance.get_team_stats.return_value = None
                mock_db_instance.get_league_standings.return_value = []
                mock_db_instance.get_head_to_head.return_value = []
                mock_db_instance.query_historical_data.return_value = []
                mock_db_instance.get_team_form.return_value = []
                mock_db_instance.get_match_odds.return_value = None
                mock_db_instance.get_odds_history.return_value = []

                # Mock cache misses
                mock_cache_instance.get.return_value = None

                server = SIPAPDataMCP(
                    db_host="localhost",
                    db_port=5432,
                    db_name="test_db",
                    db_user="test_user",
                    db_password="test_pass",
                    redis_url="redis://localhost:6379/0"
                )

                await server._setup()

                # Test each tool is callable
                tools = server.list_tools()

                for tool in tools:
                    tool_name = tool["name"]
                    # We'll just verify the method exists and is callable
                    assert hasattr(server, tool_name)
                    assert callable(getattr(server, tool_name))

                await server._cleanup()
