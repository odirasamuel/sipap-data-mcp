# SIPAP Data MCP Examples

This directory contains working examples demonstrating how to use the sipap-data-mcp package.

## Prerequisites

1. Python 3.12+
2. PostgreSQL database with SIPAP schema
3. Install sipap-data-mcp:
   ```bash
   pip install sipap-data-mcp
   ```

## Environment Setup

Set the following environment variables:

```bash
export DB_HOST="your-aurora-endpoint.rds.amazonaws.com"
export DB_PORT="5432"
export DB_NAME="sipap"
export DB_USER="sipap_readonly"
export DB_PASSWORD="your-password"

# Optional: For caching examples
export REDIS_URL="redis://localhost:6379/0"
```

## Examples

### 1. Match Schedule (`match_schedule.py`)
Demonstrates how to:
- Get upcoming matches for a date range
- Filter matches by status (scheduled, live, finished)
- Filter by specific league

### 2. Team Statistics (`team_statistics.py`)
Demonstrates how to:
- Get team statistics for a season
- Retrieve league standings/table
- Analyze home/away records

### 3. Head-to-Head Analysis (`head_to_head.py`)
Demonstrates how to:
- Compare two teams' historical matchups
- Calculate win/loss/draw statistics
- Retrieve recent match results

### 4. Historical Analysis (`historical_analysis.py`)
Demonstrates how to:
- Query historical match data with flexible filters
- Calculate team form from recent results
- Analyze performance trends over time
- Filter by date range and league
- Compare form over different periods

### 5. Odds Analysis (`odds_analysis.py`)
Demonstrates how to:
- Retrieve current betting odds from multiple bookmakers
- Find best available odds for each outcome
- Track odds movements over time
- Identify sharp money (steam moves)
- Calculate implied probabilities
- Detect value bets using probability models

### 6. Cached Data Access (`cached_data_access.py`)
Demonstrates how to:
- Use Redis caching for improved performance (<100ms responses)
- Implement cache-aside pattern
- Configure TTLs for different data types
- Handle cache hits and misses
- Manually invalidate cached data

## Running Examples

```bash
# Run match schedule example
python examples/match_schedule.py

# Run team statistics example
python examples/team_statistics.py

# Run head-to-head analysis example
python examples/head_to_head.py

# Run historical analysis example
python examples/historical_analysis.py

# Run odds analysis example
python examples/odds_analysis.py

# Run cached data access example (requires Redis)
python examples/cached_data_access.py
```

## Expected Output

Each example includes:
- Clear console output showing the data retrieved
- Error handling demonstrations
- Proper resource cleanup (database connections)
