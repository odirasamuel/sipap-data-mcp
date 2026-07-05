"""Unit tests for TypedDict data models.

Following TDD methodology: Tests written BEFORE implementation.
These tests define the expected structure of TypedDict models.
"""

from tests.fixtures.matches import SAMPLE_MATCH
from tests.fixtures.teams import SAMPLE_LEAGUE_TABLE, SAMPLE_TEAM_STATS


class TestMatchModel:
    """Tests for Match TypedDict model."""

    def test_match_model_exists(self) -> None:
        """Test Match model can be imported."""
        from sipap_data_mcp.models import Match

        assert Match is not None

    def test_match_model_has_required_fields(self) -> None:
        """Test Match model has all required fields."""
        from sipap_data_mcp.models import Match

        # Get required and optional keys
        required = Match.__required_keys__
        optional = Match.__optional_keys__

        # Required fields
        assert "id" in required
        assert "external_id" in required
        assert "scheduled_at" in required
        assert "status" in required
        assert "home_team" in required
        assert "away_team" in required
        assert "home_team_id" in required
        assert "away_team_id" in required
        assert "league" in required
        assert "league_id" in required
        assert "sport" in required

        # Optional fields (can be None for scheduled matches)
        assert "venue" in optional or "venue" in required
        assert "home_score" in optional or "home_score" in required
        assert "away_score" in optional or "away_score" in required
        assert "metadata" in optional or "metadata" in required

    def test_match_model_accepts_sample_data(self) -> None:
        """Test Match model works with sample fixture data."""
        from sipap_data_mcp.models import Match

        # This should not raise type errors (checked by mypy)
        match: Match = SAMPLE_MATCH  # type: ignore[assignment]

        # Verify we can access fields
        assert match["home_team"] == "Arsenal"
        assert match["away_team"] == "Chelsea"
        assert match["status"] == "scheduled"


class TestMatchMetadataModel:
    """Tests for MatchMetadata TypedDict model."""

    def test_match_metadata_model_exists(self) -> None:
        """Test MatchMetadata model can be imported."""
        from sipap_data_mcp.models import MatchMetadata

        assert MatchMetadata is not None

    def test_match_metadata_has_required_fields(self) -> None:
        """Test MatchMetadata model has required fields."""
        from sipap_data_mcp.models import MatchMetadata

        required = MatchMetadata.__required_keys__

        assert "source" in required
        assert "external_source_id" in required
        assert "imported_at" in required

    def test_match_metadata_accepts_sample_data(self) -> None:
        """Test MatchMetadata works with sample fixture data."""
        from sipap_data_mcp.models import MatchMetadata

        metadata: MatchMetadata = SAMPLE_MATCH["metadata"]  # type: ignore[assignment]

        assert metadata["source"] == "api-football"
        assert metadata["external_source_id"] == "12345"


class TestOddsDataModel:
    """Tests for OddsData TypedDict model."""

    def test_odds_data_model_exists(self) -> None:
        """Test OddsData model can be imported."""
        from sipap_data_mcp.models import OddsData

        assert OddsData is not None

    def test_odds_data_has_required_fields(self) -> None:
        """Test OddsData model has required odds fields."""
        from sipap_data_mcp.models import OddsData

        required = OddsData.__required_keys__

        # For 1X2 betting market
        assert "home_win" in required
        assert "draw" in required
        assert "away_win" in required

    def test_odds_data_accepts_sample_data(self) -> None:
        """Test OddsData works with sample odds data."""
        from sipap_data_mcp.models import OddsData

        odds: OddsData = SAMPLE_MATCH["metadata"]["odds"]  # type: ignore[assignment]

        assert odds["home_win"] == 1.85
        assert odds["draw"] == 3.50
        assert odds["away_win"] == 4.20


class TestTeamStatsModel:
    """Tests for TeamStats TypedDict model."""

    def test_team_stats_model_exists(self) -> None:
        """Test TeamStats model can be imported."""
        from sipap_data_mcp.models import TeamStats

        assert TeamStats is not None

    def test_team_stats_has_required_fields(self) -> None:
        """Test TeamStats model has required fields."""
        from sipap_data_mcp.models import TeamStats

        required = TeamStats.__required_keys__

        assert "team_id" in required
        assert "team_name" in required
        assert "season" in required
        assert "matches_played" in required
        assert "wins" in required
        assert "draws" in required
        assert "losses" in required
        assert "goals_scored" in required
        assert "goals_conceded" in required
        assert "goal_difference" in required
        assert "points" in required

    def test_team_stats_accepts_sample_data(self) -> None:
        """Test TeamStats works with sample fixture data."""
        from sipap_data_mcp.models import TeamStats

        stats: TeamStats = SAMPLE_TEAM_STATS  # type: ignore[assignment]

        assert stats["team_name"] == "Arsenal"
        assert stats["matches_played"] == 38
        assert stats["points"] == 91


class TestHomeAwayRecordModel:
    """Tests for HomeAwayRecord TypedDict model."""

    def test_home_away_record_model_exists(self) -> None:
        """Test HomeAwayRecord model can be imported."""
        from sipap_data_mcp.models import HomeAwayRecord

        assert HomeAwayRecord is not None

    def test_home_away_record_has_required_fields(self) -> None:
        """Test HomeAwayRecord model has required fields."""
        from sipap_data_mcp.models import HomeAwayRecord

        required = HomeAwayRecord.__required_keys__

        assert "wins" in required
        assert "draws" in required
        assert "losses" in required

    def test_home_away_record_accepts_sample_data(self) -> None:
        """Test HomeAwayRecord works with sample fixture data."""
        from sipap_data_mcp.models import HomeAwayRecord

        home_record: HomeAwayRecord = SAMPLE_TEAM_STATS["home_record"]  # type: ignore[assignment]

        assert home_record["wins"] == 16
        assert home_record["draws"] == 2
        assert home_record["losses"] == 1


class TestLeagueStandingModel:
    """Tests for LeagueStanding TypedDict model."""

    def test_league_standing_model_exists(self) -> None:
        """Test LeagueStanding model can be imported."""
        from sipap_data_mcp.models import LeagueStanding

        assert LeagueStanding is not None

    def test_league_standing_has_required_fields(self) -> None:
        """Test LeagueStanding model has required fields."""
        from sipap_data_mcp.models import LeagueStanding

        required = LeagueStanding.__required_keys__

        assert "position" in required
        assert "team_name" in required
        assert "team_id" in required
        assert "matches_played" in required
        assert "wins" in required
        assert "draws" in required
        assert "losses" in required
        assert "goals_scored" in required
        assert "goals_conceded" in required
        assert "goal_difference" in required
        assert "points" in required

    def test_league_standing_accepts_sample_data(self) -> None:
        """Test LeagueStanding works with sample fixture data."""
        from sipap_data_mcp.models import LeagueStanding

        standing: LeagueStanding = SAMPLE_LEAGUE_TABLE[0]  # type: ignore[assignment]

        assert standing["position"] == 1
        assert standing["team_name"] == "Arsenal"
        assert standing["points"] == 91


class TestModelsIntegration:
    """Integration tests for all models working together."""

    def test_all_models_importable(self) -> None:
        """Test all models can be imported from models package."""
        from sipap_data_mcp.models import (
            HomeAwayRecord,
            LeagueStanding,
            Match,
            MatchMetadata,
            OddsData,
            TeamStats,
        )

        assert Match is not None
        assert MatchMetadata is not None
        assert OddsData is not None
        assert TeamStats is not None
        assert HomeAwayRecord is not None
        assert LeagueStanding is not None

    def test_models_exported_in_all(self) -> None:
        """Test all models are exported in __all__."""
        from sipap_data_mcp import models

        assert "Match" in models.__all__
        assert "MatchMetadata" in models.__all__
        assert "OddsData" in models.__all__
        assert "TeamStats" in models.__all__
        assert "HomeAwayRecord" in models.__all__
        assert "LeagueStanding" in models.__all__
