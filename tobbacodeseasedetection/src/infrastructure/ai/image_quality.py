"""
Image quality validation and preprocessing
"""
import cv2
import numpy as np
from typing import Tuple, Dict
from core.constants import MIN_IMAGE_SIZE, MAX_IMAGE_SIZE

class ImageQualityChecker:
    """Check and validate image quality"""
    
    @staticmethod
    def validate(image_bytes: bytes) -> Tuple[bool, str, Dict]:
        """
        Validate image quality
        Args:
            image_bytes: Raw image bytes
        Returns:
            (is_valid, message, details)
        """
        details = {
            "size": len(image_bytes),
            "format": "unknown",
            "dimensions": (0, 0),
            "blur_score": 0,
            "brightness": 0
        }
        
        # Check file size
        if len(image_bytes) < MIN_IMAGE_SIZE:
            return False, "❌ Image too small. Please send a clearer photo.", details
        
        if len(image_bytes) > MAX_IMAGE_SIZE:
            return False, "❌ Image too large. Maximum size is 16MB.", details
        
        # Decode image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return False, "❌ Invalid image format. Please send JPG or PNG.", details
        
        # Get image properties
        height, width = img.shape[:2]
        details["dimensions"] = (width, height)
        details["format"] = "color"
        
        # Check resolution
        if height < 200 or width < 200:
            return False, "❌ Image resolution too low. Please take a closer photo.", details
        
        # Check aspect ratio (should not be too extreme)
        aspect_ratio = width / height
        if aspect_ratio > 3 or aspect_ratio < 0.33:
            return False, "❌ Unusual image proportions. Please retake.", details
        
        # Check brightness
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        details["brightness"] = brightness
        
        if brightness < 40:
            return False, "❌ Image too dark. Please use better lighting.", details
        if brightness > 220:
            return False, "❌ Image too bright. Avoid overexposure.", details
        
        # Check blurriness using Laplacian variance
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        details["blur_score"] = blur_score
        
        if blur_score < 100:
            return False, "❌ Image is too blurry. Please hold camera steady.", details
        
        # All checks passed
        return True, "✅ Image quality acceptable", details
    
    @staticmethod
    def preprocess(image_bytes: bytes, target_size: Tuple[int, int] = (640, 640)) -> Optional[np.ndarray]:
        """
        Preprocess image for model input
        Args:
            image_bytes: Raw image bytes
            target_size: Desired dimensions (width, height)
        Returns:
            Preprocessed image or None
        """
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            # Resize
            img = cv2.resize(img, target_size)
            
            # Normalize (if needed)
            img = img.astype(np.float32) / 255.0
            
            return img
            
        except Exception as e:
            print(f"❌ Preprocessing error: {e}")
            return None
    
    @staticmethod
    def enhance(image_bytes: bytes) -> Optional[bytes]:
        """
        Enhance image quality (optional)
        Args:
            image_bytes: Raw image bytes
        Returns:
            Enhanced image bytes or None
        """
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            # Apply slight sharpening
            kernel = np.array([[-1,-1,-1],
                               [-1, 9,-1],
                               [-1,-1,-1]])
            img = cv2.filter2D(img, -1, kernel)
            
            # Adjust contrast
            img = cv2.convertScaleAbs(img, alpha=1.1, beta=10)
            
            # Encode back to bytes
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return buffer.tobytes()
            
        except Exception as e:
            print(f"❌ Enhancement error: {e}")
            return None
    
    @staticmethod
    def get_quality_report(image_bytes: bytes) -> Dict:
        """Get detailed quality report"""
        is_valid, message, details = ImageQualityChecker.validate(image_bytes)
        
        report = {
            "valid": is_valid,
            "message": message,
            **details
        }
        
        # Add recommendations
        if not is_valid:
            if details["blur_score"] < 100:
                report["recommendation"] = "Hold camera steady and ensure good focus"
            elif details["brightness"] < 40:
                report["recommendation"] = "Add more light or use flash"
            elif details["brightness"] > 220:
                report["recommendation"] = "Avoid direct sunlight, find shade"
            elif details["dimensions"][0] < 200:
                report["recommendation"] = "Move closer to the leaf"
        
        return report