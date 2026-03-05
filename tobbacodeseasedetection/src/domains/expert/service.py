"""
Expert service - handles farmer-expert connections
"""
from typing import Dict, Any, Optional
from core.constants import UserState
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.database.user_repository import UserRepository
from infrastructure.admin.expert_forwarder import ExpertForwarder

class ExpertService:
    """Handle expert connection requests"""
    
    def __init__(self, 
                 user_repo: UserRepository,
                 whatsapp: WhatsAppClient):
        
        self.user_repo = user_repo
        self.whatsapp = whatsapp
        self.expert_forwarder = ExpertForwarder()
    
    def initiate_contact(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """
        Start expert contact flow
        Args:
            phone_number: User's phone number
            user: User data dict
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Update user state
        self.user_repo.update_user_state(phone_number, UserState.AWAITING_EXPERT_QUERY.value)
        
        # Send options
        message = (
            f"👨‍🌾 *Connect with an Expert*\n\n"
            f"{user_name}, our agricultural experts can help with:\n\n"
            f"• Disease identification and treatment\n"
            f"• Fertilizer recommendations\n"
            f"• Pest control advice\n"
            f"• General farming questions\n"
            f"• Market information\n\n"
            f"Please type your question below, and an expert will respond shortly.\n\n"
            f"(Type *skip* to just request a call, or *cancel* to go back)"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "awaiting_query"}
    
    def handle_query(self, phone_number: str, query: str, user: Dict) -> Dict[str, Any]:
        """
        Handle user's expert query
        Args:
            phone_number: User's phone number
            query: User's question
            user: User data dict
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Check for special commands
        if query.lower() in ['cancel', 'menu']:
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
            self.whatsapp.send_text(
                phone_number,
                "Expert request cancelled. Type *menu* for main menu."
            )
            return {"status": "ok", "action": "cancelled"}
        
        if query.lower() == 'skip':
            # Just request a call without question
            return self._request_callback(phone_number, user)
        
        # Validate query
        if len(query) < 10:
            self.whatsapp.send_text(
                phone_number,
                "❌ Please provide more detail about your question (at least 10 characters).\n\n"
                "Type your question or *cancel* to go back."
            )
            return {"status": "ok", "action": "retry"}
        
        # Submit expert request
        result = self.expert_forwarder.request_expert(
            phone_number=phone_number,
            user_name=user_name,
            query=query
        )
        
        if result.get("success"):
            # Confirmation already sent by forwarder
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
        else:
            # Fallback if forwarder fails
            self.whatsapp.send_text(
                phone_number,
                f"✅ *Request Received, {user_name}!*\n\n"
                f"Your question has been recorded. An expert will contact you soon.\n\n"
                f"Reply *menu* for main menu."
            )
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
        
        return {"status": "ok", "action": "expert_requested"}
    
    def _request_callback(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """Request a callback without specific question"""
        user_name = user.get("name", "Farmer")
        
        result = self.expert_forwarder.request_expert(
            phone_number=phone_number,
            user_name=user_name,
            query="Callback requested - no specific question"
        )
        
        message = (
            f"✅ *Callback Requested, {user_name}!*\n\n"
            f"An expert will call you shortly. Please keep your phone nearby.\n\n"
            f"Reply *menu* for main menu."
        )
        
        self.whatsapp.send_text(phone_number, message)
        self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
        
        return {"status": "ok", "action": "callback_requested"}
    
    def check_expert_status(self, phone_number: str) -> Dict[str, Any]:
        """
        Check status of user's expert requests
        Args:
            phone_number: User's phone number
        Returns:
            Dict with request status
        """
        requests = self.expert_forwarder.get_user_requests(phone_number)
        
        if not requests:
            message = (
                f"📋 *Expert Requests*\n\n"
                f"You have no pending expert requests.\n\n"
                f"Type *expert* to request assistance."
            )
        else:
            message = "📋 *Your Expert Requests*\n\n"
            
            for i, req in enumerate(requests[:5], 1):
                status = req.get('status', 'unknown')
                status_emoji = {
                    'pending': '⏳',
                    'assigned': '👨‍🌾',
                    'resolved': '✅'
                }.get(status, '📝')
                
                date = req.get('created_at')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%d %b')
                else:
                    date = 'Recently'
                
                message += f"{i}. {status_emoji} {status.title()} - {date}\n"
            
            message += "\nType *expert* for new request."
        
        message += "\n\n---\n0️⃣ Main Menu"
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok"}
    
    def get_expert_info(self, phone_number: str) -> Dict[str, Any]:
        """
        Get information about expert service
        Args:
            phone_number: User's phone number
        Returns:
            Response dict
        """
        message = (
            f"👨‍🌾 *Expert Service Information*\n\n"
            f"Our agricultural experts are available to help you with:\n\n"
            f"• Disease diagnosis confirmation\n"
            f"• Treatment recommendations\n"
            f"• Fertilizer calculations\n"
            f"• Pest identification\n"
            f"• Market price inquiries\n"
            f"• General farming advice\n\n"
            f"⏱️ *Response Time:* Usually within 2-4 hours\n"
            f"💰 *Cost:* Free for registered farmers\n"
            f"📱 *Contact:* Experts will reach you on WhatsApp\n\n"
            f"Type *expert* to start a request."
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok"}