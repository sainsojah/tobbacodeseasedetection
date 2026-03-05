"""
Main request router - directs messages to appropriate handlers
"""
import time
from ..config.firebase import get_db
from ..infrastructure.database.user_repository import UserRepository
from ..infrastructure.database.detection_repository import DetectionRepository
from ..infrastructure.whatsapp.client import WhatsAppClient
from ..infrastructure.ai.yolo_engine import YOLOEngine
from .state_machine import StateMachine, get_state_timeout
from .constants import UserState
from ..domains.registration.service import RegistrationService
from ..domains.detection.service import DetectionService
from ..domains.menu.service import MenuService
from ..domains.education.service import EducationService
from ..domains.history.service import HistoryService
from ..domains.feedback.service import FeedbackService
from ..domains.expert.service import ExpertService

class Router:
    """Routes incoming messages to appropriate domain services"""
    
    def __init__(self):
        # Initialize dependencies
        self.user_repo = UserRepository()
        self.detection_repo = DetectionRepository()
        self.whatsapp = WhatsAppClient()
        self.yolo = YOLOEngine()
        
        # Initialize services
        self.registration = RegistrationService(self.user_repo, self.whatsapp)
        self.detection = DetectionService(
            self.user_repo, 
            self.detection_repo, 
            self.whatsapp, 
            self.yolo
        )
        self.menu = MenuService(self.whatsapp)
        self.education = EducationService(self.whatsapp)
        self.history = HistoryService(self.detection_repo, self.whatsapp)
        self.feedback = FeedbackService(self.user_repo, self.whatsapp)
        self.expert = ExpertService(self.user_repo, self.whatsapp)
    
    def route(self, from_number, message_type, content):
        """
        Route message based on user state
        Returns: response dict
        """
        try:
            # Get or create user
            user = self.user_repo.get_user(from_number)
            
            # New user
            if not user:
                return self.registration.handle_new_user(from_number)
            
            # Update last interaction
            self.user_repo.update_last_interaction(from_number)
            
            # Check state timeout
            current_state = user.get("state", UserState.ACTIVE.value)
            last_interaction = user.get("last_interaction")
            
            if last_interaction:
                time_diff = time.time() - last_interaction.timestamp()
                timeout = get_state_timeout(current_state)
                
                if time_diff > timeout:
                    # Reset to active state
                    self.user_repo.update_user_state(from_number, UserState.ACTIVE.value)
                    current_state = UserState.ACTIVE.value
                    self.whatsapp.send_text(
                        from_number,
                        "⏰ Session expired. Returning to main menu.\n\nType *menu* to see options."
                    )
            
            # Route based on state and message type
            if current_state == UserState.AWAITING_NAME.value:
                return self.registration.handle_name_input(from_number, content)
            
            elif current_state == UserState.WAITING_IMAGE.value:
                if message_type == "image":
                    return self.detection.handle_image(from_number, content, user)
                else:
                    self.whatsapp.send_text(
                        from_number,
                        "📸 Please send a photo of the tobacco leaf for analysis."
                    )
                    return {"status": "ok"}
            
            elif current_state == UserState.AWAITING_COMMENT.value:
                return self.feedback.handle_comment(from_number, content, user)
            
            elif current_state == UserState.AWAITING_EXPERT_QUERY.value:
                return self.expert.handle_query(from_number, content, user)
            
            elif current_state == UserState.AWAITING_CLARIFICATION.value:
                return self.detection.handle_clarification(from_number, content, user)
            
            # Default: ACTIVE state - process commands
            if message_type == "text":
                return self._handle_text_command(from_number, content.lower().strip(), user)
            
            elif message_type == "image":
                # Direct image detection
                self.user_repo.update_user_state(from_number, UserState.WAITING_IMAGE.value)
                return self.detection.handle_image(from_number, content, user)
            
            return {"status": "ok"}
            
        except Exception as e:
            print(f"❌ Router error: {e}")
            self.whatsapp.send_text(
                from_number,
                "❌ System error. Please try again later."
            )
            return {"status": "error"}
    
    def _handle_text_command(self, from_number, text, user):
        """Handle text commands in active state"""
        
        # Menu commands
        if text in ["menu", "main menu", "start", "0"]:
            return self.menu.show_main_menu(from_number, user)
        
        # History
        elif text in ["history", "my scans", "7"]:
            return self.history.show_history(from_number, user)
        
        # Feedback
        elif text.startswith("comment "):
            self.user_repo.update_user_state(from_number, UserState.AWAITING_COMMENT.value)
            self.whatsapp.send_text(
                from_number,
                "📝 Please type your comment or feedback:"
            )
            return {"status": "ok"}
        
        elif text in ["feedback", "8"]:
            self.user_repo.update_user_state(from_number, UserState.AWAITING_COMMENT.value)
            self.whatsapp.send_text(
                from_number,
                "📝 Please type your comment or feedback:"
            )
            return {"status": "ok"}
        
        # Expert
        elif text in ["expert", "talk to expert", "9"]:
            self.user_repo.update_user_state(from_number, UserState.AWAITING_EXPERT_QUERY.value)
            return self.expert.initiate_contact(from_number, user)
        
        # Fun facts
        elif text in ["fun fact", "fact", "6"]:
            return self.education.send_fun_fact(from_number)
        
        # Daily tip
        elif text in ["tip", "daily tip", "5"]:
            return self.education.send_daily_tip(from_number)
        
        # Education sections (1-4)
        elif text == "1":
            return self.education.send_planting_guide(from_number)
        elif text == "2":
            return self.education.send_fertilizer_guide(from_number)
        elif text == "3":
            return self.education.send_harvesting_guide(from_number)
        elif text == "4":
            return self.education.send_marketing_guide(from_number)
        
        # Disease detection
        elif text in ["detect", "scan", "disease"]:
            self.user_repo.update_user_state(from_number, UserState.WAITING_IMAGE.value)
            self.whatsapp.send_text(
                from_number,
                "📸 *Disease Detection Mode*\n\nPlease send a clear photo of the tobacco leaf.\n\nTips:\n• Good lighting\n• Plain background\n• Close-up of affected area"
            )
            return {"status": "ok"}
        
        # Default
        else:
            self.whatsapp.send_text(
                from_number,
                "❓ Command not recognized.\n\nType *menu* to see available options."
            )
            return {"status": "ok"}