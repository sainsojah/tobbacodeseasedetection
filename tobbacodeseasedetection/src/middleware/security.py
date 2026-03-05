"""
Security middleware
Handles webhook verification, request validation, and basic security
"""
import hmac
import hashlib
from typing import Dict, Any, Optional
from config.settings import VERIFY_TOKEN, WHATSAPP_TOKEN

class SecurityMiddleware:
    """Security checks and validation"""
    
    @staticmethod
    def verify_webhook_token(mode: str, token: str) -> bool:
        """
        Verify webhook token for Facebook/WhatsApp
        Args:
            mode: Should be "subscribe"
            token: Verify token
        Returns:
            bool: True if valid
        """
        return mode == "subscribe" and token == VERIFY_TOKEN
    
    @staticmethod
    def validate_webhook_signature(signature: str, body: bytes, app_secret: str) -> bool:
        """
        Validate webhook signature (for production)
        Args:
            signature: X-Hub-Signature-256 header
            body: Request body
            app_secret: Facebook App Secret
        Returns:
            bool: True if signature valid
        """
        if not signature or not body:
            return False
        
        # Expected format: sha256=hashvalue
        if not signature.startswith("sha256="):
            return False
        
        # Extract hash
        expected_hash = signature.split("=")[1]
        
        # Compute HMAC
        computed_hash = hmac.new(
            key=app_secret.encode('utf-8'),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Compare in constant time
        return hmac.compare_digest(computed_hash, expected_hash)
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitize user input
        Args:
            text: Raw input text
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove any control characters
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())
        
        # Limit length
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]
        
        return sanitized
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """
        Validate phone number format
        Args:
            phone: Phone number
        Returns:
            bool: True if valid
        """
        if not phone:
            return False
        
        # Remove any non-digit characters
        cleaned = ''.join(char for char in phone if char.isdigit())
        
        # Check length (international format)
        return 10 <= len(cleaned) <= 15
    
    @staticmethod
    def validate_message_content(content: Any, msg_type: str) -> bool:
        """
        Validate message content
        Args:
            content: Message content
            msg_type: Message type
        Returns:
            bool: True if valid
        """
        if msg_type == "text":
            return isinstance(content, str) and len(content.strip()) > 0
        
        elif msg_type == "image":
            if isinstance(content, dict):
                return "media_id" in content
            return isinstance(content, str) and len(content) > 0
        
        return False
    
    @staticmethod
    def extract_ip_address(request) -> Optional[str]:
        """
        Extract client IP address from request
        Args:
            request: Flask request object
        Returns:
            IP address or None
        """
        # Check for forwarded headers
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        # Direct IP
        return request.remote_addr
    
    @staticmethod
    def is_allowed_ip(ip_address: str, allowed_ips: list) -> bool:
        """
        Check if IP is allowed (for admin functions)
        Args:
            ip_address: IP to check
            allowed_ips: List of allowed IPs
        Returns:
            bool: True if allowed
        """
        if not allowed_ips:
            return True  # No restrictions
        
        return ip_address in allowed_ips
    
    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """
        Mask phone number for logging
        Args:
            phone: Full phone number
        Returns:
            Masked number (e.g., +263******123)
        """
        if not phone or len(phone) < 8:
            return "****"
        
        # Show first 4 and last 3 digits
        return phone[:4] + "****" + phone[-3:]
    
    @staticmethod
    def create_csrf_token() -> str:
        """Create CSRF token for forms"""
        import secrets
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_csrf_token(token: str, session_token: str) -> bool:
        """Validate CSRF token"""
        return hmac.compare_digest(token, session_token)


# Request validator
class RequestValidator:
    """Validate incoming requests"""
    
    @staticmethod
    def validate_whatsapp_request(request) -> Tuple[bool, Optional[str]]:
        """
        Validate WhatsApp webhook request
        Args:
            request: Flask request object
        Returns:
            (valid, error_message)
        """
        # Check method
        if request.method not in ['GET', 'POST']:
            return False, "Invalid method"
        
        # For GET requests (webhook verification)
        if request.method == 'GET':
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            
            if SecurityMiddleware.verify_webhook_token(mode, token):
                return True, None
            else:
                return False, "Invalid verification token"
        
        # For POST requests
        elif request.method == 'POST':
            # Check content type
            if not request.is_json:
                return False, "Content-Type must be application/json"
            
            # Check for required headers
            # In production, also validate signature here
            
            return True, None
    
    @staticmethod
    def get_request_summary(request) -> Dict[str, Any]:
        """
        Get summary of request for logging
        Args:
            request: Flask request object
        Returns:
            Dict with request info
        """
        return {
            "method": request.method,
            "path": request.path,
            "ip": SecurityMiddleware.extract_ip_address(request),
            "user_agent": request.headers.get('User-Agent'),
            "content_type": request.content_type,
            "content_length": request.content_length
        }