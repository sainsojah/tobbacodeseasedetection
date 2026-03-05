"""
Message formatting utilities
"""
from typing import Dict, Any, List, Optional

class Formatters:
    """Format various types of messages"""
    
    @staticmethod
    def bold(text: str) -> str:
        """Format as bold"""
        return f"*{text}*"
    
    @staticmethod
    def italic(text: str) -> str:
        """Format as italic"""
        return f"_{text}_"
    
    @staticmethod
    def strikethrough(text: str) -> str:
        """Format as strikethrough"""
        return f"~{text}~"
    
    @staticmethod
    def code(text: str) -> str:
        """Format as code"""
        return f"```{text}```"
    
    @staticmethod
    def bullet_point(text: str) -> str:
        """Format as bullet point"""
        return f"• {text}"
    
    @staticmethod
    def numbered_list(items: List[str], start: int = 1) -> str:
        """Format as numbered list"""
        lines = []
        for i, item in enumerate(items, start):
            lines.append(f"{i}. {item}")
        return '\n'.join(lines)
    
    @staticmethod
    def bullet_list(items: List[str]) -> str:
        """Format as bullet list"""
        return '\n'.join(f"• {item}" for item in items)
    
    @staticmethod
    def header(text: str, level: int = 1) -> str:
        """Format as header"""
        if level == 1:
            return f"*{text.upper()}*"
        elif level == 2:
            return f"*{text}*"
        else:
            return text
    
    @staticmethod
    def separator(char: str = "─", length: int = 20) -> str:
        """Create separator line"""
        return char * length
    
    @staticmethod
    def table(headers: List[str], rows: List[List[str]]) -> str:
        """
        Format as simple table
        Args:
            headers: Column headers
            rows: List of row data
        Returns:
            Formatted table
        """
        if not headers or not rows:
            return ""
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Build header
        lines = []
        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        lines.append(header_line)
        lines.append("-+-".join("-" * w for w in col_widths))
        
        # Build rows
        for row in rows:
            line = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def progress_bar(percentage: float, width: int = 10) -> str:
        """Create progress bar"""
        filled = int(width * percentage / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}] {percentage:.1f}%"
    
    @staticmethod
    def format_detection_result(disease: str, confidence: float, 
                                severity: str, recommendations: List[str]) -> str:
        """Format disease detection result"""
        lines = [
            Formatters.header("DETECTION RESULT", 1),
            "",
            f"{Formatters.bold('Disease:')} {disease}",
            f"{Formatters.bold('Confidence:')} {confidence:.1f}%",
            f"{Formatters.bold('Severity:')} {severity}",
            "",
            Formatters.header("Recommendations", 2),
            Formatters.bullet_list(recommendations)
        ]
        return '\n'.join(lines)
    
    @staticmethod
    def format_history(records: List[Dict]) -> str:
        """Format scan history"""
        if not records:
            return "No scan history available."
        
        lines = [Formatters.header("SCAN HISTORY", 1), ""]
        
        for i, record in enumerate(records, 1):
            disease = record.get('disease_detected', 'Unknown')
            conf = record.get('confidence_score', 0)
            date = record.get('display_date', 'Unknown')
            
            lines.append(f"{i}. {Formatters.bold(disease)} - {conf:.1f}%")
            lines.append(f"   🕐 {date}")
            lines.append("")
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_educational(title: str, content: str, sections: Optional[List[str]] = None) -> str:
        """Format educational content"""
        lines = [
            Formatters.header(title, 1),
            "",
            content
        ]
        
        if sections:
            lines.extend(["", Formatters.header("Quick Reference", 2), ""])
            lines.extend(Formatters.bullet_list(sections))
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_menu(title: str, options: Dict[str, str]) -> str:
        """Format menu options"""
        lines = [
            Formatters.header(title, 1),
            ""
        ]
        
        for key, value in options.items():
            lines.append(f"{key}. {value}")
        
        lines.extend(["", "Reply with option number"])
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_error(error_type: str, message: str, suggestion: Optional[str] = None) -> str:
        """Format error message"""
        emoji_map = {
            "general": "❌",
            "network": "🌐",
            "image": "📸",
            "auth": "🔒",
            "not_found": "🔍"
        }
        
        emoji = emoji_map.get(error_type, "⚠️")
        
        lines = [
            f"{emoji} {Formatters.bold('Error')}",
            "",
            message
        ]
        
        if suggestion:
            lines.extend(["", Formatters.bold("Suggestion:"), suggestion])
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_success(message: str, details: Optional[List[str]] = None) -> str:
        """Format success message"""
        lines = [
            "✅ " + Formatters.bold("Success"),
            "",
            message
        ]
        
        if details:
            lines.extend(["", Formatters.bold("Details:")])
            lines.extend(Formatters.bullet_list(details))
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_welcome(user_name: str, features: List[str]) -> str:
        """Format welcome message"""
        lines = [
            f"🌿 {Formatters.bold(f'Welcome, {user_name}!')}",
            "",
            "I can help you with:",
            Formatters.bullet_list(features),
            "",
            "Type *menu* to see all options."
        ]
        return '\n'.join(lines)


# Emoji constants
class Emojis:
    """Emoji constants for consistent use"""
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # Diseases
    DISEASE = "🦠"
    HEALTHY = "🌿"
    PEST = "🐛"
    
    # Navigation
    MENU = "📋"
    BACK = "🔙"
    NEXT = "🔜"
    HOME = "🏠"
    
    # Education
    BOOK = "📚"
    TIP = "💡"
    FACT = "🎲"
    GUIDE = "📖"
    
    # Actions
    DETECT = "🔍"
    ANALYZE = "📊"
    EXPERT = "👨‍🌾"
    HISTORY = "📋"
    SETTINGS = "⚙️"
    
    # Time
    CALENDAR = "📅"
    CLOCK = "🕐"
    
    # Weather
    SUN = "☀️"
    RAIN = "🌧️"
    CLOUD = "☁️"