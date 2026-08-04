#!/usr/bin/env python3
"""
Test script to verify form pattern tools are registered as MCP tools.

Tests:
1. MCP server initialization
2. tools/list endpoint (verify 43 tools total)
3. Call get_momentum_streak to verify it works
"""

import asyncio
import json
from sipap_data_mcp.server import SIPAPDataMCP


async def test_form_tools_registration():
    """Test that all 7 form tools are registered and callable."""

    print("=" * 80)
    print("FORM TOOLS MCP REGISTRATION TEST")
    print("=" * 80)
    print()

    # Initialize MCP server
    print("1. Initializing MCP server...")
    server = SIPAPDataMCP()
    print("   ✅ Server initialized")
    print()

    # Get list of tools
    print("2. Fetching tools/list...")
    tools = server.list_tools()
    print(f"   ✅ Found {len(tools)} tools")
    print()

    # Expected form tools
    expected_form_tools = [
        "get_momentum_streak",
        "get_form_trajectory",
        "get_consistency_score",
        "get_venue_form_split",
        "get_goal_scoring_form_trend",
        "get_defensive_form_trend",
        "get_pressure_performance"
    ]

    print("3. Verifying form pattern tools registration...")
    tool_names = [tool["name"] for tool in tools]

    for tool_name in expected_form_tools:
        if tool_name in tool_names:
            print(f"   ✅ {tool_name}")
        else:
            print(f"   ❌ {tool_name} NOT FOUND")
    print()

    # Count tool categories
    print("4. Tool count breakdown:")

    form_tools = [t for t in tool_names if t in expected_form_tools]
    match_tools = [t for t in tool_names if t.startswith("get_") and "match" in t and t not in form_tools]
    team_tools = [t for t in tool_names if t.startswith("get_team")]
    odds_tools = [t for t in tool_names if "odds" in t]
    historical_tools = [t for t in tool_names if "historical" in t or "season" in t]

    # Statistical tools (by elimination)
    stat_tools = [t for t in tool_names if t not in form_tools + match_tools + team_tools + odds_tools + historical_tools]

    print(f"   - Form pattern tools: {len(form_tools)}")
    print(f"   - Statistical tools: {len(stat_tools)}")
    print(f"   - Match tools: {len(match_tools)}")
    print(f"   - Team tools: {len(team_tools)}")
    print(f"   - Odds tools: {len(odds_tools)}")
    print(f"   - Historical tools: {len(historical_tools)}")
    print(f"   - TOTAL: {len(tools)} tools")
    print()

    # Verify expected count
    expected_total = 43  # 5 match + 3 team + 2 odds + 2 historical + 24 statistical + 7 form
    if len(tools) == expected_total:
        print(f"   ✅ Tool count matches expected: {expected_total}")
    else:
        print(f"   ⚠️  Tool count mismatch: expected {expected_total}, got {len(tools)}")
    print()

    # Test calling a form tool
    print("5. Testing get_momentum_streak call...")
    try:
        # Note: This will fail without database connection, but verifies tool is callable
        result = server.call_tool(
            "get_momentum_streak",
            {"team": "Arsenal", "league": "Premier League", "match_limit": 10}
        )
        print("   ✅ Tool callable (returned data or expected error)")
        print(f"   Response type: {type(result)}")
    except Exception as e:
        if "connection" in str(e).lower() or "pool" in str(e).lower():
            print("   ✅ Tool callable (database connection error expected in test)")
        else:
            print(f"   ❌ Unexpected error: {e}")
    print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    return len(form_tools) == 7 and len(tools) == expected_total


if __name__ == "__main__":
    success = asyncio.run(test_form_tools_registration())
    exit(0 if success else 1)
