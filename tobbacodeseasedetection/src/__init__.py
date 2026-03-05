"""
Tobacco AI Assistant - Main Source Package
This file marks the src directory as a Python package
"""

__version__ = "1.0.0"
__author__ = "Tobacco AI Assistant"

# Import key components for easier access
from .core import (
    ConfidenceLevel,
    UserState,
    MenuOption,
    StateMachine,
    Router,
    ResponseBuilder
)

from .config import Settings, validate_config, get_db
from .content import (
    TREATMENTS,
    DISEASE_CLARIFICATIONS,
    PLANTING_GUIDE,
    FERTILIZER_GUIDE,
    HARVESTING_GUIDE,
    MARKETING_GUIDE,
    GROWTH_JOURNEY,
    DAILY_TIPS,
    FUN_FACTS
)

# Define what gets imported with "from src import *"
__all__ = [
    # Version info
    "__version__",
    "__author__",
    
    # Core
    "ConfidenceLevel",
    "UserState",
    "MenuOption",
    "StateMachine",
    "Router",
    "ResponseBuilder",
    
    # Config
    "Settings",
    "validate_config",
    "get_db",
    
    # Content
    "TREATMENTS",
    "DISEASE_CLARIFICATIONS",
    "PLANTING_GUIDE",
    "FERTILIZER_GUIDE",
    "HARVESTING_GUIDE",
    "MARKETING_GUIDE",
    "GROWTH_JOURNEY",
    "DAILY_TIPS",
    "FUN_FACTS"
]

# Print confirmation (optional)
print("✅ Tobacco AI Assistant src package loaded")