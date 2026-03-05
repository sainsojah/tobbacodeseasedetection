"""
Date and time utilities
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time

class DateTimeUtils:
    """Helper functions for date and time operations"""
    
    @staticmethod
    def now() -> datetime:
        """Get current datetime"""
        return datetime.now()
    
    @staticmethod
    def timestamp() -> float:
        """Get current timestamp"""
        return time.time()
    
    @staticmethod
    def format_date(date: datetime, format: str = "%d %b %Y") -> str:
        """
        Format date for display
        Args:
            date: Datetime object
            format: Strftime format
        Returns:
            Formatted date string
        """
        if not date:
            return "Unknown"
        
        try:
            if hasattr(date, 'strftime'):
                return date.strftime(format)
            return str(date)
        except:
            return "Unknown"
    
    @staticmethod
    def format_datetime(date: datetime) -> str:
        """Format datetime for display"""
        return DateTimeUtils.format_date(date, "%d %b %Y, %H:%M")
    
    @staticmethod
    def format_time_ago(date: datetime) -> str:
        """
        Format as relative time (e.g., "2 hours ago")
        Args:
            date: Datetime object
        Returns:
            Relative time string
        """
        if not date:
            return "Unknown"
        
        now = datetime.now()
        
        try:
            if hasattr(date, 'timestamp'):
                diff = now - date
            else:
                return str(date)
        except:
            return str(date)
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
        elif seconds < 2419200:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            return DateTimeUtils.format_date(date)
    
    @staticmethod
    def parse_date(date_str: str, format: str = "%Y-%m-%d") -> Optional[datetime]:
        """
        Parse date string to datetime
        Args:
            date_str: Date string
            format: Expected format
        Returns:
            Datetime object or None
        """
        try:
            return datetime.strptime(date_str, format)
        except:
            return None
    
    @staticmethod
    def get_start_of_day(date: Optional[datetime] = None) -> datetime:
        """Get start of day (00:00:00)"""
        if not date:
            date = datetime.now()
        return datetime(date.year, date.month, date.day)
    
    @staticmethod
    def get_end_of_day(date: Optional[datetime] = None) -> datetime:
        """Get end of day (23:59:59)"""
        if not date:
            date = datetime.now()
        return datetime(date.year, date.month, date.day, 23, 59, 59)
    
    @staticmethod
    def get_days_between(date1: datetime, date2: datetime) -> int:
        """Get number of days between two dates"""
        diff = date2 - date1
        return abs(diff.days)
    
    @staticmethod
    def add_days(date: datetime, days: int) -> datetime:
        """Add days to date"""
        return date + timedelta(days=days)
    
    @staticmethod
    def subtract_days(date: datetime, days: int) -> datetime:
        """Subtract days from date"""
        return date - timedelta(days=days)
    
    @staticmethod
    def is_today(date: datetime) -> bool:
        """Check if date is today"""
        if not date:
            return False
        today = datetime.now().date()
        try:
            if hasattr(date, 'date'):
                return date.date() == today
            return False
        except:
            return False
    
    @staticmethod
    def is_this_week(date: datetime) -> bool:
        """Check if date is this week"""
        if not date:
            return False
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        try:
            if hasattr(date, 'date'):
                d = date.date()
                return start_of_week <= d <= end_of_week
            return False
        except:
            return False
    
    @staticmethod
    def is_this_month(date: datetime) -> bool:
        """Check if date is this month"""
        if not date:
            return False
        now = datetime.now()
        try:
            if hasattr(date, 'month'):
                return date.month == now.month and date.year == now.year
            return False
        except:
            return False
    
    @staticmethod
    def to_iso_string(date: datetime) -> str:
        """Convert to ISO format string"""
        if not date:
            return ""
        try:
            if hasattr(date, 'isoformat'):
                return date.isoformat()
            return str(date)
        except:
            return ""
    
    @staticmethod
    def from_timestamp(ts: float) -> datetime:
        """Create datetime from timestamp"""
        return datetime.fromtimestamp(ts)
    
    @staticmethod
    def get_age_in_days(date: datetime) -> int:
        """Get age in days from date to now"""
        if not date:
            return 0
        now = datetime.now()
        diff = now - date
        return diff.days


# Specific farming calendar utilities
class FarmingCalendar:
    """Tobacco farming calendar utilities"""
    
    @staticmethod
    def get_planting_months() -> list:
        """Get recommended planting months"""
        return ["August", "September", "October", "November"]
    
    @staticmethod
    def get_harvest_months() -> list:
        """Get harvest months"""
        return ["January", "February", "March", "April"]
    
    @staticmethod
    def get_current_season() -> str:
        """Get current farming season"""
        month = datetime.now().month
        
        if 8 <= month <= 11:
            return "Planting Season"
        elif 12 <= month <= 2:
            return "Growing Season"
        elif 3 <= month <= 5:
            return "Harvest Season"
        else:
            return "Land Preparation Season"
    
    @staticmethod
    def weeks_until_planting() -> int:
        """Get weeks until next planting season"""
        now = datetime.now()
        current_year = now.year
        
        # Planting starts in August
        planting_start = datetime(current_year, 8, 1)
        
        if now > planting_start:
            planting_start = datetime(current_year + 1, 8, 1)
        
        diff = planting_start - now
        return diff.days // 7