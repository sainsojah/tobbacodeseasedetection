"""
Expert forwarder service for connecting farmers with agronomists
"""
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from config.settings import ADMIN_PHONE_NUMBER, ADMIN_EMAIL
from config.firebase import get_db
from infrastructure.whatsapp.client import WhatsAppClient

class ExpertForwarder:
    """Handle farmer requests to connect with agricultural experts"""
    
    def __init__(self):
        self.whatsapp = WhatsAppClient()
        self.db = get_db()
        self.admin_phone = ADMIN_PHONE_NUMBER
        self.admin_email = ADMIN_EMAIL
        
        # Collections
        self.expert_requests_collection = "expert_requests" if self.db else None
        self.experts_collection = "experts" if self.db else None
    
    def request_expert(self, phone_number: str, user_name: str, 
                       query: str = None, preferred_time: str = None) -> Dict[str, Any]:
        """
        Request connection with an expert
        Args:
            phone_number: User's phone number
            user_name: User's name
            query: Optional specific question
            preferred_time: Optional preferred contact time
        Returns:
            Dict with request status and info
        """
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Store request
        self._store_request(request_id, phone_number, user_name, query, preferred_time)
        
        # Notify admin
        self._notify_admin(request_id, phone_number, user_name, query)
        
        # Send confirmation to user
        self._send_user_confirmation(phone_number, user_name, request_id)
        
        return {
            "success": True,
            "request_id": request_id,
            "message": "Expert request submitted successfully"
        }
    
    def _store_request(self, request_id: str, phone_number: str, 
                       user_name: str, query: str = None, 
                       preferred_time: str = None) -> bool:
        """Store expert request in database"""
        try:
            if not self.db or not self.expert_requests_collection:
                return False
            
            request_data = {
                "request_id": request_id,
                "user_phone": phone_number,
                "user_name": user_name,
                "query": query,
                "preferred_time": preferred_time,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP,
                "assigned_to": None,
                "assigned_at": None,
                "resolved_at": None
            }
            
            self.db.collection(self.expert_requests_collection).document(request_id).set(request_data)
            print(f"✅ Expert request {request_id} stored")
            return True
            
        except Exception as e:
            print(f"❌ Error storing expert request: {e}")
            return False
    
    def _notify_admin(self, request_id: str, phone_number: str, 
                      user_name: str, query: str = None):
        """Notify admin about new expert request"""
        try:
            if not self.admin_phone:
                print("⚠️ Admin phone not configured")
                return
            
            # Build message
            message = (
                f"👨‍🌾 *NEW EXPERT REQUEST*\n\n"
                f"🆔 *Request ID:* {request_id}\n"
                f"👤 *Farmer:* {user_name}\n"
                f"📱 *Phone:* {phone_number}\n"
                f"⏱️ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            
            if query:
                message += f"\n❓ *Question:*\n{query}\n"
            
            message += f"\n---\nReply to this message to connect with the farmer."
            
            # Send to admin
            self.whatsapp.send_text(self.admin_phone, message)
            
        except Exception as e:
            print(f"❌ Error notifying admin: {e}")
    
    def _send_user_confirmation(self, phone_number: str, user_name: str, request_id: str):
        """Send confirmation to user"""
        confirmation = (
            f"✅ *Expert Request Submitted, {user_name}!*\n\n"
            f"Your request has been sent to our agricultural experts. "
            f"Someone will contact you shortly.\n\n"
            f"📋 *Request ID:* {request_id}\n\n"
            f"You will receive a response via WhatsApp. Please keep your phone nearby.\n\n"
            f"Reply *menu* to return to main menu."
        )
        self.whatsapp.send_text(phone_number, confirmation)
    
    def assign_expert(self, request_id: str, expert_phone: str) -> bool:
        """
        Assign an expert to a request
        Args:
            request_id: Request ID
            expert_phone: Expert's phone number
        Returns:
            bool: Success status
        """
        try:
            if not self.db or not self.expert_requests_collection:
                return False
            
            # Get expert info
            expert = self.get_expert(expert_phone)
            if not expert:
                print(f"❌ Expert {expert_phone} not found")
                return False
            
            # Update request
            self.db.collection(self.expert_requests_collection).document(request_id).update({
                "status": "assigned",
                "assigned_to": expert_phone,
                "assigned_to_name": expert.get("name"),
                "assigned_at": firestore.SERVER_TIMESTAMP
            })
            
            # Get request details
            request_doc = self.db.collection(self.expert_requests_collection).document(request_id).get()
            if request_doc.exists:
                request_data = request_doc.to_dict()
                
                # Notify farmer
                self._notify_farmer_assignment(
                    request_data.get("user_phone"),
                    request_data.get("user_name"),
                    expert.get("name")
                )
                
                # Notify expert
                self._notify_expert_assignment(
                    expert_phone,
                    expert.get("name"),
                    request_data
                )
            
            return True
            
        except Exception as e:
            print(f"❌ Error assigning expert: {e}")
            return False
    
    def _notify_farmer_assignment(self, farmer_phone: str, farmer_name: str, expert_name: str):
        """Notify farmer that an expert has been assigned"""
        message = (
            f"👨‍🌾 *Good news, {farmer_name}!*\n\n"
            f"An agricultural expert has been assigned to help you.\n\n"
            f"👤 *Expert:* {expert_name}\n\n"
            f"They will contact you shortly. Please be ready to discuss your farming needs.\n\n"
            f"Reply *menu* for main menu."
        )
        self.whatsapp.send_text(farmer_phone, message)
    
    def _notify_expert_assignment(self, expert_phone: str, expert_name: str, request_data: Dict):
        """Notify expert about new assignment"""
        message = (
            f"👋 *Hello {expert_name}!*\n\n"
            f"You have been assigned to help a farmer.\n\n"
            f"👤 *Farmer:* {request_data.get('user_name')}\n"
            f"📱 *Phone:* {request_data.get('user_phone')}\n"
        )
        
        if request_data.get("query"):
            message += f"\n❓ *Question:*\n{request_data.get('query')}\n"
        
        if request_data.get("preferred_time"):
            message += f"\n⏰ *Preferred time:* {request_data.get('preferred_time')}\n"
        
        message += f"\nPlease contact the farmer as soon as possible.\n"
        message += f"Reply to this message to communicate with the farmer."
        
        self.whatsapp.send_text(expert_phone, message)
    
    def resolve_request(self, request_id: str, notes: str = None) -> bool:
        """
        Mark request as resolved
        Args:
            request_id: Request ID
            notes: Resolution notes
        Returns:
            bool: Success status
        """
        try:
            if not self.db or not self.expert_requests_collection:
                return False
            
            update_data = {
                "status": "resolved",
                "resolved_at": firestore.SERVER_TIMESTAMP
            }
            
            if notes:
                update_data["resolution_notes"] = notes
            
            self.db.collection(self.expert_requests_collection).document(request_id).update(update_data)
            
            # Get request to notify farmer
            request_doc = self.db.collection(self.expert_requests_collection).document(request_id).get()
            if request_doc.exists:
                request_data = request_doc.to_dict()
                
                # Notify farmer
                self._notify_farmer_resolved(
                    request_data.get("user_phone"),
                    request_data.get("user_name")
                )
            
            return True
            
        except Exception as e:
            print(f"❌ Error resolving request: {e}")
            return False
    
    def _notify_farmer_resolved(self, farmer_phone: str, farmer_name: str):
        """Notify farmer that request is resolved"""
        message = (
            f"✅ *Request Resolved, {farmer_name}!*\n\n"
            f"Your expert request has been marked as resolved. "
            f"We hope your questions were answered.\n\n"
            f"If you need further assistance, just type *expert* to start a new request.\n\n"
            f"Reply *menu* for main menu."
        )
        self.whatsapp.send_text(farmer_phone, message)
    
    def add_expert(self, name: str, phone: str, specialty: str, 
                   email: str = None, location: str = None) -> bool:
        """
        Add a new expert to the system
        Args:
            name: Expert's name
            phone: Expert's phone number
            specialty: Area of expertise
            email: Optional email
            location: Optional location
        Returns:
            bool: Success status
        """
        try:
            if not self.db or not self.experts_collection:
                return False
            
            expert_data = {
                "name": name,
                "phone": phone,
                "specialty": specialty,
                "email": email,
                "location": location,
                "active": True,
                "total_assigned": 0,
                "total_resolved": 0,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            
            self.db.collection(self.experts_collection).document(phone).set(expert_data)
            print(f"✅ Expert {name} added")
            return True
            
        except Exception as e:
            print(f"❌ Error adding expert: {e}")
            return False
    
    def get_expert(self, phone: str) -> Optional[Dict]:
        """Get expert by phone number"""
        try:
            if not self.db or not self.experts_collection:
                return None
            
            expert_doc = self.db.collection(self.experts_collection).document(phone).get()
            if expert_doc.exists:
                return expert_doc.to_dict()
            return None
            
        except Exception as e:
            print(f"❌ Error getting expert: {e}")
            return None
    
    def get_all_experts(self, active_only: bool = True) -> list:
        """Get all experts"""
        try:
            if not self.db or not self.experts_collection:
                return []
            
            query = self.db.collection(self.experts_collection)
            if active_only:
                query = query.where("active", "==", True)
            
            docs = query.stream()
            
            experts = []
            for doc in docs:
                expert = doc.to_dict()
                expert["phone"] = doc.id
                experts.append(expert)
            
            return experts
            
        except Exception as e:
            print(f"❌ Error getting experts: {e}")
            return []
    
    def get_pending_requests(self) -> list:
        """Get all pending expert requests"""
        try:
            if not self.db or not self.expert_requests_collection:
                return []
            
            docs = self.db.collection(self.expert_requests_collection)\
                .where("status", "==", "pending")\
                .order_by("created_at", direction="DESCENDING")\
                .stream()
            
            requests = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                requests.append(data)
            
            return requests
            
        except Exception as e:
            print(f"❌ Error getting pending requests: {e}")
            return []
    
    def get_user_requests(self, phone_number: str) -> list:
        """Get all requests by a user"""
        try:
            if not self.db or not self.expert_requests_collection:
                return []
            
            docs = self.db.collection(self.expert_requests_collection)\
                .where("user_phone", "==", phone_number)\
                .order_by("created_at", direction="DESCENDING")\
                .stream()
            
            requests = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                requests.append(data)
            
            return requests
            
        except Exception as e:
            print(f"❌ Error getting user requests: {e}")
            return []
    
    def get_expert_stats(self) -> Dict[str, Any]:
        """Get expert service statistics"""
        try:
            if not self.db:
                return {}
            
            # Get all requests
            requests = list(self.db.collection(self.expert_requests_collection).stream())
            
            total = len(requests)
            pending = sum(1 for r in requests if r.to_dict().get("status") == "pending")
            assigned = sum(1 for r in requests if r.to_dict().get("status") == "assigned")
            resolved = sum(1 for r in requests if r.to_dict().get("status") == "resolved")
            
            # Average response time (simplified)
            response_times = []
            for r in requests:
                data = r.to_dict()
                if data.get("assigned_at") and data.get("created_at"):
                    # Calculate time difference
                    if hasattr(data["assigned_at"], "timestamp") and hasattr(data["created_at"], "timestamp"):
                        time_diff = data["assigned_at"].timestamp() - data["created_at"].timestamp()
                        response_times.append(time_diff / 3600)  # Convert to hours
            
            avg_response = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                "total_requests": total,
                "pending": pending,
                "assigned": assigned,
                "resolved": resolved,
                "average_response_hours": avg_response,
                "resolution_rate": (resolved / total * 100) if total > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting expert stats: {e}")
            return {}