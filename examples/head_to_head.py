"""Example: Retrieve head-to-head statistics using SIPAP Data MCP tools.

This example demonstrates:
- Comparing two teams' historical matchups
- Calculating win/loss/draw statistics
- Retrieving recent match results
- Analyzing match history
"""

import asyncio
import os

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.teams import get_head_to_head


async def main():
    """Demonstrate head-to-head analysis."""
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

        # Example 1: Head-to-head between Arsenal and Chelsea
        print("=" * 60)
        print("Example 1: Arsenal vs Chelsea (Last 10 Matches)")
        print("=" * 60)

        team1_id = "550e8400-e29b-41d4-a716-446655440010"  # Arsenal
        team2_id = "550e8400-e29b-41d4-a716-446655440011"  # Chelsea

        result = await get_head_to_head(
            db_client=client,
            team1_id=team1_id,
            team2_id=team2_id,
            limit=10,
        )

        h2h = result["head_to_head"]

        print(f"\n{h2h['team1_name']} vs {h2h['team2_name']}")
        print("=" * 40)
        print(f"Total Matches: {h2h['total_matches']}")
        print(f"{h2h['team1_name']} Wins: {h2h['team1_wins']}")
        print(f"{h2h['team2_name']} Wins: {h2h['team2_wins']}")
        print(f"Draws: {h2h['draws']}")

        if h2h['total_matches'] > 0:
            team1_win_pct = (h2h['team1_wins'] / h2h['total_matches']) * 100
            team2_win_pct = (h2h['team2_wins'] / h2h['total_matches']) * 100
            draw_pct = (h2h['draws'] / h2h['total_matches']) * 100

            print("\nWin Percentages:")
            print(f"  {h2h['team1_name']}: {team1_win_pct:.1f}%")
            print(f"  {h2h['team2_name']}: {team2_win_pct:.1f}%")
            print(f"  Draws: {draw_pct:.1f}%")

        # Show recent matches
        if h2h['recent_matches']:
            print("\nRecent Matches:")
            print("-" * 60)
            for match in h2h['recent_matches'][:5]:  # Show last 5
                print(f"\n  {match['scheduled_at']}")
                print(f"  {match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}")

        # Example 2: Limited results (last 5 matches only)
        print("\n" + "=" * 60)
        print("Example 2: Last 5 Matches Only")
        print("=" * 60)

        limited_result = await get_head_to_head(
            db_client=client,
            team1_id=team1_id,
            team2_id=team2_id,
            limit=5,
        )

        limited_h2h = limited_result["head_to_head"]
        print(f"\nAnalyzing last {len(limited_h2h['recent_matches'])} matches:")
        print(f"{limited_h2h['team1_name']}: {limited_h2h['team1_wins']} wins")
        print(f"{limited_h2h['team2_name']}: {limited_h2h['team2_wins']} wins")
        print(f"Draws: {limited_h2h['draws']}")

        # Example 3: Teams with no history
        print("\n" + "=" * 60)
        print("Example 3: Teams With No Match History")
        print("=" * 60)

        team3_id = "550e8400-e29b-41d4-a716-446655440030"  # New team
        team4_id = "550e8400-e29b-41d4-a716-446655440031"  # Another new team

        no_history_result = await get_head_to_head(
            db_client=client,
            team1_id=team3_id,
            team2_id=team4_id,
            limit=10,
        )

        no_history_h2h = no_history_result["head_to_head"]
        if no_history_h2h['total_matches'] == 0:
            print(f"\n{no_history_h2h['team1_name']} and {no_history_h2h['team2_name']} have never played.")

        # Example 4: Error handling - Same team comparison
        print("\n" + "=" * 60)
        print("Example 4: Error Handling (Same Team)")
        print("=" * 60)

        try:
            invalid_result = await get_head_to_head(
                db_client=client,
                team1_id=team1_id,
                team2_id=team1_id,  # Same team
                limit=10,
            )
        except ValueError as e:
            print(f"✅ Caught expected error: {e}")

        # Example 5: Error handling - Invalid UUID
        print("\n" + "=" * 60)
        print("Example 5: Error Handling (Invalid UUID)")
        print("=" * 60)

        try:
            invalid_result = await get_head_to_head(
                db_client=client,
                team1_id="not-a-valid-uuid",
                team2_id=team2_id,
                limit=10,
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
