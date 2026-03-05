"""
Feedback service for handling user comments and forwarding to admin
Supports both WhatsApp and Email forwarding
"""
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime
from config.settings import ADMIN_PHONE_NUMBER, ADMIN_EMAIL, SMTP_PASSWORD
from config.firebase import get_db
from infrastructure.whatsapp.client import WhatsAppClient

class FeedbackService:
    """Handle user feedback and forward to admin"""
    
    def __init__(self):
        self.whatsapp = WhatsAppClient()
        self.db = get_db()
        self.admin_phone = ADMIN_PHONE_NUMBER
        self.admin_email = ADMIN_EMAIL
        self.smtp_password = SMTP_PASSWORD
        
        # Collection for storing feedback
        self.feedback_collection = "feedback" if self.db else None
    
    def process_feedback(self, phone_number: str, user_name: str, 
                        feedback_text: str, feedback_type: str = "general") -> bool:
        """
        Process and forward user feedback
        Args:
            phone_number: User's phone number
            user_name: User's name
            feedback_text: The feedback message
            feedback_type: Type of feedback (general, bug, suggestion)
        Returns:
            bool: Success status
        """
        # Store in database
        self._store_feedback(phone_number, user_name, feedback_text, feedback_type)
        
        # Forward to admin via WhatsApp
        whatsapp_sent = self._forward_to_whatsapp(phone_number, user_name, feedback_text)
        
        # Forward to admin via Email
        email_sent = self._forward_to_email(phone_number, user_name, feedback_text)
        
        # Send confirmation to user
        self._send_user_confirmation(phone_number, user_name)
        
        return whatsapp_sent or email_sent
    
    def _store_feedback(self, phone_number: str, user_name: str, 
                        feedback_text: str, feedback_type: str) -> bool:
        """Store feedback in Firebase"""
        try:
            if not self.db or not self.feedback_collection:
                return False
            
            feedback_data = {
                "user_phone": phone_number,
                "user_name": user_name,
                "feedback": feedback_text,
                "type": feedback_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "status": "new",
                "read": False
            }
            
            self.db.collection(self.feedback_collection).add(feedback_data)
            print(f"✅ Feedback stored for {user_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error storing feedback: {e}")
            return False
    
    def _forward_to_whatsapp(self, phone_number: str, user_name: str, 
                             feedback_text: str) -> bool:
        """Forward feedback to admin via WhatsApp"""
        try:
            if not self.admin_phone:
                print("⚠️ Admin WhatsApp number not configured")
                return False
            
            # Format message for admin
            admin_message = (
                f"📝 *NEW FEEDBACK RECEIVED*\n\n"
                f"👤 *From:* {user_name}\n"
                f"📱 *Phone:* {phone_number}\n"
                f"⏱️ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💬 *Message:*\n{feedback_text}\n\n"
                f"---\n"
                f"Reply to this message to respond directly to the user."
            )
            
            # Send to admin
            return self.whatsapp.send_text(self.admin_phone, admin_message)
            
        except Exception as e:
            print(f"❌ Error forwarding to WhatsApp: {e}")
            return False
    
    def _forward_to_email(self, phone_number: str, user_name: str, 
                          feedback_text: str) -> bool:
        """Forward feedback to admin via Email"""
        try:
            if not self.admin_email or not self.smtp_password:
                print("⚠️ Admin email not configured")
                return False
            
            # Email configuration
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = self.admin_email  # Using admin email as sender
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = self.admin_email
            msg["Subject"] = f"📝 New Feedback from {user_name}"
            
            # Email body
            body = f"""
            <h2>New Feedback Received</h2>
            
            <p><strong>From:</strong> {user_name}</p>
            <p><strong>Phone:</strong> {phone_number}</p>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h3>Message:</h3>
            <p>{feedback_text}</p>
            
            <hr>
            <p><small>This is an automated message from your Tobacco AI Assistant.</small></p>
            """
            
            msg.attach(MIMEText(body, "html"))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Feedback emailed to admin")
            return True
            
        except Exception as e:
            print(f"❌ Error forwarding to email: {e}")
            return False
    
    def _send_user_confirmation(self, phone_number: str, user_name: str):
        """Send confirmation to user"""
        confirmation = (
            f"✅ *Thank you for your feedback, {user_name}!*\n\n"
            f"Your message has been sent to our team. We appreciate your input "
            f"and will use it to improve our service.\n\n"
            f"Reply *menu* to return to main menu."
        )
        self.whatsapp.send_text(phone_number, confirmation)
    
    def get_all_feedback(self, status: str = None, limit: int = 50) -> list:
        """Get all feedback (for admin dashboard)"""
        try:
            if not self.db or not self.feedback_collection:
                return []
            
            query = self.db.collection(self.feedback_collection)
            
            if status:
                query = query.where("status", "==", status)
            
            docs = query.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
            
            feedback_list = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                feedback_list.append(data)
            
            return feedback_list
            
        except Exception as e:
            print(f"❌ Error getting feedback: {e}")
            return []
    
    def mark_as_read(self, feedback_id: str) -> bool:
        """Mark feedback as read"""
        try:
            if not self.db or not self.feedback_collection:
                return False
            
            self.db.collection(self.feedback_collection).document(feedback_id).update({
                "read": True,
                "read_at": firestore.SERVER_TIMESTAMP
            })
            return True
            
        except Exception as e:
            print(f"❌ Error marking feedback as read: {e}")
            return False
    
    def update_feedback_status(self, feedback_id: str, status: str) -> bool:
        """Update feedback status"""
        try:
            if not self.db or not self.feedback_collection:
                return False
            
            self.db.collection(self.feedback_collection).document(feedback_id).update({
                "status": status,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            return True
            
        except Exception as e:
            print(f"❌ Error updating feedback status: {e}")
            return False
    
    def reply_to_feedback(self, feedback_id: str, reply_text: str) -> bool:
        """
        Admin replies to feedback
        This would be called when admin responds to a feedback message
        """
        try:
            if not self.db or not self.feedback_collection:
                return False
            
            # Get the original feedback
            feedback_doc = self.db.collection(self.feedback_collection).document(feedback_id).get()
            if not feedback_doc.exists:
                return False
            
            feedback_data = feedback_doc.to_dict()
            user_phone = feedback_data.get("user_phone")
            
            if not user_phone:
                return False
            
            # Send reply to user
            reply_message = (
                f"📬 *Response from our Team*\n\n"
                f"{reply_text}\n\n"
                f"---\n"
                f"Reply *menu* for main menu"
            )
            
            sent = self.whatsapp.send_text(user_phone, reply_message)
            
            if sent:
                # Update feedback with reply
                self.db.collection(self.feedback_collection).document(feedback_id).update({
                    "reply": reply_text,
                    "replied_at": firestore.SERVER_TIMESTAMP,
                    "status": "replied"
                })
            
            return sent
            
        except Exception as e:
            print(f"❌ Error replying to feedback: {e}")
            return False
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics"""
        try:
            if not self.db or not self.feedback_collection:
                return {}
            
            all_feedback = list(self.db.collection(self.feedback_collection).stream())
            
            total = len(all_feedback)
            unread = sum(1 for f in all_feedback if not f.to_dict().get("read", False))
            replied = sum(1 for f in all_feedback if f.to_dict().get("reply"))
            
            # Count by type
            types = {}
            for f in all_feedback:
                f_type = f.to_dict().get("type", "general")
                types[f_type] = types.get(f_type, 0) + 1
            
            return {
                "total": total,
                "unread": unread,
                "replied": replied,
                "by_type": types
            }
            
        except Exception as e:
            print(f"❌ Error getting feedback stats: {e}")
            return {}