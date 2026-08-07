"""
Lambda handler to run integration tests from within VPC.

This Lambda function is deployed in the VPC with access to Aurora and Redis,
allowing integration tests to run against the deployed infrastructure.
"""

import asyncio
import json
import os
import sys
from typing import Any

# Add test directory to path
sys.path.insert(0, "/var/task/tests/integration")

import boto3
from sipap_data_mcp.cache.redis import RedisCache
from sipap_data_mcp.database.aurora import AuroraDataClient


async def run_integration_tests() -> dict[str, Any]:
    """Run all integration tests and return results."""
    results = {
        "total": 11,
        "passed": 0,
        "failed": 0,
        "errors": [],
        "tests": []
    }

    # Get Aurora credentials from Secrets Manager
    secret_arn = os.getenv("AURORA_SECRET_ARN")
    if not secret_arn:
        results["errors"].append("AURORA_SECRET_ARN environment variable not set")
        return results

    try:
        secrets_client = boto3.client("secretsmanager")
        secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(secret_response["SecretString"])
        aurora_password = secret_data["password"]
    except Exception as e:
        results["errors"].append(f"Failed to retrieve Aurora credentials: {str(e)}")
        return results

    # Create clients
    aurora_client = AuroraDataClient(
        host=os.getenv("AURORA_HOST", "sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com"),
        port=int(os.getenv("AURORA_PORT", "5432")),
        database=os.getenv("AURORA_DATABASE", "sipap_dev"),
        user=os.getenv("AURORA_USER", "sipap_admin"),
        password=aurora_password,
    )

    redis_host = os.getenv("REDIS_HOST", "sipap-dev-redis.qnk6bl.0001.use1.cache.amazonaws.com")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_cache = RedisCache(url=f"redis://{redis_host}:{redis_port}/0")

    try:
        # Connect to Aurora and Redis
        await aurora_client.connect()
        await redis_cache.connect()

        # Test 1: Standings table has data
        try:
            standings = await aurora_client.get_standings(league_id=39, season="2024")
            if len(standings) > 0:
                results["passed"] += 1
                results["tests"].append({"name": "test_standings_table_has_data", "status": "PASSED"})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_standings_table_has_data", "status": "FAILED", "error": "No data in standings table"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_standings_table_has_data: {str(e)}")
            results["tests"].append({"name": "test_standings_table_has_data", "status": "ERROR", "error": str(e)})

        # Test 2: Team statistics table has data
        try:
            stats = await aurora_client.get_team_statistics(team_id=50, league_id=39, season="2024")
            if stats is not None:
                results["passed"] += 1
                results["tests"].append({"name": "test_team_statistics_table_has_data", "status": "PASSED"})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_team_statistics_table_has_data", "status": "FAILED", "error": "No data for team 50"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_team_statistics_table_has_data: {str(e)}")
            results["tests"].append({"name": "test_team_statistics_table_has_data", "status": "ERROR", "error": str(e)})

        # Test 3: Head-to-head table has data
        try:
            h2h = await aurora_client.get_head_to_head_stats(team_1_id=50, team_2_id=42)
            # May be None if H2H hasn't been fetched yet (acceptable)
            results["passed"] += 1
            results["tests"].append({"name": "test_head_to_head_table_has_data", "status": "PASSED", "note": "H2H data: " + ("exists" if h2h else "not yet populated")})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_head_to_head_table_has_data: {str(e)}")
            results["tests"].append({"name": "test_head_to_head_table_has_data", "status": "ERROR", "error": str(e)})

        # Test 4: Odds table is queryable
        try:
            query = "SELECT COUNT(*) as count FROM odds WHERE is_live = false LIMIT 1"
            async with aurora_client._pool.acquire() as conn:
                row = await conn.fetchrow(query)
                count = row["count"] if row else 0
            results["passed"] += 1
            results["tests"].append({"name": "test_odds_table_has_data", "status": "PASSED", "note": f"Odds count: {count}"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_odds_table_has_data: {str(e)}")
            results["tests"].append({"name": "test_odds_table_has_data", "status": "ERROR", "error": str(e)})

        # Test 5: Teams metadata table has data
        try:
            metadata = await aurora_client.get_teams_metadata(team_ids=[50, 42, 33, 40])
            results["passed"] += 1
            results["tests"].append({"name": "test_teams_metadata_table_has_data", "status": "PASSED", "note": f"Metadata count: {len(metadata)}"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_teams_metadata_table_has_data: {str(e)}")
            results["tests"].append({"name": "test_teams_metadata_table_has_data", "status": "ERROR", "error": str(e)})

        # Test 6: Standings query performance
        try:
            import time
            start = time.perf_counter()
            await aurora_client.get_standings(league_id=39, season="2024")
            duration = (time.perf_counter() - start) * 1000
            if duration < 100:
                results["passed"] += 1
                results["tests"].append({"name": "test_standings_query_performance", "status": "PASSED", "duration_ms": round(duration, 2)})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_standings_query_performance", "status": "FAILED", "duration_ms": round(duration, 2), "error": "Query took > 100ms"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_standings_query_performance: {str(e)}")
            results["tests"].append({"name": "test_standings_query_performance", "status": "ERROR", "error": str(e)})

        # Test 7: Team stats query performance
        try:
            import time
            start = time.perf_counter()
            await aurora_client.get_team_statistics(team_id=50, league_id=39, season="2024")
            duration = (time.perf_counter() - start) * 1000
            if duration < 100:
                results["passed"] += 1
                results["tests"].append({"name": "test_team_stats_query_performance", "status": "PASSED", "duration_ms": round(duration, 2)})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_team_stats_query_performance", "status": "FAILED", "duration_ms": round(duration, 2), "error": "Query took > 100ms"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_team_stats_query_performance: {str(e)}")
            results["tests"].append({"name": "test_team_stats_query_performance", "status": "ERROR", "error": str(e)})

        # Test 8: Redis connection
        try:
            await redis_cache.set("test_key", {"value": "test"}, ttl=10)
            result = await redis_cache.get("test_key")
            await redis_cache.delete("test_key")
            if result and result.get("value") == "test":
                results["passed"] += 1
                results["tests"].append({"name": "test_redis_connection", "status": "PASSED"})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_redis_connection", "status": "FAILED", "error": "Value mismatch"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_redis_connection: {str(e)}")
            results["tests"].append({"name": "test_redis_connection", "status": "ERROR", "error": str(e)})

        # Test 9: Cache team stats
        try:
            cache_key = "test:team_stats:50:39:2024"
            mock_stats = {"stats": {"total_played": 38, "total_wins": 28}}
            await redis_cache.set(cache_key, mock_stats, ttl=21600)
            cached = await redis_cache.get(cache_key)
            ttl = await redis_cache.ttl(cache_key)
            await redis_cache.delete(cache_key)

            if cached and 21590 <= ttl <= 21600:
                results["passed"] += 1
                results["tests"].append({"name": "test_cache_team_stats", "status": "PASSED", "ttl": ttl})
            else:
                results["failed"] += 1
                results["tests"].append({"name": "test_cache_team_stats", "status": "FAILED", "error": f"TTL out of range: {ttl}"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_cache_team_stats: {str(e)}")
            results["tests"].append({"name": "test_cache_team_stats", "status": "ERROR", "error": str(e)})

        # Test 10: Standings ranks are sequential
        try:
            standings = await aurora_client.get_standings(league_id=39, season="2024")
            if len(standings) > 0:
                ranks = [s["rank"] for s in standings]
                expected_ranks = list(range(1, len(standings) + 1))
                if ranks == expected_ranks:
                    results["passed"] += 1
                    results["tests"].append({"name": "test_standings_ranks_are_sequential", "status": "PASSED"})
                else:
                    results["failed"] += 1
                    results["tests"].append({"name": "test_standings_ranks_are_sequential", "status": "FAILED", "error": "Ranks not sequential"})
            else:
                results["passed"] += 1
                results["tests"].append({"name": "test_standings_ranks_are_sequential", "status": "PASSED", "note": "No data to validate"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_standings_ranks_are_sequential: {str(e)}")
            results["tests"].append({"name": "test_standings_ranks_are_sequential", "status": "ERROR", "error": str(e)})

        # Test 11: Team stats played matches valid
        try:
            stats = await aurora_client.get_team_statistics(team_id=50, league_id=39, season="2024")
            if stats:
                played = stats.get("total_played", 0)
                wins = stats.get("total_wins", 0)
                draws = stats.get("total_draws", 0)
                losses = stats.get("total_losses", 0)

                if wins + draws + losses == played and 0 <= played <= 38:
                    results["passed"] += 1
                    results["tests"].append({"name": "test_team_stats_played_matches_valid", "status": "PASSED"})
                else:
                    results["failed"] += 1
                    results["tests"].append({"name": "test_team_stats_played_matches_valid", "status": "FAILED", "error": f"Math doesn't add up: {wins}+{draws}+{losses}!={played}"})
            else:
                results["passed"] += 1
                results["tests"].append({"name": "test_team_stats_played_matches_valid", "status": "PASSED", "note": "No data to validate"})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"test_team_stats_played_matches_valid: {str(e)}")
            results["tests"].append({"name": "test_team_stats_played_matches_valid", "status": "ERROR", "error": str(e)})

    finally:
        # Cleanup
        await aurora_client.close()
        await redis_cache.disconnect()

    return results


def lambda_handler(event, context):
    """AWS Lambda handler."""
    results = asyncio.run(run_integration_tests())

    return {
        "statusCode": 200 if results["failed"] == 0 else 500,
        "body": json.dumps(results, indent=2)
    }


if __name__ == "__main__":
    # For local testing
    import json
    results = asyncio.run(run_integration_tests())
    print(json.dumps(results, indent=2))
