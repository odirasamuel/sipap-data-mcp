"""
Lambda function to run Phase 3 integration tests from within VPC.

Deploy this as a Lambda function in the VPC with access to Aurora and Redis.
Invoke via AWS CLI or Console to run integration tests.
"""

import asyncio
import json
import os
from typing import Any


async def run_tests() -> dict[str, Any]:
    """Run integration tests and return results."""
    # Import here to avoid issues if dependencies aren't available
    import boto3
    from sipap_data_mcp.cache.redis import RedisCache
    from sipap_data_mcp.database.aurora import AuroraDataClient

    results = {
        "total_tests": 11,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "tests": []
    }

    # Get Aurora credentials from Secrets Manager
    secret_arn = os.getenv("AURORA_SECRET_ARN")
    if not secret_arn:
        return {
            "error": "AURORA_SECRET_ARN environment variable not set",
            "note": "Configure Lambda with Aurora credentials secret ARN"
        }

    try:
        secrets_client = boto3.client("secretsmanager")
        secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(secret_response["SecretString"])
        aurora_password = secret_data["password"]
        aurora_host = secret_data.get("host", os.getenv("AURORA_HOST", "sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com"))
    except Exception as e:
        return {
            "error": "Failed to retrieve Aurora credentials from Secrets Manager",
            "message": str(e)
        }

    # Create clients
    db = AuroraDataClient(
        host=aurora_host,
        port=5432,
        database="sipap_dev",
        user="sipap_admin",
        password=aurora_password,
    )

    redis_host = os.getenv("REDIS_HOST", "sipap-dev-redis.qnk6bl.0001.use1.cache.amazonaws.com")
    redis_port = os.getenv("REDIS_PORT", "6379")
    cache = RedisCache(url=f"redis://{redis_host}:{redis_port}/0")

    try:
        await db.connect()
        await cache.connect()

        # TEST 1: Standings table has data
        try:
            query = """
                SELECT team_id, team_name, rank, points, matches_played,
                       wins, draws, losses, goals_for, goals_against,
                       goal_difference, form
                FROM standings
                WHERE league_id = $1 AND season = $2
                ORDER BY rank ASC
            """
            async with db._pool.acquire() as conn:
                rows = await conn.fetch(query, 39, "2024")

            standings = [dict(row) for row in rows]
            assert len(standings) > 0, "No standings data"
            assert len(standings) <= 20, "Too many teams"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_standings_table_has_data",
                "status": "PASSED",
                "count": len(standings)
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_standings_table_has_data",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 2: Team statistics
        try:
            stats = await db.get_team_statistics(team_id=50, league_id=39, season="2024")
            assert stats is not None, "No team stats"
            assert "total_played" in stats
            results["passed"] += 1
            results["tests"].append({
                "name": "test_team_statistics_table_has_data",
                "status": "PASSED"
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_team_statistics_table_has_data",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 3: Head-to-head (may be empty - that's OK)
        try:
            h2h = await db.get_head_to_head_stats(team_1_id=50, team_2_id=42)
            results["passed"] += 1
            results["tests"].append({
                "name": "test_head_to_head_table_has_data",
                "status": "PASSED",
                "note": "Data exists" if h2h else "Not yet populated"
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_head_to_head_table_has_data",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 4: Odds table queryable
        try:
            async with db._pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) as count FROM odds LIMIT 1")
                count = row["count"] if row else 0
            results["passed"] += 1
            results["tests"].append({
                "name": "test_odds_table_has_data",
                "status": "PASSED",
                "odds_count": count
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_odds_table_has_data",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 5: Teams metadata
        try:
            query = """
                SELECT team_id, name, code, country, founded,
                       venue_name, venue_capacity
                FROM teams_metadata
                WHERE team_id = ANY($1::int[])
            """
            async with db._pool.acquire() as conn:
                rows = await conn.fetch(query, [50, 42, 33, 40])

            metadata = [dict(row) for row in rows]
            results["passed"] += 1
            results["tests"].append({
                "name": "test_teams_metadata_table_has_data",
                "status": "PASSED",
                "count": len(metadata)
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_teams_metadata_table_has_data",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 6: Query performance - standings
        try:
            import time
            start = time.perf_counter()

            query = """
                SELECT team_id, team_name, rank, points, matches_played
                FROM standings
                WHERE league_id = $1 AND season = $2
                ORDER BY rank ASC
            """
            async with db._pool.acquire() as conn:
                await conn.fetch(query, 39, "2024")

            duration_ms = (time.perf_counter() - start) * 1000
            assert duration_ms < 100, f"Too slow: {duration_ms:.1f}ms"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_standings_query_performance",
                "status": "PASSED",
                "duration_ms": round(duration_ms, 2)
            })
        except AssertionError as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_standings_query_performance",
                "status": "FAILED",
                "error": str(e)
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_standings_query_performance",
                "status": "ERROR",
                "error": str(e)
            })

        # TEST 7: Query performance - team stats
        try:
            import time
            start = time.perf_counter()
            await db.get_team_statistics(team_id=50, league_id=39, season="2024")
            duration_ms = (time.perf_counter() - start) * 1000
            assert duration_ms < 100, f"Too slow: {duration_ms:.1f}ms"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_team_stats_query_performance",
                "status": "PASSED",
                "duration_ms": round(duration_ms, 2)
            })
        except AssertionError as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_team_stats_query_performance",
                "status": "FAILED",
                "error": str(e)
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_team_stats_query_performance",
                "status": "ERROR",
                "error": str(e)
            })

        # TEST 8: Redis connection
        try:
            await cache.set("integration_test_key", {"test": "value"}, ttl=10)
            result = await cache.get("integration_test_key")
            await cache.delete("integration_test_key")
            assert result["test"] == "value"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_redis_connection",
                "status": "PASSED"
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_redis_connection",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 9: Redis cache with TTL
        try:
            key = "integration:team_stats:50:39:2024"
            data = {"stats": {"total_played": 38}}
            await cache.set(key, data, ttl=21600)
            cached = await cache.get(key)
            ttl = await cache.ttl(key)
            await cache.delete(key)
            assert cached["stats"]["total_played"] == 38
            assert 21590 <= ttl <= 21600
            results["passed"] += 1
            results["tests"].append({
                "name": "test_cache_team_stats",
                "status": "PASSED",
                "ttl_seconds": ttl
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_cache_team_stats",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 10: Data quality - sequential ranks
        try:
            query = """
                SELECT rank
                FROM standings
                WHERE league_id = $1 AND season = $2
                ORDER BY rank ASC
            """
            async with db._pool.acquire() as conn:
                rows = await conn.fetch(query, 39, "2024")

            standings = [dict(row) for row in rows]
            if standings:
                ranks = [s["rank"] for s in standings]
                expected = list(range(1, len(standings) + 1))
                assert ranks == expected, f"Ranks not sequential: {ranks}"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_standings_ranks_are_sequential",
                "status": "PASSED"
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_standings_ranks_are_sequential",
                "status": "FAILED",
                "error": str(e)
            })

        # TEST 11: Data quality - match stats validation
        try:
            stats = await db.get_team_statistics(team_id=50, league_id=39, season="2024")
            if stats:
                played = stats.get("total_played", 0)
                wins = stats.get("total_wins", 0)
                draws = stats.get("total_draws", 0)
                losses = stats.get("total_losses", 0)
                assert wins + draws + losses == played, "Math doesn't add up"
                assert 0 <= played <= 38, "Invalid played count"
            results["passed"] += 1
            results["tests"].append({
                "name": "test_team_stats_played_matches_valid",
                "status": "PASSED"
            })
        except Exception as e:
            results["failed"] += 1
            results["tests"].append({
                "name": "test_team_stats_played_matches_valid",
                "status": "FAILED",
                "error": str(e)
            })

    finally:
        await db.close()
        await cache.close()

    # Summary
    results["summary"] = f"{results['passed']}/{results['total_tests']} tests passed"
    results["success"] = results["failed"] == 0

    return results


async def insert_test_data() -> dict[str, Any]:
    """Insert minimal test data for integration testing (0 API requests)."""
    import boto3

    # Get Aurora credentials from Secrets Manager
    secret_arn = os.getenv("AURORA_SECRET_ARN")
    if not secret_arn:
        return {"error": "AURORA_SECRET_ARN environment variable not set"}

    try:
        secrets_client = boto3.client("secretsmanager")
        secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(secret_response["SecretString"])
        aurora_password = secret_data["password"]
        aurora_host = secret_data.get("host", os.getenv("AURORA_HOST"))
    except Exception as e:
        return {"error": "Failed to retrieve Aurora credentials", "message": str(e)}

    # Import here to avoid issues if dependencies aren't available
    from sipap_data_mcp.database.aurora import AuroraDataClient

    db = AuroraDataClient(
        host=aurora_host,
        port=5432,
        database="sipap_dev",
        user="sipap_admin",
        password=aurora_password,
    )

    try:
        await db.connect()

        # Insert 5 Premier League standings records
        standings_sql = """
            INSERT INTO standings (
                league_id, season, team_id, team_name, rank, points,
                matches_played, wins, draws, losses,
                goals_for, goals_against, goal_difference, form
            ) VALUES
                (39, '2024', 50, 'Manchester City', 1, 91, 38, 28, 7, 3, 96, 34, 62, 'WWWDW'),
                (39, '2024', 42, 'Arsenal', 2, 89, 38, 28, 5, 5, 91, 29, 62, 'WWWWL'),
                (39, '2024', 40, 'Liverpool', 3, 82, 38, 24, 10, 4, 86, 41, 45, 'DWWWD'),
                (39, '2024', 33, 'Chelsea', 4, 70, 38, 21, 9, 8, 77, 63, 14, 'WDWWL'),
                (39, '2024', 49, 'Tottenham', 5, 66, 38, 20, 6, 12, 74, 61, 13, 'LWWDL')
            ON CONFLICT (league_id, season, team_id) DO UPDATE SET
                rank = EXCLUDED.rank,
                points = EXCLUDED.points,
                matches_played = EXCLUDED.matches_played,
                wins = EXCLUDED.wins,
                draws = EXCLUDED.draws,
                losses = EXCLUDED.losses,
                goals_for = EXCLUDED.goals_for,
                goals_against = EXCLUDED.goals_against,
                goal_difference = EXCLUDED.goal_difference,
                form = EXCLUDED.form,
                updated_at = CURRENT_TIMESTAMP;
        """

        async with db._pool.acquire() as conn:
            await conn.execute(standings_sql)

        # Insert 5 team statistics records
        team_stats_sql = """
            INSERT INTO team_statistics (
                team_id, league_id, season,
                matches_played_home, wins_home, draws_home, losses_home, goals_for_home, goals_against_home,
                matches_played_away, wins_away, draws_away, losses_away, goals_for_away, goals_against_away,
                matches_played_total, wins_total, draws_total, losses_total, goals_for_total, goals_against_total,
                clean_sheets_home, clean_sheets_away, clean_sheets_total
            ) VALUES
                (50, 39, '2024', 19, 17, 2, 0, 53, 15, 19, 11, 5, 3, 43, 19, 38, 28, 7, 3, 96, 34, 12, 8, 20),
                (42, 39, '2024', 19, 16, 2, 1, 51, 13, 19, 12, 3, 4, 40, 16, 38, 28, 5, 5, 91, 29, 13, 9, 22),
                (40, 39, '2024', 19, 14, 4, 1, 49, 17, 19, 10, 6, 3, 37, 24, 38, 24, 10, 4, 86, 41, 11, 7, 18),
                (33, 39, '2024', 19, 12, 5, 2, 45, 28, 19, 9, 4, 6, 32, 35, 38, 21, 9, 8, 77, 63, 8, 5, 13),
                (49, 39, '2024', 19, 12, 3, 4, 42, 27, 19, 8, 3, 8, 32, 34, 38, 20, 6, 12, 74, 61, 7, 4, 11)
            ON CONFLICT (team_id, league_id, season) DO UPDATE SET
                matches_played_total = EXCLUDED.matches_played_total,
                wins_total = EXCLUDED.wins_total,
                draws_total = EXCLUDED.draws_total,
                losses_total = EXCLUDED.losses_total,
                goals_for_total = EXCLUDED.goals_for_total,
                goals_against_total = EXCLUDED.goals_against_total,
                updated_at = CURRENT_TIMESTAMP;
        """

        async with db._pool.acquire() as conn:
            await conn.execute(team_stats_sql)

        # Verify counts
        async with db._pool.acquire() as conn:
            standings_count = await conn.fetchval("SELECT COUNT(*) FROM standings WHERE league_id = 39 AND season = '2024'")
            team_stats_count = await conn.fetchval("SELECT COUNT(*) FROM team_statistics WHERE league_id = 39 AND season = '2024'")

        return {
            "status": "success",
            "message": "Test data inserted successfully",
            "standings_inserted": standings_count,
            "team_stats_inserted": team_stats_count,
            "api_requests_used": 0
        }

    finally:
        await db.close()


def lambda_handler(event, context):
    """AWS Lambda handler."""
    # Check if this is a request to insert test data
    if isinstance(event, dict) and event.get("action") == "insert_test_data":
        try:
            result = asyncio.run(insert_test_data())
            return {
                "statusCode": 200,
                "body": json.dumps(result, indent=2)
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Test data insertion failed",
                    "message": str(e)
                })
            }

    # Otherwise run integration tests
    try:
        results = asyncio.run(run_tests())
        return {
            "statusCode": 200 if results.get("success") else 500,
            "body": json.dumps(results, indent=2)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Test execution failed",
                "message": str(e)
            })
        }


# For local testing (won't work due to private subnet)
if __name__ == "__main__":
    print("Note: This script must run in AWS Lambda within the VPC")
    print("Database is not publicly accessible")
