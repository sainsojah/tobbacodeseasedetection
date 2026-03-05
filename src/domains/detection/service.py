"""
Detection service - handles disease detection from images
"""
import time
from typing import Dict, Any, Optional
from core.constants import UserState
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.whatsapp.media import MediaHandler
from infrastructure.ai.yolo_engine import YOLOEngine
from infrastructure.ai.confidence import ConfidenceGrader
from infrastructure.ai.image_quality import ImageQualityChecker
from infrastructure.database.user_repository import UserRepository
from infrastructure.database.detection_repository import DetectionRepository
from content.disease.treatments import TREATMENTS
from content.disease.clarifications import DISEASE_CLARIFICATIONS
from content.tips.daily_tips import get_random_tip

class DetectionService:
    """Handle disease detection flow"""
    
    def __init__(self, 
                 user_repo: UserRepository,
                 detection_repo: DetectionRepository,
                 whatsapp: WhatsAppClient,
                 yolo: YOLOEngine):
        
        self.user_repo = user_repo
        self.detection_repo = detection_repo
        self.whatsapp = whatsapp
        self.yolo = yolo
        self.media_handler = MediaHandler()
        self.quality_checker = ImageQualityChecker()
        self.confidence_grader = ConfidenceGrader()
        
        # Store temporary detection data (in production, use Redis)
        self.pending_detections = {}
    
    def handle_image(self, phone_number: str, media_id: str, user: Dict) -> Dict[str, Any]:
        """
        Process incoming image for disease detection
        Args:
            phone_number: User's phone number
            media_id: WhatsApp media ID
            user: User data dict
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Send processing message
        self.whatsapp.send_text(
            phone_number,
            f"🔍 *Analyzing your leaf image, {user_name}...*\n\nPlease wait a moment."
        )
        
        try:
            # Download image
            image_bytes = self.media_handler.download_image(media_id)
            if not image_bytes:
                self.whatsapp.send_text(
                    phone_number,
                    "❌ Failed to download image. Please try again."
                )
                return {"status": "error"}
            
            # Check image quality
            is_valid, quality_msg, details = self.quality_checker.validate(image_bytes)
            if not is_valid:
                self.whatsapp.send_text(phone_number, quality_msg)
                return {"status": "ok", "action": "quality_rejected"}
            
            # Run YOLO inference
            start_time = time.time()
            predictions = self.yolo.predict(image_bytes)
            inference_time = time.time() - start_time
            
            if not predictions:
                # No disease detected
                self._handle_no_detection(phone_number, user_name)
                return {"status": "ok", "action": "no_detection"}
            
            # Get top prediction
            top_pred = predictions[0]
            disease = top_pred['class']
            confidence = top_pred['confidence'] * 100
            
            # Map class name if needed
            disease = self.yolo.map_class_name(disease)
            
            # Check confidence
            grade = self.confidence_grader.grade(top_pred['confidence'])
            
            # Log detection
            self.detection_repo.log_detection(
                phone_number=phone_number,
                user_name=user_name,
                disease=disease,
                confidence=confidence,
                metadata={
                    "inference_time_ms": inference_time * 1000,
                    "image_quality": details,
                    "all_predictions": predictions[:3]  # Store top 3
                }
            )
            
            # Increment user scan count
            self.user_repo.increment_scan_count(phone_number)
            
            # Handle based on confidence
            if grade["level"] == "REJECT":
                self._handle_low_confidence(phone_number, user_name)
                return {"status": "ok", "action": "low_confidence"}
            
            # Get treatment info
            treatment = TREATMENTS.get(disease, TREATMENTS["Healthy"])
            
            # Check if clarification needed
            if (grade["level"] == "MODERATE" and 
                disease in DISEASE_CLARIFICATIONS):
                
                # Store for clarification
                self.pending_detections[phone_number] = {
                    "disease": disease,
                    "confidence": confidence,
                    "treatment": treatment,
                    "predictions": predictions
                }
                
                # Send clarification question
                self._send_clarification_question(phone_number, disease)
                return {"status": "ok", "action": "awaiting_clarification"}
            
            # Send result
            self._send_detection_result(
                phone_number, user_name, disease, 
                confidence, treatment, grade
            )
            
            # Send random tip (30% chance)
            import random
            if random.random() < 0.3:
                tip = get_random_tip()
                self.whatsapp.send_text(
                    phone_number,
                    f"💡 *Daily Tip:* {tip}"
                )
            
            return {"status": "ok", "action": "result_sent"}
            
        except Exception as e:
            print(f"❌ Detection error: {e}")
            self.whatsapp.send_text(
                phone_number,
                "❌ An error occurred during analysis. Please try again."
            )
            return {"status": "error"}
    
    def _handle_no_detection(self, phone_number: str, user_name: str):
        """Handle case where no disease detected"""
        message = (
            f"🌿 *No Disease Detected, {user_name}*\n\n"
            f"I couldn't identify any disease in the image. This could be because:\n"
            f"• The leaf might be healthy\n"
            f"• The image might not show the affected area clearly\n"
            f"• The symptoms might be in early stages\n\n"
            f"📸 *Suggestions:*\n"
            f"• Take a closer photo of affected areas\n"
            f"• Ensure good lighting\n"
            f"• Include multiple leaves if possible\n\n"
            f"Would you like to try another photo? (Send image or type *menu*)"
        )
        self.whatsapp.send_text(phone_number, message)
    
    def _handle_low_confidence(self, phone_number: str, user_name: str):
        """Handle low confidence detection"""
        message = (
            f"⚠️ *Low Quality Image, {user_name}*\n\n"
            f"The image quality wasn't sufficient for reliable analysis.\n\n"
            f"📸 *For better results:*\n"
            f"• Use good lighting (natural light is best)\n"
            f"• Hold camera steady to avoid blur\n"
            f"• Get closer to the affected area\n"
            f"• Use a plain background\n\n"
            f"Please send another photo when ready."
        )
        self.whatsapp.send_text(phone_number, message)
    
    def _send_detection_result(self, phone_number: str, user_name: str,
                               disease: str, confidence: float,
                               treatment: Dict, grade: Dict):
        """Send formatted detection result"""
        
        # Build message based on disease
        if disease == "Healthy":
            message = (
                f"🌿 *Healthy Leaf Detected!*\n\n"
                f"👤 *Farmer:* {user_name}\n"
                f"{grade['emoji']} *Confidence:* {confidence:.1f}%\n\n"
                f"🎉 Great news! Your tobacco leaf appears healthy.\n\n"
                f"📋 *Prevention Tips:*\n"
                f"• Continue regular monitoring\n"
                f"• Maintain good field hygiene\n"
                f"• Follow your fertilization schedule\n"
                f"• Scout for pests regularly\n\n"
                f"Keep up the good work! 👍"
            )
        else:
            # Get severity emoji
            severity = treatment.get('severity', 'Moderate')
            severity_emoji = {
                "Low": "🟢",
                "Low to Moderate": "🟡",
                "Moderate": "🟠",
                "Moderate to High": "🔴",
                "High": "⛔"
            }.get(severity, "⚠️")
            
            message = (
                f"📊 *Disease Detection Result*\n\n"
                f"👤 *Farmer:* {user_name}\n"
                f"{grade['emoji']} *Disease:* {disease}\n"
                f"📈 *Confidence:* {confidence:.1f}%\n"
                f"{severity_emoji} *Severity:* {severity}\n\n"
                f"🔍 *Symptoms:*\n{treatment.get('symptoms', 'N/A')}\n\n"
                f"🛠️ *Recommended Action:*\n{treatment.get('action', 'Consult expert')}\n"
            )
            
            # Add chemicals if available
            if treatment.get('chemicals'):
                chems = treatment['chemicals'][:3]  # Max 3
                message += f"\n🧪 *Recommended Chemicals:*\n"
                for chem in chems:
                    message += f"• {chem}\n"
            
            # Add organic options if available
            if treatment.get('organic'):
                message += f"\n🌱 *Organic Options:*\n"
                for opt in treatment['organic'][:2]:  # Max 2
                    message += f"• {opt}\n"
        
        # Add navigation
        message += "\n\n---\n0️⃣ Main Menu  |  9️⃣ New Scan"
        
        self.whatsapp.send_text(phone_number, message)
    
    def _send_clarification_question(self, phone_number: str, disease: str):
        """Send clarification question for similar diseases"""
        clarification = DISEASE_CLARIFICATIONS.get(disease, {})
        
        if clarification and clarification.get('questions'):
            question = clarification['questions'][0]['question']
            
            message = (
                f"❓ *Clarification Needed*\n\n"
                f"To provide a more accurate diagnosis, please answer:\n\n"
                f"*{question}*\n\n"
                f"Reply with:\n"
                f"• *Yes* - if yes\n"
                f"• *No* - if no\n"
                f"• *Skip* - to proceed with current result"
            )
            
            self.whatsapp.send_text(phone_number, message)
    
    def handle_clarification(self, phone_number: str, answer: str, user: Dict) -> Dict[str, Any]:
        """Handle user response to clarification question"""
        
        # Get pending detection
        pending = self.pending_detections.get(phone_number)
        if not pending:
            # No pending clarification, go to active state
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
            return {"status": "ok"}
        
        answer = answer.lower().strip()
        
        if answer in ['yes', 'no', 'skip']:
            disease = pending['disease']
            clarification = DISEASE_CLARIFICATIONS.get(disease, {})
            
            if answer == 'skip':
                # Send original result
                self._send_detection_result(
                    phone_number, 
                    user.get("name", "Farmer"),
                    disease,
                    pending['confidence'],
                    pending['treatment'],
                    {"emoji": "⚠️", "level": "MODERATE"}
                )
            else:
                # Process clarification
                self._send_refined_result(
                    phone_number, user, disease, answer, pending
                )
            
            # Clear pending
            del self.pending_detections[phone_number]
            self.user_repo.update_user_state(phone_number, UserState.ACTIVE.value)
        
        else:
            # Invalid answer
            self.whatsapp.send_text(
                phone_number,
                "Please reply with *Yes*, *No*, or *Skip*."
            )
        
        return {"status": "ok"}
    
    def _send_refined_result(self, phone_number: str, user: Dict,
                             disease: str, answer: str, pending: Dict):
        """Send refined result after clarification"""
        
        # This would contain logic to adjust based on clarification
        # For now, just send the original result
        self._send_detection_result(
            phone_number,
            user.get("name", "Farmer"),
            disease,
            pending['confidence'],
            pending['treatment'],
            {"emoji": "✅", "level": "REFINED"}
        )