"""
Education service - handles educational content delivery
"""
import random
from typing import Dict, Any, Optional
from infrastructure.whatsapp.client import WhatsAppClient
from content.educational.planting import PLANTING_GUIDE
from content.educational.fertilizers import FERTILIZER_GUIDE
from content.educational.harvesting import HARVESTING_GUIDE
from content.educational.marketing import MARKETING_GUIDE
from content.educational.full_growth_journey import GROWTH_JOURNEY
from content.disease.treatments import TREATMENTS
from content.tips.daily_tips import DAILY_TIPS, get_random_tip
from content.tips.fun_facts import FUN_FACTS, get_random_fact
from core.constants import DISEASE_CLASSES

class EducationService:
    """Handle educational content delivery"""
    
    def __init__(self, whatsapp: WhatsAppClient):
        self.whatsapp = whatsapp
        
        # Content mappings
        self.guides = {
            "planting": PLANTING_GUIDE,
            "fertilizer": FERTILIZER_GUIDE,
            "harvesting": HARVESTING_GUIDE,
            "marketing": MARKETING_GUIDE,
            "journey": GROWTH_JOURNEY
        }
    
    def send_planting_guide(self, phone_number: str, lang: str = "en") -> Dict[str, Any]:
        """Send planting guide"""
        content = PLANTING_GUIDE.get(lang, PLANTING_GUIDE["en"])
        
        message = (
            f"📚 *TOBACCO PLANTING GUIDE*\n\n"
            f"{content}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ More Guides"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "planting_guide_sent"}
    
    def send_fertilizer_guide(self, phone_number: str, lang: str = "en") -> Dict[str, Any]:
        """Send fertilizer guide"""
        content = FERTILIZER_GUIDE.get(lang, FERTILIZER_GUIDE["en"])
        
        message = (
            f"🧪 *FERTILIZER APPLICATION GUIDE*\n\n"
            f"{content}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ More Guides"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "fertilizer_guide_sent"}
    
    def send_harvesting_guide(self, phone_number: str, lang: str = "en") -> Dict[str, Any]:
        """Send harvesting guide"""
        content = HARVESTING_GUIDE.get(lang, HARVESTING_GUIDE["en"])
        
        message = (
            f"🌾 *HARVESTING GUIDE*\n\n"
            f"{content}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ More Guides"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "harvesting_guide_sent"}
    
    def send_marketing_guide(self, phone_number: str, lang: str = "en") -> Dict[str, Any]:
        """Send marketing guide"""
        content = MARKETING_GUIDE.get(lang, MARKETING_GUIDE["en"])
        
        message = (
            f"💰 *MARKETING & SELLING GUIDE*\n\n"
            f"{content}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ More Guides"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "marketing_guide_sent"}
    
    def send_growth_journey(self, phone_number: str, lang: str = "en") -> Dict[str, Any]:
        """Send full growth journey"""
        content = GROWTH_JOURNEY.get(lang, GROWTH_JOURNEY["en"])
        
        # Split into multiple messages if too long
        parts = self._split_long_message(content)
        
        for i, part in enumerate(parts):
            if i == 0:
                header = "🌍 *COMPLETE TOBACCO GROWTH JOURNEY*\n\n"
                self.whatsapp.send_text(phone_number, header + part)
            elif i == len(parts) - 1:
                self.whatsapp.send_text(phone_number, part + "\n\n---\n0️⃣ Main Menu")
            else:
                self.whatsapp.send_text(phone_number, part)
        
        return {"status": "ok", "action": "growth_journey_sent"}
    
    def send_disease_info(self, phone_number: str, disease: str) -> Dict[str, Any]:
        """
        Send information about specific disease
        Args:
            phone_number: User's phone number
            disease: Disease name
        Returns:
            Response dict
        """
        # Find matching disease (case-insensitive)
        matching_disease = None
        for d in DISEASE_CLASSES:
            if disease.lower() in d.lower() or d.lower() in disease.lower():
                matching_disease = d
                break
        
        if not matching_disease:
            # No match found
            self._send_disease_list(phone_number)
            return {"status": "ok", "action": "disease_list_sent"}
        
        # Get treatment info
        treatment = TREATMENTS.get(matching_disease, {})
        
        if not treatment:
            self.whatsapp.send_text(
                phone_number,
                f"❌ Information not available for '{disease}'. Please check the disease name."
            )
            return {"status": "ok"}
        
        # Build message
        message = (
            f"📖 *DISEASE INFORMATION*\n\n"
            f"*{matching_disease}*\n\n"
            f"🔍 *Symptoms:*\n{treatment.get('symptoms', 'N/A')}\n\n"
            f"⚠️ *Severity:* {treatment.get('severity', 'Unknown')}\n\n"
            f"🌱 *Causes:*\n{treatment.get('causes', 'N/A')}\n\n"
            f"🛡️ *Prevention:*\n{treatment.get('prevention', 'N/A')}\n\n"
            f"🛠️ *Treatment:*\n{treatment.get('action', 'N/A')}\n"
        )
        
        # Add chemicals if available
        if treatment.get('chemicals'):
            chems = treatment['chemicals'][:5]
            message += f"\n🧪 *Recommended Chemicals:*\n"
            for chem in chems:
                message += f"• {chem}\n"
        
        # Add organic options if available
        if treatment.get('organic'):
            message += f"\n🌱 *Organic Options:*\n"
            for opt in treatment['organic'][:3]:
                message += f"• {opt}\n"
        
        message += "\n---\n0️⃣ Main Menu  |  9️⃣ More Diseases"
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "disease_info_sent"}
    
    def _send_disease_list(self, phone_number: str):
        """Send list of available diseases"""
        message = "📚 *Available Diseases:*\n\n"
        
        # Group diseases by category
        fungal = ["Black Spot", "Black Shank", "Early Blight", "Late Blight", 
                  "Leaf Mold", "Leaf Spot", "Powdery Mildew", "Septoria Blight"]
        viral = ["Tobacco Cillium Virus", "Tobacco Cillium TMDL"]
        other = ["Yellow Leaf Spot", "Spider Mites", "Healthy"]
        
        message += "*🍄 Fungal Diseases:*\n"
        for d in fungal:
            if d in DISEASE_CLASSES:
                message += f"• {d}\n"
        
        message += "\n*🦠 Viral Diseases:*\n"
        for d in viral:
            if d in DISEASE_CLASSES:
                message += f"• {d}\n"
        
        message += "\n*🐛 Pests & Other:*\n"
        for d in other:
            if d in DISEASE_CLASSES:
                message += f"• {d}\n"
        
        message += "\nReply with the disease name (e.g., 'Black Spot') for details.\n\n---\n0️⃣ Main Menu"
        
        self.whatsapp.send_text(phone_number, message)
    
    def send_fun_fact(self, phone_number: str) -> Dict[str, Any]:
        """Send random fun fact"""
        fact = get_random_fact()
        
        message = (
            f"🎲 *Did You Know?*\n\n"
            f"{fact}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ Another Fact"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "fun_fact_sent"}
    
    def send_daily_tip(self, phone_number: str) -> Dict[str, Any]:
        """Send daily farming tip"""
        tip = get_random_tip()
        
        message = (
            f"💡 *Daily Farming Tip*\n\n"
            f"{tip}\n\n"
            f"---\n"
            f"0️⃣ Main Menu  |  9️⃣ Another Tip"
        )
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "daily_tip_sent"}
    
    def send_tip_by_index(self, phone_number: str, index: int) -> bool:
        """Send specific tip by index"""
        if 0 <= index < len(DAILY_TIPS):
            tip = DAILY_TIPS[index]
            self.whatsapp.send_text(phone_number, f"💡 *Tip #{index+1}:*\n\n{tip}")
            return True
        return False
    
    def send_fact_by_index(self, phone_number: str, index: int) -> bool:
        """Send specific fact by index"""
        if 0 <= index < len(FUN_FACTS):
            fact = FUN_FACTS[index]
            self.whatsapp.send_text(phone_number, f"🎲 *Fact #{index+1}:*\n\n{fact}")
            return True
        return False
    
    def _split_long_message(self, text: str, max_length: int = 1500) -> list:
        """
        Split long message into chunks
        Args:
            text: Long text to split
            max_length: Maximum message length
        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def search_content(self, phone_number: str, query: str) -> Dict[str, Any]:
        """
        Search educational content
        Args:
            phone_number: User's phone number
            query: Search query
        Returns:
            Response dict
        """
        query = query.lower()
        results = []
        
        # Search in disease treatments
        for disease, info in TREATMENTS.items():
            if query in disease.lower() or query in info.get('symptoms', '').lower():
                results.append(f"• *{disease}* - Disease information")
                if len(results) >= 5:
                    break
        
        # Search in tips
        for tip in DAILY_TIPS:
            if query in tip.lower():
                results.append(f"• *Tip:* {tip[:50]}...")
                if len(results) >= 5:
                    break
        
        if results:
            message = f"🔍 *Search Results for '{query}':*\n\n" + '\n'.join(results)
        else:
            message = f"❌ No results found for '{query}'. Try a different keyword."
        
        message += "\n\n---\n0️⃣ Main Menu"
        
        self.whatsapp.send_text(phone_number, message)
        return {"status": "ok", "action": "search_completed"}