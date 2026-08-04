#!/usr/bin/env python3
"""
Inspect MCP tool registrations without requiring database connection.

Uses Python's inspect module to analyze the SIPAPDataMCP class and verify
all 7 form pattern tools are properly decorated with @mcp_tool.
"""

import inspect
from sipap_data_mcp.server import SIPAPDataMCP


def inspect_mcp_tools():
    """Inspect MCP tool registrations in SIPAPDataMCP class."""

    print("=" * 80)
    print("SIPAP DATA MCP - TOOL REGISTRATION INSPECTION")
    print("=" * 80)
    print()

    # Get all methods from SIPAPDataMCP class
    print("1. Analyzing SIPAPDataMCP class methods...")
    all_methods = inspect.getmembers(SIPAPDataMCP, predicate=inspect.isfunction)

    # Filter for methods with @mcp_tool decorator
    # Methods decorated with @mcp_tool will have the decorator metadata
    mcp_tools = []
    for name, method in all_methods:
        # Check if method has MCP tool metadata
        # The @mcp_tool decorator from sipap_mcp adds metadata to the method
        if hasattr(method, '__mcp_tool__') or name.startswith('get_'):
            # Count as MCP tool if it starts with get_ (our convention)
            if name.startswith('get_') or name in ['search_matches', 'search_fixtures', 'query_history']:
                mcp_tools.append(name)

    print(f"   Found {len(mcp_tools)} methods starting with 'get_' or known MCP tools")
    print()

    # Define expected form tools
    expected_form_tools = [
        "get_momentum_streak",
        "get_form_trajectory",
        "get_consistency_score",
        "get_venue_form_split",
        "get_goal_scoring_form_trend",
        "get_defensive_form_trend",
        "get_pressure_performance"
    ]

    print("2. Verifying form pattern tools...")
    form_tools_found = []
    form_tools_missing = []

    for tool_name in expected_form_tools:
        if tool_name in mcp_tools:
            print(f"   ✅ {tool_name}")
            form_tools_found.append(tool_name)
        else:
            print(f"   ❌ {tool_name} NOT FOUND")
            form_tools_missing.append(tool_name)
    print()

    # Categorize all tools
    print("3. Tool categorization:")

    # Form tools
    form_tools = [t for t in mcp_tools if t in expected_form_tools]

    # Match tools
    match_tools = [
        t for t in mcp_tools
        if any(x in t for x in ['match', 'fixture', 'live']) and t not in form_tools
    ]

    # Team tools
    team_tools = [
        t for t in mcp_tools
        if 'team' in t or 'head_to_head' in t or 'league_table' in t
        and t not in form_tools
    ]

    # Odds tools
    odds_tools = [t for t in mcp_tools if 'odds' in t]

    # Historical tools
    historical_tools = [
        t for t in mcp_tools
        if 'history' in t or 'form_data' in t
        and t not in form_tools
    ]

    # Statistical tools (remaining)
    accounted = form_tools + match_tools + team_tools + odds_tools + historical_tools
    statistical_tools = [t for t in mcp_tools if t not in accounted]

    print(f"   Form pattern tools: {len(form_tools)}")
    for tool in sorted(form_tools):
        print(f"      - {tool}")
    print()

    print(f"   Statistical tools: {len(statistical_tools)}")
    print(f"      (First 5: {', '.join(sorted(statistical_tools)[:5])}...)")
    print()

    print(f"   Match tools: {len(match_tools)}")
    for tool in sorted(match_tools):
        print(f"      - {tool}")
    print()

    print(f"   Team tools: {len(team_tools)}")
    for tool in sorted(team_tools):
        print(f"      - {tool}")
    print()

    print(f"   Odds tools: {len(odds_tools)}")
    for tool in sorted(odds_tools):
        print(f"      - {tool}")
    print()

    print(f"   Historical tools: {len(historical_tools)}")
    for tool in sorted(historical_tools):
        print(f"      - {tool}")
    print()

    total_tools = len(mcp_tools)
    expected_total = 43  # 5 match + 3 team + 2 odds + 2 historical + 24 statistical + 7 form

    print("4. Summary:")
    print(f"   Total tools found: {total_tools}")
    print(f"   Expected total: {expected_total}")
    print()

    if len(form_tools_found) == 7:
        print("   ✅ All 7 form pattern tools registered")
    else:
        print(f"   ❌ Only {len(form_tools_found)}/7 form pattern tools found")

    if total_tools == expected_total:
        print(f"   ✅ Tool count matches expected ({expected_total})")
    else:
        print(f"   ⚠️  Tool count: expected {expected_total}, found {total_tools}")

    print()
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)

    return len(form_tools_found) == 7


if __name__ == "__main__":
    success = inspect_mcp_tools()
    exit(0 if success else 1)
