"""
User repository for Firestore operations
Handles all user-related database operations
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from google.cloud import firestore
from config.firebase import get_db
from core.constants import UserState

class UserRepository:
    """Repository for user data operations"""
    
    def __init__(self):
        self.db = get_db()
        self.collection = "users"
    
    def _get_collection(self):
        """Get Firestore collection reference"""
        if not self.db:
            return None
        return self.db.collection(self.collection)
    
    def get_user(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user by phone number
        Args:
            phone_number: User's phone number
        Returns:
            User dict or None
        """
        try:
            collection = self._get_collection()
            if not collection:
                return None
            
            user_ref = collection.document(phone_number)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                return user_doc.to_dict()
            return None
            
        except Exception as e:
            print(f"❌ Error getting user {phone_number}: {e}")
            return None
    
    def create_user(self, phone_number: str, user_data: Dict[str, Any]) -> bool:
        """
        Create new user
        Args:
            phone_number: User's phone number
            user_data: User data dictionary
        Returns:
            bool: Success status
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            # Add timestamps
            user_data["created_at"] = firestore.SERVER_TIMESTAMP
            user_data["updated_at"] = firestore.SERVER_TIMESTAMP
            user_data["phone"] = phone_number
            
            # Set default values if not provided
            if "state" not in user_data:
                user_data["state"] = UserState.AWAITING_NAME.value
            if "language" not in user_data:
                user_data["language"] = "en"
            if "history_count" not in user_data:
                user_data["history_count"] = 0
            if "total_scans" not in user_data:
                user_data["total_scans"] = 0
            
            user_ref = collection.document(phone_number)
            user_ref.set(user_data)
            
            print(f"✅ User {phone_number} created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating user {phone_number}: {e}")
            return False
    
    def update_user(self, phone_number: str, user_data: Dict[str, Any]) -> bool:
        """
        Update existing user
        Args:
            phone_number: User's phone number
            user_data: Updated fields
        Returns:
            bool: Success status
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            # Add update timestamp
            user_data["updated_at"] = firestore.SERVER_TIMESTAMP
            
            user_ref = collection.document(phone_number)
            user_ref.update(user_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating user {phone_number}: {e}")
            return False
    
    def update_user_state(self, phone_number: str, state: str) -> bool:
        """
        Update user's state
        Args:
            phone_number: User's phone number
            state: New state value
        Returns:
            bool: Success status
        """
        return self.update_user(phone_number, {"state": state})
    
    def update_last_interaction(self, phone_number: str) -> bool:
        """
        Update last interaction timestamp
        Args:
            phone_number: User's phone number
        Returns:
            bool: Success status
        """
        return self.update_user(
            phone_number, 
            {"last_interaction": firestore.SERVER_TIMESTAMP}
        )
    
    def user_exists(self, phone_number: str) -> bool:
        """
        Check if user exists
        Args:
            phone_number: User's phone number
        Returns:
            bool: True if exists
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            user_ref = collection.document(phone_number)
            return user_ref.get().exists
            
        except Exception as e:
            print(f"❌ Error checking user {phone_number}: {e}")
            return False
    
    def delete_user(self, phone_number: str) -> bool:
        """
        Delete user (soft delete by marking inactive)
        Args:
            phone_number: User's phone number
        Returns:
            bool: Success status
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            user_ref = collection.document(phone_number)
            user_ref.update({
                "active": False,
                "deleted_at": firestore.SERVER_TIMESTAMP
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error deleting user {phone_number}: {e}")
            return False
    
    def get_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all users (for admin purposes)
        Args:
            limit: Maximum number of users to return
        Returns:
            List of user dictionaries
        """
        try:
            collection = self._get_collection()
            if not collection:
                return []
            
            docs = collection.limit(limit).stream()
            
            users = []
            for doc in docs:
                user_data = doc.to_dict()
                user_data["phone"] = doc.id
                users.append(user_data)
            
            return users
            
        except Exception as e:
            print(f"❌ Error getting all users: {e}")
            return []
    
    def get_users_by_state(self, state: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get users by current state
        Args:
            state: User state to filter by
            limit: Maximum number of users
        Returns:
            List of users in that state
        """
        try:
            collection = self._get_collection()
            if not collection:
                return []
            
            docs = collection.where("state", "==", state).limit(limit).stream()
            
            users = []
            for doc in docs:
                user_data = doc.to_dict()
                user_data["phone"] = doc.id
                users.append(user_data)
            
            return users
            
        except Exception as e:
            print(f"❌ Error getting users by state: {e}")
            return []
    
    def increment_scan_count(self, phone_number: str) -> bool:
        """
        Increment user's scan count
        Args:
            phone_number: User's phone number
        Returns:
            bool: Success status
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            user_ref = collection.document(phone_number)
            user_ref.update({
                "total_scans": firestore.Increment(1),
                "last_scan_at": firestore.SERVER_TIMESTAMP
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error incrementing scan count: {e}")
            return False
    
    def set_language(self, phone_number: str, language: str) -> bool:
        """
        Set user's preferred language
        Args:
            phone_number: User's phone number
            language: Language code (en, sn, nd)
        Returns:
            bool: Success status
        """
        return self.update_user(phone_number, {"language": language})
    
    def get_user_stats(self) -> Dict[str, Any]:
        """
        Get user statistics (for admin dashboard)
        Returns:
            Dict with user stats
        """
        try:
            collection = self._get_collection()
            if not collection:
                return {}
            
            # This is a simplified version - for production,
            # you might want to use aggregation queries
            users = list(collection.stream())
            
            total_users = len(users)
            active_users = sum(1 for u in users if u.to_dict().get("state") == UserState.ACTIVE.value)
            new_users_today = 0  # Would need date filtering
            
            # Count by language
            languages = {}
            for user in users:
                lang = user.to_dict().get("language", "en")
                languages[lang] = languages.get(lang, 0) + 1
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "languages": languages,
                "new_users_today": new_users_today
            }
            
        except Exception as e:
            print(f"❌ Error getting user stats: {e}")
            return {}