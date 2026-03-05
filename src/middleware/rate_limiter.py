"""
Rate limiter middleware
Prevents spam and abuse by limiting message frequency
"""
import time
from typing import Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    """
    Rate limiting for user messages
    Uses in-memory storage (for production, use Redis)
    """
    
    def __init__(self):
        # Store user message history
        # Format: {user_id: [timestamp1, timestamp2, ...]}
        self.user_messages = defaultdict(list)
        
        # Store blocked users
        self.blocked_users = {}
        
        # Configuration
        self.max_messages_per_minute = 10
        self.max_messages_per_hour = 50
        self.max_messages_per_day = 200
        
        # Block durations
        self.temp_block_duration = 300  # 5 minutes
        self.permanent_block_threshold = 5  # Number of violations
        
        # Cleanup old data every hour
        self.last_cleanup = time.time()
    
    def is_allowed(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user is allowed to send message
        Args:
            user_id: User's phone number
        Returns:
            (allowed, message) - if not allowed, message explains why
        """
        now = time.time()
        
        # Periodic cleanup
        self._cleanup_old_data(now)
        
        # Check if user is blocked
        if user_id in self.blocked_users:
            block_expiry = self.blocked_users[user_id]
            if now < block_expiry:
                wait_time = int(block_expiry - now)
                return False, f"⛔ You are temporarily blocked. Please wait {wait_time} seconds."
            else:
                # Block expired
                del self.blocked_users[user_id]
        
        # Get user's message history
        messages = self.user_messages[user_id]
        
        # Filter messages within time windows
        last_minute = [t for t in messages if now - t < 60]
        last_hour = [t for t in messages if now - t < 3600]
        last_day = [t for t in messages if now - t < 86400]
        
        # Check limits
        violations = 0
        
        if len(last_minute) >= self.max_messages_per_minute:
            violations += 1
            wait_time = 60 - (now - last_minute[0])
            return False, f"⏳ Too many messages. Please wait {int(wait_time)} seconds."
        
        if len(last_hour) >= self.max_messages_per_hour:
            violations += 1
            return False, "⏳ Hourly message limit reached. Please try again later."
        
        if len(last_day) >= self.max_messages_per_day:
            violations += 1
            return False, "⏳ Daily message limit reached. Please try again tomorrow."
        
        # Check for spam patterns (multiple messages in quick succession)
        if len(last_minute) >= 5:
            time_diff = last_minute[-1] - last_minute[0]
            if time_diff < 10:  # 5 messages in 10 seconds
                violations += 2
        
        # Handle violations
        if violations >= self.permanent_block_threshold:
            # Permanent block (actually 24 hours)
            self.blocked_users[user_id] = now + 86400
            return False, "⛔ Account temporarily suspended due to spam. Please contact support."
        
        # Allow message
        self.user_messages[user_id].append(now)
        
        # Keep only last 200 messages to save memory
        if len(self.user_messages[user_id]) > 200:
            self.user_messages[user_id] = self.user_messages[user_id][-200:]
        
        return True, None
    
    def _cleanup_old_data(self, now: float):
        """Remove old message history"""
        # Cleanup every hour
        if now - self.last_cleanup < 3600:
            return
        
        # Remove messages older than 24 hours
        cutoff = now - 86400
        
        for user_id in list(self.user_messages.keys()):
            self.user_messages[user_id] = [
                t for t in self.user_messages[user_id] if t > cutoff
            ]
            
            # Remove empty entries
            if not self.user_messages[user_id]:
                del self.user_messages[user_id]
        
        # Remove expired blocks
        for user_id in list(self.blocked_users.keys()):
            if now > self.blocked_users[user_id]:
                del self.blocked_users[user_id]
        
        self.last_cleanup = now
    
    def get_remaining_quota(self, user_id: str) -> Dict[str, int]:
        """
        Get user's remaining quota
        Args:
            user_id: User's phone number
        Returns:
            Dict with remaining counts
        """
        now = time.time()
        messages = self.user_messages.get(user_id, [])
        
        last_minute = [t for t in messages if now - t < 60]
        last_hour = [t for t in messages if now - t < 3600]
        last_day = [t for t in messages if now - t < 86400]
        
        return {
            "minute_remaining": max(0, self.max_messages_per_minute - len(last_minute)),
            "hour_remaining": max(0, self.max_messages_per_hour - len(last_hour)),
            "day_remaining": max(0, self.max_messages_per_day - len(last_day))
        }
    
    def reset_user(self, user_id: str):
        """Reset rate limit for a user (for testing/admin)"""
        if user_id in self.user_messages:
            del self.user_messages[user_id]
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
    
    def block_user(self, user_id: str, duration: int = 3600):
        """Manually block a user"""
        self.blocked_users[user_id] = time.time() + duration
    
    def unblock_user(self, user_id: str):
        """Unblock a user"""
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        return {
            "active_users": len(self.user_messages),
            "blocked_users": len(self.blocked_users),
            "total_messages_tracked": sum(len(msgs) for msgs in self.user_messages.values()),
            "config": {
                "max_per_minute": self.max_messages_per_minute,
                "max_per_hour": self.max_messages_per_hour,
                "max_per_day": self.max_messages_per_day
            }
        }


# Redis-based rate limiter for production
class RedisRateLimiter:
    """
    Rate limiter using Redis (for production)
    Placeholder - implement when using Redis
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def is_allowed(self, user_id: str) -> Tuple[bool, Optional[str]]:
        # Redis implementation would go here
        # Use INCR and EXPIRE commands
        pass