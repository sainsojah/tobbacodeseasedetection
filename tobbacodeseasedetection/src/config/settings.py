"""
Application Configuration Settings
Handles environment variables and system constants
"""

import os
from dotenv import load_dotenv

# Load .env in development only
if os.path.exists(".env"):
    load_dotenv()


class Settings:
    # ==============================
    # WhatsApp Configuration
    # ==============================
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID: str = os.getenv("PHONE_NUMBER_ID")
    VERIFY_TOKEN: str = os.getenv("VERIFY_TOKEN")

    # ==============================
    # Firebase Configuration
    # ==============================
    FIREBASE_CONFIG: str = os.getenv("FIREBASE_CONFIG")

    # ==============================
    # Admin Configuration
    # ==============================
    ADMIN_PHONE_NUMBER: str = os.getenv("ADMIN_PHONE_NUMBER")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD")

    # ==============================
    # AI / Model Configuration
    # ==============================
    MODEL_PATH: str = "best.pt"

    CONFIDENCE_LOW: float = 0.45
    CONFIDENCE_MODERATE: float = 0.60

    # ==============================
    # System Settings
    # ==============================
    APP_NAME: str = "Tobacco AI Assistant"
    DEFAULT_LANGUAGE: str = "en"


def validate_config():
    """
    Ensures required environment variables are set.
    Raises error if missing.
    """

    required = {
        "WHATSAPP_TOKEN": Settings.WHATSAPP_TOKEN,
        "PHONE_NUMBER_ID": Settings.PHONE_NUMBER_ID,
        "VERIFY_TOKEN": Settings.VERIFY_TOKEN,
        "FIREBASE_CONFIG": Settings.FIREBASE_CONFIG,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return True