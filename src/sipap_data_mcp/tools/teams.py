"""Team-related MCP tools for sports data access.

Provides tools for retrieving team statistics, league tables, and head-to-head data.

UPDATED for Phase 3: Now uses integer IDs from API-Football instead of UUIDs.
UPDATED: Added fallback logic for empty team stats (computes from recent matches).
"""

import re
from typing import Any

from sipap_data_mcp.database.aurora import AuroraDataClient


async def get_team_stats(
    db_client: AuroraDataClient,
    team_id: int,
    league_id: int,
    season: str,
) -> dict[str, Any]:
    """Get team statistics for a specific season.

    UPDATED for Phase 3: Now accepts integer IDs from API-Football.

    If team_statistics table is empty for the current season (e.g., season hasn't
    started yet or no data available), automatically falls back to computing
    form data from the last 15 finished matches.

    Args:
        db_client: Database client instance
        team_id: API-Football team ID (e.g., 50 for Manchester City)
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)

    Returns:
        Dictionary with "stats" key containing team statistics.
        If using fallback, includes "computed_from_matches": True and "num_matches" field.

    Raises:
        ValueError: If season format is invalid

    Example:
        ```python
        result = await get_team_stats(
            db_client=client,
            team_id=50,
            league_id=39,
            season="2024"
        )
        # Returns: {"stats": {...}}
        # OR with fallback: {"stats": {..., "computed_from_matches": True, "num_matches": 15}}
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Query team_statistics table first
    stats = await db_client.get_team_stats(
        team_id=team_id, league_id=league_id, season=season
    )

    if stats is not None:
        return {"stats": stats}

    # FALLBACK: team_statistics is empty - compute from recent matches
    # This happens when:
    # 1. Current season hasn't started yet
    # 2. Data hasn't been backfilled for this team/league/season
    # 3. Team is new to the league
    return await _compute_stats_from_matches(db_client, team_id)


async def _compute_stats_from_matches(
    db_client: AuroraDataClient,
    team_id: int,
    num_matches: int = 15,
) -> dict[str, Any]:
    """Compute team statistics from recent finished matches.

    Fallback logic when team_statistics table is empty.

    Args:
        db_client: Database client instance
        team_id: API-Football team ID
        num_matches: Number of recent matches to analyze (default: 15)

    Returns:
        Dictionary with computed statistics including:
        - total_played, total_wins, total_draws, total_losses
        - total_goals_for, total_goals_against, goal_difference
        - form (string like "WWDLW")
        - points (3 per win, 1 per draw)
        - computed_from_matches: True (indicates this is computed, not from team_statistics)
    """
    # Query last N finished matches for this team
    matches = await db_client.query_match_history_by_api_team_id(
        team_api_id=team_id,
        limit=num_matches,
    )

    if not matches:
        # No matches found - return empty stats structure
        return {
            "stats": {
                "total_played": 0,
                "total_wins": 0,
                "total_draws": 0,
                "total_losses": 0,
                "total_goals_for": 0,
                "total_goals_against": 0,
                "goal_difference": 0,
                "form": "",
                "points": 0,
                "computed_from_matches": True,
                "num_matches": 0,
            }
        }

    # Compute form and stats from matches
    form_letters = []
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for match in matches:
        home_team_api_id = match.get("home_team_api_id")
        home_score = match.get("home_score")
        away_score = match.get("away_score")

        # Skip matches without scores
        if home_score is None or away_score is None:
            continue

        is_home = home_team_api_id == team_id

        if is_home:
            team_goals = home_score
            opponent_goals = away_score
        else:
            team_goals = away_score
            opponent_goals = home_score

        goals_for += team_goals
        goals_against += opponent_goals

        # Determine result
        if team_goals > opponent_goals:
            form_letters.append("W")
            wins += 1
        elif team_goals < opponent_goals:
            form_letters.append("L")
            losses += 1
        else:
            form_letters.append("D")
            draws += 1

    # Calculate points (3 per win, 1 per draw)
    points = (wins * 3) + draws

    return {
        "stats": {
            "total_played": len(form_letters),
            "total_wins": wins,
            "total_draws": draws,
            "total_losses": losses,
            "total_goals_for": goals_for,
            "total_goals_against": goals_against,
            "goal_difference": goals_for - goals_against,
            "form": "".join(form_letters[:5]),  # Last 5 for form string
            "points": points,
            "computed_from_matches": True,
            "num_matches": len(matches),
        }
    }


async def get_league_table(
    db_client: AuroraDataClient,
    league_id: int,
    season: str,
) -> dict[str, Any]:
    """Get league standings/table for a specific season.

    UPDATED for Phase 3: Now accepts integer league ID from API-Football.

    Args:
        db_client: Database client instance
        league_id: API-Football league ID (e.g., 39 for Premier League)
        season: Season year as string (e.g., "2024" for 2024-2025 season)

    Returns:
        Dictionary with "standings" key containing list of team standings
        sorted by rank (1st place first)

    Raises:
        ValueError: If season format is invalid

    Example:
        ```python
        result = await get_league_table(
            db_client=client,
            league_id=39,
            season="2024"
        )
        # Returns: {"standings": [{"rank": 1, ...}, {"rank": 2, ...}, ...]}
        ```
    """
    # Validate season format (YYYY)
    if not re.match(r"^\d{4}$", season):
        raise ValueError(
            f"Invalid season format: {season}. Expected format: YYYY (e.g., 2024)"
        )

    # Query database
    standings = await db_client.get_league_table(league_id=league_id, season=season)

    return {"standings": standings}


async def get_head_to_head(
    db_client: AuroraDataClient,
    home_team_id: int,
    away_team_id: int,
) -> dict[str, Any]:
    """Get head-to-head statistics between two teams.

    UPDATED for Phase 3: Now accepts integer team IDs from API-Football.

    Args:
        db_client: Database client instance
        home_team_id: API-Football home team ID (e.g., 50 for Manchester City)
        away_team_id: API-Football away team ID (e.g., 42 for Arsenal)

    Returns:
        Dictionary with "head_to_head" key containing:
        - team_1_id, team_2_id (auto-ordered: team_1_id < team_2_id)
        - last_10_matches (JSONB array of recent matches)
        - team_1_wins, team_2_wins, draws

    Raises:
        ValueError: If both teams are the same

    Example:
        ```python
        result = await get_head_to_head(
            db_client=client,
            home_team_id=50,
            away_team_id=42
        )
        # Returns: {"head_to_head": {...}}
        ```
    """
    # Check if both teams are the same
    if home_team_id == away_team_id:
        raise ValueError("Cannot compare team with itself")

    # Query database
    h2h_data = await db_client.get_head_to_head(
        home_team_id=home_team_id,
        away_team_id=away_team_id
    )

    return {"head_to_head": h2h_data}
