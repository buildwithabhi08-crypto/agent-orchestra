"""Data analysis and reporting tools."""

from __future__ import annotations

import json

from langchain_core.tools import tool


@tool
def analyze_competitors(competitors_data: str) -> str:
    """Analyze competitor data and generate a structured comparison.

    Args:
        competitors_data: JSON string with competitor info. Each entry should have
            'name', 'features', 'pricing', 'strengths', 'weaknesses'.
    """
    try:
        competitors = json.loads(competitors_data)
        if not isinstance(competitors, list):
            return "Error: Input must be a JSON array of competitor objects."

        report = "# Competitive Analysis Report\n\n"

        for comp in competitors:
            name = comp.get("name", "Unknown")
            report += f"## {name}\n"
            report += f"- **Features**: {comp.get('features', 'N/A')}\n"
            report += f"- **Pricing**: {comp.get('pricing', 'N/A')}\n"
            report += f"- **Strengths**: {comp.get('strengths', 'N/A')}\n"
            report += f"- **Weaknesses**: {comp.get('weaknesses', 'N/A')}\n\n"

        report += "## Summary\n"
        report += f"Total competitors analyzed: {len(competitors)}\n"

        return report
    except json.JSONDecodeError:
        return "Error: Invalid JSON format. Please provide valid JSON data."
    except Exception as e:
        return f"Analysis error: {str(e)}"


@tool
def generate_swot_analysis(
    strengths: str, weaknesses: str, opportunities: str, threats: str
) -> str:
    """Generate a formatted SWOT analysis report.

    Args:
        strengths: Comma-separated list of strengths.
        weaknesses: Comma-separated list of weaknesses.
        opportunities: Comma-separated list of opportunities.
        threats: Comma-separated list of threats.
    """
    report = "# SWOT Analysis\n\n"

    sections = [
        ("Strengths", strengths),
        ("Weaknesses", weaknesses),
        ("Opportunities", opportunities),
        ("Threats", threats),
    ]

    for title, items in sections:
        report += f"## {title}\n"
        for item in items.split(","):
            item = item.strip()
            if item:
                report += f"- {item}\n"
        report += "\n"

    return report


@tool
def create_validation_scorecard(
    idea: str,
    market_size: str = "unknown",
    competition_level: str = "unknown",
    demand_signals: str = "unknown",
    technical_feasibility: str = "unknown",
    monetization_potential: str = "unknown",
) -> str:
    """Create a validation scorecard for a product idea.

    Args:
        idea: The product idea to validate.
        market_size: Estimated market size (small/medium/large/unknown).
        competition_level: Level of competition (low/medium/high/unknown).
        demand_signals: Evidence of demand (strong/moderate/weak/unknown).
        technical_feasibility: How feasible to build (easy/moderate/hard/unknown).
        monetization_potential: Revenue potential (low/medium/high/unknown).
    """
    score_map = {
        "small": 2, "medium": 5, "large": 8,
        "low": 8, "moderate": 5, "high": 2,
        "strong": 8, "weak": 2,
        "easy": 8, "hard": 3,
        "unknown": 5,
    }

    criteria = {
        "Market Size": market_size,
        "Competition Level": competition_level,
        "Demand Signals": demand_signals,
        "Technical Feasibility": technical_feasibility,
        "Monetization Potential": monetization_potential,
    }

    report = f"# Validation Scorecard: {idea}\n\n"
    total_score = 0

    for criterion, value in criteria.items():
        score = score_map.get(value.lower(), 5)
        total_score += score
        bar = "█" * score + "░" * (10 - score)
        report += f"**{criterion}**: {value} [{bar}] {score}/10\n"

    avg_score = total_score / len(criteria)
    report += f"\n**Overall Score: {avg_score:.1f}/10**\n\n"

    if avg_score >= 7:
        report += "✅ **Verdict: STRONG - Worth building!**\n"
    elif avg_score >= 5:
        report += "⚠️ **Verdict: MODERATE - Needs more validation.**\n"
    else:
        report += "❌ **Verdict: WEAK - Consider pivoting.**\n"

    return report
