"""
Feedback service - handles user feedback and comments
"""
from typing import Dict, Any, Optional
from core.constants import UserState
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.database.user_repository import UserRepository
from infrastructure.admin.feedback_service import FeedbackService as AdminFeedbackService

class FeedbackService:
    """Handle user feedback and comments"""
    
    def __init__(self, 
                 user_repo: UserRepository,
                 whatsapp: WhatsAppClient):
        
        self.user_repo = user_repo
        self.whatsapp = whatsapp
        self.admin_feedback = AdminFeedbackService()
    
    def initiate_feedback(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """
        Start feedback collection flow
        Args:
            phone_number: User's phone number
            user: User data dict
        Returns:
            Response dict
        """
        # Update user state
        self.user_repo.update_user_state(phone_number, UserState.AWAITING_COMMENT.value)
        
        # Send prompt
        message = (
            f"📝 *Share Your Feedback*\n\n"
            f"Your input helps us improve! Please tell us:\n\n"
            f"• What you like about the service\n"
            f"• Any issues you've encountered\n"
            f"• Features you'd like to see\n"
            f"• General suggestions\n\n"
            f"Type your message below (or type *cancel* to go back):"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "awaiting_feedback"}
    
    def handle_comment(self, phone_number: str, comment: str, user: Dict) -> Dict[str, Any]:
        """
        Process user comment/feedback
        Args:
            phone_number: User's phone number
            comment: User's comment text
            user: User data dict
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Check for cancellation
        if comment.lower() in ['cancel', 'back', 'menu']:
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
            self.whatsapp.send_text(
                phone_number,
                "Feedback cancelled. Type *menu* to return to main menu."
            )
            return {"status": "ok", "action": "cancelled"}
        
        # Validate comment length
        if len(comment) < 5:
            self.whatsapp.send_text(
                phone_number,
                "❌ Please provide more detail (at least 5 characters).\n\nType your feedback or *cancel* to go back."
            )
            return {"status": "ok", "action": "retry"}
        
        if len(comment) > 1000:
            self.whatsapp.send_text(
                phone_number,
                "❌ Feedback is too long (max 1000 characters). Please shorten your message."
            )
            return {"status": "ok", "action": "retry"}
        
        # Process feedback
        success = self.admin_feedback.process_feedback(
            phone_number=phone_number,
            user_name=user_name,
            feedback_text=comment,
            feedback_type="user_comment"
        )
        
        # Reset user state
        self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
        
        if success:
            # Send confirmation
            confirmation = (
                f"✅ *Thank You, {user_name}!*\n\n"
                f"Your feedback has been sent to our team. We appreciate your input "
                f"and will use it to improve Tobacco AI Assistant.\n\n"
                f"Reply *menu* to continue."
            )
        else:
            # Fallback confirmation even if admin notification failed
            confirmation = (
                f"✅ *Thank You, {user_name}!*\n\n"
                f"Your feedback has been recorded. We appreciate your input.\n\n"
                f"Reply *menu* to continue."
            )
        
        self.whatsapp.send_text(phone_number, confirmation)
        
        return {"status": "ok", "action": "feedback_received"}
    
    def send_quick_feedback_options(self, phone_number: str) -> Dict[str, Any]:
        """
        Send quick feedback options (buttons)
        Args:
            phone_number: User's phone number
        Returns:
            Response dict
        """
        # This would use interactive buttons in production
        message = (
            f"📝 *Quick Feedback*\n\n"
            f"How would you rate your experience?\n\n"
            f"1️⃣ 👍 Excellent\n"
            f"2️⃣ 👌 Good\n"
            f"3️⃣ 🤔 Average\n"
            f"4️⃣ 👎 Poor\n"
            f"5️⃣ 💬 Write Comment\n\n"
            f"Reply with the number, or type *menu* to go back."
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "quick_feedback"}
    
    def handle_rating(self, phone_number: str, rating: str, user: Dict) -> Dict[str, Any]:
        """
        Handle numeric rating from user
        Args:
            phone_number: User's phone number
            rating: Rating number (1-5)
            user: User data dict
        Returns:
            Response dict
        """
        rating_map = {
            "1": "Excellent",
            "2": "Good", 
            "3": "Average",
            "4": "Poor",
            "5": "Very Poor"
        }
        
        rating_text = rating_map.get(rating, "Unknown")
        
        # Send to admin as feedback
        self.admin_feedback.process_feedback(
            phone_number=phone_number,
            user_name=user.get("name", "Farmer"),
            feedback_text=f"Rating: {rating} - {rating_text}",
            feedback_type="rating"
        )
        
        # Thank user
        if rating in ["1", "2"]:
            thanks = "🌟 We're glad you're enjoying the service!"
        elif rating == "3":
            thanks = "📝 Thanks for your feedback. We're working to improve!"
        else:
            thanks = "🔧 We're sorry to hear that. We'll work on improvements!"
        
        message = (
            f"✅ *Thank You!*\n\n"
            f"{thanks}\n\n"
            f"Would you like to add a comment? (Reply *yes* or *no*)"
        )
        
        self.whatsapp.send_text(phone_number, message)
        
        # Set state for possible follow-up
        if rating in ["3", "4", "5"]:
            self.user_repo.update_user_state(phone_number, UserState.AWAITING_COMMENT.value)
        
        return {"status": "ok", "action": "rating_received"}