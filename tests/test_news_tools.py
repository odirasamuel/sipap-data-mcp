"""Tests for news intelligence tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sipap_data_mcp.tools.news import analyze_news_impact


@pytest.mark.asyncio
async def test_analyze_news_impact_with_critical_injury():
    """Test news analysis with critical injury news."""
    # Mock Bedrock response
    mock_bedrock_response = {
        "prediction": {
            "market": "1X2",
            "outcome": "home",
            "probability": 0.55,
            "confidence": 75,
            "impact_score": -10.0
        },
        "reasoning": "Arsenal's star striker (20 goals) ruled out with hamstring injury, reducing home win probability by ~10%.",
        "evidence": [
            "BBC Sport (2026-08-04): Arsenal striker ruled out for 3 weeks",
            "Arsenal.com (2026-08-04): Manager confirms striker absence"
        ],
        "news_items": [
            {
                "category": "injury",
                "severity": "critical",
                "impact": -10.0,
                "description": "Arsenal's top scorer (20 goals) out with hamstring injury (3 weeks)"
            }
        ]
    }

    with patch("sipap_data_mcp.tools.news.analyze_news_impact.invoke_bedrock_agent", new_callable=AsyncMock) as mock_bedrock:
        mock_bedrock.return_value = mock_bedrock_response

        result = await analyze_news_impact(
            match_id="arsenal_vs_chelsea_20260810",
            home_team="Arsenal",
            away_team="Chelsea",
            match_date="2026-08-10",
            base_probability=0.65
        )

        # Verify structure
        assert result["tool"] == "analyze_news_impact"
        assert "data" in result
        assert "metadata" in result

        # Verify prediction data
        assert result["data"]["prediction"]["probability"] == 0.55
        assert result["data"]["prediction"]["impact_score"] == -10.0
        assert result["data"]["prediction"]["confidence"] == 75

        # Verify news items
        assert len(result["data"]["news_items"]) == 1
        assert result["data"]["news_items"][0]["category"] == "injury"
        assert result["data"]["news_items"][0]["severity"] == "critical"

        # Verify evidence
        assert len(result["data"]["evidence"]) >= 1
        assert "BBC Sport" in result["data"]["evidence"][0]


@pytest.mark.asyncio
async def test_analyze_news_impact_no_significant_news():
    """Test news analysis when no significant news found."""
    mock_bedrock_response = {
        "prediction": {
            "market": "1X2",
            "outcome": "home",
            "probability": 0.65,
            "confidence": 80,
            "impact_score": 0.0
        },
        "reasoning": "No significant news affecting this match. Both teams have full squads available.",
        "evidence": [
            "BBC Sport (2026-08-09): No injury news",
            "Chelsea.com (2026-08-09): Full squad available"
        ],
        "news_items": []
    }

    with patch("sipap_data_mcp.tools.news.analyze_news_impact.invoke_bedrock_agent", new_callable=AsyncMock) as mock_bedrock:
        mock_bedrock.return_value = mock_bedrock_response

        result = await analyze_news_impact(
            match_id="liverpool_vs_everton_20260815",
            home_team="Liverpool",
            away_team="Everton",
            match_date="2026-08-15",
            base_probability=0.65
        )

        # Verify no impact
        assert result["data"]["prediction"]["impact_score"] == 0.0
        assert len(result["data"]["news_items"]) == 0

        # Probability unchanged
        assert result["data"]["prediction"]["probability"] == 0.65


@pytest.mark.asyncio
async def test_analyze_news_impact_multiple_news_items():
    """Test news analysis with multiple news items."""
    mock_bedrock_response = {
        "prediction": {
            "market": "1X2",
            "outcome": "home",
            "probability": 0.59,
            "confidence": 72,
            "impact_score": -6.0
        },
        "reasoning": "Man City missing two key players (-11% total), Brighton new signing (+5% morale).",
        "evidence": [
            "BBC Sport: De Bruyne out 4 weeks",
            "Man City Official: Rodri unavailable",
            "Brighton.com: New striker signed"
        ],
        "news_items": [
            {
                "category": "injury",
                "severity": "critical",
                "impact": -8.0,
                "description": "Kevin De Bruyne out 4 weeks (ankle) - star playmaker"
            },
            {
                "category": "injury",
                "severity": "major",
                "impact": -5.0,
                "description": "Rodri out - defensive midfielder"
            },
            {
                "category": "transfer",
                "severity": "minor",
                "impact": 2.0,
                "description": "Brighton new striker signed - morale boost"
            }
        ]
    }

    with patch("sipap_data_mcp.tools.news.analyze_news_impact.invoke_bedrock_agent", new_callable=AsyncMock) as mock_bedrock:
        mock_bedrock.return_value = mock_bedrock_response

        result = await analyze_news_impact(
            match_id="man_city_vs_brighton_20260815",
            home_team="Manchester City",
            away_team="Brighton",
            match_date="2026-08-15",
            base_probability=0.65
        )

        # Verify multiple news items
        assert len(result["data"]["news_items"]) == 3

        # Verify categories
        categories = [item["category"] for item in result["data"]["news_items"]]
        assert "injury" in categories
        assert "transfer" in categories

        # Verify net impact
        assert result["data"]["prediction"]["impact_score"] == -6.0


@pytest.mark.asyncio
async def test_analyze_news_impact_bedrock_error():
    """Test error handling when Bedrock fails."""
    with patch("sipap_data_mcp.tools.news.analyze_news_impact.invoke_bedrock_agent", new_callable=AsyncMock) as mock_bedrock:
        mock_bedrock.side_effect = Exception("Bedrock API error")

        result = await analyze_news_impact(
            match_id="test_match",
            home_team="Team A",
            away_team="Team B",
            match_date="2026-08-10",
            base_probability=0.60
        )

        # Verify error response
        assert result["tool"] == "analyze_news_impact"
        assert "error" in result["data"]
        assert "Bedrock" in result["data"]["error"]

        # Should return baseline probability unchanged
        assert result["data"]["prediction"]["probability"] == 0.60
        assert result["data"]["prediction"]["impact_score"] == 0.0
        assert len(result["data"]["news_items"]) == 0
