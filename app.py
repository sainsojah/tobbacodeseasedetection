"""
Tobacco AI Assistant - Render WhatsApp Bot
Fixed: ALL responses concise (800 char limit) and spam-safe
"""
import os
import json
import random
import requests
import time
import base64
import re
import gc
from flask import Flask, request, jsonify
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai

# ==============================
# INITIALIZATION
# ==============================
app = Flask(__name__)

def debug_log(message):
    """Print debug with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# Load environment variables
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsouldier-tobacco-ai.hf.space")

# AI API Keys
AI_API_KEY = os.environ.get("AI_API_KEY")

# Configure Google Generative AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    debug_log("✅ Google Generative AI configured")

# CORRECT MODEL NAMES
GEMINI_MODELS = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-pro',
    'models/gemini-3.1-pro-preview',
    'models/gemini-3.1-flash-lite-preview',
    'models/gemini-2.0-flash',
    'models/gemini-2.0-flash-lite',
    'models/gemini-flash-latest',
    'models/gemini-pro-latest'
]

# CONSISTENT 800 CHAR LIMIT FOR ALL RESPONSES
MAX_RESPONSE_LENGTH = 800

# Generation config for AI
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 400,  # ~800 chars
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
]

# Vision-specific config
vision_config = {
    "temperature": 0.7,
    "max_output_tokens": 300,  # ~600 chars
    "top_p": 0.8
}

# Tip/Fact config
tip_config = {
    "temperature": 0.8,
    "max_output_tokens": 200,  # ~400 chars
}

# ==============================
# UNIVERSAL RESPONSE TRIMMER - 800 CHAR LIMIT FOR ALL
# ==============================
def trim_response(text, max_length=MAX_RESPONSE_LENGTH):
    """
    UNIVERSAL function to trim ALL responses to 800 chars
    Used for EVERY message before sending to WhatsApp
    """
    if not text:
        return "No response available."
    
    # Convert to string if needed
    text = str(text).strip()
    
    # If within limit, return as is
    if len(text) <= max_length:
        return text
    
    # Trim and add ellipsis
    trimmed = text[:max_length-3] + "..."
    
    # Log when trimming happens
    debug_log(f"⚠️ Trimmed response from {len(text)} to {max_length} chars")
    
    return trimmed

# ==============================
# HTTP SESSION WITH RETRIES
# ==============================
def create_session_with_retries():
    """Create requests session with retry logic for API calls"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=5)
    session.mount('https://', adapter)
    return session

# Create global session
http_session = create_session_with_retries()

# ==============================
# FIREBASE CONNECTION
# ==============================
db = None
if FIREBASE_CONFIG:
    try:
        cred_dict = json.loads(FIREBASE_CONFIG)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        debug_log("✅ Firebase connected")
    except Exception as e:
        debug_log(f"❌ Firebase error: {e}")

# ==============================
# ENHANCED USER STATES
# ==============================
USER_STATES = {
    "AWAITING_NAME": "awaiting_name",
    "ACTIVE": "active",
    "WAITING_IMAGE": "waiting_image",
    "AWAITING_FEEDBACK": "awaiting_feedback",
    "AWAITING_EXPERT": "awaiting_expert",
    "AWAITING_AI_QUESTION": "awaiting_ai_question",
    "FARMING_MENU": "farming_menu",
    "WAITING_GRADE_IMAGE": "waiting_grade_image",
    "EXPERT_MENU": "expert_menu",
    "DASHBOARD_MENU": "dashboard_menu"
}

# ==============================
# CONCISE STATIC GUIDES (All under 800 chars)
# ==============================
PLANTING_GUIDE = """🌱 *PLANTING*
━━━━━━━━━━━━━━
• Spacing: 1.1-1.2m between ridges
• Population: 15,000 plants/ha
• Transplant: 6-8 weeks after sowing
• Water immediately after planting
• Gap fill within 7-10 days"""

FERTILIZER_GUIDE = """🧪 *FERTILIZER*
━━━━━━━━━━━━━━
• Basal: Compound L 400-600 kg/ha
• Top dress 1: Ammonium Nitrate 150-200 kg/ha
• Top dress 2: Potassium Nitrate 100-150 kg/ha
• Apply when soil moist
• Target pH 5.5-6.5"""

HARVESTING_GUIDE = """🌾 *HARVEST*
━━━━━━━━━━━━━━
• Harvest bottom up (priming)
• 2-3 leaves per harvest
• 4-6 primings total
• Ripeness: Light green, sticky, midrib snaps
• Priming 2-3 = Best quality"""

CURING_GUIDE = """🔥 *CURING*
━━━━━━━━━━━━━━
• Yellowing: 32-38°C, 48hrs, 85-90% humidity
• Leaf drying: 38-52°C, 48hrs, 70-80%
• Midrib drying: 52-60°C, 24hrs, 50-60%
• Killing out: 60-71°C, 6hrs, 30-40%"""

MARKETING_GUIDE = """💰 *MARKETING 2026*
━━━━━━━━━━━━━━━━
• Opens: March 2026
• Biometric ID required
• Register by Feb 2026
• Grades: A(Premium), B(Good), C(Fair), D(Low)
• Payment within 24hrs"""

DISEASE_QUICK_GUIDES = {
    "Black Shank": "💧 *Black Shank*\n• Cause: Wet soil fungus\n• Treatment: Remove plants, Ridomil\n• Prevention: Rotate crops, improve drainage",
    "Black Spot": "🔴 *Black Spot*\n• Cause: Fungal\n• Treatment: Copper fungicide\n• Prevention: Air circulation, no overhead water",
    "Early Blight": "🍂 *Early Blight*\n• Cause: Alternaria fungus\n• Treatment: Mancozeb\n• Prevention: Crop rotation, spacing",
    "Late Blight": "🌧️ *Late Blight*\n• Cause: Water mold\n• Treatment: Remove plants, Ridomil Gold\n• Prevention: Disease-free transplants",
    "Tobacco Mosaic Virus": "⚠️ *TMV*\n• Cause: Virus\n• Treatment: NO CURE - remove immediately\n• Prevention: Wash hands, resistant varieties"
}

# ==============================
# USER STATISTICS FUNCTION
# ==============================
def get_user_statistics(phone):
    """Get detailed statistics for a user"""
    if not db:
        return {
            "total_scans": 0,
            "top_disease": "None",
            "healthy_count": 0
        }
    
    try:
        docs = db.collection("detections")\
            .where("phone", "==", phone)\
            .stream()
        
        total_scans = 0
        disease_counts = {}
        healthy_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            total_scans += 1
            disease = data.get("disease", "Unknown")
            
            if disease == "Healthy":
                healthy_count += 1
            else:
                disease_counts[disease] = disease_counts.get(disease, 0) + 1
        
        top_disease = "None"
        if disease_counts:
            top_disease = max(disease_counts, key=disease_counts.get)
        
        return {
            "total_scans": total_scans,
            "top_disease": top_disease,
            "healthy_count": healthy_count
        }
    except Exception as e:
        debug_log(f"❌ Stats error: {e}")
        return {
            "total_scans": 0,
            "top_disease": "None",
            "healthy_count": 0
        }

# ==============================
# CONFIDENCE INTERPRETATION
# ==============================
def get_confidence_message(confidence):
    """Return human-readable confidence level with emoji"""
    if confidence > 85:
        return "✔ High Accuracy"
    elif confidence > 60:
        return "⚠ Medium Accuracy"
    else:
        return "❗ Low Accuracy - retake photo"

# ==============================
# CONCISE AI ADVISOR - 800 CHAR MAX
# ==============================
def ask_ai_advisor(question):
    """AI advisor with concise, 800-char max responses"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured"
    
    # Check for known diseases for quick response
    for disease, guide in DISEASE_QUICK_GUIDES.items():
        if disease.lower() in question.lower():
            return guide
    
    # Try each model
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(1)
            debug_log(f"🔄 Trying: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # CONCISE PROMPT - 800 char target
            prompt = f"""Zimbabwe tobacco expert. Answer in 5 lines max:

Q: {question}

Format:
• Key point 1
• Key point 2
• Key point 3
• Key point 4 (if needed)

MAX 800 CHARACTERS TOTAL. Be direct."""

            response = model.generate_content(prompt)
            
            if response and response.text:
                answer = response.text.strip()
                debug_log(f"✅ Got {len(answer)} chars")
                return answer
                
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:50]}")
            continue
    
    return "⚠️ Service busy. Try *menu* for guides."

# ==============================
# CONCISE LEAF GRADING
# ==============================
def grade_leaf_with_ai(image_bytes):
    """Grade leaf with concise output"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI grading not configured"
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(1)
            debug_log(f"🔄 Grading with: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            # Concise grading prompt
            prompt = """Grade this tobacco leaf (MAX 600 chars):

📊 *GRADE:*
• Color: 
• Texture: 
• Damage: 
• Market:"""

            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                return "Grade", response.text.strip()
                
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:50]}")
            continue
    
    return None, "❌ Grading failed"

# ==============================
# DAILY TIP - SHORT
# ==============================
def get_gemini_tip():
    """Short, actionable tip"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        tips = [
            "🚜 Rotate crops with maize to prevent soil diseases",
            "💧 Water early morning to prevent fungal growth",
            "🔍 Check lower leaves weekly for pests",
            "🧪 Test soil pH before fertilizing (target 5.5-6.5)",
            "🌱 Plant after good rains, not before"
        ]
        return random.choice(tips)
    
    for model_name in GEMINI_MODELS[:2]:
        try:
            current_month = datetime.now().strftime("%B")
            season = "rainy" if current_month in ["Nov","Dec","Jan","Feb","Mar"] else "dry"
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=tip_config
            )
            
            prompt = f"ONE short tobacco tip for {season} season in Zimbabwe. 1-2 sentences. Start with emoji."
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
                
        except Exception:
            continue
    
    return "🌱 Monitor fields daily for early disease signs."

# ==============================
# FUN FACT - SHORT
# ==============================
def get_gemini_fact():
    """Short, interesting fact"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        facts = [
            "🌍 Zimbabwe exports tobacco to 50+ countries",
            "👨‍🌾 Tobacco supports 500,000+ families",
            "💰 Tobacco is Zimbabwe's 2nd largest forex earner",
            "🌱 Tobacco related to tomatoes & potatoes",
            "🔥 Curing turns leaves gold in 6-7 days"
        ]
        return random.choice(facts)
    
    for model_name in GEMINI_MODELS[:2]:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=tip_config
            )
            
            prompt = "ONE short fact about Zimbabwe tobacco. 1-2 sentences. Start with emoji."
            response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
                
        except Exception:
            continue
    
    return "🌱 Zimbabwe tobacco is world-famous for quality"

# ==============================
# UNIVERSAL WHATSAPP SENDER - TRIMS ALL RESPONSES TO 800 CHARS
# ==============================
def send_whatsapp(to, text):
    """
    UNIVERSAL sender - EVERY message passes through trim_response()
    Ensures ALL responses are ≤ 800 characters
    """
    if not text:
        text = "Processing..."
    
    # TRIM EVERY SINGLE RESPONSE to 800 chars max
    safe_text = trim_response(text)
    
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": safe_text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        debug_log(f"📤 Sent {len(safe_text)} chars to {to}: {response.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ Send error: {e}")
        return False

# ==============================
# OTHER HELPER FUNCTIONS
# ==============================
def get_user(phone):
    """Get user from Firebase"""
    if not db:
        return None
    try:
        doc = db.collection("users").document(phone).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        debug_log(f"❌ Firebase get error: {e}")
        return None

def save_user(phone, data):
    """Save user to Firebase"""
    if not db:
        return False
    try:
        db.collection("users").document(phone).set(data, merge=True)
        return True
    except Exception as e:
        debug_log(f"❌ Firebase save error: {e}")
        return False

def log_detection(phone, name, disease, confidence):
    """Log detection to Firebase"""
    if not db:
        return
    try:
        db.collection("detections").add({
            "phone": phone,
            "name": name,
            "disease": disease,
            "confidence": confidence,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        debug_log(f"📊 Logged: {disease}")
    except Exception as e:
        debug_log(f"❌ Log error: {e}")
    gc.collect()

def download_image(media_id):
    """Download image from WhatsApp"""
    try:
        debug_log(f"📥 Downloading: {media_id}")
        url_resp = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            timeout=10
        )
        if url_resp.status_code != 200:
            return None
        
        media_data = url_resp.json()
        media_url = media_data.get("url")
        if not media_url:
            return None
        
        img_resp = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            timeout=30
        )
        return img_resp.content if img_resp.status_code == 200 else None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

def call_huggingface_detection(image_bytes):
    """Call Hugging Face Space for ML detection"""
    try:
        debug_log("🔄 Calling HF...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(f"{HF_SPACE_URL}/predict", files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return {
                    "disease": result.get("disease"),
                    "confidence": result.get("confidence"),
                    "treatment": result.get("treatment"),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False)
                }
        return None
    except Exception as e:
        debug_log(f"❌ HF error: {e}")
        return None
    finally:
        gc.collect()

def get_user_history(phone, limit=3):
    """Get user's detection history (limited to 3 for brevity)"""
    if not db:
        return []
    try:
        docs = db.collection("detections")\
            .where("phone", "==", phone)\
            .order_by("timestamp", direction="DESCENDING")\
            .limit(limit)\
            .stream()
        
        history = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("timestamp"):
                ts = data["timestamp"]
                if hasattr(ts, "strftime"):
                    data["date"] = ts.strftime("%d %b")
            history.append(data)
        return history
    except Exception as e:
        debug_log(f"❌ History error: {e}")
        return []

# ==============================
# CONCISE MENUS (All under 800 chars)
# ==============================
def send_main_menu(phone):
    menu = (
        "🌿 *TOBACCO AI*\n"
        "━━━━━━━━━━━━━━\n"
        "1️⃣ Disease Detection\n"
        "2️⃣ Farming Guides\n"
        "3️⃣ My Dashboard\n"
        "4️⃣ Leaf Grading\n"
        "5️⃣ Expert Help\n"
        "6️⃣ Feedback\n\n"
        "Reply with number (1-6)"
    )
    return send_whatsapp(phone, menu)

def send_farming_menu(phone):
    menu = (
        "🌱 *FARMING GUIDES*\n"
        "━━━━━━━━━━━━━━\n"
        "1️⃣ Planting\n"
        "2️⃣ Fertilizer\n"
        "3️⃣ Harvesting\n"
        "4️⃣ Curing\n"
        "5️⃣ Marketing\n"
        "6️⃣ Ask AI\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, menu)

def send_dashboard_menu(phone, name, stats):
    menu = (
        f"📊 *{name}'s STATS*\n"
        "━━━━━━━━━━━━━━\n"
        f"📝 Scans: {stats['total_scans']}\n"
        f"🦠 Top: {stats['top_disease']}\n"
        f"🌿 Healthy: {stats['healthy_count']}\n"
        "━━━━━━━━━━━━━━\n"
        "1️⃣ History\n"
        "2️⃣ Daily Tip\n"
        "3️⃣ Fun Fact\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, menu)

def send_expert_menu(phone):
    menu = (
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━\n"
        "1️⃣ AI Advisor\n"
        "2️⃣ Human Expert\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, menu)

# ==============================
# MESSAGE HANDLER
# ==============================
def handle_message(phone, msg_type, content):
    debug_log(f"📨 Handling: {msg_type} from {phone}")
    
    user = get_user(phone)
    
    # NEW USER
    if not user:
        save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, "🌿 Welcome! Please enter your *name*:")

    state = user.get("state", USER_STATES["ACTIVE"])
    name = user.get("name", "Farmer")

    # AWAITING NAME
    if state == USER_STATES["AWAITING_NAME"] and msg_type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": USER_STATES["ACTIVE"]})
        return send_whatsapp(phone, f"✅ Hi {clean_name}! Send photo to detect diseases or type *menu*")

    # EXPERT MENU
    if state == USER_STATES["EXPERT_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
            return send_whatsapp(phone, "👨‍🌾 Describe issue. Expert will respond (or *cancel*):")
        else:
            return send_whatsapp(phone, "❌ Choose 1, 2, or 0")
    
    # DASHBOARD MENU
    if state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            history = get_user_history(phone)
            if not history:
                msg = "📋 No scans yet"
            else:
                msg = "📋 *Recent*\n"
                for h in history:
                    msg += f"• {h.get('disease')} ({h.get('confidence',0):.0f}%)\n"
            send_whatsapp(phone, msg)
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "2":
            tip = get_gemini_tip()
            send_whatsapp(phone, f"💡 *Tip*\n{tip}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "3":
            fact = get_gemini_fact()
            send_whatsapp(phone, f"🎲 *Fact*\n{fact}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        else:
            return send_whatsapp(phone, "❌ Choose 1-3 or 0")

    # AWAITING AI QUESTION
    if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        send_whatsapp(phone, f"🤔 Thinking...")
        answer = ask_ai_advisor(content)
        send_whatsapp(phone, answer)  # Will be auto-trimmed by send_whatsapp
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # FARMING MENU
    if state == USER_STATES["FARMING_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        guides = {
            "1": PLANTING_GUIDE,
            "2": FERTILIZER_GUIDE,
            "3": HARVESTING_GUIDE,
            "4": CURING_GUIDE,
            "5": MARKETING_GUIDE
        }
        
        if cmd in guides:
            send_whatsapp(phone, guides[cmd])
            return send_farming_menu(phone)
        elif cmd == "6":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        else:
            return send_farming_menu(phone)

    # LEAF GRADING
    if state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Grading")
        send_whatsapp(phone, f"🔍 Analyzing...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        grade, analysis = grade_leaf_with_ai(image_bytes)
        send_whatsapp(phone, analysis)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        return

    # DISEASE DETECTION
    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Detecting")
        send_whatsapp(phone, f"🔍 Analyzing...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        result = call_huggingface_detection(image_bytes)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        
        if not result:
            send_whatsapp(phone, "❌ Analysis failed")
            return send_main_menu(phone)
        
        disease = result["disease"]
        confidence = result["confidence"]
        
        log_detection(phone, name, disease, confidence)
        
        if result["low_confidence"]:
            response = f"⚠️ *Low confidence* ({confidence:.0f}%)\nRetake photo"
        elif result["is_healthy"]:
            response = f"🎉 *Healthy!* ({confidence:.0f}%)"
        else:
            response = f"📊 *{disease}* ({confidence:.0f}%)\n{result['treatment'][:100]}"
        
        send_whatsapp(phone, response)
        
        # Quick disease guide if available
        if not result["is_healthy"] and not result["low_confidence"]:
            for d, guide in DISEASE_QUICK_GUIDES.items():
                if d.lower() in disease.lower():
                    send_whatsapp(phone, guide)
                    break
        
        send_main_menu(phone)
        return

    # AWAITING FEEDBACK
    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"📝 *Feedback* {phone}\n{content[:200]}")
            send_whatsapp(phone, "✅ Thanks!")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # AWAITING EXPERT
    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"🚨 *Expert* {phone}\n{content[:200]}")
            send_whatsapp(phone, "✅ Expert will respond")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # TEXT COMMANDS
    if msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd in ["menu", "0"]:
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            send_whatsapp(phone, "📸 Send clear photo of leaf")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        elif cmd == "3":
            stats = get_user_statistics(phone)
            save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "4":
            save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
            send_whatsapp(phone, "🏷️ Send photo of cured leaf")
        elif cmd == "5":
            save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        elif cmd == "6":
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            send_whatsapp(phone, "📝 Type feedback (or *cancel*):")
        elif cmd.startswith("ai "):
            question = cmd[3:].strip()
            if question:
                send_whatsapp(phone, f"🤔 Thinking...")
                answer = ask_ai_advisor(question)
                send_whatsapp(phone, answer)
                return send_main_menu(phone)
        elif cmd == "help":
            help_text = (
                "📚 *COMMANDS*\n"
                "• menu - Main menu\n"
                "• 1-6 - Menu options\n"
                "• ai [question] - Ask AI"
            )
            send_whatsapp(phone, help_text)
        else:
            send_whatsapp(phone, "Type *menu* for options")

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if verify_token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403
    
    try:
        data = request.json
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "statuses" in value:
            return jsonify({"status": "ok"}), 200
        
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200
        
        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")
        
        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            content = msg.get("image", {}).get("id", "")
        else:
            return jsonify({"status": "ok"}), 200
        
        handle_message(from_number, msg_type, content)
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        debug_log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI is running!"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting on port {port}")
    debug_log(f"📏 MAX RESPONSE LENGTH: {MAX_RESPONSE_LENGTH} chars")
    app.run(host="0.0.0.0", port=port, debug=False)
