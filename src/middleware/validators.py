"""
Input validators middleware
Validates all incoming data before processing
"""
import re
from typing import Dict, Any, Tuple, Optional

class InputValidator:
    """Validate all user inputs"""
    
    @staticmethod
    def validate_text(text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate text message
        Args:
            text: Text to validate
        Returns:
            (valid, error_message)
        """
        if not text:
            return False, "Empty message"
        
        if len(text) > 1000:
            return False, "Message too long (max 1000 characters)"
        
        if len(text.strip()) == 0:
            return False, "Message contains only whitespace"
        
        # Check for excessive emojis (spam)
        emoji_count = len(re.findall(r'[^\w\s,]', text))
        if emoji_count > 10 and len(text) < 50:
            return False, "Message appears to be spam"
        
        return True, None
    
    @staticmethod
    def validate_command(command: str, valid_commands: list) -> bool:
        """
        Validate command against list
        Args:
            command: Command to validate
            valid_commands: List of valid commands
        Returns:
            True if valid
        """
        return command.lower() in valid_commands
    
    @staticmethod
    def validate_menu_selection(selection: str, max_option: int) -> bool:
        """
        Validate menu selection
        Args:
            selection: User's selection
            max_option: Maximum valid option number
        Returns:
            True if valid
        """
        if not selection.isdigit():
            return False
        
        num = int(selection)
        return 0 <= num <= max_option
    
    @staticmethod
    def validate_image_media(media_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image media ID
        Args:
            media_id: WhatsApp media ID
        Returns:
            (valid, error_message)
        """
        if not media_id:
            return False, "No media ID provided"
        
        if len(media_id) > 100:
            return False, "Invalid media ID format"
        
        # Media IDs are typically alphanumeric
        if not re.match(r'^[a-zA-Z0-9_-]+$', media_id):
            return False, "Invalid media ID format"
        
        return True, None
    
    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number
        Args:
            phone: Phone number
        Returns:
            (valid, error_message)
        """
        if not phone:
            return False, "No phone number"
        
        # Remove any non-digit characters
        cleaned = re.sub(r'\D', '', phone)
        
        # Check length (international format)
        if len(cleaned) < 10 or len(cleaned) > 15:
            return False, "Invalid phone number length"
        
        return True, None
    
    @staticmethod
    def validate_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user name
        Args:
            name: User's name
        Returns:
            (valid, error_message)
        """
        if not name:
            return False, "Name is required"
        
        if len(name) < 2:
            return False, "Name too short"
        
        if len(name) > 50:
            return False, "Name too long"
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z\s\'-]+$', name):
            return False, "Name contains invalid characters"
        
        return True, None
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email address
        Args:
            email: Email to validate
        Returns:
            (valid, error_message)
        """
        if not email:
            return False, "Email is required"
        
        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        return True, None
    
    @staticmethod
    def validate_language(lang: str) -> bool:
        """
        Validate language code
        Args:
            lang: Language code
        Returns:
            True if valid
        """
        return lang in ['en', 'sn', 'nd']
    
    @staticmethod
    def validate_feedback(feedback: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user feedback
        Args:
            feedback: Feedback text
        Returns:
            (valid, error_message)
        """
        if not feedback:
            return False, "Feedback is empty"
        
        if len(feedback) < 5:
            return False, "Feedback too short (min 5 characters)"
        
        if len(feedback) > 1000:
            return False, "Feedback too long (max 1000 characters)"
        
        return True, None
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitize user input
        Args:
            text: Raw input
        Returns:
            Sanitized text
        """
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Trim
        return text.strip()
    
    @staticmethod
    def extract_number(text: str) -> Optional[int]:
        """
        Extract number from text
        Args:
            text: Text containing number
        Returns:
            Extracted number or None
        """
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        return None


# Webhook data validator
class WebhookValidator:
    """Validate webhook data structure"""
    
    @staticmethod
    def validate_webhook_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate webhook data structure
        Args:
            data: Webhook JSON data
        Returns:
            (valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Invalid data format"
        
        if "entry" not in data:
            return False, "Missing 'entry' field"
        
        entries = data.get("entry", [])
        if not entries or not isinstance(entries, list):
            return False, "Invalid 'entry' field"
        
        entry = entries[0]
        if "changes" not in entry:
            return False, "Missing 'changes' field"
        
        changes = entry.get("changes", [])
        if not changes or not isinstance(changes, list):
            return False, "Invalid 'changes' field"
        
        change = changes[0]
        if "value" not in change:
            return False, "Missing 'value' field"
        
        return True, None
    
    @staticmethod
    def validate_message(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate message structure
        Args:
            data: Message data
        Returns:
            (valid, error_message)
        """
        value = data.get("value", {})
        
        if "messages" not in value:
            return False, "No messages in payload"
        
        messages = value.get("messages", [])
        if not messages:
            return False, "Empty messages array"
        
        message = messages[0]
        if "type" not in message:
            return False, "Missing message type"
        
        if "from" not in message:
            return False, "Missing sender"
        
        return True, None