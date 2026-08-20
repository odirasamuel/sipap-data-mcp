"""Response transformers for API-Football data.

Converts API-Football response format to the format expected by MCP tools.
"""

from datetime import datetime
from typing import Any


def transform_fixture(fixture_data: dict[str, Any]) -> dict[str, Any]:
    """Transform API-Football fixture to MCP format.

    Args:
        fixture_data: Single fixture from API-Football response

    Returns:
        Transformed fixture dict matching existing MCP tool output
    """
    fixture = fixture_data.get("fixture", {})
    league = fixture_data.get("league", {})
    teams = fixture_data.get("teams", {})
    goals = fixture_data.get("goals", {})
    score = fixture_data.get("score", {})

    # Extract halftime score if available
    ht_score = score.get("halftime", {}) or {}

    return {
        "id": str(fixture.get("id")),
        "external_id": str(fixture.get("id")),
        "scheduled_at": fixture.get("date"),
        "status": fixture.get("status", {}).get("short", "NS"),
        "home_team": teams.get("home", {}).get("name"),
        "away_team": teams.get("away", {}).get("name"),
        "home_team_id": teams.get("home", {}).get("id"),
        "away_team_id": teams.get("away", {}).get("id"),
        "league": league.get("name"),
        "league_id": league.get("id"),
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "ht_home_score": ht_score.get("home"),
        "ht_away_score": ht_score.get("away"),
        "metadata": {
            "venue": fixture.get("venue", {}).get("name"),
            "referee": fixture.get("referee"),
            "league_country": league.get("country"),
            "league_logo": league.get("logo"),
            "league_round": league.get("round"),
            "home_team_logo": teams.get("home", {}).get("logo"),
            "away_team_logo": teams.get("away", {}).get("logo"),
        },
    }


def transform_fixtures(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform API-Football fixtures response to MCP format.

    Args:
        api_response: Full API-Football response

    Returns:
        List of transformed fixtures
    """
    fixtures = api_response.get("response", [])
    return [transform_fixture(f) for f in fixtures]


def transform_standings(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform API-Football standings response to MCP format.

    Args:
        api_response: Full API-Football standings response

    Returns:
        List of team standings
    """
    result = []
    response_list = api_response.get("response", [])

    if not response_list:
        return []

    # API returns nested structure: response[0].league.standings[0]
    league_data = response_list[0].get("league", {})
    standings_groups = league_data.get("standings", [[]])

    # Handle groups (e.g., Champions League groups)
    for group in standings_groups:
        for team in group:
            all_stats = team.get("all", {})
            home_stats = team.get("home", {})
            away_stats = team.get("away", {})

            result.append({
                "team_id": team.get("team", {}).get("id"),
                "team_name": team.get("team", {}).get("name"),
                "team_logo": team.get("team", {}).get("logo"),
                "rank": team.get("rank"),
                "points": team.get("points"),
                "played": all_stats.get("played", 0),
                "wins": all_stats.get("win", 0),
                "draws": all_stats.get("draw", 0),
                "losses": all_stats.get("lose", 0),
                "goals_for": all_stats.get("goals", {}).get("for", 0),
                "goals_against": all_stats.get("goals", {}).get("against", 0),
                "goal_difference": team.get("goalsDiff", 0),
                "form": team.get("form"),
                "description": team.get("description"),
                # Home stats
                "home_played": home_stats.get("played", 0),
                "home_wins": home_stats.get("win", 0),
                "home_draws": home_stats.get("draw", 0),
                "home_losses": home_stats.get("lose", 0),
                "home_goals_for": home_stats.get("goals", {}).get("for", 0),
                "home_goals_against": home_stats.get("goals", {}).get("against", 0),
                # Away stats
                "away_played": away_stats.get("played", 0),
                "away_wins": away_stats.get("win", 0),
                "away_draws": away_stats.get("draw", 0),
                "away_losses": away_stats.get("lose", 0),
                "away_goals_for": away_stats.get("goals", {}).get("for", 0),
                "away_goals_against": away_stats.get("goals", {}).get("against", 0),
            })

    return result


def transform_team_statistics(api_response: dict[str, Any]) -> dict[str, Any]:
    """Transform API-Football team statistics response to MCP format.

    Args:
        api_response: Full API-Football team statistics response

    Returns:
        Team statistics dict
    """
    response_list = api_response.get("response", {})

    if not response_list:
        return {}

    stats = response_list
    team = stats.get("team", {})
    league = stats.get("league", {})
    fixtures = stats.get("fixtures", {})
    goals = stats.get("goals", {})
    clean_sheet = stats.get("clean_sheet", {})
    failed_to_score = stats.get("failed_to_score", {})

    # Extract fixture splits
    played = fixtures.get("played", {})
    wins = fixtures.get("wins", {})
    draws = fixtures.get("draws", {})
    loses = fixtures.get("loses", {})

    # Extract goals splits
    goals_for = goals.get("for", {}).get("total", {})
    goals_against = goals.get("against", {}).get("total", {})

    return {
        "team_id": team.get("id"),
        "team_name": team.get("name"),
        "league_id": league.get("id"),
        "league_name": league.get("name"),
        "season": league.get("season"),
        "form": stats.get("form"),
        # Total stats
        "total_played": played.get("total", 0),
        "total_wins": wins.get("total", 0),
        "total_draws": draws.get("total", 0),
        "total_losses": loses.get("total", 0),
        "total_goals_for": goals_for.get("total", 0),
        "total_goals_against": goals_against.get("total", 0),
        # Home stats
        "home_played": played.get("home", 0),
        "wins_home": wins.get("home", 0),
        "draws_home": draws.get("home", 0),
        "losses_home": loses.get("home", 0),
        "goals_for_home": goals_for.get("home", 0),
        "goals_against_home": goals_against.get("home", 0),
        # Away stats
        "away_played": played.get("away", 0),
        "wins_away": wins.get("away", 0),
        "draws_away": draws.get("away", 0),
        "losses_away": loses.get("away", 0),
        "goals_for_away": goals_for.get("away", 0),
        "goals_against_away": goals_against.get("away", 0),
        # Clean sheets
        "clean_sheets_home": clean_sheet.get("home", 0),
        "clean_sheets_away": clean_sheet.get("away", 0),
        "clean_sheets_total": clean_sheet.get("total", 0),
        # Failed to score
        "failed_to_score_home": failed_to_score.get("home", 0),
        "failed_to_score_away": failed_to_score.get("away", 0),
        "failed_to_score_total": failed_to_score.get("total", 0),
        # Lineups and penalties info
        "biggest": stats.get("biggest", {}),
        "penalty": stats.get("penalty", {}),
    }


def transform_odds(api_response: dict[str, Any], fixture_id: int) -> dict[str, Any]:
    """Transform API-Football odds response to MCP format.

    Args:
        api_response: Full API-Football odds response
        fixture_id: Fixture ID for context

    Returns:
        Odds data dict
    """
    response_list = api_response.get("response", [])

    if not response_list:
        return {"fixture_id": fixture_id, "count": 0, "odds": []}

    # API returns multiple bookmakers
    bookmakers_data = response_list[0].get("bookmakers", [])
    odds_list = []

    for bookmaker in bookmakers_data:
        bookmaker_id = bookmaker.get("id")
        bookmaker_name = bookmaker.get("name")

        # Find 1X2 (Match Winner) market
        for bet in bookmaker.get("bets", []):
            if bet.get("id") == 1:  # Match Winner
                values = bet.get("values", [])
                home_odds = None
                draw_odds = None
                away_odds = None

                for val in values:
                    if val.get("value") == "Home":
                        home_odds = float(val.get("odd", 0))
                    elif val.get("value") == "Draw":
                        draw_odds = float(val.get("odd", 0))
                    elif val.get("value") == "Away":
                        away_odds = float(val.get("odd", 0))

                if home_odds and draw_odds and away_odds:
                    odds_list.append({
                        "bookmaker_id": bookmaker_id,
                        "bookmaker_name": bookmaker_name,
                        "market": "1X2",
                        "home_odds": home_odds,
                        "draw_odds": draw_odds,
                        "away_odds": away_odds,
                        "is_live": False,
                        "updated_at": datetime.now().isoformat(),
                    })
                break

    return {
        "fixture_id": fixture_id,
        "count": len(odds_list),
        "odds": odds_list,
    }


def transform_odds_for_market(
    api_response: dict[str, Any],
    fixture_id: int,
    bet_id: int,
    target_outcome: str,
    line: float | None = None,
) -> dict[str, Any]:
    """Transform API-Football odds response for a specific market and outcome.

    Extracts odds from all bookmakers for a specific bet type and outcome value.
    Returns the best odds available across all bookmakers.

    Args:
        api_response: Full API-Football odds response
        fixture_id: Fixture ID for context
        bet_id: API-Football bet type ID (1=Match Winner, 5=Over/Under, 8=BTTS, etc.)
        target_outcome: The outcome value to extract (e.g., "Home", "Over 2.5", "Yes")
        line: Optional goal line for Over/Under markets (e.g., 2.5)

    Returns:
        Dictionary with:
        - fixture_id: The fixture ID
        - bet_id: The bet type ID
        - outcome: The requested outcome
        - best_odds: Highest odds found across bookmakers
        - best_bookmaker: Name of bookmaker with best odds
        - all_odds: List of all bookmaker odds for this outcome

    Example:
        ```python
        # Get BTTS Yes odds
        result = transform_odds_for_market(
            api_response=response,
            fixture_id=1234567,
            bet_id=8,  # BTTS
            target_outcome="Yes"
        )
        # Returns:
        # {
        #   "fixture_id": 1234567,
        #   "bet_id": 8,
        #   "outcome": "Yes",
        #   "best_odds": 1.85,
        #   "best_bookmaker": "Bet365",
        #   "all_odds": [{"bookmaker": "Bet365", "odds": 1.85}, ...]
        # }
        ```
    """
    response_list = api_response.get("response", [])

    if not response_list:
        return {
            "fixture_id": fixture_id,
            "bet_id": bet_id,
            "outcome": target_outcome,
            "line": line,
            "best_odds": 0.0,
            "best_bookmaker": None,
            "all_odds": [],
        }

    bookmakers_data = response_list[0].get("bookmakers", [])

    best_odds = 0.0
    best_bookmaker: str | None = None
    all_odds: list[dict[str, Any]] = []

    for bookmaker in bookmakers_data:
        bookmaker_name = bookmaker.get("name")

        for bet in bookmaker.get("bets", []):
            if bet.get("id") != bet_id:
                continue

            # Found the right bet type, now find the outcome
            for value in bet.get("values", []):
                value_str = value.get("value", "")

                # For Over/Under markets, need to match both outcome and line
                # API returns values like "Over 2.5", "Under 2.5"
                matches_outcome = False

                if line is not None:
                    # Over/Under market - match outcome and line
                    # target_outcome could be "Over 2.5" or just "Over"
                    expected_value = f"{target_outcome.split()[0]} {line}" if " " not in target_outcome else target_outcome
                    matches_outcome = value_str == expected_value or value_str == target_outcome
                else:
                    # Non-line market - direct match
                    matches_outcome = value_str == target_outcome

                if matches_outcome:
                    odds = float(value.get("odd", 0))
                    if odds > 0:
                        all_odds.append({
                            "bookmaker": bookmaker_name,
                            "odds": odds,
                        })
                        if odds > best_odds:
                            best_odds = odds
                            best_bookmaker = bookmaker_name
                    break  # Found outcome in this bet

            break  # Found bet type in this bookmaker

    # Sort all_odds by odds descending (best first)
    all_odds.sort(key=lambda x: x["odds"], reverse=True)

    return {
        "fixture_id": fixture_id,
        "bet_id": bet_id,
        "outcome": target_outcome,
        "line": line,
        "best_odds": best_odds,
        "best_bookmaker": best_bookmaker,
        "all_odds": all_odds,
    }


def transform_h2h(api_response: dict[str, Any]) -> dict[str, Any]:
    """Transform API-Football H2H response to MCP format.

    Args:
        api_response: Full API-Football H2H response

    Returns:
        H2H data dict with stats and recent matches
    """
    fixtures = api_response.get("response", [])

    if not fixtures:
        return {"head_to_head": [], "summary": {}}

    # Calculate summary stats
    team1_id = None
    team2_id = None
    team1_wins = 0
    team2_wins = 0
    draws = 0
    team1_goals = 0
    team2_goals = 0

    matches = []

    for fixture_data in fixtures:
        fixture = fixture_data.get("fixture", {})
        teams = fixture_data.get("teams", {})
        goals = fixture_data.get("goals", {})

        home = teams.get("home", {})
        away = teams.get("away", {})
        home_goals = goals.get("home") or 0
        away_goals = goals.get("away") or 0

        # Set team IDs from first match
        if team1_id is None:
            team1_id = home.get("id")
            team2_id = away.get("id")

        # Determine winner
        home_id = home.get("id")
        if home_goals > away_goals:
            if home_id == team1_id:
                team1_wins += 1
            else:
                team2_wins += 1
        elif away_goals > home_goals:
            if home_id == team1_id:
                team2_wins += 1
            else:
                team1_wins += 1
        else:
            draws += 1

        # Track goals
        if home_id == team1_id:
            team1_goals += home_goals
            team2_goals += away_goals
        else:
            team1_goals += away_goals
            team2_goals += home_goals

        matches.append(transform_fixture(fixture_data))

    return {
        "head_to_head": matches,
        "summary": {
            "team_1_id": team1_id,
            "team_2_id": team2_id,
            "team_1_wins": team1_wins,
            "team_2_wins": team2_wins,
            "draws": draws,
            "total_matches": len(fixtures),
            "team_1_goals": team1_goals,
            "team_2_goals": team2_goals,
        },
    }


def calculate_form_from_fixtures(
    fixtures: list[dict[str, Any]],
    team_id: int,
) -> dict[str, Any]:
    """Calculate W/D/L form string from fixtures.

    Args:
        fixtures: List of transformed fixtures
        team_id: Team ID to calculate form for

    Returns:
        Form data dict with string and stats
    """
    form_str = ""
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for fixture in fixtures:
        home_id = fixture.get("home_team_id")
        home_goals = fixture.get("home_score") or 0
        away_goals = fixture.get("away_score") or 0

        is_home = home_id == team_id

        if is_home:
            team_goals = home_goals
            opp_goals = away_goals
        else:
            team_goals = away_goals
            opp_goals = home_goals

        goals_for += team_goals
        goals_against += opp_goals

        if team_goals > opp_goals:
            form_str += "W"
            wins += 1
        elif team_goals < opp_goals:
            form_str += "L"
            losses += 1
        else:
            form_str += "D"
            draws += 1

    total = wins + draws + losses
    points = wins * 3 + draws

    return {
        "form_string": form_str,
        "matches_analyzed": total,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": points,
        "points_per_match": round(points / total, 2) if total > 0 else 0,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
        "goals_per_match": round(goals_for / total, 2) if total > 0 else 0,
        "conceded_per_match": round(goals_against / total, 2) if total > 0 else 0,
    }
