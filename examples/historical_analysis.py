"""Example: Query historical data and analyze team form using SIPAP Data MCP tools.

This example demonstrates:
- Querying historical match data with filters
- Calculating team form from recent matches
- Analyzing performance trends
- Date range filtering
"""

import asyncio
import os
from datetime import datetime, timedelta, UTC

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.historical import query_history, get_form_data


async def main():
    """Demonstrate historical data analysis."""
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

        # Example 1: Query team's recent match history
        print("=" * 60)
        print("Example 1: Arsenal's Last 10 Matches")
        print("=" * 60)

        team_id = "550e8400-e29b-41d4-a716-446655440010"  # Arsenal

        result = await query_history(
            db_client=client,
            team_id=team_id,
            limit=10
        )

        print(f"\nFound {len(result['matches'])} historical matches:")
        for i, match in enumerate(result["matches"][:5], 1):  # Show first 5
            print(f"\n  {i}. {match['scheduled_at']}")
            print(f"     {match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}")
            print(f"     Status: {match['status']}")

        # Example 2: Calculate team form from recent matches
        print("\n" + "=" * 60)
        print("Example 2: Arsenal's Recent Form (Last 5 Matches)")
        print("=" * 60)

        form_result = await get_form_data(
            db_client=client,
            team_id=team_id,
            num_matches=5
        )

        print(f"\nForm: {' '.join(form_result['form'])}")
        print(f"{'=' * 40}")
        print(f"Wins: {form_result['wins']}")
        print(f"Draws: {form_result['draws']}")
        print(f"Losses: {form_result['losses']}")
        print(f"Points: {form_result['points']} / {len(form_result['form']) * 3}")

        # Calculate win percentage
        if form_result['form']:
            total_matches = len(form_result['form'])
            win_pct = (form_result['wins'] / total_matches) * 100
            print(f"Win Rate: {win_pct:.1f}%")

        # Example 3: Query matches within specific date range
        print("\n" + "=" * 60)
        print("Example 3: Arsenal's Matches in January 2026")
        print("=" * 60)

        jan_result = await query_history(
            db_client=client,
            team_id=team_id,
            date_from="2026-01-01",
            date_to="2026-01-31",
            limit=50
        )

        print(f"\nMatches in January 2026: {len(jan_result['matches'])}")
        if jan_result['matches']:
            for match in jan_result['matches'][:3]:  # Show first 3
                date_str = match['scheduled_at'][:10]
                print(f"\n  {date_str}: {match['home_team']} vs {match['away_team']}")
                print(f"  Score: {match['home_score']}-{match['away_score']}")

        # Example 4: Filter by league
        print("\n" + "=" * 60)
        print("Example 4: Arsenal's Premier League Matches Only")
        print("=" * 60)

        league_id = "550e8400-e29b-41d4-a716-446655440020"  # Premier League

        league_result = await query_history(
            db_client=client,
            team_id=team_id,
            league_id=league_id,
            limit=10
        )

        print(f"\nPremier League matches: {len(league_result['matches'])}")
        for match in league_result['matches'][:3]:  # Show first 3
            print(f"\n  {match['scheduled_at'][:10]}")
            print(f"  {match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}")
            print(f"  League: {match['league']}")

        # Example 5: Compare form over different periods
        print("\n" + "=" * 60)
        print("Example 5: Form Comparison (Last 5 vs Last 10 Matches)")
        print("=" * 60)

        form_5 = await get_form_data(
            db_client=client,
            team_id=team_id,
            num_matches=5
        )

        form_10 = await get_form_data(
            db_client=client,
            team_id=team_id,
            num_matches=10
        )

        print(f"\nLast 5 matches:")
        print(f"  Form: {' '.join(form_5['form'])}")
        print(f"  Points: {form_5['points']} / 15")
        print(f"  Win rate: {(form_5['wins'] / len(form_5['form']) * 100):.1f}%" if form_5['form'] else "N/A")

        print(f"\nLast 10 matches:")
        print(f"  Form: {' '.join(form_10['form'])}")
        print(f"  Points: {form_10['points']} / 30")
        print(f"  Win rate: {(form_10['wins'] / len(form_10['form']) * 100):.1f}%" if form_10['form'] else "N/A")

        # Trend analysis
        if form_5['form'] and form_10['form']:
            recent_ppg = form_5['points'] / len(form_5['form'])
            overall_ppg = form_10['points'] / len(form_10['form'])

            print(f"\nTrend Analysis:")
            print(f"  Recent PPG (last 5): {recent_ppg:.2f}")
            print(f"  Overall PPG (last 10): {overall_ppg:.2f}")

            if recent_ppg > overall_ppg:
                print(f"  📈 Improving form (+{(recent_ppg - overall_ppg):.2f} PPG)")
            elif recent_ppg < overall_ppg:
                print(f"  📉 Declining form ({(recent_ppg - overall_ppg):.2f} PPG)")
            else:
                print(f"  ➡️  Consistent form")

        # Example 6: Error handling - Invalid UUID
        print("\n" + "=" * 60)
        print("Example 6: Error Handling (Invalid UUID)")
        print("=" * 60)

        try:
            invalid_result = await query_history(
                db_client=client,
                team_id="not-a-valid-uuid",
                limit=10
            )
        except ValueError as e:
            print(f"✅ Caught expected error: {e}")

        # Example 7: Error handling - Invalid date format
        print("\n" + "=" * 60)
        print("Example 7: Error Handling (Invalid Date Format)")
        print("=" * 60)

        try:
            invalid_result = await query_history(
                db_client=client,
                team_id=team_id,
                date_from="2026-13-01",  # Invalid month
                limit=10
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
