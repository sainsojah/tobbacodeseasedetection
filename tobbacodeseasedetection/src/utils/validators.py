"""
Input validation utilities
"""
import re
from typing import Tuple, Optional, Any

class Validators:
    """Input validation functions"""
    
    @staticmethod
    def phone_number(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number
        Args:
            phone: Phone number to validate
        Returns:
            (is_valid, formatted_number or error)
        """
        if not phone:
            return False, "Phone number is required"
        
        # Remove any non-digit characters
        cleaned = re.sub(r'\D', '', phone)
        
        # Check length (Zimbabwe: 10 digits after 0, or 12 with 263)
        if len(cleaned) < 10 or len(cleaned) > 12:
            return False, "Invalid phone number length"
        
        # Format to international if needed
        if cleaned.startswith('0'):
            formatted = '263' + cleaned[1:]
        elif cleaned.startswith('263'):
            formatted = cleaned
        else:
            formatted = '263' + cleaned
        
        return True, formatted
    
    @staticmethod
    def name(name: str) -> Tuple[bool, Optional[str]]:
        """Validate user name"""
        if not name:
            return False, "Name is required"
        
        name = name.strip()
        
        if len(name) < 2:
            return False, "Name too short (min 2 characters)"
        
        if len(name) > 50:
            return False, "Name too long (max 50 characters)"
        
        # Allow letters, spaces, hyphens, apostrophes
        if not re.match(r'^[A-Za-z\s\'-]+$', name):
            return False, "Name contains invalid characters"
        
        return True, name.title()
    
    @staticmethod
    def email(email: str) -> Tuple[bool, Optional[str]]:
        """Validate email address"""
        if not email:
            return False, "Email is required"
        
        email = email.strip().lower()
        
        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        return True, email
    
    @staticmethod
    def age(age: Any) -> Tuple[bool, Optional[int]]:
        """Validate age"""
        try:
            age = int(age)
            if 18 <= age <= 100:
                return True, age
            return False, "Age must be between 18 and 100"
        except:
            return False, "Invalid age format"
    
    @staticmethod
    def language(lang: str) -> bool:
        """Validate language code"""
        return lang in ['en', 'sn', 'nd']
    
    @staticmethod
    def message_length(text: str, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
        """Validate message length"""
        if not text:
            return False, "Message is empty"
        
        if len(text) > max_length:
            return False, f"Message too long (max {max_length} characters)"
        
        return True, None
    
    @staticmethod
    def menu_selection(selection: str, max_option: int) -> Tuple[bool, Optional[int]]:
        """Validate menu selection"""
        if not selection.isdigit():
            return False, "Please enter a number"
        
        num = int(selection)
        if 0 <= num <= max_option:
            return True, num
        else:
            return False, f"Please enter a number between 0 and {max_option}"
    
    @staticmethod
    def disease_name(disease: str) -> Tuple[bool, Optional[str]]:
        """Validate disease name"""
        if not disease:
            return False, "Disease name is required"
        
        # List of valid diseases from constants
        valid_diseases = [
            "Black Spot", "Black Shank", "Early Blight", "Late Blight",
            "Leaf Mold", "Leaf Spot", "Powdery Mildew", "Septoria Blight",
            "Tobacco Cillium Virus", "Tobacco Cillium TMDL",
            "Yellow Leaf Spot", "Spider Mites", "Healthy"
        ]
        
        # Case-insensitive match
        for valid in valid_diseases:
            if disease.lower() == valid.lower():
                return True, valid
        
        return False, f"Unknown disease. Type 'diseases' to see list."
    
    @staticmethod
    def confidence_score(score: float) -> bool:
        """Validate confidence score"""
        return 0 <= score <= 100
    
    @staticmethod
    def is_positive_integer(value: Any) -> bool:
        """Check if value is positive integer"""
        try:
            return int(value) > 0
        except:
            return False
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid"""
        pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text:
            return ""
        
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Remove multiple spaces
        text = ' '.join(text.split())
        
        return text.strip()