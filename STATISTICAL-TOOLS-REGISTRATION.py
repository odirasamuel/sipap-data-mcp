# STATISTICAL TOOLS REGISTRATION - To be appended to server.py
# This file contains all 24 statistical tool registrations

STATISTICAL_TOOLS_CODE = '''
    # ========================================================================
    # Statistical Analysis Tools - Phase 1: Core Tools (5)
    # ========================================================================

    @mcp_tool(
        description="Analyze head-to-head full-time results with recency weighting",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6, "description": "Number of seasons to analyze"},
                "current_form_matches": {"type": "integer", "default": 10, "description": "Number of recent matches for form analysis"}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_full_time_result(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze head-to-head full-time results."""
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_full_time_result(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze total goals in h2h fixtures with over/under thresholds",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6},
                "current_form_matches": {"type": "integer", "default": 10}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_h2h_goals(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze total goals in h2h fixtures."""
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_h2h_goals(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze both teams to score probability",
        input_schema={
            "type": "object",
            "properties": {
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6},
                "current_form_matches": {"type": "integer", "default": 10}
            },
            "required": ["home_team", "away_team", "league"]
        }
    )
    def get_bts(
        self,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze both teams to score probability."""
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_bts(
                pool=db_client._pool,
                home_team=home_team,
                away_team=away_team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze home team goal-scoring capability (all home matches)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6},
                "current_form_matches": {"type": "integer", "default": 10}
            },
            "required": ["team", "league"]
        }
    )
    def get_home_total_goals(
        self,
        team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze home team goal-scoring capability."""
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_home_total_goals(
                pool=db_client._pool,
                team=team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )

    @mcp_tool(
        description="Analyze away team goal-scoring capability (all away matches)",
        input_schema={
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name"},
                "league": {"type": "string", "description": "League name"},
                "seasons_back": {"type": "integer", "default": 6},
                "current_form_matches": {"type": "integer", "default": 10}
            },
            "required": ["team", "league"]
        }
    )
    def get_away_total_goals(
        self,
        team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """Analyze away team goal-scoring capability."""
        db_client, _ = self._ensure_connections()
        return self._run_async(
            statistical.get_away_total_goals(
                pool=db_client._pool,
                team=team,
                league=league,
                seasons_back=seasons_back,
                current_form_matches=current_form_matches
            )
        )
'''

# Due to length, I'll create this as a reference file
# The actual implementation will be added to server.py in chunks
