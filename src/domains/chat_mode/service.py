"""
Chat mode service - future AI chat feature
Placeholder for now
"""
from typing import Dict, Any
from infrastructure.whatsapp.client import WhatsAppClient

class ChatModeService:
    """Future AI chat mode - placeholder"""
    
    def __init__(self, whatsapp: WhatsAppClient):
        self.whatsapp = whatsapp
    
    def enter_chat_mode(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """
        Enter AI chat mode (future feature)
        Args:
            phone_number: User's phone number
            user: User data dict
        Returns:
            Response dict
        """
        message = (
            f"🤖 *AI Chat Mode*\n\n"
            f"This feature is coming soon! You'll be able to chat with an AI "
            f"assistant about all things tobacco farming.\n\n"
            f"For now, you can:\n"
            f"• Send photos for disease detection\n"
            f"• Type *menu* for educational content\n"
            f"• Type *expert* to talk to a human expert\n\n"
            f"Stay tuned for updates! 🚀"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "chat_mode_unavailable"}
    
    def handle_chat_message(self, phone_number: str, message: str, user: Dict) -> Dict[str, Any]:
        """
        Handle message in chat mode (future)
        Args:
            phone_number: User's phone number
            message: User's message
            user: User data dict
        Returns:
            Response dict
        """
       # Placeholder - will be implemented with actual AI later
        response = (
            f"🤖 *AI Assistant*\n\n"
            f"I understand you're asking about '{message[:50]}...'\n\n"
            f"This feature is under development. Please check back soon!\n\n"
            f"Type *menu* for other options."
        )
        
        self.whatsapp.send_text(phone_number, response)
        return {"status": "ok"}