"""
Registration service - handles new user onboarding
"""
from typing import Dict, Any, Optional
from core.constants import UserState
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.database.user_repository import UserRepository

class RegistrationService:
    """Handle user registration flow"""
    
    def __init__(self, user_repo: UserRepository, whatsapp: WhatsAppClient):
        self.user_repo = user_repo
        self.whatsapp = whatsapp
    
    def handle_new_user(self, phone_number: str) -> Dict[str, Any]:
        """
        Handle first interaction with new user
        Args:
            phone_number: User's phone number
        Returns:
            Response dict
        """
        # Create user in awaiting_name state
        self.user_repo.create_user(phone_number, {
            "state": UserState.AWAITING_NAME.value,
            "phone": phone_number,
            "language": "en",
            "total_scans": 0
        })
        
        # Send welcome message
        welcome_msg = (
            "🌿 *Welcome to Tobacco AI Assistant!*\n\n"
            "I'm your intelligent farming companion, designed to help you:\n"
            "✅ Detect diseases from leaf photos\n"
            "✅ Learn about tobacco farming practices\n"
            "✅ Get expert advice when needed\n"
            "✅ Track your scan history\n\n"
            "To get started, please enter your *preferred name*:"
        )
        
        self.whatsapp.send_text(phone_number, welcome_msg)
        
        return {"status": "ok", "action": "awaiting_name"}
    
    def handle_name_input(self, phone_number: str, name: str) -> Dict[str, Any]:
        """
        Process name input from user
        Args:
            phone_number: User's phone number
            name: User's provided name
        Returns:
            Response dict
        """
        # Validate name
        if not name or len(name) < 2 or len(name) > 50:
            self.whatsapp.send_text(
                phone_number,
                "❌ Please enter a valid name (2-50 characters)."
            )
            return {"status": "ok", "action": "retry_name"}
        
        # Clean name
        clean_name = name.strip().title()
        
        # Update user
        self.user_repo.update_user(phone_number, {
            "name": clean_name,
            "state": UserState.ACTIVE.value
        })
        
        # Send welcome message
        welcome_msg = (
            f"✅ *Welcome, {clean_name}!*\n\n"
            f"Your profile has been created successfully.\n\n"
            f"🌿 *What can I do for you today?*\n\n"
            f"• Send a *photo* of a tobacco leaf for disease detection\n"
            f"• Type *menu* to see all available options\n"
            f"• Type *help* for assistance\n\n"
            f"Let's grow together! 🚜"
        )
        
        self.whatsapp.send_text(phone_number, welcome_msg)
        
        return {"status": "ok", "action": "registered"}
    
    def update_language(self, phone_number: str, language: str) -> bool:
        """
        Update user's preferred language
        Args:
            phone_number: User's phone number
            language: Language code (en, sn, nd)
        Returns:
            bool: Success status
        """
        if language not in ["en", "sn", "nd"]:
            return False
        
        return self.user_repo.set_language(phone_number, language)
    
    def get_user_profile(self, phone_number: str) -> Optional[Dict]:
        """
        Get user profile information
        Args:
            phone_number: User's phone number
        Returns:
            User profile dict or None
        """
        user = self.user_repo.get_user(phone_number)
        if not user:
            return None
        
        return {
            "name": user.get("name"),
            "phone": phone_number,
            "language": user.get("language", "en"),
            "registered_since": user.get("created_at"),
            "total_scans": user.get("total_scans", 0),
            "state": user.get("state")
        }