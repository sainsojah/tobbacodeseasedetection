"""
General helper functions
"""
import random
import string
import hashlib
from typing import List, Dict, Any, Optional
import json

class Helpers:
    """General helper functions"""
    
    @staticmethod
    def generate_id(length: int = 8) -> str:
        """Generate random ID"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate numeric OTP"""
        return ''.join(random.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def hash_string(text: str) -> str:
        """Create SHA-256 hash of string"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to max length"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def chunk_list(items: List, chunk_size: int) -> List[List]:
        """Split list into chunks"""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    @staticmethod
    def safe_get(data: Dict, path: str, default: Any = None) -> Any:
        """
        Safely get nested dict value using dot notation
        Example: safe_get(user, 'profile.name', 'Unknown')
        """
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    @staticmethod
    def parse_bool(value: Any) -> bool:
        """Parse various inputs to boolean"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', 'yes', '1', 'y', 'on']
        if isinstance(value, (int, float)):
            return value != 0
        return bool(value)
    
    @staticmethod
    def format_number(num: float, decimals: int = 2) -> str:
        """Format number with thousand separators"""
        return f"{num:,.{decimals}f}"
    
    @staticmethod
    def safe_json_loads(text: str, default: Any = None) -> Any:
        """Safely load JSON"""
        try:
            return json.loads(text)
        except:
            return default
    
    @staticmethod
    def remove_emoji(text: str) -> str:
        """Remove emojis from text"""
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', text)
    
    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        """Extract @mentions from text"""
        return re.findall(r'@(\w+)', text)
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extract #hashtags from text"""
        return re.findall(r'#(\w+)', text)
    
    @staticmethod
    def mask_sensitive(text: str, visible_chars: int = 4) -> str:
        """Mask sensitive data (like API keys)"""
        if len(text) <= visible_chars:
            return '*' * len(text)
        return text[:visible_chars] + '*' * (len(text) - visible_chars)
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension"""
        return filename.split('.')[-1].lower() if '.' in filename else ''
    
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """Check if file is image"""
        ext = Helpers.get_file_extension(filename)
        return ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    
    @staticmethod
    def format_bytes(size_bytes: int) -> str:
        """Format bytes to human readable"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    @staticmethod
    def time_function(func):
        """Decorator to time function execution"""
        def wrapper(*args, **kwargs):
            import time
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print(f"{func.__name__} took {end - start:.3f}s")
            return result
        return wrapper


# WhatsApp specific helpers
class WhatsAppHelpers:
    """WhatsApp-specific helper functions"""
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number for WhatsApp"""
        # Remove any non-digit characters
        cleaned = re.sub(r'\D', '', phone)
        
        # Ensure it has country code
        if cleaned.startswith('0'):
            cleaned = '263' + cleaned[1:]
        elif not cleaned.startswith('263'):
            cleaned = '263' + cleaned
        
        return cleaned
    
    @staticmethod
    def clean_phone(phone: str) -> str:
        """Clean phone number for storage"""
        return re.sub(r'\D', '', phone)
    
    @staticmethod
    def extract_media_id(message: Dict) -> Optional[str]:
        """Extract media ID from message"""
        if message.get('type') == 'image':
            return message.get('image', {}).get('id')
        return None
    
    @staticmethod
    def extract_caption(message: Dict) -> str:
        """Extract caption from image message"""
        if message.get('type') == 'image':
            return message.get('image', {}).get('caption', '')
        return ''