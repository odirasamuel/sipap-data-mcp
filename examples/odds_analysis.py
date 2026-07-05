"""Example: Analyze betting odds and movements using SIPAP Data MCP tools.

This example demonstrates:
- Retrieving current betting odds from multiple bookmakers
- Finding best available odds for each outcome
- Tracking odds movements over time
- Identifying sharp money (steam moves)
- Calculating value bets
"""

import asyncio
import os

from sipap_data_mcp.database.aurora import AuroraDataClient
from sipap_data_mcp.tools.odds import get_match_odds, get_odds_movements


async def main():
    """Demonstrate odds intelligence analysis."""
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

        # Example 1: Get current betting odds for a match
        print("=" * 60)
        print("Example 1: Current Betting Odds Analysis")
        print("=" * 60)

        match_id = "550e8400-e29b-41d4-a716-446655440000"  # Arsenal vs Chelsea

        result = await get_match_odds(
            db_client=client,
            match_id=match_id
        )

        if result:
            print(f"\nMatch ID: {result['match_id']}")
            print(f"\nBookmakers offering odds: {len(result['bookmakers'])}")

            # Show first 3 bookmakers
            print("\nSample Bookmaker Odds:")
            for bookmaker_data in result["bookmakers"][:3]:
                print(f"\n  {bookmaker_data['bookmaker']}:")
                print(f"    Home: {bookmaker_data['home_odds']}")
                print(f"    Draw: {bookmaker_data['draw_odds']}")
                print(f"    Away: {bookmaker_data['away_odds']}")
                print(f"    Updated: {bookmaker_data['updated_at']}")

            # Show best odds
            print("\n" + "=" * 40)
            print("Best Available Odds:")
            print("=" * 40)
            if result["best_odds"]:
                print(f"\n  Home Win: {result['best_odds']['home']['odds']} ({result['best_odds']['home']['bookmaker']})")
                print(f"  Draw:     {result['best_odds']['draw']['odds']} ({result['best_odds']['draw']['bookmaker']})")
                print(f"  Away Win: {result['best_odds']['away']['odds']} ({result['best_odds']['away']['bookmaker']})")

            # Calculate implied probabilities
            if result["best_odds"]:
                print("\n" + "=" * 40)
                print("Implied Probabilities (from best odds):")
                print("=" * 40)
                home_prob = 1 / result['best_odds']['home']['odds'] * 100
                draw_prob = 1 / result['best_odds']['draw']['odds'] * 100
                away_prob = 1 / result['best_odds']['away']['odds'] * 100
                total_prob = home_prob + draw_prob + away_prob
                overround = total_prob - 100

                print(f"\n  Home Win: {home_prob:.2f}%")
                print(f"  Draw:     {draw_prob:.2f}%")
                print(f"  Away Win: {away_prob:.2f}%")
                print(f"  Total:    {total_prob:.2f}% (Overround: {overround:.2f}%)")
        else:
            print("❌ No odds data available for this match")

        # Example 2: Track odds movements over 24 hours
        print("\n" + "=" * 60)
        print("Example 2: Odds Movement Analysis (24 hours)")
        print("=" * 60)

        movements = await get_odds_movements(
            db_client=client,
            match_id=match_id,
            time_window="24h"
        )

        if movements:
            print(f"\nTime Window: {movements['time_window']}")
            print(f"Movements Tracked: {len(movements['movements'])}")

            # Show opening vs current odds
            if movements["opening_odds"] and movements["current_odds"]:
                print("\n" + "=" * 40)
                print("Opening vs Current Odds:")
                print("=" * 40)
                print("\n  Opening:")
                print(f"    Home: {movements['opening_odds']['home']}")
                print(f"    Draw: {movements['opening_odds']['draw']}")
                print(f"    Away: {movements['opening_odds']['away']}")

                print("\n  Current:")
                print(f"    Home: {movements['current_odds']['home']}")
                print(f"    Draw: {movements['current_odds']['draw']}")
                print(f"    Away: {movements['current_odds']['away']}")

            # Show movement summary
            if movements["movement_summary"]:
                print("\n" + "=" * 40)
                print("Movement Summary:")
                print("=" * 40)
                home_move = movements['movement_summary']['home']
                draw_move = movements['movement_summary']['draw']
                away_move = movements['movement_summary']['away']

                print(f"\n  Home: {home_move:+.2f} {'📉' if home_move < 0 else '📈' if home_move > 0 else '➡️'}")
                print(f"  Draw: {draw_move:+.2f} {'📉' if draw_move < 0 else '📈' if draw_move > 0 else '➡️'}")
                print(f"  Away: {away_move:+.2f} {'📉' if away_move < 0 else '📈' if away_move > 0 else '➡️'}")

                # Identify sharp money
                print("\n" + "=" * 40)
                print("Sharp Money Analysis:")
                print("=" * 40)
                if abs(home_move) > 0.15:
                    direction = "backing" if home_move < 0 else "avoiding"
                    print(f"\n  ⚠️  Significant movement on Home ({direction})")
                    print(f"      Odds moved {abs(home_move):.2f} - potential sharp money")
                if abs(away_move) > 0.15:
                    direction = "backing" if away_move < 0 else "avoiding"
                    print(f"\n  ⚠️  Significant movement on Away ({direction})")
                    print(f"      Odds moved {abs(away_move):.2f} - potential sharp money")

            # Show sample movements
            if movements["movements"]:
                print("\n" + "=" * 40)
                print("Recent Movements (last 3):")
                print("=" * 40)
                for movement in movements["movements"][:3]:
                    print(f"\n  {movement['timestamp']}")
                    print(f"    Bookmaker: {movement['bookmaker']}")
                    print(f"    Home: {movement['home_odds']}")
                    print(f"    Draw: {movement['draw_odds']}")
                    print(f"    Away: {movement['away_odds']}")
        else:
            print("❌ No odds movement data available for this match")

        # Example 3: Compare different time windows
        print("\n" + "=" * 60)
        print("Example 3: Multi-Window Movement Analysis")
        print("=" * 60)

        time_windows = ["1h", "6h", "24h"]
        for window in time_windows:
            movements = await get_odds_movements(
                db_client=client,
                match_id=match_id,
                time_window=window
            )

            if movements and movements["movement_summary"]:
                home_move = movements['movement_summary'].get('home', 0)
                print(f"\n  {window:>4}: Home odds moved {home_move:+.2f}")

        # Example 4: Calculate value bets
        print("\n" + "=" * 60)
        print("Example 4: Value Bet Detection")
        print("=" * 60)

        odds_result = await get_match_odds(
            db_client=client,
            match_id=match_id
        )

        if odds_result and odds_result["best_odds"]:
            # Assume we have our own probability model
            our_probabilities = {
                "home": 0.55,  # 55% chance home wins
                "draw": 0.25,  # 25% chance draw
                "away": 0.20,  # 20% chance away wins
            }

            print("\nOur Model Probabilities:")
            print(f"  Home: {our_probabilities['home']*100:.1f}%")
            print(f"  Draw: {our_probabilities['draw']*100:.1f}%")
            print(f"  Away: {our_probabilities['away']*100:.1f}%")

            print("\n" + "=" * 40)
            print("Value Analysis:")
            print("=" * 40)

            best_odds = odds_result["best_odds"]

            # Calculate expected value
            for outcome in ["home", "draw", "away"]:
                market_prob = 1 / best_odds[outcome]["odds"]
                our_prob = our_probabilities[outcome]
                ev = (our_prob * best_odds[outcome]["odds"]) - 1
                value_pct = (our_prob - market_prob) / market_prob * 100

                print(f"\n  {outcome.upper()}:")
                print(f"    Best odds: {best_odds[outcome]['odds']}")
                print(f"    Market prob: {market_prob*100:.2f}%")
                print(f"    Our prob: {our_prob*100:.2f}%")
                print(f"    Expected Value: {ev*100:+.2f}%")

                if ev > 0.05:  # 5% edge
                    print(f"    ✅ VALUE BET ({value_pct:+.1f}% value)")

        # Example 5: Error handling - Invalid UUID
        print("\n" + "=" * 60)
        print("Example 5: Error Handling (Invalid UUID)")
        print("=" * 60)

        try:
            await get_match_odds(
                db_client=client,
                match_id="not-a-valid-uuid"
            )
        except ValueError as e:
            print(f"✅ Caught expected error: {e}")

        # Example 6: Error handling - Invalid time window
        print("\n" + "=" * 60)
        print("Example 6: Error Handling (Invalid Time Window)")
        print("=" * 60)

        try:
            await get_odds_movements(
                db_client=client,
                match_id=match_id,
                time_window="invalid"
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
