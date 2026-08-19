"""
Base classes and utilities for statistical analysis tools.

Provides:
- RecencyWeightCalculator: Apply 50/30/20 weighting to recent/last season/older data
- DataQualityClassifier: Assess data quality based on sample size
- BaseStatisticalTool: Common database query patterns for h2h and team matches

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
"""

import logging
from typing import Any, Literal, Callable
from datetime import datetime
import asyncpg

from sipap_data_mcp.api.football_client import APIFootballClient

logger = logging.getLogger(__name__)


class RecencyWeightCalculator:
    """
    Calculate weighted probabilities with recency bias.

    Weights:
    - Recent matches (last 10): 50%
    - Last season: 30%
    - Older seasons (2-6): 20%
    """

    @staticmethod
    def calculate(
        recent_matches: list[dict[str, Any]],
        last_season: list[dict[str, Any]],
        older_seasons: list[dict[str, Any]],
        condition_fn: Callable[[dict[str, Any]], bool]
    ) -> float:
        """
        Apply recency weighting to calculate final probability.

        Args:
            recent_matches: Last N matches (typically 10)
            last_season: Previous season matches
            older_seasons: Seasons 2-6 matches
            condition_fn: Function to check if condition met (returns bool)

        Returns:
            Weighted probability (0.0-1.0)

        Example:
            >>> calculator = RecencyWeightCalculator()
            >>> recent = [{"home_score": 2, "away_score": 1}, ...]
            >>> last = [{"home_score": 1, "away_score": 1}, ...]
            >>> older = [{"home_score": 0, "away_score": 2}, ...]
            >>> prob = calculator.calculate(
            ...     recent, last, older,
            ...     lambda m: m["home_score"] > m["away_score"]
            ... )
            >>> # Returns weighted probability of home win
        """
        # Calculate probability for each period
        recent_prob = (
            sum(1 for m in recent_matches if condition_fn(m)) / len(recent_matches)
            if recent_matches else 0.0
        )

        last_season_prob = (
            sum(1 for m in last_season if condition_fn(m)) / len(last_season)
            if last_season else 0.0
        )

        older_prob = (
            sum(1 for m in older_seasons if condition_fn(m)) / len(older_seasons)
            if older_seasons else 0.0
        )

        # Apply weights: 50% recent, 30% last season, 20% older
        weighted = (
            recent_prob * 0.50 +
            last_season_prob * 0.30 +
            older_prob * 0.20
        )

        return round(weighted, 4)


class DataQualityClassifier:
    """Classify data quality based on sample size."""

    @staticmethod
    def assess(total_matches: int) -> Literal["high", "medium", "low"]:
        """
        Classify data quality based on number of matches.

        Args:
            total_matches: Total number of matches analyzed

        Returns:
            "high" (≥15), "medium" (8-14), or "low" (<8)

        Example:
            >>> DataQualityClassifier.assess(20)
            'high'
            >>> DataQualityClassifier.assess(10)
            'medium'
            >>> DataQualityClassifier.assess(5)
            'low'
        """
        if total_matches >= 15:
            return "high"
        elif total_matches >= 8:
            return "medium"
        else:
            return "low"


class BaseStatisticalTool:
    """
    Base class for statistical analysis tools.

    Provides:
    - Common database query logic
    - Season partitioning (recent/last/older)
    - H2H match filtering
    - Team-specific match filtering
    - API-Football integration (2026-08-19)
    """

    @staticmethod
    async def get_h2h_matches_api(
        api_client: APIFootballClient,
        home_team_id: int,
        away_team_id: int,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve head-to-head matches using API-Football.

        Args:
            api_client: API-Football client instance
            home_team_id: API-Football home team ID
            away_team_id: API-Football away team ID
            current_form_matches: Recent matches for "current form" (default: 10)

        Returns:
            Same structure as get_h2h_matches
        """
        # API-Football returns up to 50 H2H matches
        response = await api_client.get_h2h(
            team1_id=home_team_id,
            team2_id=away_team_id,
            last=50,
        )

        # Transform fixtures to match format
        all_matches = []
        for item in response.get("response", []):
            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            date_str = fixture.get("date", "")

            # Parse year from date
            season_year = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    season_year = dt.year
                except ValueError:
                    pass

            all_matches.append({
                "id": fixture.get("id"),
                "scheduled_at": date_str,
                "home_team": teams.get("home", {}).get("name"),
                "away_team": teams.get("away", {}).get("name"),
                "home_team_id": teams.get("home", {}).get("id"),
                "away_team_id": teams.get("away", {}).get("id"),
                "home_score": goals.get("home"),
                "away_score": goals.get("away"),
                "status": "finished",
                "season_year": season_year,
            })

        if not all_matches:
            return {
                "all_matches": [],
                "recent_matches": [],
                "last_season": [],
                "older_seasons": [],
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None,
            }

        # Partition by recency
        recent_matches = all_matches[:current_form_matches]

        current_year = datetime.now().year
        last_season = [m for m in all_matches if m.get('season_year') == current_year - 1]
        older_seasons = [m for m in all_matches if m.get('season_year') and m['season_year'] < current_year - 1]

        seasons = {m['season_year'] for m in all_matches if m.get('season_year')}
        dates = [m['scheduled_at'] for m in all_matches if m.get('scheduled_at')]

        logger.info(
            f"get_h2h_matches_api: {home_team_id} vs {away_team_id}, "
            f"{len(all_matches)} matches"
        )

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(seasons),
            "earliest_match": min(dates) if dates else None,
            "latest_match": max(dates) if dates else None,
        }

    @staticmethod
    async def get_team_matches_api(
        api_client: APIFootballClient,
        team_id: int,
        venue: Literal["home", "away"] | None,
        league_id: int | None = None,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve team matches using API-Football.

        Args:
            api_client: API-Football client instance
            team_id: API-Football team ID
            venue: "home" or "away" (or None for all)
            league_id: Optional league ID filter
            current_form_matches: Recent matches for current form (default: 10)

        Returns:
            Same structure as get_team_matches
        """
        params: dict[str, Any] = {
            "team": team_id,
            "status": "FT",
            "last": 50,
        }

        if league_id:
            params["league"] = league_id

        response = await api_client.get_fixtures(**params)

        # Transform and filter by venue
        all_matches = []
        for item in response.get("response", []):
            fixture = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            date_str = fixture.get("date", "")

            home_team_id = teams.get("home", {}).get("id")
            is_home = home_team_id == team_id

            # Filter by venue if specified
            if venue == "home" and not is_home:
                continue
            if venue == "away" and is_home:
                continue

            season_year = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    season_year = dt.year
                except ValueError:
                    pass

            all_matches.append({
                "id": fixture.get("id"),
                "scheduled_at": date_str,
                "home_team": teams.get("home", {}).get("name"),
                "away_team": teams.get("away", {}).get("name"),
                "home_team_id": home_team_id,
                "away_team_id": teams.get("away", {}).get("id"),
                "home_score": goals.get("home"),
                "away_score": goals.get("away"),
                "status": "finished",
                "season_year": season_year,
            })

        if not all_matches:
            return {
                "all_matches": [],
                "recent_matches": [],
                "last_season": [],
                "older_seasons": [],
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None,
            }

        # Partition by recency
        recent_matches = all_matches[:current_form_matches]

        current_year = datetime.now().year
        last_season = [m for m in all_matches if m.get('season_year') == current_year - 1]
        older_seasons = [m for m in all_matches if m.get('season_year') and m['season_year'] < current_year - 1]

        seasons = {m['season_year'] for m in all_matches if m.get('season_year')}
        dates = [m['scheduled_at'] for m in all_matches if m.get('scheduled_at')]

        logger.info(
            f"get_team_matches_api: team {team_id}, venue {venue}, "
            f"{len(all_matches)} matches"
        )

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(seasons),
            "earliest_match": min(dates) if dates else None,
            "latest_match": max(dates) if dates else None,
        }

    @staticmethod
    async def get_h2h_matches(
        pool: asyncpg.Pool,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve head-to-head matches partitioned by recency.

        Args:
            pool: AsyncPG connection pool
            home_team: Home team name
            away_team: Away team name
            league: League/competition name
            seasons_back: Number of historical seasons (default: 6)
            current_form_matches: Recent matches for "current form" (default: 10)

        Returns:
            {
                "all_matches": [...],      # All h2h matches
                "recent_matches": [...],   # Last N matches
                "last_season": [...],      # Previous season
                "older_seasons": [...],    # Seasons 2-6
                "seasons_analyzed": int,   # Number of unique seasons
                "earliest_match": datetime,
                "latest_match": datetime
            }

        Example:
            >>> matches = await BaseStatisticalTool.get_h2h_matches(
            ...     pool, "Arsenal", "Chelsea", "Premier League"
            ... )
            >>> print(len(matches["all_matches"]))
            18
        """
        # Query database for h2h matches
        query = """
            SELECT
                id,
                scheduled_at,
                home_team,
                away_team,
                home_score,
                away_score,
                status,
                league,
                metadata,
                EXTRACT(YEAR FROM scheduled_at) as season_year
            FROM matches
            WHERE
                (
                    (home_team = $1 AND away_team = $2) OR
                    (home_team = $2 AND away_team = $1)
                )
                AND league = $3
                AND status = 'finished'
                AND scheduled_at >= NOW() - INTERVAL '%s years'
            ORDER BY scheduled_at DESC
            LIMIT 50
        """ % seasons_back

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, home_team, away_team, league)

        # Convert to dictionaries
        all_matches = [dict(row) for row in rows]

        if not all_matches:
            return {
                "all_matches": [],
                "recent_matches": [],
                "last_season": [],
                "older_seasons": [],
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None
            }

        # Partition matches by recency
        recent_matches = all_matches[:current_form_matches]

        # Determine last season cutoff (matches from previous calendar year)
        current_year = datetime.now().year
        last_season = [
            m for m in all_matches
            if m['season_year'] == current_year - 1
        ]

        older_seasons = [
            m for m in all_matches
            if m['season_year'] < current_year - 1
        ]

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(set(m['season_year'] for m in all_matches)),
            "earliest_match": min(m['scheduled_at'] for m in all_matches),
            "latest_match": max(m['scheduled_at'] for m in all_matches)
        }

    @staticmethod
    async def get_team_matches(
        pool: asyncpg.Pool,
        team: str,
        venue: Literal["home", "away"],
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve all matches for a specific team (home or away) partitioned by recency.

        Args:
            pool: AsyncPG connection pool
            team: Team name
            venue: "home" or "away"
            league: League/competition name
            seasons_back: Number of historical seasons (default: 6)
            current_form_matches: Recent matches for current form (default: 10)

        Returns:
            Same structure as get_h2h_matches

        Example:
            >>> matches = await BaseStatisticalTool.get_team_matches(
            ...     pool, "Arsenal", "home", "Premier League"
            ... )
            >>> print(len(matches["all_matches"]))
            114
        """
        # Query database for team matches
        venue_column = "home_team" if venue == "home" else "away_team"

        query = f"""
            SELECT
                id,
                scheduled_at,
                home_team,
                away_team,
                home_score,
                away_score,
                status,
                league,
                metadata,
                EXTRACT(YEAR FROM scheduled_at) as season_year
            FROM matches
            WHERE
                {venue_column} = $1
                AND league = $2
                AND status = 'finished'
                AND scheduled_at >= NOW() - INTERVAL '%s years'
            ORDER BY scheduled_at DESC
            LIMIT 150
        """ % seasons_back

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, team, league)

        all_matches = [dict(row) for row in rows]

        if not all_matches:
            return {
                "all_matches": [],
                "recent_matches": [],
                "last_season": [],
                "older_seasons": [],
                "seasons_analyzed": 0,
                "earliest_match": None,
                "latest_match": None
            }

        # Partition by recency
        recent_matches = all_matches[:current_form_matches]

        current_year = datetime.now().year
        last_season = [m for m in all_matches if m['season_year'] == current_year - 1]
        older_seasons = [m for m in all_matches if m['season_year'] < current_year - 1]

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(set(m['season_year'] for m in all_matches)),
            "earliest_match": min(m['scheduled_at'] for m in all_matches),
            "latest_match": max(m['scheduled_at'] for m in all_matches)
        }
