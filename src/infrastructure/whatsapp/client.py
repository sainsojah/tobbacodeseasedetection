"""
WhatsApp Cloud API client wrapper
Handles all communication with WhatsApp
"""
import requests
import time
from typing import Optional, Dict, Any, List
from config.settings import WHATSAPP_TOKEN, PHONE_NUMBER_ID

class WhatsAppClient:
    """Main WhatsApp API client"""
    
    def __init__(self):
        self.token = WHATSAPP_TOKEN
        self.phone_number_id = PHONE_NUMBER_ID
        self.base_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
        
    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def send_text(self, to: str, text: str) -> bool:
        """
        Send a plain text message
        Args:
            to: Recipient phone number
            text: Message text
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            if response.status_code == 200:
                print(f"✅ Message sent to {to}")
                return True
            else:
                print(f"❌ WhatsApp send error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ WhatsApp send exception: {e}")
            return False
    
    def send_image(self, to: str, image_url: str, caption: str = "") -> bool:
        """
        Send an image message
        Args:
            to: Recipient phone number
            image_url: URL of the image
            caption: Optional caption
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": caption
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Image send error: {e}")
            return False
    
    def send_document(self, to: str, document_url: str, filename: str) -> bool:
        """
        Send a document file
        Args:
            to: Recipient phone number
            document_url: URL of the document
            filename: Name to display
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Document send error: {e}")
            return False
    
    def send_audio(self, to: str, audio_url: str) -> bool:
        """
        Send an audio message
        Args:
            to: Recipient phone number
            audio_url: URL of the audio file
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"link": audio_url}
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Audio send error: {e}")
            return False
    
    def send_location(self, to: str, latitude: float, longitude: float, name: str = "") -> bool:
        """
        Send a location message
        Args:
            to: Recipient phone number
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            name: Optional location name
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "location",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": name
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Location send error: {e}")
            return False
    
    def send_contact(self, to: str, contacts: List[Dict]) -> bool:
        """
        Send contact information
        Args:
            to: Recipient phone number
            contacts: List of contact dictionaries
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "contacts",
            "contacts": contacts
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Contact send error: {e}")
            return False
    
    def send_reaction(self, to: str, message_id: str, emoji: str) -> bool:
        """
        React to a message
        Args:
            to: Recipient phone number
            message_id: ID of message to react to
            emoji: Emoji reaction
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "reaction",
            "reaction": {
                "message_id": message_id,
                "emoji": emoji
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Reaction send error: {e}")
            return False
    
    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read
        Args:
            message_id: ID of message to mark as read
        Returns:
            bool: Success status
        """
        self._rate_limit()
        
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Mark read error: {e}")
            return False
    
    def get_media_url(self, media_id: str) -> Optional[str]:
        """
        Get download URL for media
        Args:
            media_id: WhatsApp media ID
        Returns:
            str: Media URL or None
        """
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        
        try:
            response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})
            if response.status_code == 200:
                return response.json().get("url")
            return None
        except Exception as e:
            print(f"❌ Get media URL error: {e}")
            return None
    
    def download_media(self, media_url: str) -> Optional[bytes]:
        """
        Download media from URL
        Args:
            media_url: Media download URL
        Returns:
            bytes: Media content or None
        """
        try:
            response = requests.get(media_url, headers={"Authorization": f"Bearer {self.token}"})
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            print(f"❌ Download media error: {e}")
            return None
    
    def check_health(self) -> bool:
        """
        Check if WhatsApp API is accessible
        Returns:
            bool: True if healthy
        """
        try:
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
            response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})
            return response.status_code == 200
        except:
            return False