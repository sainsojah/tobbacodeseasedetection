"""
Webhook filter middleware
Filters out non-message events (status updates, deliveries, reads)
"""
import json
from typing import Dict, Any, Optional

class WebhookFilter:
    """
    Filter webhook events to process only relevant messages
    Ignores status updates, delivery receipts, and read receipts
    """
    
    # Message types we want to process
    ALLOWED_MESSAGE_TYPES = ['text', 'image']
    
    # Status types to ignore
    IGNORED_STATUSES = ['sent', 'delivered', 'read', 'failed']
    
    @classmethod
    def filter(cls, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Filter webhook data to extract only relevant messages
        Args:
            webhook_data: Raw webhook JSON from WhatsApp
        Returns:
            Filtered message data or None if should be ignored
        """
        try:
            # Log raw webhook for debugging (optional)
            cls._log_webhook(webhook_data)
            
            # Extract entry
            entries = webhook_data.get("entry", [])
            if not entries:
                return None
            
            # Get changes from first entry
            changes = entries[0].get("changes", [])
            if not changes:
                return None
            
            # Get value from first change
            value = changes[0].get("value", {})
            
            # Check if this is a status update
            if "statuses" in value:
                statuses = value.get("statuses", [])
                if statuses:
                    status = statuses[0].get("status")
                    if status in cls.IGNORED_STATUSES:
                        print(f"⏭️ Ignoring {status} status update")
                        return None
            
            # Check for messages
            if "messages" not in value:
                return None
            
            messages = value.get("messages", [])
            if not messages:
                return None
            
            # Get first message
            message = messages[0]
            msg_type = message.get("type")
            
            # Filter by message type
            if msg_type not in cls.ALLOWED_MESSAGE_TYPES:
                print(f"⏭️ Ignoring {msg_type} message (not allowed)")
                return None
            
            # Extract common fields
            from_number = message.get("from")
            msg_id = message.get("id")
            timestamp = message.get("timestamp")
            
            # Extract content based on type
            content = None
            if msg_type == "text":
                content = message.get("text", {}).get("body", "")
            elif msg_type == "image":
                content = message.get("image", {}).get("id", "")
                
                # Also get caption if available
                caption = message.get("image", {}).get("caption", "")
                if caption:
                    content = {
                        "media_id": content,
                        "caption": caption
                    }
            
            # Get context info
            context = message.get("context", {})
            
            # Build filtered data
            filtered = {
                "from": from_number,
                "type": msg_type,
                "content": content,
                "message_id": msg_id,
                "timestamp": timestamp,
                "context": {
                    "forwarded": context.get("forwarded", False),
                    "replied_to": context.get("id") if context else None
                }
            }
            
            # Add contact info if available
            if "contacts" in value:
                contacts = value.get("contacts", [])
                if contacts:
                    profile = contacts[0].get("profile", {})
                    filtered["profile_name"] = profile.get("name")
            
            print(f"✅ Processed {msg_type} message from {from_number}")
            return filtered
            
        except Exception as e:
            print(f"❌ Webhook filter error: {e}")
            return None
    
    @classmethod
    def is_business_message(cls, webhook_data: Dict[str, Any]) -> bool:
        """
        Check if message is from business account (to avoid self-messaging)
        Args:
            webhook_data: Raw webhook data
        Returns:
            True if from business account
        """
        try:
            entries = webhook_data.get("entry", [])
            if not entries:
                return False
            
            changes = entries[0].get("changes", [])
            if not changes:
                return False
            
            value = changes[0].get("value", {})
            metadata = value.get("metadata", {})
            display_phone = metadata.get("display_phone_number")
            
            # Get sender
            if "messages" in value:
                messages = value.get("messages", [])
                if messages:
                    from_number = messages[0].get("from")
                    # Check if sender is the business number
                    return from_number and from_number.replace("+", "") == display_phone.replace("+", "")
            
            return False
            
        except Exception:
            return False
    
    @classmethod
    def _log_webhook(cls, data: Dict[str, Any]):
        """Log webhook data for debugging (optional)"""
        # Uncomment for debugging
        # print(f"📥 Webhook received: {json.dumps(data, indent=2)}")
        pass
    
    @classmethod
    def extract_metadata(cls, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from webhook
        Args:
            webhook_data: Raw webhook data
        Returns:
            Dict with metadata
        """
        try:
            entries = webhook_data.get("entry", [])
            if not entries:
                return {}
            
            changes = entries[0].get("changes", [])
            if not changes:
                return {}
            
            value = changes[0].get("value", {})
            metadata = value.get("metadata", {})
            
            return {
                "phone_number_id": metadata.get("phone_number_id"),
                "display_phone": metadata.get("display_phone_number"),
                "webhook_timestamp": entries[0].get("time")
            }
            
        except Exception as e:
            print(f"❌ Metadata extraction error: {e}")
            return {}


# Convenience function for app.py
def filter_webhook_event(data):
    """Simple wrapper for backward compatibility"""
    return WebhookFilter.filter(data)