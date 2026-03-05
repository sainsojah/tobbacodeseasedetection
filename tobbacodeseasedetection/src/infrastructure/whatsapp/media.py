"""
Media handling utilities for WhatsApp
"""
import os
import tempfile
from typing import Optional, Tuple
from .client import WhatsAppClient

class MediaHandler:
    """Handle media downloads and processing"""
    
    def __init__(self):
        self.client = WhatsAppClient()
        self.temp_dir = tempfile.gettempdir()
    
    def download_image(self, media_id: str) -> Optional[bytes]:
        """
        Download image by media ID
        Args:
            media_id: WhatsApp media ID
        Returns:
            bytes: Image content or None
        """
        media_url = self.client.get_media_url(media_id)
        if not media_url:
            return None
        
        return self.client.download_media(media_url)
    
    def get_image_info(self, media_id: str) -> Optional[dict]:
        """
        Get image metadata
        Args:
            media_id: WhatsApp media ID
        Returns:
            dict: Image info or None
        """
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        
        try:
            response = requests.get(
                url, 
                headers={"Authorization": f"Bearer {self.client.token}"}
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data.get("id"),
                    "mime_type": data.get("mime_type"),
                    "file_size": data.get("file_size"),
                    "sha256": data.get("sha256")
                }
            return None
        except:
            return None
    
    def save_temp_image(self, media_id: str) -> Optional[str]:
        """
        Download image and save to temp file
        Args:
            media_id: WhatsApp media ID
        Returns:
            str: Path to temp file or None
        """
        image_bytes = self.download_image(media_id)
        if not image_bytes:
            return None
        
        temp_path = os.path.join(self.temp_dir, f"wa_{media_id}.jpg")
        try:
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            return temp_path
        except:
            return None
    
    def cleanup_temp_file(self, file_path: str):
        """Delete temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass