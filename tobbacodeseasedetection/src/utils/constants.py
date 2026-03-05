"""
Constant messages and strings
"""
# Error messages
ERROR_MESSAGES = {
    "general": "❌ An error occurred. Please try again.",
    "network": "🌐 Network error. Please check your connection.",
    "timeout": "⏰ Request timed out. Please try again.",
    "invalid_input": "❌ Invalid input. Please check and try again.",
    "not_found": "🔍 Resource not found.",
    "unauthorized": "🔒 You are not authorized to perform this action.",
    "rate_limit": "⏳ Too many requests. Please wait a moment.",
    "image_invalid": "📸 Invalid image. Please send a clear photo.",
    "image_too_large": "📸 Image too large. Maximum size is 16MB.",
    "image_too_small": "📸 Image too small. Please take a closer photo.",
    "image_blurry": "📸 Image is blurry. Please hold the camera steady.",
    "no_detection": "🔍 No disease detected. Please try another photo.",
    "low_confidence": "⚠️ Low confidence detection. Please try with a clearer image.",
    "session_expired": "⏰ Session expired. Please start again.",
    "maintenance": "🔧 System under maintenance. Please try again later."
}

# Success messages
SUCCESS_MESSAGES = {
    "general": "✅ Operation completed successfully.",
    "detection": "📊 Disease detection completed.",
    "feedback": "📝 Thank you for your feedback!",
    "expert_request": "👨‍🌾 Expert request submitted. You will be contacted soon.",
    "history": "📋 Scan history retrieved.",
    "registration": "✅ Registration successful!",
    "menu": "📋 Menu loaded."
}

# Help text
HELP_TEXT = """
*Tobacco AI Assistant Help*

*Commands:*
• Send a *photo* - Detect diseases
• *menu* - Show main menu
• *history* - View scan history
• *expert* - Talk to an expert
• *feedback* - Send feedback
• *fact* - Random farming fact
• *tip* - Daily farming tip
• *help* - Show this message

*Tips for best results:*
• Use good lighting
• Take clear, focused photos
• Show affected areas clearly
• Include multiple leaves if possible

Need more help? Type *expert* to talk to a human.
"""

# About text
ABOUT_TEXT = """
🌿 *Tobacco AI Assistant*

Version: 1.0.0
Powered by: YOLOv8 AI Model

*Features:*
• Disease detection from photos
• Educational farming guides
• Expert connection
• Scan history tracking
• Multi-language support (coming soon)

*Developed for:* Tobacco farmers of Zimbabwe
*Contact:* support@tobaccoai.co.zw

Type *menu* to get started!
"""

# Feature list
FEATURES = [
    "🔍 Disease Detection - Upload leaf photos for instant diagnosis",
    "📚 Educational Guides - Planting, fertilizer, harvesting tips",
    "👨‍🌾 Expert Connection - Talk to real agronomists",
    "📋 Scan History - Track your past diagnoses",
    "🎲 Fun Facts - Daily farming facts and tips",
    "🌍 Multi-language - English, Shona, Ndebele (coming soon)"
]

# Quick replies
QUICK_REPLIES = {
    "yes": "Yes",
    "no": "No",
    "menu": "Main Menu",
    "help": "Help",
    "cancel": "Cancel",
    "skip": "Skip"
}

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    "high": 70,
    "medium": 45,
    "low": 0
}

# Response times
RESPONSE_TIMES = {
    "ai_detection": "2-5 seconds",
    "expert_response": "2-4 hours",
    "feedback_response": "24 hours"
}

# Limits
LIMITS = {
    "max_message_length": 1000,
    "max_feedback_length": 1000,
    "max_name_length": 50,
    "max_history_display": 10,
    "max_image_size_mb": 16,
    "min_image_size_kb": 10
}