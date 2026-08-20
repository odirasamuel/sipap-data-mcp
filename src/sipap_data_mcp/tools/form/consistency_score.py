"""
Consistency score analysis tool.

Measures form volatility and consistency using statistical analysis.

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

from typing import Any, Literal

# asyncpg removed (2026-08-20) - database removed

from sipap_data_mcp.api.football_client import APIFootballClient

from .base import BaseFormTool, ConsistencyAnalyzer


async def get_consistency_score(
    pool: Any,
    team: str | int,
    league: str | int,
    match_limit: int = 15,
    venue: Literal["home", "away"] | None = None,
    api_client: APIFootballClient | None = None,
) -> dict[str, Any]:
    """
    Analyze form consistency and volatility.

    REDESIGNED (2026-08-19): Uses API-Football directly when available.

    Args:
        pool: AsyncPG connection pool (fallback, can be None if api_client provided)
        team: Team name (for DB) or API-Football team ID (for API)
        league: League name (for DB) or API-Football league ID (for API)
        match_limit: Number of recent matches to analyze (default: 15)
        venue: Optional venue filter ("home" or "away")
        api_client: Optional API-Football client (preferred)

    Returns:
        {
            "tool": "get_consistency_score",
            "data": {
                "consistency_rating": int,  # 0-100 (higher = more consistent)
                "volatility": "low" | "medium" | "high",
                "pattern": "consistent" | "erratic" | "trending",
                "std_deviation": float,
                "result_distribution": {
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "dominant_result": "wins" | "draws" | "losses" | "mixed"
                },
                "points_per_match_avg": float,
                "reliability_assessment": str  # Human-readable assessment
            },
            "metadata": {
                "venue": "all" | "home" | "away",
                "matches_analyzed": int
            }
        }

    Example:
        >>> result = await get_consistency_score(
        ...     pool=None, team=42, league=39, api_client=client
        ... )
        >>> print(result["data"]["consistency_rating"])
        85
    """
    # Use API client if available
    if api_client is not None and isinstance(team, int):
        league_id = league if isinstance(league, int) else None
        matches = await BaseFormTool.get_recent_team_matches_api(
            api_client=api_client,
            team_id=team,
            league_id=league_id,
            match_limit=match_limit,
            venue=venue,
        )
        team_identifier: str | int = team
    else:
        # Fallback to database
        if pool is None:
            raise ValueError("Either api_client or pool must be provided")
        matches = await BaseFormTool.get_recent_team_matches(
            pool=pool,
            team=str(team),
            league=str(league),
            match_limit=match_limit,
            venue=venue,
        )
        team_identifier = str(team)

    def is_home_team(match: dict[str, Any]) -> bool:
        """Check if our team is the home team."""
        if isinstance(team_identifier, int):
            return match.get('home_team_id') == team_identifier
        return match.get('home_team') == team_identifier

    # Handle no data case
    if not matches:
        return {
            "tool": "get_consistency_score",
            "data": {
                "consistency_rating": 0,
                "volatility": "high",
                "pattern": "erratic",
                "std_deviation": 0.0,
                "result_distribution": {
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "dominant_result": "mixed"
                },
                "points_per_match_avg": 0.0,
                "reliability_assessment": "No data available"
            },
            "metadata": {
                "venue": venue or "all",
                "matches_analyzed": 0
            }
        }

    # Analyze consistency using ConsistencyAnalyzer
    # For ConsistencyAnalyzer, we need to pass the team identifier
    team_for_analyzer = str(team_identifier) if isinstance(team_identifier, int) else team_identifier
    consistency_analysis = ConsistencyAnalyzer.analyze(matches, team_for_analyzer)

    # Count result distribution
    wins = 0
    draws = 0
    losses = 0
    total_points = 0

    for match in matches:
        is_home = is_home_team(match)
        home_score = match.get('home_score', 0) or 0
        away_score = match.get('away_score', 0) or 0

        if is_home:
            if home_score > away_score:
                wins += 1
                total_points += 3
            elif home_score == away_score:
                draws += 1
                total_points += 1
            else:
                losses += 1
        else:
            if away_score > home_score:
                wins += 1
                total_points += 3
            elif away_score == home_score:
                draws += 1
                total_points += 1
            else:
                losses += 1

    # Determine dominant result
    results_map = {"wins": wins, "draws": draws, "losses": losses}
    max_result = max(results_map.values())
    dominant_results = [k for k, v in results_map.items() if v == max_result]

    if len(dominant_results) > 1 or max_result < len(matches) * 0.4:
        dominant_result = "mixed"
    else:
        dominant_result = dominant_results[0]

    # Calculate points per match average
    points_per_match = total_points / len(matches) if matches else 0.0

    # Generate reliability assessment
    if consistency_analysis["consistency_rating"] >= 80:
        reliability = "Highly predictable - consistent performance across matches"
    elif consistency_analysis["consistency_rating"] >= 60:
        reliability = "Moderately reliable - some variation in results"
    elif consistency_analysis["consistency_rating"] >= 40:
        reliability = "Unpredictable - significant fluctuation in form"
    else:
        reliability = "Highly volatile - unreliable form pattern"

    # Add context based on pattern
    if consistency_analysis["pattern"] == "consistent":
        if wins > losses:
            reliability += " (consistently strong)"
        elif losses > wins:
            reliability += " (consistently weak)"
        else:
            reliability += " (consistently balanced)"
    elif consistency_analysis["pattern"] == "trending":
        reliability += " (form is changing)"

    return {
        "tool": "get_consistency_score",
        "data": {
            "consistency_rating": consistency_analysis["consistency_rating"],
            "volatility": consistency_analysis["volatility"],
            "pattern": consistency_analysis["pattern"],
            "std_deviation": consistency_analysis["std_deviation"],
            "result_distribution": {
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "dominant_result": dominant_result
            },
            "points_per_match_avg": round(points_per_match, 2),
            "reliability_assessment": reliability
        },
        "metadata": {
            "venue": venue or "all",
            "matches_analyzed": len(matches)
        }
    }
