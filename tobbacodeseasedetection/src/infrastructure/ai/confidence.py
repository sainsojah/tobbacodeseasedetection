"""
Confidence scoring and grading utilities
"""
from typing import Tuple, Dict
from core.constants import ConfidenceLevel

class ConfidenceGrader:
    """Grade confidence scores and provide recommendations"""
    
    @staticmethod
    def grade(confidence: float) -> Dict[str, any]:
        """
        Grade confidence score
        Args:
            confidence: Confidence score (0-1)
        Returns:
            Dict with level, emoji, message, action
        """
        confidence_pct = confidence * 100
        
        if confidence < ConfidenceLevel.REJECT.value:
            return {
                "level": "REJECT",
                "emoji": "❌",
                "label": "Too Low",
                "message": "Image quality too low for reliable detection",
                "action": "Please send a clearer photo with better lighting",
                "threshold": "below 45%"
            }
        
        elif confidence < ConfidenceLevel.MODERATE.value:
            return {
                "level": "MODERATE",
                "emoji": "⚠️",
                "label": "Moderate",
                "message": f"Moderate confidence ({confidence_pct:.1f}%)",
                "action": "Please verify manually or retake photo",
                "threshold": "45-60%"
            }
        
        else:
            return {
                "level": "HIGH",
                "emoji": "✅",
                "label": "High",
                "message": f"High confidence ({confidence_pct:.1f}%)",
                "action": "Reliable detection - proceed with treatment",
                "threshold": "above 60%"
            }
    
    @staticmethod
    def should_reject(confidence: float) -> bool:
        """Check if confidence is too low"""
        return confidence < ConfidenceLevel.REJECT.value
    
    @staticmethod
    def is_reliable(confidence: float) -> bool:
        """Check if confidence is reliable enough"""
        return confidence >= ConfidenceLevel.MODERATE.value
    
    @staticmethod
    def is_high_confidence(confidence: float) -> bool:
        """Check if confidence is high"""
        return confidence >= ConfidenceLevel.HIGH.value
    
    @staticmethod
    def get_confidence_color(confidence: float) -> str:
        """Get color code for confidence display"""
        if confidence < 0.45:
            return "🔴"  # Red
        elif confidence < 0.60:
            return "🟡"  # Yellow
        else:
            return "🟢"  # Green
    
    @staticmethod
    def get_recommendation(confidence: float, disease: str) -> str:
        """Get recommendation based on confidence"""
        grade = ConfidenceGrader.grade(confidence)
        
        if grade["level"] == "REJECT":
            return "📸 Please take another photo with:\n• Better lighting\n• Closer view\n• Less blur"
        
        elif grade["level"] == "MODERATE":
            return "👨‍🌾 Please verify with local expert or send another photo"
        
        else:
            if disease == "Healthy":
                return "👍 Keep up the good work! Continue monitoring."
            else:
                return "🧪 Apply recommended treatment and monitor progress"