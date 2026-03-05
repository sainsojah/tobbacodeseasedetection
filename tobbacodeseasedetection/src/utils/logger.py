"""
Logging utility
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional

class Logger:
    """Application logger"""
    
    _instances = {}
    
    def __new__(cls, name="app", log_dir="logs"):
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._initialize(name, log_dir)
            cls._instances[name] = instance
        return cls._instances[name]
    
    def _initialize(self, name: str, log_dir: str):
        """Initialize logger"""
        self.name = name
        self.log_dir = log_dir
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # File handler (rotating)
        log_file = os.path.join(log_dir, f"{name}.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5  # 10MB
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, extra: Optional[dict] = None):
        """Log debug message"""
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, extra: Optional[dict] = None):
        """Log info message"""
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, extra: Optional[dict] = None):
        """Log warning message"""
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, extra: Optional[dict] = None):
        """Log error message"""
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, extra: Optional[dict] = None):
        """Log critical message"""
        self.logger.critical(message, extra=extra)
    
    def log_request(self, method: str, path: str, ip: str, status: int, duration: float):
        """Log HTTP request"""
        self.info(
            f"Request: {method} {path} - {status} - {duration:.3f}s",
            extra={"ip": ip, "method": method, "path": path, "status": status, "duration": duration}
        )
    
    def log_whatsapp(self, direction: str, to: str, message_type: str, status: str):
        """Log WhatsApp message"""
        self.info(
            f"WhatsApp {direction}: to={to}, type={message_type}, status={status}",
            extra={"direction": direction, "to": to, "type": message_type, "status": status}
        )
    
    def log_detection(self, user: str, disease: str, confidence: float, time_ms: float):
        """Log disease detection"""
        self.info(
            f"Detection: user={user}, disease={disease}, conf={confidence:.1f}%, time={time_ms:.0f}ms",
            extra={"user": user, "disease": disease, "confidence": confidence, "time_ms": time_ms}
        )


# Simple function logger decorator
def log_function(logger: Logger):
    """Decorator to log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} completed")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed: {str(e)}")
                raise
        return wrapper
    return decorator