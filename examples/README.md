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
```

## Expected Output

Each example includes:
- Clear console output showing the data retrieved
- Error handling demonstrations
- Proper resource cleanup (database connections)
