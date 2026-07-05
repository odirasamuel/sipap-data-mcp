# SIPAP Data MCP Server

Consolidated data access MCP (Model Context Protocol) server providing read-only access to sports data stored in Aurora PostgreSQL.

## Overview

**sipap-data-mcp** consolidates 3 separate MCPs into a single unified server:
- Sports data (matches, teams, leagues)
- Odds intelligence (betting odds from 37+ bookmakers)
- Historical data (season stats, head-to-head)

## Features

- **10 Tools** for AI agents:
  - 4 match tools (schedule, details, live, search)
  - 3 team tools (stats, standings, head-to-head)
  - 2 odds tools (current odds, movement tracking)
  - 1 historical tool (season aggregations)

- **Fast Response Times**: <100ms via Redis caching
- **JSON-RPC 2.0 Protocol**: Standard MCP protocol
- **Lambda ARM64 Deployment**: Cost-effective, auto-scaling
- **Read-Only Access**: No writes (batch scraper handles writes)

## Installation

```bash
# Clone repository
cd /Users/charlesotuya/AI-Odi/sentinel/sipap/repos/sipap-data-mcp

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e '.[dev]'
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/sipap_data_mcp --cov-report=term-missing

# Run specific test file
pytest tests/unit/database/test_aurora.py -v
```

### Type Checking

```bash
mypy src/sipap_data_mcp --strict
```

### Linting

```bash
ruff check src/ tests/
ruff check --fix src/ tests/  # Auto-fix issues
```

## Quality Gates

Before deploying, all quality gates must pass:

1. **Tests**: 80%+ coverage, all tests passing
2. **Type Checking**: Zero mypy errors (strict mode)
3. **Linting**: Zero ruff errors
4. **Imports**: All public APIs importable

```bash
# Run all quality gates
pytest --cov=src/sipap_data_mcp --cov-fail-under=80 && \
mypy src/sipap_data_mcp --strict && \
ruff check src/ tests/
```

## Project Structure

```
sipap-data-mcp/
├── src/sipap_data_mcp/
│   ├── tools/          # MCP tool implementations
│   ├── database/       # Aurora PostgreSQL client
│   ├── models/         # TypedDict data models
│   └── exceptions/     # Exception hierarchy
├── tests/
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── fixtures/       # Test data fixtures
└── examples/           # Working examples
```

## License

Proprietary - SIPAP Project

## Status

🚧 **Under Development** - Phase 2.B: Data Layer (Week 5)

Current: Day 1 - Repository setup and database client (TDD)
