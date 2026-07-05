"""Example: Retrieve team statistics using SIPAP Data MCP tools.

This example demonstrates:
- Getting team statistics for a season
- Retrieving league standings
- Analyzing home/away records
- Proper error handling
"""

import asyncio
import os

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.teams import get_team_stats, get_league_table


async def main():
    """Demonstrate team statistics retrieval."""
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

        # Example 1: Get team statistics
        print("=" * 60)
        print("Example 1: Team Statistics (Arsenal 2024-2025)")
        print("=" * 60)

        team_id = "550e8400-e29b-41d4-a716-446655440010"
        season = "2024-2025"

        result = await get_team_stats(
            db_client=client,
            team_id=team_id,
            season=season,
        )

        stats = result["stats"]
        print(f"\n{stats['team_name']} - Season {stats['season']}")
        print(f"{'=' * 40}")
        print(f"Matches Played: {stats['matches_played']}")
        print(f"Record: {stats['wins']}W - {stats['draws']}D - {stats['losses']}L")
        print(f"Goals: {stats['goals_scored']} scored, {stats['goals_conceded']} conceded")
        print(f"Goal Difference: {stats['goal_difference']:+d}")
        print(f"Points: {stats['points']}")
        print(f"Recent Form: {' '.join(stats['form'])}")

        print(f"\nHome Record:")
        print(f"  {stats['home_record']['wins']}W - {stats['home_record']['draws']}D - {stats['home_record']['losses']}L")

        print(f"\nAway Record:")
        print(f"  {stats['away_record']['wins']}W - {stats['away_record']['draws']}D - {stats['away_record']['losses']}L")

        # Example 2: Get league standings
        print("\n" + "=" * 60)
        print("Example 2: Premier League Standings 2024-2025")
        print("=" * 60)

        league_id = "550e8400-e29b-41d4-a716-446655440020"

        standings_result = await get_league_table(
            db_client=client,
            league_id=league_id,
            season=season,
        )

        print(f"\n{'Pos':<4} {'Team':<25} {'P':<4} {'W':<4} {'D':<4} {'L':<4} {'GD':<6} {'Pts'}")
        print("-" * 60)

        for team in standings_result["standings"][:10]:  # Top 10
            print(
                f"{team['position']:<4} "
                f"{team['team_name']:<25} "
                f"{team['matches_played']:<4} "
                f"{team['wins']:<4} "
                f"{team['draws']:<4} "
                f"{team['losses']:<4} "
                f"{team['goal_difference']:+6} "
                f"{team['points']}"
            )

        # Example 3: Error handling - Team not found
        print("\n" + "=" * 60)
        print("Example 3: Error Handling (Team Not Found)")
        print("=" * 60)

        try:
            invalid_result = await get_team_stats(
                db_client=client,
                team_id="00000000-0000-0000-0000-000000000000",
                season=season,
            )
        except ValueError as e:
            print(f"✅ Caught expected error: {e}")

        # Example 4: Error handling - Invalid season format
        print("\n" + "=" * 60)
        print("Example 4: Error Handling (Invalid Season Format)")
        print("=" * 60)

        try:
            invalid_result = await get_team_stats(
                db_client=client,
                team_id=team_id,
                season="2024",  # Invalid format, should be YYYY-YYYY
            )
        except ValueError as e:
            print(f"✅ Caught expected error: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up resources
        await client.close()
        print("\n✅ Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
