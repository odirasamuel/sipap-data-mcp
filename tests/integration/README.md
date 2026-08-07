# Integration Tests

Integration tests for SIPAP Data MCP that run against deployed AWS infrastructure.

## Prerequisites

### 1. Infrastructure Deployed

Verify infrastructure is deployed:
```bash
cd /Users/charlesotuya/AI-Odi/sentinel/sipap/repos/sipap-terraform
terraform output aurora_cluster_endpoint
terraform output elasticache_configuration_endpoint
```

**Expected Output:**
```
aurora_cluster_endpoint = "sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com"
elasticache_configuration_endpoint = "sipap-dev-redis.qnk6bl.0001.use1.cache.amazonaws.com"
```

### 2. Phase 3 Migrations Applied

Verify Phase 3 tables exist:
```bash
# Check latest migration version
aws logs tail /aws/lambda/SipapMigrationRunner --since 1h --profile odiraaws | grep "Final migration version"

# Expected: "Final migration version: 20260806_011"
```

### 3. Database Credentials

Get Aurora password from AWS Secrets Manager:
```bash
aws secretsmanager get-secret-value \
  --secret-id sipap-dev-aurora-credentials \
  --query SecretString \
  --output text \
  --profile odiraaws \
  --region us-east-1 | jq -r '.password'
```

### 4. Environment Variables

Create `.env` file in repository root:
```bash
cd /Users/charlesotuya/AI-Odi/sentinel/sipap/repos/sipap-data-mcp

cat > .env <<EOF
# Aurora PostgreSQL
AURORA_HOST=sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com
AURORA_PORT=5432
AURORA_DATABASE=sipap
AURORA_USER=postgres
AURORA_PASSWORD=<password_from_secrets_manager>

# Elasticache Redis
REDIS_HOST=sipap-dev-redis.qnk6bl.0001.use1.cache.amazonaws.com
REDIS_PORT=6379
EOF
```

**Security Note:** Never commit `.env` to git. It's already in `.gitignore`.

## Running Integration Tests

### Run All Integration Tests

```bash
source .venv/bin/activate
pytest tests/integration/ -v
```

### Run Specific Test Classes

**Phase 3 Table Population:**
```bash
pytest tests/integration/test_phase3_integration.py::TestPhase3TablePopulation -v
```

**Query Performance:**
```bash
pytest tests/integration/test_phase3_integration.py::TestAuroraQueryPerformance -v
```

**Redis Cache:**
```bash
pytest tests/integration/test_phase3_integration.py::TestRedisCacheIntegration -v
```

**Data Quality:**
```bash
pytest tests/integration/test_phase3_integration.py::TestDataQualityValidation -v
```

### Run With Coverage

```bash
pytest tests/integration/ -v --cov=src/sipap_data_mcp --cov-report=term-missing
```

## Test Scenarios

### 1. Phase 3 Table Population Tests

Verifies Phase 4 batch jobs have populated Phase 3 tables:
- `test_standings_table_has_data` - Checks standings for Premier League 2024
- `test_team_statistics_table_has_data` - Checks team stats for Man City
- `test_head_to_head_table_has_data` - Checks H2H data exists
- `test_odds_table_has_data` - Checks odds table is queryable
- `test_teams_metadata_table_has_data` - Checks team metadata exists

**Expected Results:**
- PASS: If Phase 4 batch jobs have run and populated tables
- SKIP: If `AURORA_PASSWORD` not set (no .env file)
- FAIL: If tables exist but have no data (batch jobs haven't run)

### 2. Aurora Query Performance Tests

Verifies Phase 3 queries are fast (< 100ms):
- `test_standings_query_performance` - Target: < 100ms
- `test_team_stats_query_performance` - Target: < 100ms

**Expected Results:**
- PASS: Queries complete in < 100ms (10x faster than Phase 2 JSONB queries)
- FAIL: Queries take > 100ms (investigate database performance, indexes)

### 3. Redis Cache Integration Tests

Verifies Redis caching works:
- `test_redis_connection` - Basic SET/GET test
- `test_cache_team_stats` - Cache with 6-hour TTL

**Expected Results:**
- PASS: Redis responds and caches data correctly
- FAIL: Cannot connect to Redis (check security groups, network)

### 4. Data Quality Validation Tests

Verifies data integrity:
- `test_standings_ranks_are_sequential` - Ranks should be 1-20 (no gaps)
- `test_team_stats_played_matches_valid` - Wins + draws + losses = played

**Expected Results:**
- PASS: Data is consistent and valid
- FAIL: Data quality issues (investigate batch job logic)

## Troubleshooting

### Issue: "AURORA_PASSWORD not set - integration tests require deployed infrastructure"

**Cause:** `.env` file missing or `AURORA_PASSWORD` not set.

**Solution:**
1. Create `.env` file (see "Environment Variables" section above)
2. Get password from AWS Secrets Manager
3. Add password to `.env`

### Issue: "Connection refused" or "Timeout"

**Cause:** Security groups not allowing local IP to connect to Aurora/Redis.

**Solution:**
1. Check security group rules:
```bash
aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=sipap-dev-aurora-sg" \
  --profile odiraaws \
  --region us-east-1 \
  --query 'SecurityGroups[0].IpPermissions'
```

2. Temporarily add your IP:
```bash
# Get your public IP
MY_IP=$(curl -s ifconfig.me)

# Add to Aurora security group (port 5432)
aws ec2 authorize-security-group-ingress \
  --group-id <aurora-sg-id> \
  --protocol tcp \
  --port 5432 \
  --cidr $MY_IP/32 \
  --profile odiraaws \
  --region us-east-1
```

### Issue: "No data in Phase 3 tables"

**Cause:** Phase 4 batch jobs haven't run yet.

**Solution:**
1. Check if batch jobs exist:
```bash
aws lambda list-functions \
  --profile odiraaws \
  --region us-east-1 \
  --query "Functions[?contains(FunctionName, 'standings') || contains(FunctionName, 'team-stats')].FunctionName"
```

2. If deployed, invoke manually:
```bash
aws lambda invoke \
  --function-name sipap-dev-standings-updater \
  --profile odiraaws \
  --region us-east-1 \
  response.json
```

3. If not deployed, see Phase 4 batch jobs deployment guide.

### Issue: "Query performance > 100ms"

**Cause:** Missing indexes or Aurora instance too small.

**Solution:**
1. Check Aurora instance type:
```bash
terraform output database_mode
# Expected: "Standard RDS Instance (db.t4g.micro)"
```

2. Verify indexes exist:
```sql
-- Connect to Aurora
psql -h sipap-dev-rds.c2hooq6iskvw.us-east-1.rds.amazonaws.com -U postgres -d sipap

-- Check indexes on standings table
\d standings
```

3. If indexes missing, re-run Phase 3 migrations.

## Success Criteria

Integration tests should:
- ✅ All tests passing (100%)
- ✅ Query performance < 100ms (P99)
- ✅ Cache hit rate measurable (Redis responding)
- ✅ Data quality validated (no integrity issues)

If any tests fail:
1. Check prerequisites (infrastructure deployed, migrations applied)
2. Review troubleshooting section
3. Investigate specific failure (check CloudWatch logs, query database directly)

## Next Steps

After integration tests pass:
1. Run Phase 4 batch jobs to populate tables (if not already done)
2. Test MCP server endpoints (Lambda function URL)
3. Run load testing (1,000 predictions/day)
4. Monitor cache hit rates (target: ≥ 50%)
5. Proceed to Phase 7: Deployment
