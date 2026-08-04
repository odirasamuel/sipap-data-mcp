#!/usr/bin/env python3
"""
Verify historical data availability for statistical tools.

This script checks:
1. Total seasons of data available
2. Halftime score availability
3. Sample size for top teams/leagues
4. Data quality metrics

Run:
    python scripts/verify_historical_data.py

Requirements:
    - POSTGRES_HOST environment variable
    - POSTGRES_DB environment variable
    - POSTGRES_USER environment variable
    - POSTGRES_PASSWORD environment variable
"""

import os
import asyncio
import asyncpg
from datetime import datetime


async def verify_data():
    """Verify historical data availability."""

    # Get database credentials from environment
    host = os.environ.get("POSTGRES_HOST", "localhost")
    db = os.environ.get("POSTGRES_DB", "sipap")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")

    print(f"\n{'=' * 80}")
    print(f"SIPAP Historical Data Verification")
    print(f"{'=' * 80}\n")
    print(f"Connecting to: {host}/{db}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Connect to database
    try:
        conn = await asyncpg.connect(
            host=host,
            port=5432,
            database=db,
            user=user,
            password=password
        )
        print("✅ Database connection successful\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}\n")
        return

    try:
        # ====================================================================
        # Check 1: Total seasons of data per league
        # ====================================================================
        print(f"{'=' * 80}")
        print("Check 1: Historical Data Availability by League")
        print(f"{'=' * 80}\n")

        query = """
            SELECT
                league,
                MIN(EXTRACT(YEAR FROM scheduled)) as earliest_year,
                MAX(EXTRACT(YEAR FROM scheduled)) as latest_year,
                MAX(EXTRACT(YEAR FROM scheduled)) - MIN(EXTRACT(YEAR FROM scheduled)) + 1 as total_years,
                COUNT(*) as total_matches,
                COUNT(CASE WHEN status = 'finished' THEN 1 END) as finished_matches,
                COUNT(CASE WHEN metadata ? 'halftime_home_score' THEN 1 END) as with_halftime,
                COUNT(CASE WHEN metadata ? 'odds' THEN 1 END) as with_odds
            FROM fixtures
            WHERE status = 'finished'
            GROUP BY league
            ORDER BY total_matches DESC
            LIMIT 20;
        """

        rows = await conn.fetch(query)

        print(f"{'League':<35} | {'Years':<6} | {'Matches':<8} | {'Halftime':<10} | {'Odds':<10}")
        print(f"{'-' * 35} | {'-' * 6} | {'-' * 8} | {'-' * 10} | {'-' * 10}")

        for row in rows:
            halftime_pct = (row['with_halftime'] / row['total_matches']) * 100 if row['total_matches'] > 0 else 0
            odds_pct = (row['with_odds'] / row['total_matches']) * 100 if row['total_matches'] > 0 else 0

            league_name = row['league'][:34]  # Truncate long names
            years_range = f"{int(row['earliest_year'])}-{int(row['latest_year'])}"

            # Quality indicator
            quality = "✅" if row['total_years'] >= 3 and halftime_pct >= 70 else "⚠️" if row['total_years'] >= 2 else "❌"

            print(f"{quality} {league_name:<33} | {years_range:<6} | {row['total_matches']:<8} | "
                  f"{halftime_pct:>6.1f}% | {odds_pct:>6.1f}%")

        # ====================================================================
        # Check 2: Top teams by historical matches
        # ====================================================================
        print(f"\n{'=' * 80}")
        print("Check 2: Top Teams by Historical Matches")
        print(f"{'=' * 80}\n")

        query = """
            SELECT
                team,
                COUNT(*) as total_matches,
                MIN(scheduled) as earliest,
                MAX(scheduled) as latest,
                COUNT(DISTINCT league) as leagues_played
            FROM (
                SELECT home_team as team, scheduled, league FROM fixtures WHERE status = 'finished'
                UNION ALL
                SELECT away_team as team, scheduled, league FROM fixtures WHERE status = 'finished'
            ) all_teams
            GROUP BY team
            ORDER BY total_matches DESC
            LIMIT 15;
        """

        rows = await conn.fetch(query)

        print(f"{'Team':<35} | {'Matches':<8} | {'Period':<15} | {'Leagues':<8}")
        print(f"{'-' * 35} | {'-' * 8} | {'-' * 15} | {'-' * 8}")

        for row in rows:
            team_name = row['team'][:34]
            period = f"{row['earliest'].year}-{row['latest'].year}"
            quality = "✅" if row['total_matches'] >= 20 else "⚠️" if row['total_matches'] >= 10 else "❌"

            print(f"{quality} {team_name:<33} | {row['total_matches']:<8} | {period:<15} | {row['leagues_played']:<8}")

        # ====================================================================
        # Check 3: Halftime data availability
        # ====================================================================
        print(f"\n{'=' * 80}")
        print("Check 3: Halftime Data Availability")
        print(f"{'=' * 80}\n")

        query = """
            SELECT
                COUNT(*) as total_finished,
                COUNT(CASE WHEN metadata ? 'halftime_home_score' THEN 1 END) as with_halftime,
                COUNT(CASE WHEN metadata ? 'halftime_home_score' THEN 1 END) * 100.0 / COUNT(*) as halftime_percentage
            FROM fixtures
            WHERE status = 'finished';
        """

        row = await conn.fetchrow(query)

        halftime_pct = row['halftime_percentage']
        halftime_status = "✅ GOOD" if halftime_pct >= 70 else "⚠️ WARNING" if halftime_pct >= 50 else "❌ POOR"

        print(f"Total finished matches: {row['total_finished']:,}")
        print(f"Matches with halftime data: {row['with_halftime']:,}")
        print(f"Halftime data coverage: {halftime_pct:.1f}% {halftime_status}")

        # ====================================================================
        # Check 4: Head-to-head sample size
        # ====================================================================
        print(f"\n{'=' * 80}")
        print("Check 4: Head-to-Head Match Availability (Sample)")
        print(f"{'=' * 80}\n")

        query = """
            WITH h2h_pairs AS (
                SELECT
                    LEAST(home_team, away_team) as team_a,
                    GREATEST(home_team, away_team) as team_b,
                    league,
                    COUNT(*) as matches
                FROM fixtures
                WHERE status = 'finished'
                    AND scheduled >= NOW() - INTERVAL '6 years'
                GROUP BY
                    LEAST(home_team, away_team),
                    GREATEST(home_team, away_team),
                    league
                HAVING COUNT(*) >= 5
            )
            SELECT
                team_a,
                team_b,
                league,
                matches
            FROM h2h_pairs
            ORDER BY matches DESC
            LIMIT 10;
        """

        rows = await conn.fetch(query)

        print(f"{'Team A':<25} | {'Team B':<25} | {'League':<20} | {'Matches':<8}")
        print(f"{'-' * 25} | {'-' * 25} | {'-' * 20} | {'-' * 8}")

        for row in rows:
            quality = "✅" if row['matches'] >= 15 else "⚠️" if row['matches'] >= 8 else "❌"
            print(f"{quality} {row['team_a']:<23} | {row['team_b']:<23} | {row['league']:<18} | {row['matches']:<8}")

        # ====================================================================
        # Summary and Recommendations
        # ====================================================================
        print(f"\n{'=' * 80}")
        print("Summary & Recommendations")
        print(f"{'=' * 80}\n")

        # Determine overall status
        total_leagues = len(await conn.fetch("SELECT DISTINCT league FROM fixtures WHERE status = 'finished'"))
        leagues_with_3plus_years = len([r for r in await conn.fetch(
            """
            SELECT
                league,
                MAX(EXTRACT(YEAR FROM scheduled)) - MIN(EXTRACT(YEAR FROM scheduled)) + 1 as years
            FROM fixtures
            WHERE status = 'finished'
            GROUP BY league
            HAVING MAX(EXTRACT(YEAR FROM scheduled)) - MIN(EXTRACT(YEAR FROM scheduled)) + 1 >= 3
            """
        )])

        quality_score = 0
        recommendations = []

        # Assess historical depth
        if leagues_with_3plus_years >= 10:
            print("✅ Historical Depth: EXCELLENT (10+ leagues with 3+ seasons)")
            quality_score += 40
        elif leagues_with_3plus_years >= 5:
            print("⚠️  Historical Depth: GOOD (5-9 leagues with 3+ seasons)")
            quality_score += 30
            recommendations.append("Consider API subscription for leagues with <3 seasons")
        else:
            print("❌ Historical Depth: POOR (<5 leagues with 3+ seasons)")
            quality_score += 10
            recommendations.append("CRITICAL: Subscribe to API for historical data (Sportmonks, API-Football)")

        # Assess halftime data
        if halftime_pct >= 70:
            print("✅ Halftime Data: EXCELLENT (≥70% coverage)")
            quality_score += 30
        elif halftime_pct >= 50:
            print("⚠️  Halftime Data: MODERATE (50-69% coverage)")
            quality_score += 20
            recommendations.append("Phase 2 tools (halftime analysis) will have reduced accuracy")
        else:
            print("❌ Halftime Data: POOR (<50% coverage)")
            quality_score += 5
            recommendations.append("Skip Phase 2 tools until halftime data improves")

        # Assess sample size
        h2h_pairs_count = len(rows)
        if h2h_pairs_count >= 50:
            print("✅ H2H Sample Size: EXCELLENT (50+ pairs with 5+ matches)")
            quality_score += 30
        elif h2h_pairs_count >= 20:
            print("⚠️  H2H Sample Size: GOOD (20-49 pairs with 5+ matches)")
            quality_score += 20
        else:
            print("❌ H2H Sample Size: POOR (<20 pairs with 5+ matches)")
            quality_score += 5
            recommendations.append("Limited h2h data may reduce prediction accuracy")

        # Final recommendation
        print(f"\n{'=' * 80}")
        print(f"Overall Data Quality Score: {quality_score}/100")
        print(f"{'=' * 80}\n")

        if quality_score >= 80:
            print("🎉 RECOMMENDATION: Proceed with Phase 1-5 implementation")
            print("   - Data quality is excellent for all 24 statistical tools")
            print("   - Expected prediction accuracy: High")
        elif quality_score >= 60:
            print("✅ RECOMMENDATION: Proceed with Phase 1-5 implementation")
            print("   - Data quality is good for most tools")
            print("   - Expected prediction accuracy: Medium-High")
        elif quality_score >= 40:
            print("⚠️  RECOMMENDATION: Proceed with Phase 1 only, consider API subscription")
            print("   - Implement 5 core tools first")
            print("   - Evaluate results before investing in Phase 2-4")
            print("   - Expected prediction accuracy: Medium")
        else:
            print("❌ RECOMMENDATION: Subscribe to sports data API before implementation")
            print("   - Current data insufficient for reliable predictions")
            print("   - Suggested APIs: Sportmonks ($59/mo), API-Football ($30/mo)")

        if recommendations:
            print(f"\n{'Specific Recommendations:'}")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        print(f"\n{'=' * 80}\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(verify_data())
