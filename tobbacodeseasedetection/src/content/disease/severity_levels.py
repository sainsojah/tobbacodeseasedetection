"""
Severity level definitions and recommendations
"""
SEVERITY_LEVELS = {
    "Low": {
        "emoji": "🟢",
        "description": "Early stage or minor infection. Easy to control.",
        "timeline": "Act within 1 week",
        "action": "Remove affected leaves, monitor closely"
    },
    "Low to Moderate": {
        "emoji": "🟡",
        "description": "Developing infection. Needs attention.",
        "timeline": "Act within 3-5 days",
        "action": "Remove affected leaves, apply preventive treatments"
    },
    "Moderate": {
        "emoji": "🟠",
        "description": "Active infection. Treatment needed urgently.",
        "timeline": "Act within 24-48 hours",
        "action": "Apply appropriate treatments, remove severely affected plants"
    },
    "Moderate to High": {
        "emoji": "🔴",
        "description": "Severe infection. Immediate action required.",
        "timeline": "Act immediately",
        "action": "Apply strongest recommended treatments, consider removing affected plants"
    },
    "High": {
        "emoji": "⛔",
        "description": "Very severe. May require plant removal.",
        "timeline": "Act immediately",
        "action": "Remove and destroy infected plants, treat surrounding plants"
    },
    "None": {
        "emoji": "✅",
        "description": "No disease detected",
        "timeline": "No action needed",
        "action": "Continue monitoring"
    }
}