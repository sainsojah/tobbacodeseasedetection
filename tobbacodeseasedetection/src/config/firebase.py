"""
Firebase initialization and Firestore connection
"""

import json
import firebase_admin
from firebase_admin import credentials, firestore
from src.config.settings import Settings

_db_instance = None


def initialize_firebase():
    """
    Initializes Firebase app safely.
    Returns Firestore client instance.
    """

    global _db_instance

    if _db_instance:
        return _db_instance

    if not Settings.FIREBASE_CONFIG:
        raise ValueError("FIREBASE_CONFIG environment variable is missing")

    try:
        # Parse JSON credentials from environment
        cred_dict = json.loads(Settings.FIREBASE_CONFIG)

        # Initialize Firebase only once
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)

        _db_instance = firestore.client()
        return _db_instance

    except json.JSONDecodeError:
        raise ValueError("Invalid FIREBASE_CONFIG JSON format")

    except Exception as e:
        raise RuntimeError(f"Firebase initialization failed: {str(e)}")


def get_db():
    """
    Returns Firestore database instance.
    Initializes Firebase if not already initialized.
    """
    return initialize_firebase()