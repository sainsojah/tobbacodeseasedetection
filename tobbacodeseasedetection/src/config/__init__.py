"""
Configuration package initialization
Exports settings and firebase modules for easy imports
"""

from .settings import Settings, validate_config
from .firebase import initialize_firebase, get_db

# Define what gets imported with "from src.config import *"
__all__ = [
    "Settings",
    "validate_config",
    "initialize_firebase",
    "get_db"
]

# Optional: Create convenience aliases
config = Settings
firebase = {
    "initialize": initialize_firebase,
    "get_db": get_db
}

# Version info for the config module
__version__ = "1.0.0"
__author__ = "Tobacco AI Assistant"