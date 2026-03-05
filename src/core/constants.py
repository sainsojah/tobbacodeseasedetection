"""
System-wide constants and enums
All magic strings, thresholds, and static config live here
"""

from enum import Enum

# ============================================================
# CONFIDENCE THRESHOLDS
# ============================================================

# Below this → reject result
CONFIDENCE_REJECT = 0.45

# Between REJECT and MODERATE → low confidence warning
CONFIDENCE_MODERATE = 0.60


# ============================================================
# USER STATES (State Machine)
# ============================================================

class UserState(str, Enum):
    # Registration
    AWAITING_NAME = "awaiting_name"

    # Normal flow
    ACTIVE = "active"
    WAITING_IMAGE = "waiting_image"
    ANALYZING = "analyzing"
    RESULT_SENT = "result_sent"

    # Interactive modes
    FEEDBACK_MODE = "feedback_mode"
    AWAITING_COMMENT = "awaiting_comment"
    AWAITING_EXPERT_QUERY = "awaiting_expert_query"
    AWAITING_CLARIFICATION = "awaiting_clarification"

    # Future expansion
    AWAITING_LOCATION = "awaiting_location"
    CHAT_MODE = "chat_mode"


# ============================================================
# MENU NAVIGATION
# ============================================================

class MenuOption(str, Enum):
    MAIN = "main"
    DISEASE_DETECTION = "disease_detection"
    DISEASE_EDUCATION = "disease_education"
    PLANT_EDUCATION = "plant_education"
    HISTORY = "history"
    FEEDBACK = "feedback"
    EXPERT = "expert"
    FUN_FACTS = "fun_facts"
    DAILY_TIP = "daily_tip"
    PREVIOUS = "previous"


NAVIGATION = {
    "main_menu": "0️⃣ Main Menu",
    "previous": "🔙 Previous",
    "back": "◀️ Back"
}


# ============================================================
# IMAGE VALIDATION
# ============================================================

MIN_IMAGE_SIZE = 10 * 1024          # 10 KB
MAX_IMAGE_SIZE = 16 * 1024 * 1024   # 16 MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


# ============================================================
# DISEASE CLASSES (MUST MATCH MODEL OUTPUT EXACTLY)
# ============================================================

DISEASE_CLASSES = [
    "Black Spot",
    "Black Shank",
    "Early Blight",
    "Late Blight",
    "Leaf Mold",
    "Leaf Spot",
    "Powdery Mildew",
    "Septoria Blight",
    "Tobacco Cillium Virus",
    "Tobacco Cillium TMDL",
    "Yellow Leaf Spot",
    "from Yellow Leaf Spot",
    "Healthy",
    "Spider Mites"
]


# ============================================================
# DISEASE CATEGORIES
# ============================================================

DISEASE_CATEGORIES = {
    "fungal": [
        "Black Spot",
        "Black Shank",
        "Early Blight",
        "Late Blight",
        "Leaf Mold",
        "Leaf Spot",
        "Powdery Mildew",
        "Septoria Blight"
    ],
    "viral": [
        "Tobacco Cillium Virus",
        "Tobacco Cillium TMDL"
    ],
    "other": [
        "Yellow Leaf Spot",
        "from Yellow Leaf Spot"
    ],
    "pest": [
        "Spider Mites"
    ],
    "healthy": [
        "Healthy"
    ]
}


# ============================================================
# SYSTEM MESSAGES
# ============================================================

SYSTEM_MESSAGES = {
    "welcome": "🌿 Welcome to Tobacco AI Assistant!",
    "error": "❌ An error occurred. Please try again.",
    "processing": "⏳ Processing your image...",
    "low_confidence": "⚠️ The result confidence is moderate. Please verify the image quality.",
    "rejected": "❌ The image confidence is too low. Please send a clearer image."
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def categorize_disease(disease_name: str) -> str:
    """
    Returns category of disease.
    """
    for category, diseases in DISEASE_CATEGORIES.items():
        if disease_name in diseases:
            return category
    return "unknown"


# ============================================================
# VALIDATION CHECK (Safety Guard)
# ============================================================

_all_categorized = sum(DISEASE_CATEGORIES.values(), [])
_uncategorized = set(DISEASE_CLASSES) - set(_all_categorized)

if _uncategorized:
    raise ValueError(f"Uncategorized diseases found: {_uncategorized}")