"""Test data fixtures for matches."""


SAMPLE_MATCH = {
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
    "metadata": {
        "source": "api-football",
        "external_source_id": "12345",
        "imported_at": "2026-07-04T10:02:06Z",
        "odds": {
            "home_win": 1.85,
            "draw": 3.50,
            "away_win": 4.20
        }
    }
}

SAMPLE_MATCH_LIST = [SAMPLE_MATCH]

SAMPLE_LIVE_MATCH = {
    **SAMPLE_MATCH,
    "id": "live-match-uuid",
    "status": "live",
    "home_score": 1,
    "away_score": 1
}

SAMPLE_COMPLETED_MATCH = {
    **SAMPLE_MATCH,
    "id": "completed-match-uuid",
    "status": "completed",
    "home_score": 3,
    "away_score": 1
}
