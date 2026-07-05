"""TypedDict models for SIPAP sports data.

Defines structured data types for matches, teams, odds, and leagues.
All models use TypedDict for zero runtime overhead with full type safety.
"""

from typing import Any, NotRequired, TypedDict


class OddsData(TypedDict):
    """Betting odds data for 1X2 market (home win, draw, away win).

    Example:
        ```python
        odds: OddsData = {
            "home_win": 1.85,
            "draw": 3.50,
            "away_win": 4.20
        }
        ```
    """

    home_win: float
    draw: float
    away_win: float


class MatchMetadata(TypedDict):
    """Metadata for match data source and additional information.

    Example:
        ```python
        metadata: MatchMetadata = {
            "source": "api-football",
            "external_source_id": "12345",
            "imported_at": "2026-07-04T10:02:06Z",
            "odds": {
                "home_win": 1.85,
                "draw": 3.50,
                "away_win": 4.20
            }
        }
        ```
    """

    source: str  # Required: Data source identifier
    external_source_id: str  # Required: External ID from source
    imported_at: str  # Required: ISO 8601 timestamp when data was imported
    odds: OddsData  # Required: Current odds data
    referee: NotRequired[str]  # Optional: Match referee name
    weather: NotRequired[dict[str, Any]]  # Optional: Weather data
    attendance: NotRequired[int]  # Optional: Stadium attendance
    broadcast_channels: NotRequired[list[str]]  # Optional: TV/streaming channels


class Match(TypedDict):
    """Match data from normalized sports data schema.

    Represents a single match/fixture with all associated data.
    Some fields are optional depending on match status (scheduled vs finished).

    Example:
        ```python
        match: Match = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "external_id": "api-football-12345",
            "scheduled_at": "2026-07-05T15:00:00Z",
            "status": "scheduled",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_team_id": "team-uuid-1",
            "away_team_id": "team-uuid-2",
            "league": "Premier League",
            "league_id": "league-uuid-1",
            "sport": "Soccer",
            "venue": "Emirates Stadium",
            "home_score": None,
            "away_score": None,
            "metadata": {...}
        }
        ```
    """

    # Required fields (all matches must have these)
    id: str  # Internal UUID
    external_id: str  # External source ID
    scheduled_at: str  # ISO 8601 datetime
    status: str  # scheduled, live, finished, postponed, cancelled
    home_team: str  # Home team name
    away_team: str  # Away team name
    home_team_id: str  # Home team UUID
    away_team_id: str  # Away team UUID
    league: str  # League name
    league_id: str  # League UUID
    sport: str  # Sport type (Soccer, Basketball, etc.)
    venue: str | None  # Stadium/venue name
    home_score: int | None  # Final home team score
    away_score: int | None  # Final away team score
    metadata: MatchMetadata  # Source metadata and additional data


class HomeAwayRecord(TypedDict):
    """Home or away record for a team.

    Example:
        ```python
        home_record: HomeAwayRecord = {
            "wins": 16,
            "draws": 2,
            "losses": 1
        }
        ```
    """

    wins: int
    draws: int
    losses: int


class TeamStats(TypedDict):
    """Team statistics for a season.

    Example:
        ```python
        stats: TeamStats = {
            "team_id": "team-uuid-1",
            "team_name": "Arsenal",
            "season": "2024-2025",
            "matches_played": 38,
            "wins": 28,
            "draws": 7,
            "losses": 3,
            "goals_scored": 88,
            "goals_conceded": 29,
            "goal_difference": 59,
            "points": 91,
            "form": ["W", "W", "D", "W", "W"],
            "home_record": {...},
            "away_record": {...}
        }
        ```
    """

    # Required fields
    team_id: str
    team_name: str
    season: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    points: int
    form: list[str]  # Recent form (last 5 matches)
    home_record: HomeAwayRecord
    away_record: HomeAwayRecord
    # Optional fields
    clean_sheets: NotRequired[int]
    failed_to_score: NotRequired[int]


class LeagueStanding(TypedDict):
    """League table standing entry.

    Example:
        ```python
        standing: LeagueStanding = {
            "position": 1,
            "team_name": "Arsenal",
            "team_id": "team-uuid-1",
            "matches_played": 38,
            "wins": 28,
            "draws": 7,
            "losses": 3,
            "goals_scored": 88,
            "goals_conceded": 29,
            "goal_difference": 59,
            "points": 91,
            "form": ["W", "W", "D", "W", "W"]
        }
        ```
    """

    position: int
    team_name: str
    team_id: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    points: int
    form: list[str]
