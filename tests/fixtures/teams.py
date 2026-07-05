"""Test data fixtures for teams."""

SAMPLE_TEAM_STATS = {
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
    "home_record": {
        "wins": 16,
        "draws": 2,
        "losses": 1
    },
    "away_record": {
        "wins": 12,
        "draws": 5,
        "losses": 2
    }
}

SAMPLE_LEAGUE_TABLE = [
    {
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
    },
    {
        "position": 2,
        "team_name": "Manchester City",
        "team_id": "team-uuid-2",
        "matches_played": 38,
        "wins": 27,
        "draws": 8,
        "losses": 3,
        "goals_scored": 86,
        "goals_conceded": 28,
        "goal_difference": 58,
        "points": 89,
        "form": ["W", "D", "W", "W", "W"]
    }
]
