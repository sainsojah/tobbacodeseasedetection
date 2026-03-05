"""
Detection repository for logging and retrieving disease detections
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google.cloud import firestore
from config.firebase import get_db

class DetectionRepository:
    """Repository for detection records"""
    
    def __init__(self):
        self.db = get_db()
        self.collection = "detections"
    
    def _get_collection(self):
        """Get Firestore collection reference"""
        if not self.db:
            return None
        return self.db.collection(self.collection)
    
    def log_detection(self, phone_number: str, user_name: str, 
                      disease: str, confidence: float, 
                      image_url: str = None, metadata: Dict = None) -> bool:
        """
        Log a disease detection
        Args:
            phone_number: User's phone number
            user_name: User's name
            disease: Detected disease name
            confidence: Confidence score (0-100)
            image_url: Optional URL to the image
            metadata: Additional metadata
        Returns:
            bool: Success status
        """
        try:
            collection = self._get_collection()
            if not collection:
                return False
            
            detection_data = {
                "user_phone": phone_number,
                "user_name": user_name,
                "disease_detected": disease,
                "confidence_score": confidence,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if image_url:
                detection_data["image_url"] = image_url
            
            if metadata:
                detection_data["metadata"] = metadata
            
            # Add to main detections collection
            collection.add(detection_data)
            
            # Also add to user's subcollection for easier queries
            user_detections = self.db.collection("users").document(phone_number)\
                                   .collection("detections")
            user_detections.add(detection_data)
            
            print(f"✅ Detection logged for {user_name}: {disease} ({confidence:.1f}%)")
            return True
            
        except Exception as e:
            print(f"❌ Error logging detection: {e}")
            return False
    
    def get_user_history(self, phone_number: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get user's detection history
        Args:
            phone_number: User's phone number
            limit: Maximum number of records
        Returns:
            List of detection records
        """
        try:
            collection = self._get_collection()
            if not collection:
                return []
            
            # Query main collection
            docs = collection.where("user_phone", "==", phone_number)\
                .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()
            
            history = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                
                # Format timestamp for display
                if data.get("timestamp"):
                    if hasattr(data["timestamp"], "strftime"):
                        data["display_date"] = data["timestamp"].strftime("%d %b %Y, %H:%M")
                    else:
                        data["display_date"] = data.get("date", "Unknown")
                
                history.append(data)
            
            return history
            
        except Exception as e:
            print(f"❌ Error getting user history: {e}")
            return []
    
    def get_detection_by_id(self, detection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific detection by ID
        Args:
            detection_id: Document ID
        Returns:
            Detection record or None
        """
        try:
            collection = self._get_collection()
            if not collection:
                return None
            
            doc = collection.document(detection_id).get()
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data
            return None
            
        except Exception as e:
            print(f"❌ Error getting detection: {e}")
            return None
    
    def get_recent_detections(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent detections
        Args:
            hours: How many hours back
            limit: Maximum records
        Returns:
            List of recent detections
        """
        try:
            collection = self._get_collection()
            if not collection:
                return []
            
            # Calculate cutoff time
            cutoff = datetime.now() - timedelta(hours=hours)
            
            docs = collection.where("timestamp", ">=", cutoff)\
                .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()
            
            detections = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                detections.append(data)
            
            return detections
            
        except Exception as e:
            print(f"❌ Error getting recent detections: {e}")
            return []
    
    def get_disease_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get disease statistics for dashboard
        Args:
            days: Number of days to analyze
        Returns:
            Dict with disease statistics
        """
        try:
            collection = self._get_collection()
            if not collection:
                return {}
            
            # Calculate cutoff
            cutoff = datetime.now() - timedelta(days=days)
            
            # Get all detections in period
            docs = collection.where("timestamp", ">=", cutoff).stream()
            
            stats = {
                "total_detections": 0,
                "by_disease": {},
                "by_confidence": {
                    "high": 0,      # >60%
                    "moderate": 0,  # 45-60%
                    "low": 0        # <45%
                },
                "daily_average": 0,
                "most_common": None
            }
            
            disease_counts = {}
            dates = {}
            
            for doc in docs:
                data = doc.to_dict()
                stats["total_detections"] += 1
                
                # Count by disease
                disease = data.get("disease_detected", "Unknown")
                disease_counts[disease] = disease_counts.get(disease, 0) + 1
                
                # Count by confidence
                conf = data.get("confidence_score", 0)
                if conf >= 60:
                    stats["by_confidence"]["high"] += 1
                elif conf >= 45:
                    stats["by_confidence"]["moderate"] += 1
                else:
                    stats["by_confidence"]["low"] += 1
                
                # Count by date
                if data.get("timestamp"):
                    date_str = data["timestamp"].strftime("%Y-%m-%d")
                    dates[date_str] = dates.get(date_str, 0) + 1
            
            # Calculate most common disease
            if disease_counts:
                most_common = max(disease_counts.items(), key=lambda x: x[1])
                stats["most_common"] = {
                    "disease": most_common[0],
                    "count": most_common[1],
                    "percentage": (most_common[1] / stats["total_detections"]) * 100
                }
            
            stats["by_disease"] = disease_counts
            
            # Calculate daily average
            if dates:
                stats["daily_average"] = stats["total_detections"] / len(dates)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting disease stats: {e}")
            return {}
    
    def get_user_detection_summary(self, phone_number: str) -> Dict[str, Any]:
        """
        Get summary of user's detections
        Args:
            phone_number: User's phone number
        Returns:
            Dict with user detection summary
        """
        try:
            collection = self._get_collection()
            if not collection:
                return {}
            
            docs = collection.where("user_phone", "==", phone_number).stream()
            
            summary = {
                "total_scans": 0,
                "unique_diseases": set(),
                "by_disease": {},
                "last_scan": None,
                "average_confidence": 0
            }
            
            total_confidence = 0
            
            for doc in docs:
                data = doc.to_dict()
                summary["total_scans"] += 1
                
                disease = data.get("disease_detected", "Unknown")
                summary["unique_diseases"].add(disease)
                summary["by_disease"][disease] = summary["by_disease"].get(disease, 0) + 1
                
                conf = data.get("confidence_score", 0)
                total_confidence += conf
                
                # Track last scan
                if not summary["last_scan"] or data.get("timestamp") > summary["last_scan"].get("timestamp"):
                    summary["last_scan"] = {
                        "disease": disease,
                        "confidence": conf,
                        "date": data.get("display_date", "Unknown")
                    }
            
            if summary["total_scans"] > 0:
                summary["average_confidence"] = total_confidence / summary["total_scans"]
            
            summary["unique_diseases"] = list(summary["unique_diseases"])
            
            return summary
            
        except Exception as e:
            print(f"❌ Error getting user summary: {e}")
            return {}
    
    def delete_old_detections(self, days: int = 365) -> int:
        """
        Delete detections older than specified days
        Args:
            days: Age threshold in days
        Returns:
            Number of records deleted
        """
        try:
            collection = self._get_collection()
            if not collection:
                return 0
            
            cutoff = datetime.now() - timedelta(days=days)
            
            # Get old documents
            docs = collection.where("timestamp", "<", cutoff).stream()
            
            deleted = 0
            for doc in docs:
                doc.reference.delete()
                deleted += 1
            
            print(f"✅ Deleted {deleted} old detection records")
            return deleted
            
        except Exception as e:
            print(f"❌ Error deleting old detections: {e}")
            return 0