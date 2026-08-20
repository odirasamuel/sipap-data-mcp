"""
Pressure performance analysis tool.

Analyzes form against strong opponents vs weaker opponents.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any

# asyncpg removed (2026-08-20) - database removed

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool


async def get_pressure_performance(
    pool: Any,
    team: str | int,
    league: str | int,
    match_limit: int = 15,
    top_team_threshold: float = 2.0,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze form against strong opponents.

    Strong opponents are identified as teams averaging 2+ points per match
    in recent form (typically top 6-8 teams).

    REDESIGNED (2026-08-19): Uses API-Football directly when available.
    When using API, opponent strength is estimated from league standings.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        team: Team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        match_limit: Number of recent matches to analyze (default: 15)
        top_team_threshold: Points per match threshold for "strong" teams (default: 2.0)
        api_client: Optional API-Football client (preferred)

    Returns:
        {
            "tool": "get_pressure_performance",
            "data": {
                "vs_strong_opponents": {
                    "matches": int,
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "points_per_match": float,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "vs_weaker_opponents": {
                    "matches": int,
                    "points": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "points_per_match": float,
                    "goals_scored": int,
                    "goals_conceded": int
                },
                "comparison": {
                    "points_per_match_diff": float,  # negative = struggles vs strong teams
                    "win_rate_diff": float,
                    "performance_differential": int,  # -100 to +100
                    "pressure_rating": "high" | "medium" | "low"
                },
                "pressure_performance_rating": int  # 0-100 scale
            },
            "metadata": {
                "strong_opponent_threshold": float,
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_pressure_performance(
        ...     pool=None, team=42, league=39, api_client=client
        ... )
        >>> print(result["data"]["comparison"]["pressure_rating"])
        "high"
    """
    # Use API client if available
    if api_client is not None and isinstance(team, int):
        league_id = league if isinstance(league, int) else None
        matches = await BaseFormTool.get_recent_team_matches_api(
            api_client=api_client,
            team_id=team,
            league_id=league_id,
            match_limit=match_limit,
            venue=None,
        )
        team_identifier: str | int = team
        use_api = True

        # For API-based analysis, get standings to identify strong teams
        strong_team_ids: set[int] = set()
        if league_id:
            try:
                standings_response = await api_client.get_standings(
                    league_id=league_id, season=2026
                )
                standings = standings_response.get("response", [])
                if standings and standings[0].get("league", {}).get("standings"):
                    league_standings = standings[0]["league"]["standings"]
                    if league_standings and isinstance(league_standings[0], list):
                        # Top 8 teams are "strong"
                        for standing in league_standings[0][:8]:
                            if standing.get("team", {}).get("id"):
                                strong_team_ids.add(standing["team"]["id"])
            except Exception:
                # Fallback: no strong teams identified
                pass
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        matches = await BaseFormTool.get_recent_team_matches(
            pool=pool,
            team=str(team),
            league=str(league),
            match_limit=match_limit,
            venue=None,
        )
        team_identifier = str(team)
        use_api = False
        strong_team_ids = set()

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    # Handle no data case
    if not matches:
        return {
            "tool": "get_pressure_performance",
            "data": {
                "vs_strong_opponents": {
                    "matches": 0,
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "points_per_match": 0.0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "vs_weaker_opponents": {
                    "matches": 0,
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "points_per_match": 0.0,
                    "goals_scored": 0,
                    "goals_conceded": 0
                },
                "comparison": {
                    "points_per_match_diff": 0.0,
                    "win_rate_diff": 0.0,
                    "performance_differential": 0,
                    "pressure_rating": "low"
                },
                "pressure_performance_rating": 50
            },
            "metadata": {
                "strong_opponent_threshold": top_team_threshold,
                "matches_analyzed": 0
            }
        }

    # Categorize opponents as strong or weaker
    strong_opponent_matches = []
    weaker_opponent_matches = []

    if use_api:
        # API-based: use standings to identify strong teams
        for match in matches:
            is_home = is_home_team(match)
            opponent_id = match.get('away_team_id') if is_home else match.get('home_team_id')

            if opponent_id in strong_team_ids:
                strong_opponent_matches.append(match)
            else:
                weaker_opponent_matches.append(match)
    else:
        # Database-based: query opponent's recent form
        async with pool.acquire() as conn:  # type: ignore
            for match in matches:
                # Identify opponent
                is_home = match['home_team'] == str(team_identifier)
                opponent = match['away_team'] if is_home else match['home_team']

                # Get opponent's recent form (last 10 matches)
                opponent_query = """
                    SELECT COUNT(*) FILTER (WHERE
                        (home_team = $1 AND home_score > away_score) OR
                        (away_team = $1 AND away_score > home_score)
                    ) as wins,
                    COUNT(*) as total_matches
                    FROM matches
                    WHERE
                        (home_team = $1 OR away_team = $1)
                        AND league = $2
                        AND status = 'finished'
                        AND scheduled_at <= $3
                    ORDER BY scheduled_at DESC
                    LIMIT 10
                """

                opponent_stats = await conn.fetchrow(
                    opponent_query,
                    opponent,
                    str(league),
                    match['scheduled_at']
                )

                # Classify opponent
                if opponent_stats and opponent_stats['total_matches'] > 0:
                    opponent_win_rate = opponent_stats['wins'] / opponent_stats['total_matches']
                    # Strong opponent = >60% win rate OR top team threshold
                    if opponent_win_rate >= 0.6:
                        strong_opponent_matches.append(match)
                    else:
                        weaker_opponent_matches.append(match)
                else:
                    # Unknown opponent strength, classify as weaker
                    weaker_opponent_matches.append(match)

    def analyze_matches(match_list: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze performance against a category of opponents."""
        if not match_list:
            return {
                "matches": 0,
                "points": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points_per_match": 0.0,
                "goals_scored": 0,
                "goals_conceded": 0
            }

        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        for match in match_list:
            is_home = is_home_team(match)
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0

            if is_home:
                scored = home_score
                conceded = away_score
                if home_score > away_score:
                    wins += 1
                elif home_score == away_score:
                    draws += 1
                else:
                    losses += 1
            else:
                scored = away_score
                conceded = home_score
                if away_score > home_score:
                    wins += 1
                elif away_score == home_score:
                    draws += 1
                else:
                    losses += 1

            goals_scored += scored
            goals_conceded += conceded

        points = wins * 3 + draws
        points_per_match = points / len(match_list)

        return {
            "matches": len(match_list),
            "points": points,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points_per_match": round(points_per_match, 2),
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded
        }

    # Analyze both categories
    strong_stats = analyze_matches(strong_opponent_matches)
    weaker_stats = analyze_matches(weaker_opponent_matches)

    # Calculate comparison
    points_per_match_diff = strong_stats["points_per_match"] - weaker_stats["points_per_match"]

    strong_win_rate = (
        strong_stats["wins"] / strong_stats["matches"]
        if strong_stats["matches"] > 0
        else 0
    )
    weaker_win_rate = (
        weaker_stats["wins"] / weaker_stats["matches"]
        if weaker_stats["matches"] > 0
        else 0
    )
    win_rate_diff = strong_win_rate - weaker_win_rate

    # Performance differential (-100 to +100)
    # Positive = performs better vs strong teams
    # Negative = struggles vs strong teams
    performance_differential = int(points_per_match_diff * 33.33)  # Scale to -100 to +100

    # Determine pressure rating
    # High: performs well vs strong teams (diff > -0.5)
    # Medium: moderate drop-off (diff -0.5 to -1.5)
    # Low: struggles vs strong teams (diff < -1.5)
    if points_per_match_diff > -0.5:
        pressure_rating = "high"
    elif points_per_match_diff > -1.5:
        pressure_rating = "medium"
    else:
        pressure_rating = "low"

    # Calculate pressure performance rating (0-100)
    # Based on: points vs strong teams (60%), relative performance (40%)

    # Points vs strong component (60%)
    max_points_per_match = 3.0
    strong_points_normalized = strong_stats["points_per_match"] / max_points_per_match
    strong_points_component = strong_points_normalized * 60

    # Relative performance component (40%)
    # +1.0 diff = excellent, -1.0 diff = poor
    relative_performance_normalized = min(1.0, max(-1.0, points_per_match_diff + 1.0))
    relative_component = relative_performance_normalized * 40

    pressure_performance_rating = int(strong_points_component + relative_component)

    return {
        "tool": "get_pressure_performance",
        "data": {
            "vs_strong_opponents": strong_stats,
            "vs_weaker_opponents": weaker_stats,
            "comparison": {
                "points_per_match_diff": round(points_per_match_diff, 2),
                "win_rate_diff": round(win_rate_diff, 3),
                "performance_differential": performance_differential,
                "pressure_rating": pressure_rating
            },
            "pressure_performance_rating": pressure_performance_rating
        },
        "metadata": {
            "strong_opponent_threshold": top_team_threshold,
            "matches_analyzed": len(matches)
        }
    }
