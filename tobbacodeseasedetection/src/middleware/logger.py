"""
Request logging middleware
Logs all incoming requests and outgoing responses
"""
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

class RequestLogger:
    """Log all requests and responses"""
    
    def __init__(self, log_file: str = None):
        self.log_file = log_file
        self.logs = []  # In-memory logs
        
    def log_request(self, request_data: Dict[str, Any], response_data: Dict[str, Any] = None, 
                    error: str = None, duration: float = None):
        """
        Log a request
        Args:
            request_data: Request information
            response_data: Response information (optional)
            error: Error message (optional)
            duration: Request duration in seconds
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request": request_data,
            "response": response_data,
            "error": error,
            "duration": duration
        }
        
        # Add to in-memory logs
        self.logs.append(log_entry)
        
        # Keep only last 1000 logs in memory
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
        # Write to file if configured
        if self.log_file:
            self._write_to_file(log_entry)
        
        # Print to console
        self._print_log(log_entry)
    
    def _write_to_file(self, log_entry: Dict):
        """Write log entry to file"""
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"❌ Failed to write log: {e}")
    
    def _print_log(self, log_entry: Dict):
        """Print log to console"""
        request = log_entry["request"]
        method = request.get("method", "UNKNOWN")
        path = request.get("path", "")
        from_number = request.get("from", "unknown")
        msg_type = request.get("type", "unknown")
        
        duration = log_entry.get("duration", 0)
        error = log_entry.get("error")
        
        if error:
            print(f"❌ {method} {path} | {from_number} | {msg_type} | Error: {error} | {duration:.3f}s")
        else:
            print(f"✅ {method} {path} | {from_number} | {msg_type} | {duration:.3f}s")
    
    def get_recent_logs(self, limit: int = 50) -> list:
        """Get recent logs"""
        return self.logs[-limit:]
    
    def get_logs_by_user(self, phone_number: str, limit: int = 20) -> list:
        """Get logs for specific user"""
        user_logs = []
        for log in reversed(self.logs):
            if log["request"].get("from") == phone_number:
                user_logs.append(log)
                if len(user_logs) >= limit:
                    break
        return user_logs
    
    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        if not self.logs:
            return {}
        
        total = len(self.logs)
        errors = sum(1 for log in self.logs if log.get("error"))
        
        # Count by type
        by_type = {}
        for log in self.logs:
            msg_type = log["request"].get("type", "unknown")
            by_type[msg_type] = by_type.get(msg_type, 0) + 1
        
        # Average duration
        durations = [log.get("duration", 0) for log in self.logs if log.get("duration")]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_logs": total,
            "errors": errors,
            "error_rate": (errors / total * 100) if total > 0 else 0,
            "by_type": by_type,
            "avg_duration_ms": avg_duration * 1000
        }
    
    def clear_logs(self):
        """Clear in-memory logs"""
        self.logs = []
    
    def export_logs(self, format: str = "json") -> str:
        """Export logs as string"""
        if format == "json":
            return json.dumps(self.logs, indent=2, default=str)
        elif format == "csv":
            # Simple CSV export
            lines = ["timestamp,method,path,from,type,duration,error"]
            for log in self.logs:
                req = log["request"]
                lines.append(
                    f"{log['timestamp']},"
                    f"{req.get('method','')},"
                    f"{req.get('path','')},"
                    f"{req.get('from','')},"
                    f"{req.get('type','')},"
                    f"{log.get('duration',0)},"
                    f"{log.get('error','')}"
                )
            return "\n".join(lines)
        return ""


# Decorator for automatic logging
def log_request(logger: RequestLogger):
    """
    Decorator to automatically log requests
    Usage: @log_request(logger)
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            
            # Get request from args (assumes first arg is request)
            request = args[0] if args else None
            
            request_data = {
                "method": request.method if request else "UNKNOWN",
                "path": request.path if request else "UNKNOWN",
                "from": request.args.get('from') or request.json.get('from') if request else None,
                "type": "webhook"
            }
            
            try:
                result = f(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.log_request(
                    request_data=request_data,
                    response_data={"status": "success"},
                    duration=duration
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.log_request(
                    request_data=request_data,
                    error=str(e),
                    duration=duration
                )
                
                raise
        
        return wrapped
    return decorator


# Simple in-memory logger for quick use
_default_logger = RequestLogger()

def log_webhook_request(data):
    """Quick log function for webhook"""
    _default_logger.log_request(request_data=data)