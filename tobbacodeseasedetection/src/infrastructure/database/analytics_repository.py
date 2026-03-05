"""
Analytics repository for dashboard and reporting
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from google.cloud import firestore
from config.firebase import get_db

class AnalyticsRepository:
    """Repository for analytics and dashboard data"""
    
    def __init__(self):
        self.db = get_db()
        self.detections_collection = "detections"
        self.users_collection = "users"
        self.analytics_collection = "analytics"
    
    def get_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """
        Get complete dashboard data
        Args:
            days: Number of days to analyze
        Returns:
            Dict with all dashboard metrics
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        dashboard = {
            "period": f"Last {days} days",
            "users": self._get_user_stats(cutoff),
            "detections": self._get_detection_stats(cutoff),
            "diseases": self._get_disease_breakdown(cutoff),
            "trends": self._get_trend_data(cutoff),
            "performance": self._get_performance_metrics(cutoff)
        }
        
        return dashboard
    
    def _get_user_stats(self, cutoff: datetime) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            users_ref = self.db.collection(self.users_collection)
            
            # Total users
            total_users = len(list(users_ref.stream()))
            
            # New users in period
            new_users = len(list(
                users_ref.where("created_at", ">=", cutoff).stream()
            ))
            
            # Active users (with detection in period)
            detections_ref = self.db.collection(self.detections_collection)
            active_users = set()
            for doc in detections_ref.where("timestamp", ">=", cutoff).stream():
                data = doc.to_dict()
                active_users.add(data.get("user_phone"))
            
            return {
                "total": total_users,
                "new": new_users,
                "active": len(active_users),
                "engagement_rate": (len(active_users) / total_users * 100) if total_users > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting user stats: {e}")
            return {}
    
    def _get_detection_stats(self, cutoff: datetime) -> Dict[str, Any]:
        """Get detection statistics"""
        try:
            detections_ref = self.db.collection(self.detections_collection)
            
            # Total detections in period
            total = 0
            high_conf = 0
            low_conf = 0
            
            for doc in detections_ref.where("timestamp", ">=", cutoff).stream():
                total += 1
                data = doc.to_dict()
                conf = data.get("confidence_score", 0)
                if conf >= 60:
                    high_conf += 1
                elif conf < 45:
                    low_conf += 1
            
            return {
                "total": total,
                "daily_average": total / 30 if total > 0 else 0,
                "high_confidence": high_conf,
                "low_confidence": low_conf,
                "accuracy_rate": (high_conf / total * 100) if total > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting detection stats: {e}")
            return {}
    
    def _get_disease_breakdown(self, cutoff: datetime) -> List[Dict[str, Any]]:
        """Get disease occurrence breakdown"""
        try:
            detections_ref = self.db.collection(self.detections_collection)
            
            disease_counts = {}
            total = 0
            
            for doc in detections_ref.where("timestamp", ">=", cutoff).stream():
                total += 1
                data = doc.to_dict()
                disease = data.get("disease_detected", "Unknown")
                disease_counts[disease] = disease_counts.get(disease, 0) + 1
            
            # Format for charts
            breakdown = []
            for disease, count in disease_counts.items():
                breakdown.append({
                    "disease": disease,
                    "count": count,
                    "percentage": (count / total * 100) if total > 0 else 0
                })
            
            # Sort by count descending
            breakdown.sort(key=lambda x: x["count"], reverse=True)
            
            return breakdown
            
        except Exception as e:
            print(f"❌ Error getting disease breakdown: {e}")
            return []
    
    def _get_trend_data(self, cutoff: datetime) -> Dict[str, List]:
        """Get trend data for charts"""
        try:
            detections_ref = self.db.collection(self.detections_collection)
            
            # Group by date
            daily_counts = {}
            daily_diseases = {}
            
            for doc in detections_ref.where("timestamp", ">=", cutoff).stream():
                data = doc.to_dict()
                timestamp = data.get("timestamp")
                if timestamp and hasattr(timestamp, "strftime"):
                    date = timestamp.strftime("%Y-%m-%d")
                    
                    # Count by date
                    daily_counts[date] = daily_counts.get(date, 0) + 1
                    
                    # Track diseases by date
                    if date not in daily_diseases:
                        daily_diseases[date] = {}
                    
                    disease = data.get("disease_detected", "Unknown")
                    daily_diseases[date][disease] = daily_diseases[date].get(disease, 0) + 1
            
            # Sort dates
            dates = sorted(daily_counts.keys())
            
            return {
                "dates": dates,
                "counts": [daily_counts.get(date, 0) for date in dates],
                "by_disease": daily_diseases
            }
            
        except Exception as e:
            print(f"❌ Error getting trend data: {e}")
            return {"dates": [], "counts": [], "by_disease": {}}
    
    def _get_performance_metrics(self, cutoff: datetime) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            detections_ref = self.db.collection(self.detections_collection)
            
            total_confidence = 0
            total_detections = 0
            response_times = []
            
            for doc in detections_ref.where("timestamp", ">=", cutoff).stream():
                data = doc.to_dict()
                total_detections += 1
                total_confidence += data.get("confidence_score", 0)
                
                # Check if we have metadata with response time
                metadata = data.get("metadata", {})
                if metadata and "response_time_ms" in metadata:
                    response_times.append(metadata["response_time_ms"])
            
            avg_confidence = total_confidence / total_detections if total_detections > 0 else 0
            avg_response = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                "average_confidence": avg_confidence,
                "average_response_time_ms": avg_response,
                "total_processed": total_detections
            }
            
        except Exception as e:
            print(f"❌ Error getting performance metrics: {e}")
            return {}
    
    def save_daily_snapshot(self) -> bool:
        """
        Save daily analytics snapshot
        Returns:
            bool: Success status
        """
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            cutoff = datetime.now() - timedelta(days=1)
            
            snapshot = {
                "date": today,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "users": self._get_user_stats(cutoff),
                "detections": self._get_detection_stats(cutoff),
                "diseases": self._get_disease_breakdown(cutoff)
            }
            
            self.db.collection(self.analytics_collection).document(today).set(snapshot)
            
            print(f"✅ Daily snapshot saved for {today}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving daily snapshot: {e}")
            return False
    
    def get_historical_trends(self, days: int = 90) -> List[Dict[str, Any]]:
        """
        Get historical trends from snapshots
        Args:
            days: Number of days to look back
        Returns:
            List of daily snapshots
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d")
            
            docs = self.db.collection(self.analytics_collection)\
                .where("date", ">=", cutoff_str)\
                .order_by("date")\
                .stream()
            
            trends = []
            for doc in docs:
                trends.append(doc.to_dict())
            
            return trends
            
        except Exception as e:
            print(f"❌ Error getting historical trends: {e}")
            return []