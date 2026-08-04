"""
Base classes and utilities for form pattern analysis tools.

Provides:
- FormWeightCalculator: Apply 60/30/10 weighting to last 5/previous 5/longer-term
- FormTrendCalculator: Detect improving/declining/stable patterns
- ConsistencyAnalyzer: Measure form volatility
- BaseFormTool: Common database query patterns for recent form analysis
"""

import statistics
from typing import Any, Literal

import asyncpg


class FormWeightCalculator:
    """
    Calculate weighted form scores with recency bias.

    Weights:
    - Last 5 matches: 60%
    - Previous 5 matches: 30%
    - Longer-term (11-15): 10%
    """

    @staticmethod
    def calculate_points(
        last_5: list[dict[str, Any]],
        previous_5: list[dict[str, Any]],
        longer_term: list[dict[str, Any]],
        team: str,
        venue: Literal["home", "away"] | None = None
    ) -> dict[str, Any]:
        """
        Calculate weighted form points (Win=3, Draw=1, Loss=0).

        Args:
            last_5: Most recent 5 matches
            previous_5: Previous 5 matches (6-10)
            longer_term: Matches 11-15
            team: Team name to analyze
            venue: Optional venue filter ("home" or "away")

        Returns:
            {
                "weighted_points": float,
                "max_possible": float,
                "last_5_points": int,
                "previous_5_points": int,
                "longer_term_points": int
            }

        Example:
            >>> calc = FormWeightCalculator()
            >>> result = calc.calculate_points(
            ...     last_5=[...],
            ...     previous_5=[...],
            ...     longer_term=[...],
            ...     team="Arsenal"
            ... )
            >>> print(result["weighted_points"])
            11.4
        """
        def get_points(match: dict[str, Any]) -> int:
            """Calculate points for a single match from team's perspective."""
            is_home = match['home_team'] == team
            home_score = match['home_score']
            away_score = match['away_score']

            # Filter by venue if specified
            if venue == "home" and not is_home:
                return 0
            if venue == "away" and is_home:
                return 0

            # Calculate result
            if is_home:
                if home_score > away_score:
                    return 3
                if home_score == away_score:
                    return 1
                return 0
            if away_score > home_score:
                return 3
            if away_score == home_score:
                return 1
            return 0

        # Calculate points for each period
        last_5_points = sum(get_points(m) for m in last_5)
        previous_5_points = sum(get_points(m) for m in previous_5)
        longer_term_points = sum(get_points(m) for m in longer_term)

        # Apply weights: 60% last 5, 30% previous 5, 10% longer-term
        # Max points per period: 15 (5 matches * 3 points)
        weighted = (
            (last_5_points / 15) * 0.60 +
            (previous_5_points / 15) * 0.30 +
            (longer_term_points / 15) * 0.10
        ) * 15  # Scale back to 0-15 range

        return {
            "weighted_points": round(weighted, 2),
            "max_possible": 15.0,
            "last_5_points": last_5_points,
            "previous_5_points": previous_5_points,
            "longer_term_points": longer_term_points
        }


class FormTrendCalculator:
    """Detect form trajectory (improving/declining/stable)."""

    @staticmethod
    def analyze(
        last_5_points: int,
        previous_5_points: int
    ) -> dict[str, Any]:
        """
        Determine if form is improving, declining, or stable.

        Args:
            last_5_points: Points in last 5 matches (0-15)
            previous_5_points: Points in previous 5 matches (0-15)

        Returns:
            {
                "trend": "improving" | "declining" | "stable",
                "points_change": int,
                "percentage_change": float
            }

        Example:
            >>> FormTrendCalculator.analyze(13, 9)
            {
                "trend": "improving",
                "points_change": 4,
                "percentage_change": 44.4
            }
        """
        change = last_5_points - previous_5_points
        percentage = (change / previous_5_points * 100) if previous_5_points > 0 else 0.0

        # Classify trend (>2 points difference is significant)
        if change > 2:
            trend = "improving"
        elif change < -2:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "points_change": change,
            "percentage_change": round(percentage, 1)
        }


class ConsistencyAnalyzer:
    """Measure form volatility and consistency."""

    @staticmethod
    def analyze(matches: list[dict[str, Any]], team: str) -> dict[str, Any]:
        """
        Calculate consistency score and volatility.

        Args:
            matches: Recent matches (typically last 10-15)
            team: Team name to analyze

        Returns:
            {
                "consistency_rating": int (0-100),
                "volatility": "low" | "medium" | "high",
                "std_deviation": float,
                "pattern": "consistent" | "erratic" | "trending"
            }

        Example:
            >>> ConsistencyAnalyzer.analyze([...], "Arsenal")
            {
                "consistency_rating": 85,
                "volatility": "low",
                "std_deviation": 0.8,
                "pattern": "consistent"
            }
        """
        if not matches:
            return {
                "consistency_rating": 0,
                "volatility": "high",
                "std_deviation": 0.0,
                "pattern": "erratic"
            }

        def get_match_points(match: dict[str, Any]) -> int:
            """Get points for a single match."""
            is_home = match['home_team'] == team
            home_score = match['home_score']
            away_score = match['away_score']

            if is_home:
                if home_score > away_score:
                    return 3
                if home_score == away_score:
                    return 1
                return 0
            if away_score > home_score:
                return 3
            if away_score == home_score:
                return 1
            return 0

        # Get points for each match
        points = [get_match_points(m) for m in matches]

        # Calculate standard deviation
        std_dev = statistics.stdev(points) if len(points) > 1 else 0.0

        # Classify volatility
        # Low volatility: std_dev < 1.0 (consistent results)
        # High volatility: std_dev > 1.3 (erratic results)
        if std_dev < 1.0:
            volatility = "low"
            pattern = "consistent"
        elif std_dev > 1.3:
            volatility = "high"
            pattern = "erratic"
        else:
            volatility = "medium"
            pattern = "trending"

        # Consistency rating (inverse of volatility, 0-100 scale)
        # Max std_dev for 3 possible values (0,1,3) is ~1.53
        consistency_rating = max(0, min(100, int((1.0 - (std_dev / 1.53)) * 100)))

        return {
            "consistency_rating": consistency_rating,
            "volatility": volatility,
            "std_deviation": round(std_dev, 2),
            "pattern": pattern
        }


class BaseFormTool:
    """
    Base class for form pattern analysis tools.

    Provides:
    - Common database query logic for recent matches
    - Form-specific match filtering (last 10-15 matches)
    - Venue-specific queries (home/away split)
    """

    @staticmethod
    async def get_recent_team_matches(
        pool: asyncpg.Pool,
        team: str,
        league: str,
        match_limit: int = 15,
        venue: Literal["home", "away"] | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve recent matches for a team.

        Args:
            pool: AsyncPG connection pool
            team: Team name
            league: League/competition name
            match_limit: Number of recent matches (default: 15)
            venue: Optional venue filter ("home" or "away")

        Returns:
            List of recent matches ordered by scheduled_at DESC

        Example:
            >>> matches = await BaseFormTool.get_recent_team_matches(
            ...     pool, "Arsenal", "Premier League", match_limit=10
            ... )
            >>> print(len(matches))
            10
        """
        # Build venue filter (hardcoded based on enum, not user input)
        # Safe to use in f-string - venue_clause contains only static SQL
        # Query uses parameterized queries ($1, $2, $3) to prevent SQL injection
        if venue == "home":
            venue_clause = "AND home_team = $1"
        elif venue == "away":
            venue_clause = "AND away_team = $1"
        else:
            venue_clause = "AND (home_team = $1 OR away_team = $1)"

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
                metadata
            FROM matches
            WHERE
                (home_team = $1 OR away_team = $1)
                AND league = $2
                AND status = 'finished'
                {venue_clause}
            ORDER BY scheduled_at DESC
            LIMIT $3
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, team, league, match_limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_recent_h2h_matches(
        pool: asyncpg.Pool,
        home_team: str,
        away_team: str,
        league: str,
        match_limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Retrieve recent head-to-head matches.

        Args:
            pool: AsyncPG connection pool
            home_team: Home team name
            away_team: Away team name
            league: League/competition name
            match_limit: Number of recent matches (default: 10)

        Returns:
            List of recent h2h matches ordered by scheduled_at DESC

        Example:
            >>> matches = await BaseFormTool.get_recent_h2h_matches(
            ...     pool, "Arsenal", "Chelsea", "Premier League"
            ... )
            >>> print(len(matches))
            10
        """
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
                metadata
            FROM matches
            WHERE
                (
                    (home_team = $1 AND away_team = $2) OR
                    (home_team = $2 AND away_team = $1)
                )
                AND league = $3
                AND status = 'finished'
            ORDER BY scheduled_at DESC
            LIMIT $4
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, home_team, away_team, league, match_limit)

        return [dict(row) for row in rows]
