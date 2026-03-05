"""
Menu service - handles main menu and navigation
"""
from typing import Dict, Any
from infrastructure.whatsapp.client import WhatsAppClient
from infrastructure.whatsapp.interactive import InteractiveMenu

class MenuService:
    """Handle menu display and navigation"""
    
    def __init__(self, whatsapp: WhatsAppClient):
        self.whatsapp = whatsapp
    
    def show_main_menu(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """
        Show main interactive menu
        Args:
            phone_number: User's phone number
            user: User data dict
        Returns:
            Response dict
        """
        user_name = user.get("name", "Farmer")
        
        # Send interactive menu
        menu_payload = InteractiveMenu.main_menu(phone_number, user_name)
        
        # In a real implementation, you'd use the interactive builder
        # For now, send a text menu as fallback
        self._send_text_menu(phone_number, user_name)
        
        return {"status": "ok", "action": "menu_shown"}
    
    def _send_text_menu(self, phone_number: str, user_name: str):
        """Send text-based menu (fallback)"""
        menu = (
            f"🌿 *Welcome back, {user_name}!*\n\n"
            f"*MAIN MENU*\n\n"
            f"🔍 *1. Disease Detection*\n"
            f"   Upload leaf photo for analysis\n\n"
            f"📚 *2. Disease Education*\n"
            f"   Learn about tobacco diseases\n\n"
            f"🌱 *3. Planting Guide*\n"
            f"   Nursery to field preparation\n\n"
            f"🧪 *4. Fertilizer Guide*\n"
            f"   Application rates & timing\n\n"
            f"🌾 *5. Harvesting Guide*\n"
            f"   Priming & curing methods\n\n"
            f"💰 *6. Marketing Guide*\n"
            f"   Selling your crop\n\n"
            f"📋 *7. Scan History*\n"
            f"   View past diagnoses\n\n"
            f"👨‍🌾 *8. Talk to Expert*\n"
            f"   Connect with agronomist\n\n"
            f"💬 *9. Feedback*\n"
            f"   Send comments to admin\n\n"
            f"🎲 *0. Fun Fact*\n"
            f"   Daily farming fact\n\n"
            f"---\n"
            f"Reply with the number of your choice (e.g., *1* for Detection)"
        )
        
        self.whatsapp.send_text(phone_number, menu)
    
    def show_detection_menu(self, phone_number: str) -> Dict[str, Any]:
        """Show disease detection options"""
        menu = (
            "📸 *Disease Detection*\n\n"
            "Please send a clear photo of the tobacco leaf.\n\n"
            "📝 *Tips for best results:*\n"
            "• Use good lighting (natural light)\n"
            "• Plain background (avoid clutter)\n"
            "• Close-up of affected area\n"
            "• Hold camera steady\n\n"
            "Send your photo now, or type *menu* to go back."
        )
        
        self.whatsapp.send_text(phone_number, menu)
        return {"status": "ok"}
    
    def show_education_menu(self, phone_number: str) -> Dict[str, Any]:
        """Show education submenu"""
        menu = (
            "📚 *Education Center*\n\n"
            "Select a topic:\n\n"
            "🌱 *1. Planting Guide*\n"
            "🧪 *2. Fertilizer Application*\n"
            "🌾 *3. Harvesting Guide*\n"
            "💰 *4. Marketing Guide*\n"
            "🌍 *5. Full Growth Journey*\n"
            "📖 *6. Disease Information*\n\n"
            "0️⃣ *Main Menu*"
        )
        
        self.whatsapp.send_text(phone_number, menu)
        return {"status": "ok"}
    
    def show_settings_menu(self, phone_number: str, user: Dict) -> Dict[str, Any]:
        """Show settings menu"""
        current_lang = user.get("language", "en")
        lang_display = {
            "en": "🇬🇧 English",
            "sn": "🇿🇼 Shona",
            "nd": "🇿🇼 Ndebele"
        }.get(current_lang, "🇬🇧 English")
        
        menu = (
            f"⚙️ *Settings*\n\n"
            f"👤 *Name:* {user.get('name')}\n"
            f"🌐 *Language:* {lang_display}\n"
            f"📊 *Total Scans:* {user.get('total_scans', 0)}\n\n"
            f"*Options:*\n"
            f"1️⃣ Change Language\n"
            f"2️⃣ Update Name\n"
            f"3️⃣ View Profile\n\n"
            f"0️⃣ Main Menu"
        )
        
        self.whatsapp.send_text(phone_number, menu)
        return {"status": "ok"}