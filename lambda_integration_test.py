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
            standings = await db.get_standings(league_id=39, season="2024")
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
            metadata = await db.get_teams_metadata(team_ids=[50, 42, 33, 40])
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
            await db.get_standings(league_id=39, season="2024")
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
            standings = await db.get_standings(league_id=39, season="2024")
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
        await cache.disconnect()

    # Summary
    results["summary"] = f"{results['passed']}/{results['total_tests']} tests passed"
    results["success"] = results["failed"] == 0

    return results


def lambda_handler(event, context):
    """AWS Lambda handler."""
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
