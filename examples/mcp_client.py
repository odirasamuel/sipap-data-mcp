"""MCP Client Example - JSON-RPC 2.0 Protocol.

Demonstrates how to interact with the SIPAP Data MCP Server via JSON-RPC 2.0.
This is how AI agents (Claude, GPT-4) call the sports data tools.

The MCP server provides 11 tools via JSON-RPC 2.0 protocol:
- 4 match tools (schedule, details, live, search)
- 3 team tools (stats, standings, head-to-head)
- 2 historical tools (query history, form data)
- 2 odds tools (current odds, movements)

Prerequisites:
- MCP server initialized (with DB and Redis connections)
- Python 3.12+

This example shows:
1. Listing all available tools
2. Calling tools via JSON-RPC 2.0
3. Handling responses
4. Error handling
"""

import json
import os
from typing import Any

from sipap_data_mcp.server import SIPAPDataMCP


def print_separator(title: str) -> None:
    """Print a section separator."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_json(data: Any) -> None:
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2))


def list_tools_example(server: SIPAPDataMCP) -> None:
    """Example 1: List all available tools."""
    print_separator("Example 1: List Available Tools")

    # JSON-RPC 2.0 request to list tools
    request = {
        "jsonrpc": "2.0",
        "id": "list-1",
        "method": "tools/list",
        "params": {}
    }

    print("Request:")
    print_json(request)

    # Send request to MCP server
    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)

    # Extract tools from response
    if "result" in response:
        tools = response["result"]["tools"]
        print(f"\n✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")


def get_match_schedule_example(server: SIPAPDataMCP) -> None:
    """Example 2: Get match schedule via JSON-RPC."""
    print_separator("Example 2: Get Match Schedule")

    # JSON-RPC 2.0 request to call get_match_schedule tool
    request = {
        "jsonrpc": "2.0",
        "id": "schedule-1",
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

    print("Request:")
    print_json(request)

    # Send request to MCP server
    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)

    # Extract result from MCP content format
    if "result" in response:
        content = response["result"]["content"]
        if content and len(content) > 0:
            result = json.loads(content[0]["text"])
            print(f"\n✅ Found {len(result.get('matches', []))} matches")


def get_live_matches_example(server: SIPAPDataMCP) -> None:
    """Example 3: Get live matches via JSON-RPC."""
    print_separator("Example 3: Get Live Matches")

    request = {
        "jsonrpc": "2.0",
        "id": "live-1",
        "method": "tools/call",
        "params": {
            "name": "get_live_matches",
            "arguments": {}
        }
    }

    print("Request:")
    print_json(request)

    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)

    if "result" in response:
        content = response["result"]["content"]
        if content and len(content) > 0:
            result = json.loads(content[0]["text"])
            print(f"\n✅ Found {len(result.get('matches', []))} live matches")


def get_match_odds_example(server: SIPAPDataMCP, match_id: str) -> None:
    """Example 4: Get match odds via JSON-RPC."""
    print_separator("Example 4: Get Match Odds")

    request = {
        "jsonrpc": "2.0",
        "id": "odds-1",
        "method": "tools/call",
        "params": {
            "name": "get_match_odds",
            "arguments": {
                "match_id": match_id,
                "market": "h2h"
            }
        }
    }

    print("Request:")
    print_json(request)

    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)


def error_handling_example(server: SIPAPDataMCP) -> None:
    """Example 5: Error handling - nonexistent tool."""
    print_separator("Example 5: Error Handling")

    # Try to call a tool that doesn't exist
    request = {
        "jsonrpc": "2.0",
        "id": "error-1",
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    }

    print("Request (calling nonexistent tool):")
    print_json(request)

    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)

    if "error" in response:
        error = response["error"]
        print(f"\n❌ Error: {error['message']} (code: {error['code']})")


def invalid_params_example(server: SIPAPDataMCP) -> None:
    """Example 6: Error handling - invalid parameters."""
    print_separator("Example 6: Invalid Parameters")

    # Try to call tool with missing required parameters
    request = {
        "jsonrpc": "2.0",
        "id": "error-2",
        "method": "tools/call",
        "params": {
            "name": "get_match_schedule",
            "arguments": {}  # Missing date_from, date_to
        }
    }

    print("Request (missing required parameters):")
    print_json(request)

    response = server.handle_request(request)

    print("\nResponse:")
    print_json(response)

    if "error" in response:
        error = response["error"]
        print(f"\n❌ Error: {error['message']} (code: {error['code']})")


async def main() -> None:
    """Run all MCP client examples."""
    print("="*80)
    print("  SIPAP Data MCP - JSON-RPC 2.0 Client Examples")
    print("="*80)

    # Initialize MCP server
    print("\n📡 Initializing MCP server...")
    server = SIPAPDataMCP(
        db_host=os.environ.get("DB_HOST", "localhost"),
        db_port=int(os.environ.get("DB_PORT", "5432")),
        db_name=os.environ.get("DB_NAME", "sipap"),
        db_user=os.environ.get("DB_USER", "sipap_readonly"),
        db_password=os.environ.get("DB_PASSWORD", "password"),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )

    # Setup connections
    await server._setup()
    print("✅ MCP server initialized")

    try:
        # Run examples
        list_tools_example(server)
        get_match_schedule_example(server)
        get_live_matches_example(server)

        # Use a sample match ID for odds example
        match_id = "550e8400-e29b-41d4-a716-446655440000"
        get_match_odds_example(server, match_id)

        error_handling_example(server)
        invalid_params_example(server)

        print_separator("Summary")
        print("✅ All examples completed successfully!")
        print("\nKey Takeaways:")
        print("1. MCP server uses JSON-RPC 2.0 protocol")
        print("2. All requests have: jsonrpc, id, method, params")
        print("3. Successful responses have: jsonrpc, id, result")
        print("4. Error responses have: jsonrpc, id, error (with code and message)")
        print("5. Tool results are wrapped in MCP content format")
        print("\nThis is how AI agents (Claude, GPT-4) interact with SIPAP data tools.")

    finally:
        # Cleanup connections
        await server._cleanup()
        print("\n🔌 MCP server shut down")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
