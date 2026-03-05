"""
Interactive message builders for WhatsApp
Creates lists, buttons, and catalogs
"""
from typing import List, Dict, Optional

class ButtonBuilder:
    """Build interactive button messages"""
    
    @staticmethod
    def create_reply_button(button_id: str, title: str) -> Dict:
        """Create a single reply button"""
        return {
            "type": "reply",
            "reply": {
                "id": button_id,
                "title": title[:20]  # WhatsApp limit
            }
        }
    
    @staticmethod
    def build(to: str, body_text: str, buttons: List[Dict], header: str = None, footer: str = None) -> Dict:
        """
        Build complete button message payload
        Args:
            to: Recipient phone
            body_text: Main message
            buttons: List of buttons (max 3)
            header: Optional header text
            footer: Optional footer text
        Returns:
            Dict: Complete payload
        """
        interactive = {
            "type": "button",
            "body": {"text": body_text[:1024]}
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header[:60]}
        
        if footer:
            interactive["footer"] = {"text": footer[:60]}
        
        interactive["action"] = {"buttons": buttons[:3]}
        
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive
        }


class ListBuilder:
    """Build interactive list messages"""
    
    @staticmethod
    def create_section(title: str, rows: List[Dict]) -> Dict:
        """
        Create a section for list menu
        Args:
            title: Section title
            rows: List of row dicts with id, title, description
        Returns:
            Dict: Formatted section
        """
        formatted_rows = []
        for row in rows[:10]:  # Max 10 rows per section
            formatted_row = {
                "id": row["id"][:200],
                "title": row["title"][:24]
            }
            if "description" in row:
                formatted_row["description"] = row["description"][:72]
            formatted_rows.append(formatted_row)
        
        return {
            "title": title[:24],
            "rows": formatted_rows
        }
    
    @staticmethod
    def build(to: str, body_text: str, sections: List[Dict], 
              button_text: str = "View Options", 
              header: str = None, footer: str = None) -> Dict:
        """
        Build complete list message payload
        Args:
            to: Recipient phone
            body_text: Main message
            sections: List of sections with rows
            button_text: Text on call-to-action button
            header: Optional header text
            footer: Optional footer text
        Returns:
            Dict: Complete payload
        """
        interactive = {
            "type": "list",
            "body": {"text": body_text[:1024]},
            "action": {
                "button": button_text[:20],
                "sections": sections[:10]  # Max 10 sections
            }
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header[:60]}
        
        if footer:
            interactive["footer"] = {"text": footer[:60]}
        
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive
        }


class InteractiveMenu:
    """Pre-built menus for common scenarios"""
    
    @staticmethod
    def main_menu(to: str, user_name: str) -> Dict:
        """Main menu with all options"""
        sections = [
            {
                "title": "🔍 Disease Management",
                "rows": [
                    {"id": "detect", "title": "Disease Detection", "description": "Upload leaf photo"},
                    {"id": "education", "title": "Disease Education", "description": "Learn about diseases"},
                    {"id": "history", "title": "My Scan History", "description": "Past diagnoses"}
                ]
            },
            {
                "title": "🌱 Farming Knowledge",
                "rows": [
                    {"id": "planting", "title": "Planting Guide", "description": "Nursery to field"},
                    {"id": "fertilizer", "title": "Fertilizer Guide", "description": "Rates & timing"},
                    {"id": "harvesting", "title": "Harvesting Guide", "description": "Priming & curing"},
                    {"id": "marketing", "title": "Marketing Guide", "description": "Selling your crop"}
                ]
            },
            {
                "title": "🎯 More Options",
                "rows": [
                    {"id": "expert", "title": "Talk to Expert", "description": "Ask an agronomist"},
                    {"id": "feedback", "title": "Send Feedback", "description": "Comments & suggestions"},
                    {"id": "fact", "title": "Fun Fact", "description": "Daily farming fact"},
                    {"id": "tip", "title": "Daily Tip", "description": "Helpful farming tip"}
                ]
            }
        ]
        
        return ListBuilder.build(
            to=to,
            header=f"🌿 Welcome, {user_name}!",
            body_text="Please select an option below:",
            sections=sections,
            button_text="📋 Menu"
        )
    
    @staticmethod
    def detection_options(to: str) -> Dict:
        """Options after detection"""
        buttons = [
            ButtonBuilder.create_reply_button("detect_again", "🔍 New Scan"),
            ButtonBuilder.create_reply_button("education", "📚 Learn More"),
            ButtonBuilder.create_reply_button("menu", "🏠 Main Menu")
        ]
        
        return ButtonBuilder.build(
            to=to,
            body_text="What would you like to do next?",
            buttons=buttons,
            footer="Choose an option"
        )
    
    @staticmethod
    def education_menu(to: str) -> Dict:
        """Education submenu"""
        sections = [
            {
                "title": "📚 Educational Guides",
                "rows": [
                    {"id": "planting", "title": "Planting Guide"},
                    {"id": "fertilizer", "title": "Fertilizer Guide"},
                    {"id": "harvesting", "title": "Harvesting Guide"},
                    {"id": "marketing", "title": "Marketing Guide"},
                    {"id": "journey", "title": "Full Growth Journey"}
                ]
            },
            {
                "title": "ℹ️ Quick Info",
                "rows": [
                    {"id": "fact", "title": "Fun Fact"},
                    {"id": "tip", "title": "Daily Tip"}
                ]
            }
        ]
        
        return ListBuilder.build(
            to=to,
            header="📚 Learning Center",
            body_text="Select a topic to learn more:",
            sections=sections,
            button_text="Choose"
        )