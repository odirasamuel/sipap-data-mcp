-- Migration: Add indexes for statistical analysis tools
-- Purpose: Optimize queries for 6-season historical analysis
-- Target: Sub-500ms query performance for all 24 statistical tools
-- Date: 2026-08-03

-- ============================================================================
-- Index 1: Head-to-Head Queries
-- ============================================================================
-- Used by: get_h2h_* tools (h2h_full_time_result, h2h_goals, h2h_half_time_result, etc.)
-- Query pattern: WHERE (home_team = A AND away_team = B) OR (home_team = B AND away_team = A)
--                AND league = L AND status = 'finished'
--                ORDER BY scheduled DESC

CREATE INDEX IF NOT EXISTS idx_fixtures_h2h_home_away
ON fixtures(home_team, away_team, league, scheduled DESC)
WHERE status = 'finished';

CREATE INDEX IF NOT EXISTS idx_fixtures_h2h_away_home
ON fixtures(away_team, home_team, league, scheduled DESC)
WHERE status = 'finished';

COMMENT ON INDEX idx_fixtures_h2h_home_away IS
'Optimizes head-to-head queries for statistical tools (home team first)';

COMMENT ON INDEX idx_fixtures_h2h_away_home IS
'Optimizes head-to-head queries for statistical tools (away team first)';

-- ============================================================================
-- Index 2: Team Home Matches
-- ============================================================================
-- Used by: get_home_total_goals, team-specific analysis
-- Query pattern: WHERE home_team = T AND league = L AND status = 'finished'
--                ORDER BY scheduled DESC

CREATE INDEX IF NOT EXISTS idx_fixtures_team_home_league
ON fixtures(home_team, league, scheduled DESC)
WHERE status = 'finished';

COMMENT ON INDEX idx_fixtures_team_home_league IS
'Optimizes home team match queries for goal analysis tools';

-- ============================================================================
-- Index 3: Team Away Matches
-- ============================================================================
-- Used by: get_away_total_goals, team-specific analysis
-- Query pattern: WHERE away_team = T AND league = L AND status = 'finished'
--                ORDER BY scheduled DESC

CREATE INDEX IF NOT EXISTS idx_fixtures_team_away_league
ON fixtures(away_team, league, scheduled DESC)
WHERE status = 'finished';

COMMENT ON INDEX idx_fixtures_team_away_league IS
'Optimizes away team match queries for goal analysis tools';

-- ============================================================================
-- Index 4: Halftime Data Availability
-- ============================================================================
-- Used by: get_h2h_half_time_result, get_ht_ft_outcome, get_half_time_goals
-- Query pattern: WHERE metadata ? 'halftime_home_score' (check if halftime data exists)

CREATE INDEX IF NOT EXISTS idx_fixtures_metadata_halftime
ON fixtures((metadata->>'halftime_home_score'))
WHERE status = 'finished' AND metadata ? 'halftime_home_score';

COMMENT ON INDEX idx_fixtures_metadata_halftime IS
'Optimizes queries that check for halftime score availability';

-- ============================================================================
-- Index 5: Status + Scheduled (Verify Exists)
-- ============================================================================
-- This index should already exist from previous migrations
-- Verify and create if missing

CREATE INDEX IF NOT EXISTS idx_fixtures_status_scheduled
ON fixtures(status, scheduled DESC);

COMMENT ON INDEX idx_fixtures_status_scheduled IS
'General index for filtering by status and ordering by scheduled time';

-- ============================================================================
-- Index 6: League + Scheduled (for league-wide queries)
-- ============================================================================
-- Used by: General fixture queries, league statistics

CREATE INDEX IF NOT EXISTS idx_fixtures_league_scheduled
ON fixtures(league, scheduled DESC)
WHERE status = 'finished';

COMMENT ON INDEX idx_fixtures_league_scheduled IS
'Optimizes league-based queries ordered by match date';

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Query 1: Verify all indexes were created
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'fixtures'
    AND indexname LIKE 'idx_fixtures_%'
ORDER BY indexname;

-- Query 2: Check index sizes
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND relname = 'fixtures'
    AND indexrelname LIKE 'idx_fixtures_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Query 3: Benchmark query performance (h2h query example)
EXPLAIN ANALYZE
SELECT
    id,
    scheduled,
    home_team,
    away_team,
    home_score,
    away_score,
    status,
    league,
    metadata,
    EXTRACT(YEAR FROM scheduled) as season_year
FROM fixtures
WHERE
    (
        (home_team = 'Arsenal' AND away_team = 'Chelsea') OR
        (home_team = 'Chelsea' AND away_team = 'Arsenal')
    )
    AND league = 'Premier League'
    AND status = 'finished'
    AND scheduled >= NOW() - INTERVAL '6 years'
ORDER BY scheduled DESC
LIMIT 50;

-- ============================================================================
-- Performance Monitoring
-- ============================================================================

-- Query 4: Monitor index usage
SELECT
    schemaname,
    tablename,
    indexrelname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'fixtures'
    AND indexrelname LIKE 'idx_fixtures_%'
ORDER BY idx_scan DESC;

-- ============================================================================
-- Rollback Script (if needed)
-- ============================================================================

-- To remove all indexes created by this migration:
/*
DROP INDEX IF EXISTS idx_fixtures_h2h_home_away;
DROP INDEX IF EXISTS idx_fixtures_h2h_away_home;
DROP INDEX IF EXISTS idx_fixtures_team_home_league;
DROP INDEX IF EXISTS idx_fixtures_team_away_league;
DROP INDEX IF EXISTS idx_fixtures_metadata_halftime;
DROP INDEX IF EXISTS idx_fixtures_league_scheduled;
*/

-- ============================================================================
-- Expected Impact
-- ============================================================================
-- Before indexes:
--   - H2H queries: 500-1500ms (full table scan)
--   - Team queries: 300-800ms (partial index scan)
--
-- After indexes:
--   - H2H queries: <100ms (index scan only)
--   - Team queries: <50ms (index scan only)
--
-- Target: All statistical tools <500ms response time
