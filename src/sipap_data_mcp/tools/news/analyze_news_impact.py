"""News impact analysis tool - invokes Bedrock News Intelligence Agent."""

import json
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]


async def analyze_news_impact(
    match_id: str,
    home_team: str,
    away_team: str,
    match_date: str,
    base_probability: float
) -> dict[str, Any]:
    """
    Analyze news impact on match prediction using Bedrock News Intelligence Agent.

    Invokes the News Agent (AWS Bedrock) which:
    1. Searches news sources (BBC Sport, Sky Sports, ESPN, official club sites)
    2. Identifies injuries, suspensions, manager issues, team morale factors
    3. Quantifies impact on probability (-20% to +15% range)
    4. Returns structured news_items with evidence

    Args:
        match_id: Match identifier (e.g., "arsenal_vs_chelsea_20260810")
        home_team: Home team name (e.g., "Arsenal")
        away_team: Away team name (e.g., "Chelsea")
        match_date: Match date in ISO 8601 format (e.g., "2026-08-10")
        base_probability: Baseline probability from Statistical+Form ensemble (0.0-1.0)

    Returns:
        {
            "tool": "analyze_news_impact",
            "data": {
                "prediction": {
                    "market": "1X2",
                    "outcome": "home",
                    "probability": 0.55,  # Adjusted probability
                    "confidence": 75,
                    "impact_score": -10.0  # Percentage point adjustment
                },
                "reasoning": "Arsenal's star striker out with injury (-10%)...",
                "evidence": [
                    "BBC Sport (2026-08-09): Arsenal striker ruled out",
                    "Sky Sports (2026-08-09): Manager confirms absence"
                ],
                "news_items": [
                    {
                        "category": "injury|suspension|manager|morale|transfer",
                        "severity": "critical|major|minor",
                        "impact": -10.0,  # Probability adjustment
                        "description": "Star player out 3 weeks..."
                    }
                ],
                "error": "Error message if Bedrock fails"  # Optional
            },
            "metadata": {
                "match_id": str,
                "match_date": str,
                "base_probability": float,
                "agent_used": "bedrock-news-intelligence"
            }
        }

    Example:
        >>> result = await analyze_news_impact(
        ...     match_id="arsenal_vs_chelsea_20260810",
        ...     home_team="Arsenal",
        ...     away_team="Chelsea",
        ...     match_date="2026-08-10",
        ...     base_probability=0.65
        ... )
        >>> print(result["data"]["prediction"]["impact_score"])
        -10.0
    """
    try:
        # Invoke Bedrock News Agent
        agent_response = await invoke_bedrock_agent(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            base_probability=base_probability
        )

        return {
            "tool": "analyze_news_impact",
            "data": {
                "prediction": agent_response["prediction"],
                "reasoning": agent_response["reasoning"],
                "evidence": agent_response["evidence"],
                "news_items": agent_response.get("news_items", [])
            },
            "metadata": {
                "match_id": match_id,
                "match_date": match_date,
                "base_probability": base_probability,
                "agent_used": "bedrock-news-intelligence"
            }
        }

    except Exception as e:
        # Return error response with baseline probability unchanged
        return _error_response(
            match_id=match_id,
            match_date=match_date,
            base_probability=base_probability,
            error=f"Bedrock News Agent error: {str(e)}"
        )


async def invoke_bedrock_agent(
    match_id: str,
    home_team: str,
    away_team: str,
    match_date: str,
    base_probability: float
) -> dict[str, Any]:
    """
    Invoke AWS Bedrock News Intelligence Agent.

    Args:
        match_id: Match identifier
        home_team: Home team name
        away_team: Away team name
        match_date: Match date (ISO 8601)
        base_probability: Baseline probability (0.0-1.0)

    Returns:
        Agent's structured response with prediction, reasoning, evidence, news_items

    Raises:
        ClientError: If Bedrock API call fails
        Exception: If agent response parsing fails
    """
    # Create Bedrock Agent Runtime client
    client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

    # Construct input prompt
    input_text = f"""Analyze news impact for this match:

Match: {home_team} vs {away_team}
Date: {match_date}
Match ID: {match_id}
Baseline Probability (Statistical + Form ensemble): {base_probability:.2%}

Search news sources (BBC Sport, Sky Sports, ESPN, official club sites) for:
1. Injuries (especially star players)
2. Suspensions (red cards, yellow card accumulation)
3. Manager issues (sacked, under pressure, new appointment)
4. Team morale (controversies, transfers, winning/losing streaks)

Return structured analysis with:
- impact_score: Probability adjustment in percentage points (-20 to +15)
- news_items: Array of news with category, severity, impact, description
- evidence: Array of news sources with dates
- reasoning: Clear explanation of impact
"""

    try:
        # Invoke agent
        # NOTE: This assumes the Bedrock agent is already created and deployed
        # Agent ID and Alias ID should come from environment variables in production
        response = client.invoke_agent(
            agentId='SIPAP_NEWS_AGENT_ID',  # Will be set via env var
            agentAliasId='TSTALIASID',
            sessionId=match_id,
            inputText=input_text
        )

        # Parse agent response
        # Bedrock returns streaming response, we need to collect chunks
        event_stream = response['completion']
        agent_output = ""

        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    agent_output += chunk['bytes'].decode('utf-8')

        # Parse JSON response from agent
        agent_data = json.loads(agent_output)

        return agent_data

    except ClientError as e:
        raise Exception(f"Bedrock API error: {e.response['Error']['Message']}") from e
    except (json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Failed to parse agent response: {str(e)}") from e


def _error_response(
    match_id: str,
    match_date: str,
    base_probability: float,
    error: str
) -> dict[str, Any]:
    """
    Return error response when Bedrock fails.

    Returns baseline probability unchanged with zero impact.
    """
    return {
        "tool": "analyze_news_impact",
        "data": {
            "prediction": {
                "market": "1X2",
                "outcome": "home",
                "probability": base_probability,
                "confidence": 0,
                "impact_score": 0.0
            },
            "reasoning": "News analysis unavailable due to error",
            "evidence": [],
            "news_items": [],
            "error": error
        },
        "metadata": {
            "match_id": match_id,
            "match_date": match_date,
            "base_probability": base_probability,
            "agent_used": "bedrock-news-intelligence"
        }
    }
