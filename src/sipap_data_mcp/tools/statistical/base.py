"""
Base classes and utilities for statistical analysis tools.

Provides:
- get_football_season: Convert date to football season (Aug-Jul)
- RecencyWeightCalculator: Apply adaptive weighting with minimum sample guards
- DataQualityClassifier: Assess data quality with market-specific thresholds
- BaseStatisticalTool: Common database query patterns for h2h and team matches
- calculate_confidence_penalty: Penalize confidence when signals conflict
- calculate_final_confidence: Apply all confidence adjustments

REDESIGNED (2026-08-19): Supports direct API-Football calls with intelligent caching.
IMPROVED (2026-08-29): Added football season partitioning, sample guards, form blending.
"""

import logging
from typing import Any, Literal, Callable
from datetime import datetime
# asyncpg removed (2026-08-20) - database removed

from sipap_data_mcp.api.football_client import APIFootballClient

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Minimum matches needed for a bucket to be weighted
MIN_SAMPLES_FOR_WEIGHTING = 3

# Market-specific quality thresholds
MARKET_QUALITY_THRESHOLDS: dict[str, dict[str, int]] = {
    # Simple markets - need less data
    "1X2": {"high": 10, "medium": 5},
    "BTTS": {"high": 10, "medium": 5},
    "OU0.5": {"high": 10, "medium": 5},
    "OU1.5": {"high": 10, "medium": 5},
    "OU2.5": {"high": 10, "medium": 5},
    "OU3.5": {"high": 10, "medium": 5},
    "OU4.5": {"high": 10, "medium": 5},
    "DC": {"high": 10, "medium": 5},
    "DNB": {"high": 10, "medium": 5},

    # Half-time markets - more variance expected
    "HT_1X2": {"high": 8, "medium": 4},
    "HT_DC": {"high": 8, "medium": 4},
    "HT_OU0.5": {"high": 8, "medium": 4},
    "HT_OU1.5": {"high": 8, "medium": 4},
    "HT_OU2.5": {"high": 8, "medium": 4},

    # 2nd half markets
    "2H_DC": {"high": 8, "medium": 4},
    "2H_OU0.5": {"high": 8, "medium": 4},
    "2H_OU1.5": {"high": 8, "medium": 4},
    "2H_OU2.5": {"high": 8, "medium": 4},

    # Combination markets - need more data
    "1X2_OU1.5": {"high": 15, "medium": 8},
    "1X2_OU2.5": {"high": 15, "medium": 8},
    "1X2_OU3.5": {"high": 15, "medium": 8},
    "1X2_OU4.5": {"high": 15, "medium": 8},
    "1X2_BTTS": {"high": 15, "medium": 8},
    "DC_OU1.5": {"high": 15, "medium": 8},
    "DC_OU2.5": {"high": 15, "medium": 8},
    "DC_OU3.5": {"high": 15, "medium": 8},
    "DC_BTTS": {"high": 15, "medium": 8},
    "BTTS_OU2.5": {"high": 15, "medium": 8},
    "BTTS_OU3.5": {"high": 15, "medium": 8},

    # Chance mix markets
    "CHANCEMIX_1X2_OU15": {"high": 15, "medium": 8},
    "CHANCEMIX_1X2_OU25": {"high": 15, "medium": 8},
    "CHANCEMIX_1X2_OU35": {"high": 15, "medium": 8},
    "CHANCEMIX_1X2_BTTS": {"high": 15, "medium": 8},
    "CHANCEMIX_BTTS_OU15": {"high": 15, "medium": 8},
    "CHANCEMIX_BTTS_OU25": {"high": 15, "medium": 8},
    "CHANCEMIX_BTTS_OU35": {"high": 15, "medium": 8},

    # Default for unspecified markets
    "default": {"high": 12, "medium": 6},
}


# =============================================================================
# Football Season Helper
# =============================================================================

def get_football_season(date: datetime | str) -> int:
    """Get football season year (Aug-Jul).

    Football seasons span Aug Year N to Jul Year N+1.
    The season is named by the starting year.

    Args:
        date: Match date (datetime or ISO string)

    Returns:
        Season year (e.g., 2025 for Aug 2025 - Jul 2026)

    Examples:
        >>> get_football_season(datetime(2025, 8, 15))
        2025
        >>> get_football_season(datetime(2025, 12, 20))
        2025
        >>> get_football_season(datetime(2026, 1, 10))
        2025
        >>> get_football_season(datetime(2026, 7, 30))
        2025
        >>> get_football_season(datetime(2026, 8, 1))
        2026
    """
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace("Z", "+00:00"))

    if date.month >= 8:  # Aug-Dec
        return date.year
    else:  # Jan-Jul
        return date.year - 1


# =============================================================================
# Confidence Penalty Functions
# =============================================================================

def calculate_confidence_penalty(
    h2h_prob: float,
    form_prob: float,
) -> tuple[float, str]:
    """
    Calculate confidence penalty when H2H and form signals conflict.

    Args:
        h2h_prob: Probability from H2H analysis (0-1)
        form_prob: Probability from team form analysis (0-1)

    Returns:
        Tuple of (penalty_multiplier, reason)

    Examples:
        >>> calculate_confidence_penalty(0.30, 0.65)
        (0.7, 'Large disagreement (35%)')
        >>> calculate_confidence_penalty(0.50, 0.55)
        (1.0, 'Signals aligned')
    """
    disagreement = abs(h2h_prob - form_prob)

    if disagreement > 0.30:
        return (0.70, f"Large disagreement ({disagreement:.0%})")
    elif disagreement > 0.20:
        return (0.85, f"Moderate disagreement ({disagreement:.0%})")
    elif disagreement > 0.10:
        return (0.95, f"Minor disagreement ({disagreement:.0%})")
    else:
        return (1.0, "Signals aligned")


def calculate_final_confidence(
    base_confidence: float,
    h2h_prob: float | None = None,
    form_prob: float | None = None,
    data_quality: str = "medium",
) -> dict[str, Any]:
    """
    Calculate final confidence with all adjustments.

    Applies quality-based and signal disagreement penalties.

    Args:
        base_confidence: Initial confidence (0-1)
        h2h_prob: H2H probability (optional)
        form_prob: Form probability (optional)
        data_quality: "high", "medium", or "low"

    Returns:
        Dict with final_confidence, adjustments, and metadata

    Example:
        >>> result = calculate_final_confidence(0.80, 0.30, 0.60, "medium")
        >>> result["final_confidence"]  # ~0.50 after penalties
    """
    adjustments = []
    confidence = base_confidence

    # Quality adjustment
    quality_multipliers = {"high": 1.0, "medium": 0.9, "low": 0.75}
    quality_mult = quality_multipliers.get(data_quality, 0.9)
    if quality_mult < 1.0:
        confidence *= quality_mult
        adjustments.append(f"Quality penalty: {data_quality} ({quality_mult})")

    # Signal disagreement penalty
    if h2h_prob is not None and form_prob is not None:
        penalty, reason = calculate_confidence_penalty(h2h_prob, form_prob)
        if penalty < 1.0:
            confidence *= penalty
            adjustments.append(f"Signal penalty: {reason} ({penalty})")

    return {
        "final_confidence": round(confidence, 4),
        "base_confidence": base_confidence,
        "adjustments": adjustments,
        "data_quality": data_quality,
    }


class RecencyWeightCalculator:
    """
    Calculate weighted probabilities with recency bias and sample guards.

    Weights (when all buckets have sufficient data):
    - Recent matches (last 10): 50%
    - Last season: 30%
    - Older seasons (2-6): 20%

    Buckets with fewer than MIN_SAMPLES_FOR_WEIGHTING matches are excluded,
    and remaining weights are normalized to sum to 1.0.
    """

    @staticmethod
    def calculate(
        recent_matches: list[dict[str, Any]],
        last_season: list[dict[str, Any]],
        older_seasons: list[dict[str, Any]],
        condition_fn: Callable[[dict[str, Any]], bool],
        min_samples: int = MIN_SAMPLES_FOR_WEIGHTING,
    ) -> tuple[float, dict[str, Any]]:
        """
        Apply adaptive recency weighting with minimum sample guards.

        Buckets with fewer than min_samples matches are excluded.
        Remaining weights are normalized to sum to 1.0.

        Args:
            recent_matches: Last N matches (typically 10)
            last_season: Previous football season matches
            older_seasons: Seasons 2-6 matches
            condition_fn: Function to check if condition met (returns bool)
            min_samples: Minimum matches for bucket to count (default: 3)

        Returns:
            Tuple of (weighted_probability, breakdown_dict)

        Example:
            >>> recent = [{"home_score": 2, "away_score": 1}, ...]  # 10 matches
            >>> last = [{"home_score": 1, "away_score": 1}]  # 1 match - excluded!
            >>> older = [{"home_score": 0, "away_score": 2}, ...]  # 5 matches
            >>> prob, breakdown = RecencyWeightCalculator.calculate(
            ...     recent, last, older,
            ...     lambda m: m["home_score"] > m["away_score"]
            ... )
            >>> # last_season excluded, weights normalized: recent=71%, older=29%
        """
        # Define buckets with default weights
        buckets = {
            "recent": (recent_matches, 0.50),
            "last_season": (last_season, 0.30),
            "older": (older_seasons, 0.20),
        }

        valid_buckets: dict[str, tuple[float, float]] = {}
        breakdown: dict[str, Any] = {}

        for name, (matches, default_weight) in buckets.items():
            if len(matches) >= min_samples:
                prob = sum(1 for m in matches if condition_fn(m)) / len(matches)
                valid_buckets[name] = (prob, default_weight)
                breakdown[name] = {
                    "matches": len(matches),
                    "probability": round(prob, 4),
                    "included": True,
                }
            else:
                breakdown[name] = {
                    "matches": len(matches),
                    "probability": None,
                    "included": False,
                    "reason": f"Below minimum ({len(matches)} < {min_samples})",
                }

        # If no valid buckets, use all data combined
        if not valid_buckets:
            all_matches = recent_matches + last_season + older_seasons
            if all_matches:
                prob = sum(1 for m in all_matches if condition_fn(m)) / len(all_matches)
                breakdown["fallback"] = {
                    "matches": len(all_matches),
                    "probability": round(prob, 4),
                    "reason": "No bucket met minimum samples",
                }
                return (round(prob, 4), breakdown)
            # No data at all - return neutral probability
            breakdown["fallback"] = {"reason": "No data available"}
            return (0.5, breakdown)

        # Normalize weights to sum to 1.0
        total_weight = sum(w for _, w in valid_buckets.values())
        weighted_prob = sum(
            prob * (weight / total_weight)
            for prob, weight in valid_buckets.values()
        )

        breakdown["normalized_weights"] = {
            name: round(weight / total_weight, 4)
            for name, (_, weight) in valid_buckets.items()
        }

        return (round(weighted_prob, 4), breakdown)

    @staticmethod
    def calculate_simple(
        recent_matches: list[dict[str, Any]],
        last_season: list[dict[str, Any]],
        older_seasons: list[dict[str, Any]],
        condition_fn: Callable[[dict[str, Any]], bool],
    ) -> float:
        """
        Legacy method for backward compatibility.

        Returns only the weighted probability without breakdown.
        Uses sample guards internally.

        Args:
            recent_matches: Last N matches
            last_season: Previous season matches
            older_seasons: Older seasons matches
            condition_fn: Condition check function

        Returns:
            Weighted probability (0.0-1.0)
        """
        prob, _ = RecencyWeightCalculator.calculate(
            recent_matches, last_season, older_seasons, condition_fn
        )
        return prob


class DataQualityClassifier:
    """Classify data quality with market-specific thresholds."""

    @staticmethod
    def assess(
        total_matches: int,
        market: str = "default",
    ) -> Literal["high", "medium", "low"]:
        """
        Classify data quality based on matches and market type.

        Different markets have different data requirements:
        - Simple markets (1X2, BTTS): 10 for high, 5 for medium
        - Half-time markets: 8 for high, 4 for medium
        - Combination markets: 15 for high, 8 for medium

        Args:
            total_matches: Total number of matches analyzed
            market: Market code (e.g., "BTTS", "1X2_BTTS", "default")

        Returns:
            "high", "medium", or "low"

        Examples:
            >>> DataQualityClassifier.assess(12, "BTTS")
            'high'
            >>> DataQualityClassifier.assess(12, "1X2_BTTS")
            'medium'
            >>> DataQualityClassifier.assess(5, "HT_1X2")
            'medium'
        """
        thresholds = MARKET_QUALITY_THRESHOLDS.get(
            market,
            MARKET_QUALITY_THRESHOLDS["default"]
        )

        if total_matches >= thresholds["high"]:
            return "high"
        elif total_matches >= thresholds["medium"]:
            return "medium"
        else:
            return "low"

    @staticmethod
    def assess_legacy(total_matches: int) -> Literal["high", "medium", "low"]:
        """
        Legacy method for backward compatibility.

        Uses fixed thresholds: high (≥15), medium (8-14), low (<8)

        Args:
            total_matches: Total number of matches analyzed

        Returns:
            "high", "medium", or "low"
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

        Uses football season partitioning (Aug-Jul) instead of calendar year.

        Args:
            api_client: API-Football client instance
            home_team_id: API-Football home team ID
            away_team_id: API-Football away team ID
            current_form_matches: Recent matches for "current form" (default: 10)

        Returns:
            Dict with all_matches, recent_matches, last_season, older_seasons,
            seasons_analyzed, earliest_match, latest_match
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

            # Use football season (Aug-Jul) instead of calendar year
            football_season = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    football_season = get_football_season(dt)
                except ValueError:
                    pass

            # Extract halftime scores from score object
            score = item.get("score", {})
            halftime = score.get("halftime", {})
            ht_home = halftime.get("home")
            ht_away = halftime.get("away")

            all_matches.append({
                "id": fixture.get("id"),
                "scheduled_at": date_str,
                "home_team": teams.get("home", {}).get("name"),
                "away_team": teams.get("away", {}).get("name"),
                "home_team_id": teams.get("home", {}).get("id"),
                "away_team_id": teams.get("away", {}).get("id"),
                "home_score": goals.get("home"),
                "away_score": goals.get("away"),
                "ht_home_score": ht_home,
                "ht_away_score": ht_away,
                "status": "finished",
                "football_season": football_season,
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

        # Partition by football season (Aug-Jul)
        recent_matches = all_matches[:current_form_matches]

        current_season = get_football_season(datetime.now())
        last_season = [
            m for m in all_matches
            if m.get('football_season') == current_season - 1
        ]
        older_seasons = [
            m for m in all_matches
            if m.get('football_season') and m['football_season'] < current_season - 1
        ]

        seasons = {m['football_season'] for m in all_matches if m.get('football_season')}
        dates = [m['scheduled_at'] for m in all_matches if m.get('scheduled_at')]

        logger.info(
            f"get_h2h_matches_api: {home_team_id} vs {away_team_id}, "
            f"{len(all_matches)} matches, current_season={current_season}, "
            f"last_season={len(last_season)}, older={len(older_seasons)}"
        )

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(seasons),
            "earliest_match": min(dates) if dates else None,
            "latest_match": max(dates) if dates else None,
            "current_football_season": current_season,
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

        Uses football season partitioning (Aug-Jul) instead of calendar year.

        Args:
            api_client: API-Football client instance
            team_id: API-Football team ID
            venue: "home" or "away" (or None for all)
            league_id: Optional league ID filter
            current_form_matches: Recent matches for current form (default: 10)

        Returns:
            Dict with all_matches, recent_matches, last_season, older_seasons,
            seasons_analyzed, earliest_match, latest_match
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

            # Use football season (Aug-Jul) instead of calendar year
            football_season = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    football_season = get_football_season(dt)
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
                "football_season": football_season,
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

        # Partition by football season (Aug-Jul)
        recent_matches = all_matches[:current_form_matches]

        current_season = get_football_season(datetime.now())
        last_season = [
            m for m in all_matches
            if m.get('football_season') == current_season - 1
        ]
        older_seasons = [
            m for m in all_matches
            if m.get('football_season') and m['football_season'] < current_season - 1
        ]

        seasons = {m['football_season'] for m in all_matches if m.get('football_season')}
        dates = [m['scheduled_at'] for m in all_matches if m.get('scheduled_at')]

        logger.info(
            f"get_team_matches_api: team {team_id}, venue {venue}, "
            f"{len(all_matches)} matches, current_season={current_season}"
        )

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(seasons),
            "earliest_match": min(dates) if dates else None,
            "latest_match": max(dates) if dates else None,
            "current_football_season": current_season,
        }

    @staticmethod
    async def get_h2h_matches(
        pool: Any,
        home_team: str,
        away_team: str,
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve head-to-head matches partitioned by recency.

        Uses football season partitioning (Aug-Jul) instead of calendar year.

        Args:
            pool: AsyncPG connection pool
            home_team: Home team name
            away_team: Away team name
            league: League/competition name
            seasons_back: Number of historical seasons (default: 6)
            current_form_matches: Recent matches for "current form" (default: 10)

        Returns:
            Dict with all_matches, recent_matches, last_season, older_seasons,
            seasons_analyzed, earliest_match, latest_match

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
                metadata
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

        # Convert to dictionaries and add football season
        all_matches = []
        for row in rows:
            match = dict(row)
            if match.get('scheduled_at'):
                match['football_season'] = get_football_season(match['scheduled_at'])
            else:
                match['football_season'] = None
            all_matches.append(match)

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

        # Partition matches by football season (Aug-Jul)
        recent_matches = all_matches[:current_form_matches]

        current_season = get_football_season(datetime.now())
        last_season = [
            m for m in all_matches
            if m.get('football_season') == current_season - 1
        ]

        older_seasons = [
            m for m in all_matches
            if m.get('football_season') and m['football_season'] < current_season - 1
        ]

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(set(m['football_season'] for m in all_matches if m.get('football_season'))),
            "earliest_match": min(m['scheduled_at'] for m in all_matches),
            "latest_match": max(m['scheduled_at'] for m in all_matches),
            "current_football_season": current_season,
        }

    @staticmethod
    async def get_team_matches(
        pool: Any,
        team: str,
        venue: Literal["home", "away"],
        league: str,
        seasons_back: int = 6,
        current_form_matches: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve all matches for a specific team (home or away) partitioned by recency.

        Uses football season partitioning (Aug-Jul) instead of calendar year.

        Args:
            pool: AsyncPG connection pool
            team: Team name
            venue: "home" or "away"
            league: League/competition name
            seasons_back: Number of historical seasons (default: 6)
            current_form_matches: Recent matches for current form (default: 10)

        Returns:
            Dict with all_matches, recent_matches, last_season, older_seasons,
            seasons_analyzed, earliest_match, latest_match

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
                metadata
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

        # Convert to dictionaries and add football season
        all_matches = []
        for row in rows:
            match = dict(row)
            if match.get('scheduled_at'):
                match['football_season'] = get_football_season(match['scheduled_at'])
            else:
                match['football_season'] = None
            all_matches.append(match)

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

        # Partition by football season (Aug-Jul)
        recent_matches = all_matches[:current_form_matches]

        current_season = get_football_season(datetime.now())
        last_season = [
            m for m in all_matches
            if m.get('football_season') == current_season - 1
        ]
        older_seasons = [
            m for m in all_matches
            if m.get('football_season') and m['football_season'] < current_season - 1
        ]

        return {
            "all_matches": all_matches,
            "recent_matches": recent_matches,
            "last_season": last_season,
            "older_seasons": older_seasons,
            "seasons_analyzed": len(set(m['football_season'] for m in all_matches if m.get('football_season'))),
            "earliest_match": min(m['scheduled_at'] for m in all_matches),
            "latest_match": max(m['scheduled_at'] for m in all_matches),
            "current_football_season": current_season,
        }
