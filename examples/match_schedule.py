"""Example: Retrieve match schedule using SIPAP Data MCP tools.

This example demonstrates:
- Creating a database client
- Getting matches for a date range
- Filtering by status and league
- Proper resource cleanup
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.matches import get_live_matches, get_match_schedule


async def main():
    """Demonstrate match schedule retrieval."""
    # Initialize database client
    client = AuroraDataClient(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "sipap"),
        user=os.environ.get("DB_USER", "sipap_readonly"),
        password=os.environ.get("DB_PASSWORD", ""),
    )

    try:
        # Connect to database
        print("Connecting to database...")
        await client.connect()
        print("✅ Connected successfully\n")

        # Example 1: Get scheduled matches for next 7 days
        print("=" * 60)
        print("Example 1: Upcoming Matches (Next 7 Days)")
        print("=" * 60)

        today = datetime.now(UTC).date()
        next_week = today + timedelta(days=7)

        result = await get_match_schedule(
            db_client=client,
            date_from=today.isoformat(),
            date_to=next_week.isoformat(),
            status="scheduled",
        )

        print(f"Found {len(result['matches'])} scheduled matches:")
        for match in result["matches"][:5]:  # Show first 5
            print(f"\n  {match['scheduled_at']}")
            print(f"  {match['home_team']} vs {match['away_team']}")
            print(f"  League: {match['league']}")
            print(f"  Venue: {match['venue']}")

        # Example 2: Get live matches
        print("\n" + "=" * 60)
        print("Example 2: Live Matches")
        print("=" * 60)

        live_result = await get_live_matches(db_client=client)

        if live_result["matches"]:
            print(f"Found {len(live_result['matches'])} live matches:")
            for match in live_result["matches"]:
                print(f"\n  ⚽ LIVE: {match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}")
                print(f"     League: {match['league']}")
        else:
            print("No live matches at the moment.")

        # Example 3: Get matches for specific league
        print("\n" + "=" * 60)
        print("Example 3: Matches for Specific League")
        print("=" * 60)

        # Assuming we have a Premier League ID
        league_id = "550e8400-e29b-41d4-a716-446655440000"

        league_result = await get_match_schedule(
            db_client=client,
            date_from=today.isoformat(),
            date_to=next_week.isoformat(),
            status="scheduled",
            league_id=league_id,
        )

        print(f"Found {len(league_result['matches'])} matches for this league:")
        for match in league_result["matches"][:3]:  # Show first 3
            print(f"\n  {match['scheduled_at']}")
            print(f"  {match['home_team']} vs {match['away_team']}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up resources
        await client.close()
        print("\n✅ Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
