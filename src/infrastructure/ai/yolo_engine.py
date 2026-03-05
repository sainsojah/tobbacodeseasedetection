"""
YOLO model engine for disease detection
"""
import os
import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Any, Optional
from config.settings import MODEL_PATH
from core.constants import DISEASE_CLASSES

class YOLOEngine:
    """YOLO model wrapper for inference"""
    
    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.class_names = []
        self.load_model()
    
    def load_model(self) -> bool:
        """
        Load YOLO model from file
        Returns:
            bool: Success status
        """
        try:
            if not os.path.exists(self.model_path):
                print(f"❌ Model not found at {self.model_path}")
                return False
            
            self.model = YOLO(self.model_path)
            self.class_names = self.model.names
            print(f"✅ YOLO model loaded from {self.model_path}")
            print(f"📊 Classes: {len(self.class_names)}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading YOLO model: {e}")
            return False
    
    def predict(self, image_bytes: bytes, conf_threshold: float = 0.25) -> List[Dict[str, Any]]:
        """
        Run inference on image bytes
        Args:
            image_bytes: Raw image bytes
            conf_threshold: Confidence threshold (0-1)
        Returns:
            List of predictions with class, confidence, bbox
        """
        if self.model is None:
            print("❌ Model not loaded")
            return []
        
        try:
            # Convert bytes to image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print("❌ Failed to decode image")
                return []
            
            # Run inference
            results = self.model(img, conf=conf_threshold)
            
            predictions = []
            if len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    class_name = self.class_names[class_id]
                    confidence = float(box.conf[0])
                    
                    # Get bounding box coordinates
                    xyxy = box.xyxy[0].tolist()
                    
                    predictions.append({
                        'class': class_name,
                        'class_id': class_id,
                        'confidence': confidence,
                        'bbox': {
                            'x1': xyxy[0],
                            'y1': xyxy[1],
                            'x2': xyxy[2],
                            'y2': xyxy[3]
                        }
                    })
            
            # Sort by confidence (highest first)
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return predictions
            
        except Exception as e:
            print(f"❌ Inference error: {e}")
            return []
    
    def predict_batch(self, image_paths: List[str], conf_threshold: float = 0.25) -> List[List[Dict]]:
        """
        Run inference on multiple images
        Args:
            image_paths: List of image file paths
            conf_threshold: Confidence threshold
        Returns:
            List of predictions for each image
        """
        if self.model is None:
            return []
        
        try:
            results = self.model(image_paths, conf=conf_threshold)
            
            all_predictions = []
            for result in results:
                image_preds = []
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        class_name = self.class_names[class_id]
                        confidence = float(box.conf[0])
                        
                        image_preds.append({
                            'class': class_name,
                            'class_id': class_id,
                            'confidence': confidence,
                            'bbox': box.xyxy[0].tolist()
                        })
                
                image_preds.sort(key=lambda x: x['confidence'], reverse=True)
                all_predictions.append(image_preds)
            
            return all_predictions
            
        except Exception as e:
            print(f"❌ Batch inference error: {e}")
            return [[] for _ in image_paths]
    
    def get_top_prediction(self, image_bytes: bytes) -> Optional[Dict]:
        """
        Get highest confidence prediction only
        Args:
            image_bytes: Raw image bytes
        Returns:
            Top prediction or None
        """
        predictions = self.predict(image_bytes)
        if predictions:
            return predictions[0]
        return None
    
    def map_class_name(self, class_name: str) -> str:
        """
        Map model class names to standard names
        Args:
            class_name: Raw class name from model
        Returns:
            Mapped/cleaned class name
        """
        mappings = {
            "from Yellow Leaf Spot": "Yellow Leaf Spot",
            "Tobacco Cillium Virus": "Tobacco Mosaic Virus",
            "Tobacco Cillium TMDL": "Tobacco Virus Complex"
        }
        return mappings.get(class_name, class_name)
    
    def get_class_id(self, class_name: str) -> Optional[int]:
        """Get class ID by name"""
        for idx, name in self.class_names.items():
            if name.lower() == class_name.lower():
                return idx
        return None
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_model_info(self) -> Dict:
        """Get model information"""
        return {
            "loaded": self.is_loaded(),
            "path": self.model_path,
            "num_classes": len(self.class_names),
            "classes": list(self.class_names.values()) if self.class_names else []
        }