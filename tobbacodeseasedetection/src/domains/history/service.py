"""
History service - handles scan history display
"""
from typing import Dict, Any, List
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.database.detection_repository import DetectionRepository

class HistoryService:
    """Handle user scan history"""
    
    def __init__(self, 
                 detection_repo: DetectionRepository,
                 whatsapp: WhatsAppClient):
        
        self.detection_repo = detection_repo
        self.whatsapp = whatsapp
    
    def show_history(self, phone_number: str, user: Dict, limit: int = 5) -> Dict[str, Any]:
        """
        Show user's scan history
        Args:
            phone_number: User's phone number
            user: User data dict
            limit: Number of scans to show
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Get history from repository
        history = self.detection_repo.get_user_history(phone_number, limit)
        
        if not history:
            # No history found
            message = (
                f"📋 *Scan History*\n\n"
                f"👤 {user_name}, you have no previous scans.\n\n"
                f"Send a photo of a tobacco leaf to start detecting diseases!\n\n"
                f"---\n0️⃣ Main Menu"
            )
            self.whatsapp.send_text(phone_number, message)
            return {"status": "ok", "action": "no_history"}
        
        # Build history message
        message = self._format_history(history, user_name)
        self.whatsapp.send_text(phone_number, message)
        
        return {"status": "ok", "action": "history_shown"}
    
    def _format_history(self, history: List[Dict], user_name: str) -> str:
        """Format history records into message"""
        
        lines = [
            "📋 *SCAN HISTORY*",
            f"👤 *Farmer:* {user_name}",
            f"📊 *Showing last {len(history)} scans*",
            ""
        ]
        
        for i, scan in enumerate(history, 1):
            # Get disease with emoji
            disease = scan.get('disease_detected', 'Unknown')
            confidence = scan.get('confidence_score', 0)
            date = scan.get('display_date', scan.get('date', 'Unknown date'))
            
            # Add emoji based on disease
            if disease == "Healthy":
                emoji = "🌿"
            elif confidence >= 70:
                emoji = "🔴"
            elif confidence >= 45:
                emoji = "🟠"
            else:
                emoji = "🟡"
            
            # Format line
            lines.append(f"{i}. {emoji} *{disease}*")
            lines.append(f"   📈 {confidence:.1f}% confidence")
            lines.append(f"   🕐 {date}")
            lines.append("")
        
        # Add summary stats
        total_scans = len(history)
        healthy_count = sum(1 for s in history if s.get('disease_detected') == "Healthy")
        disease_count = total_scans - healthy_count
        
        lines.append("📊 *Summary:*")
        lines.append(f"• Total scans: {total_scans}")
        lines.append(f"• Diseases detected: {disease_count}")
        lines.append(f"• Healthy leaves: {healthy_count}")
        
        # Add navigation
        lines.append("")
        lines.append("---")
        lines.append("0️⃣ Main Menu  |  9️⃣ Refresh")
        
        return '\n'.join(lines)
    
    def show_detailed_scan(self, phone_number: str, scan_index: int, user: Dict) -> Dict[str, Any]:
        """
        Show detailed information for a specific scan
        Args:
            phone_number: User's phone number
            scan_index: Index of scan (1-based)
            user: User data dict
        Returns:
            Response dict
        """
        # Get history
        history = self.detection_repo.get_user_history(phone_number, 10)
        
        if not history or scan_index < 1 or scan_index > len(history):
            self.whatsapp.send_text(
                phone_number,
                f"❌ Scan #{scan_index} not found. Please try again."
            )
            return {"status": "ok"}
        
        # Get specific scan
        scan = history[scan_index - 1]
        
        # Build detailed message
        message = self._format_detailed_scan(scan, scan_index)
        self.whatsapp.send_text(phone_number, message)
        
        return {"status": "ok", "action": "detailed_scan_shown"}
    
    def _format_detailed_scan(self, scan: Dict, index: int) -> str:
        """Format detailed scan information"""
        
        disease = scan.get('disease_detected', 'Unknown')
        confidence = scan.get('confidence_score', 0)
        date = scan.get('display_date', scan.get('date', 'Unknown'))
        
        # Get metadata if available
        metadata = scan.get('metadata', {})
        inference_time = metadata.get('inference_time_ms', 'N/A')
        
        message = (
            f"📋 *SCAN DETAILS #{index}*\n\n"
            f"*Disease:* {disease}\n"
            f"*Confidence:* {confidence:.1f}%\n"
            f"*Date:* {date}\n"
            f"*Analysis Time:* {inference_time}ms\n\n"
        )
        
        # Show other predictions if available
        if metadata.get('all_predictions'):
            message += "*Other possibilities:*\n"
            for i, pred in enumerate(metadata['all_predictions'][1:3], 1):
                if pred:
                    message += f"  {i}. {pred.get('class')} ({pred.get('confidence', 0)*100:.1f}%)\n"
            message += "\n"
        
        message += "---\n0️⃣ Main Menu  |  9️⃣ Back to History"
        
        return message
    
    def get_history_stats(self, phone_number: str) -> Dict[str, Any]:
        """
        Get statistics from user's history
        Args:
            phone_number: User's phone number
        Returns:
            Dict with statistics
        """
        return self.detection_repo.get_user_detection_summary(phone_number)
    
    def clear_history(self, phone_number: str) -> bool:
        """
        Clear user's history (admin function)
        Args:
            phone_number: User's phone number
        Returns:
            bool: Success status
        """
        # This would need a method in detection_repo to delete user's history
        # For now, return False
        return False