#!/usr/bin/env python3
"""
Verify how many seasons of data API-Football returns.

Run this script to see:
- Total matches returned
- Date range (earliest to latest match)
- Number of football seasons covered
- Breakdown by season

Usage:
    python scripts/verify_data_coverage.py <team1_id> <team2_id>

Example (Lorient vs Troyes):
    python scripts/verify_data_coverage.py 167 112
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sipap_data_mcp.api.football_client import APIFootballClient
from sipap_data_mcp.tools.statistical.base import get_football_season


async def verify_data_coverage(team1_id: int, team2_id: int):
    """Verify H2H data coverage for a team pair."""

    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        print("ERROR: Set API_FOOTBALL_KEY environment variable")
        print("  export API_FOOTBALL_KEY=your_api_key")
        return

    print(f"\n{'='*60}")
    print(f"Verifying H2H data coverage for teams {team1_id} vs {team2_id}")
    print(f"{'='*60}\n")

    async with APIFootballClient(api_key=api_key) as client:
        # Fetch H2H data with last=50
        response = await client.get_h2h(
            team1_id=team1_id,
            team2_id=team2_id,
            last=50  # Same as in base.py
        )

        fixtures = response.get("response", [])

        if not fixtures:
            print("No H2H matches found!")
            return

        print(f"Total matches returned: {len(fixtures)}\n")

        # Analyze dates
        dates = []
        seasons = defaultdict(list)

        for fixture in fixtures:
            date_str = fixture.get("fixture", {}).get("date", "")
            if date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                dates.append(dt)

                # Get football season (Aug-Jul)
                season = get_football_season(dt)

                home = fixture.get("teams", {}).get("home", {}).get("name", "?")
                away = fixture.get("teams", {}).get("away", {}).get("name", "?")
                home_score = fixture.get("goals", {}).get("home", "?")
                away_score = fixture.get("goals", {}).get("away", "?")

                seasons[season].append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "match": f"{home} {home_score}-{away_score} {away}"
                })

        if dates:
            earliest = min(dates)
            latest = max(dates)

            print(f"Date Range:")
            print(f"  Earliest: {earliest.strftime('%Y-%m-%d')} (Season {get_football_season(earliest)})")
            print(f"  Latest:   {latest.strftime('%Y-%m-%d')} (Season {get_football_season(latest)})")
            print(f"  Span:     {(latest - earliest).days // 365} years\n")

        print(f"Football Seasons Covered: {len(seasons)}\n")

        # Print breakdown by season
        print("Breakdown by Football Season (Aug-Jul):")
        print("-" * 50)
        for season in sorted(seasons.keys(), reverse=True):
            matches = seasons[season]
            print(f"\nSeason {season}-{season+1}: {len(matches)} matches")
            for match in matches[:3]:  # Show first 3
                print(f"  {match['date']}: {match['match']}")
            if len(matches) > 3:
                print(f"  ... and {len(matches) - 3} more")

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"  Total matches:     {len(fixtures)}")
        print(f"  Seasons covered:   {len(seasons)}")
        if dates:
            print(f"  Date range:        {earliest.year} - {latest.year}")

        # Check if this is enough data
        current_season = get_football_season(datetime.now())
        last_season_matches = len(seasons.get(current_season - 1, []))
        older_matches = sum(len(m) for s, m in seasons.items() if s < current_season - 1)

        print(f"\n  For RecencyWeightCalculator:")
        print(f"    Recent (last 10):    {min(len(fixtures), 10)} matches")
        print(f"    Last season ({current_season-1}): {last_season_matches} matches")
        print(f"    Older (< {current_season-1}):    {older_matches} matches")

        # Check sample guards
        MIN_SAMPLES = 3
        print(f"\n  Sample Guard Check (min={MIN_SAMPLES}):")
        print(f"    Recent bucket:      {'INCLUDED' if len(fixtures) >= MIN_SAMPLES else 'EXCLUDED (too few)'}")
        print(f"    Last season bucket: {'INCLUDED' if last_season_matches >= MIN_SAMPLES else 'EXCLUDED (too few)'}")
        print(f"    Older bucket:       {'INCLUDED' if older_matches >= MIN_SAMPLES else 'EXCLUDED (too few)'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/verify_data_coverage.py <team1_id> <team2_id>")
        print("Example: python scripts/verify_data_coverage.py 167 112")
        sys.exit(1)

    team1 = int(sys.argv[1])
    team2 = int(sys.argv[2])

    asyncio.run(verify_data_coverage(team1, team2))
