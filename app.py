"""
Tobacco AI Assistant - Render WhatsApp Bot
Fixed: Complete working version with Google Generative AI
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
import google.generativeai as genai  # IMPORT THIS

# ==============================
# INITIALIZATION
# ==============================
app = Flask(__name__)

def debug_log(message):
    """Print debug with timestamp - DEFINED FIRST!"""
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
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")

# Configure Google Generative AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    debug_log("✅ Google Generative AI configured")

# Generation config for Gemini
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 200,
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

# Try different model names - will be used in fallback sequence
GEMINI_MODELS = [
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-pro',
    'gemini-1.0-pro'
]

# Helper to trim long messages for WhatsApp
def trim_message(text, max_length=900):
    """Trim message to safe WhatsApp length"""
    if not text:
        return "No response available."
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

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
# DISEASE KNOWLEDGE BASE (Offline Fallback)
# ==============================
DISEASE_KNOWLEDGE_BASE = {
    "Black Shank": {
        "cause": "Phytophthora fungus in waterlogged soil",
        "treatment": "Remove infected plants, apply Ridomil fungicide",
        "prevention": "Crop rotation with maize, use resistant varieties, improve drainage"
    },
    "Black Spot": {
        "cause": "Fungal infection (Cercospora nicotianae)",
        "treatment": "Apply copper-based fungicides, remove infected leaves",
        "prevention": "Improve air circulation, avoid overhead irrigation"
    },
    "Early Blight": {
        "cause": "Alternaria fungus",
        "treatment": "Apply Mancozeb or chlorothalonil, remove lower leaves",
        "prevention": "Crop rotation, proper spacing, avoid working in wet fields"
    },
    "Late Blight": {
        "cause": "Phytophthora infestans (water mold)",
        "treatment": "Remove infected plants immediately, apply Ridomil Gold",
        "prevention": "Avoid excessive moisture, use disease-free transplants"
    },
    "Leaf Mold": {
        "cause": "Passalora fulva fungus in high humidity",
        "treatment": "Apply sulfur-based fungicides, improve ventilation",
        "prevention": "Reduce humidity, proper plant spacing"
    },
    "Leaf Spot": {
        "cause": "Various fungal pathogens",
        "treatment": "Apply copper fungicides, remove affected leaves",
        "prevention": "Avoid overhead watering, improve air circulation"
    },
    "Powdery Mildew": {
        "cause": "Erysiphe fungus",
        "treatment": "Apply sulfur or potassium bicarbonate",
        "prevention": "Avoid high nitrogen, maintain good air flow"
    },
    "Tobacco Mosaic Virus": {
        "cause": "TMV virus (highly contagious)",
        "treatment": "NO CURE - remove infected plants immediately",
        "prevention": "Wash hands with milk/soap, use resistant varieties, disinfect tools"
    },
    "Spider Mites": {
        "cause": "Tiny arachnids (Tetranychus species)",
        "treatment": "Apply miticides or insecticidal soap",
        "prevention": "Maintain humidity, avoid water stress"
    }
}

# Confidence threshold
CONFIDENCE_THRESHOLD = 25.0

# ==============================
# STATIC GUIDES (Fallback if AI fails)
# ==============================
PLANTING_GUIDE = """🌱 *PLANTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Bed size: 1m wide x 10m long
• Plant population: 15,000 plants/ha
• Spacing: 1.1-1.2m between ridges
• Transplant: 6-8 weeks after sowing
• Water immediately after planting
• Gap filling within 7-10 days"""

FERTILIZER_GUIDE = """🧪 *FERTILIZER GUIDE*
━━━━━━━━━━━━━━━━━━
• Basal: Compound L (5:14:7) 400-600 kg/ha
• Top dressing 1: Ammonium Nitrate 150-200 kg/ha
• Top dressing 2: Potassium Nitrate 100-150 kg/ha
• Apply when soil is moist
• Never place fertilizer directly under plant
• Test soil pH (target 5.5-6.5)"""

HARVESTING_GUIDE = """🌾 *HARVESTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Harvest from bottom upward (priming)
• 2-3 leaves per harvest, 4-6 primings total
• Priming 1 (Sand leaves): 60-65 days
• Priming 2-3 (Cutters): Best quality
• Priming 4-5 (Leaf): Upper middle
• Priming 6 (Tips): Highest nicotine

Ripeness indicators:
• Color: Light green to yellow-green
• Texture: Slightly sticky
• Midrib: Snaps cleanly
• Tips: Curved down"""

CURING_GUIDE = """🔥 *CURING GUIDE*
━━━━━━━━━━━━━━━━━━
Yellowing (32-38°C, 48hrs, 85-90% humidity)
• Leaves turn yellow, chlorophyll breaks down

Leaf drying (38-52°C, 48hrs, 70-80% humidity)
• Lamina dries, color sets

Midrib drying (52-60°C, 24hrs, 50-60% humidity)
• Stems become brittle

Killing out (60-71°C, 6hrs, 30-40% humidity)
• Sterilize, fix final color"""

MARKETING_GUIDE = """💰 *MARKETING 2026*
━━━━━━━━━━━━━━━━━━
• Opening: March 2026
• Biometric ID REQUIRED
• Register before February 2026
• Grades: A (Premium), B (Good), C (Fair), D (Low)
• Payment within 24 hours
• Documents: ID, TIMB registration, grower number"""

GUIDES = {
    "planting": PLANTING_GUIDE,
    "fertilizer": FERTILIZER_GUIDE,
    "harvesting": HARVESTING_GUIDE,
    "curing": CURING_GUIDE,
    "marketing": MARKETING_GUIDE
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
        
        # Find most common disease
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
        return "✔ *High Accuracy*"
    elif confidence > 60:
        return "⚠ *Medium Accuracy*"
    else:
        return "❗ *Low Accuracy - please retake photo*"

# ==============================
# OFFLINE DISEASE ADVICE
# ==============================
def get_offline_disease_advice(disease):
    """Get disease advice from local knowledge base"""
    if disease in DISEASE_KNOWLEDGE_BASE:
        info = DISEASE_KNOWLEDGE_BASE[disease]
        return f"""📚 *{disease} - Quick Reference*

🔍 *Cause:*
{info['cause']}

💊 *Treatment:*
{info['treatment']}

🛡️ *Prevention:*
{info['prevention']}"""
    else:
        return f"ℹ️ For specific advice on {disease}, please ask the AI advisor (type *ai your question*)"

# ==============================
# AI ADVISOR WITH MODEL FALLBACK USING GENAI LIBRARY
# ==============================
def ask_ai_advisor(question):
    """AI advisor using google.generativeai library"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured. Please add API key."
    
    # Check if question contains a known disease name
    disease_found = None
    for disease in DISEASE_KNOWLEDGE_BASE.keys():
        if disease.lower() in question.lower():
            disease_found = disease
            break
    
    # Try each model in sequence until one works
    for model_name in GEMINI_MODELS:
        try:
            # ⏱️ Add small delay to prevent rate limiting
            time.sleep(1)
            
            debug_log(f"🔄 Trying Gemini model: {model_name}")
            
            # Create the model with generation config
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Create prompt
            prompt = f"You are a Zimbabwe tobacco expert. Answer briefly and practically:\n\nQuestion: {question}\n\nKeep response under 400 characters for WhatsApp."
            
            # Generate response
            response = model.generate_content(prompt)
            
            if response and response.text:
                answer = response.text.strip()
                debug_log(f"✅ Success with model: {model_name}")
                return trim_message(answer, 900)
            else:
                debug_log(f"⚠️ Empty response from {model_name}")
                continue
                
        except Exception as e:
            debug_log(f"❌ Error with {model_name}: {e}")
            continue
    
    # If all models fail, use fallback
    debug_log(f"⚠️ All Gemini models failed, using fallback")
    if disease_found:
        return trim_message(get_offline_disease_advice(disease_found), 900)
    else:
        return "⚠️ AI service temporarily unavailable. Please try again later or use the farming guides (type *menu*)."

# ==============================
# AI LEAF GRADING WITH MODEL FALLBACK
# ==============================
def grade_leaf_with_ai(image_bytes):
    """Grade leaf using google.generativeai library"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI grading not configured"
    
    # Try each model in sequence
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(1)
            
            debug_log(f"🔄 Trying Gemini Vision with model: {model_name}")
            
            # Create the model with vision capabilities
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 150,
                    "top_p": 0.8
                }
            )
            
            # Prepare image for Gemini
            image_parts = [
                {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode('utf-8')
                }
            ]
            
            # Create prompt
            prompt = "Grade this tobacco leaf by color, quality, and damage. Be brief. Return in format:\nGrade: [A/B/C/D]\nColor: [brief]\nDamage: [brief]\nMarket: [Premium/Good/Average/Poor]"
            
            # Generate response with image
            response = model.generate_content([prompt, image_parts[0]])
            
            if response and response.text:
                analysis = response.text.strip()
                debug_log(f"✅ Success with model: {model_name}")
                return "Grade", trim_message(analysis, 500)
            else:
                debug_log(f"⚠️ Empty response from {model_name}")
                continue
                
        except Exception as e:
            debug_log(f"❌ Error with {model_name}: {e}")
            continue
    
    # If all models fail
    return None, "⚠️ Grading service temporarily unavailable. Please try again later."

# ==============================
# GEMINI-POWERED DAILY TIPS
# ==============================
def get_gemini_tip():
    """Generate a fresh daily farming tip"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases",
            "💧 Water in the morning to reduce humidity and prevent fungal growth",
            "🔍 Check fields weekly for early signs of disease"
        ])
    
    # Try models for tip generation
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            
            current_month = datetime.now().strftime("%B")
            
            # Determine current season in Zimbabwe
            if current_month in ["November", "December", "January", "February", "March"]:
                season = "rainy/planting season"
            elif current_month in ["April", "May", "June", "July"]:
                season = "harvesting/curing season"
            else:
                season = "land preparation season"
            
            debug_log(f"🔄 Generating tip with {model_name}")
            
            # Create model
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.8,
                    "max_output_tokens": 100
                }
            )
            
            # Generate tip
            prompt = f"Generate ONE short farming tip for Zimbabwe tobacco farmers during {season}. Max 250 characters. Start with an emoji."
            response = model.generate_content(prompt)
            
            if response and response.text:
                tip = response.text.strip()
                return trim_message(tip, 250)
            else:
                continue
                
        except Exception:
            continue
    
    # Fallback
    return random.choice([
        "🌱 Monitor your fields daily for early disease signs.",
        "💧 Water early morning to prevent fungal growth.",
        "🔍 Check lower leaves regularly for pests and diseases."
    ])

# ==============================
# GEMINI-POWERED FUN FACTS
# ==============================
def get_gemini_fact():
    """Generate a fresh interesting fact"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🌱 Tobacco is related to tomatoes and potatoes!",
            "🍃 Zimbabwe produces world-class flue-cured tobacco",
            "📜 Tobacco has been cultivated for over 8,000 years"
        ])
    
    # Try models for fact generation
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            
            debug_log(f"🔄 Generating fact with {model_name}")
            
            # Create model
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.9,
                    "max_output_tokens": 100
                }
            )
            
            # Generate fact
            prompt = "Generate ONE interesting fact about Zimbabwe tobacco farming. Max 250 characters. Start with an emoji."
            response = model.generate_content(prompt)
            
            if response and response.text:
                fact = response.text.strip()
                return trim_message(fact, 250)
            else:
                continue
                
        except Exception:
            continue
    
    # Fallback
    return random.choice([
        "🌱 Zimbabwe's tobacco industry employs over 500,000 people.",
        "📜 Tobacco has been cultivated for over 8,000 years.",
        "🌍 Zimbabwe exports tobacco to over 50 countries."
    ])

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
    """Send WhatsApp message"""
    if not text:
        text = "Processing..."
    
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        debug_log(f"📤 WhatsApp sent to {to}: {response.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ WhatsApp send error: {e}")
        return False

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
        debug_log(f"📊 Detection logged: {disease} ({confidence:.1f}%)")
    except Exception as e:
        debug_log(f"❌ Log error: {e}")
    
    gc.collect()

def download_image(media_id):
    """Download image from WhatsApp"""
    try:
        debug_log(f"📥 Downloading media ID: {media_id}")
        url_resp = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            timeout=10
        )
        if url_resp.status_code != 200:
            debug_log(f"❌ Failed to get media URL: {url_resp.status_code}")
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
        
        if img_resp.status_code == 200:
            debug_log(f"✅ Image downloaded: {len(img_resp.content)} bytes")
            return img_resp.content
        else:
            debug_log(f"❌ Failed to download image: {img_resp.status_code}")
            return None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

def call_huggingface_detection(image_bytes):
    """Call Hugging Face Space for ML detection"""
    try:
        debug_log("🔄 Calling Hugging Face ML service...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(
            f"{HF_SPACE_URL}/predict",
            files=files,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            debug_log(f"✅ HF Response received")
            
            if result.get("success"):
                return {
                    "disease": result.get("disease"),
                    "confidence": result.get("confidence"),
                    "treatment": result.get("treatment"),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False)
                }
            else:
                debug_log(f"❌ HF returned error")
                return None
        else:
            debug_log(f"❌ HF HTTP error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        debug_log("❌ HF request timed out")
        return None
    except Exception as e:
        debug_log(f"❌ HF call error: {e}")
        return None
    finally:
        gc.collect()

def get_user_history(phone, limit=5):
    """Get user's detection history"""
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
                    data["date"] = ts.strftime("%d %b %Y")
            history.append(data)
        return history
    except Exception as e:
        debug_log(f"❌ History error: {e}")
        return []

def send_main_menu(phone):
    """Helper function to send main menu"""
    menu = (
        "🌿 *TOBACCO AI MAIN MENU*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Disease Detection* - Send photo\n"
        "2️⃣ *Farming Practices* - Guides & AI advice\n"
        "3️⃣ *My Dashboard* - Stats, History, Tips\n"
        "4️⃣ *Leaf Grading* - Quality assessment\n"
        "5️⃣ *Expert Help* - Agronomist & AI\n"
        "6️⃣ *Feedback* - Send comments\n\n"
        "Reply with number (e.g., *1*)\n"
        "Or type *help* for commands"
    )
    return send_whatsapp(phone, menu)

def send_farming_menu(phone):
    """Send farming practices submenu"""
    farming_menu = (
        "🌱 *FARMING PRACTICES*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Planting Guide*\n"
        "2️⃣ *Fertilizer Guide*\n"
        "3️⃣ *Harvesting Guide*\n"
        "4️⃣ *Curing Guide*\n"
        "5️⃣ *Marketing Guide*\n"
        "6️⃣ *Ask AI*\n\n"
        "Reply with number (1-6)\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, farming_menu)

def send_dashboard_menu(phone, name, stats):
    """Send dashboard menu"""
    dashboard = (
        "📊 *MY DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Farmer:* {name}\n"
        f"📱 *Phone:* {phone}\n\n"
        f"📝 *Total Scans:* {stats['total_scans']}\n"
        f"🦠 *Common Issue:* {stats['top_disease']}\n"
        f"🌿 *Healthy Leaves:* {stats['healthy_count']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *View History*\n"
        "2️⃣ *Daily Tip*\n"
        "3️⃣ *Fun Fact*\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, dashboard)

def send_expert_menu(phone):
    """Send expert help menu"""
    expert_menu = (
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *AI Advisor* - Ask anything\n"
        "2️⃣ *Human Expert* - Talk to agronomist\n\n"
        "Reply with number (1 or 2)\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, expert_menu)

# ==============================
# ENHANCED MESSAGE HANDLER
# ==============================
def handle_message(phone, msg_type, content):
    """Main message handler with all enhancements"""
    debug_log(f"📨 Handling message: type={msg_type}, phone={phone}")
    
    user = get_user(phone)
    nav = "\n\n---\n0️⃣ Main Menu"
    
    # NEW USER
    if not user:
        save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, 
            "🌿 *Welcome to Tobacco AI!*\n\n"
            "I help tobacco farmers detect diseases and learn best practices.\n\n"
            "Please enter your *name* to continue:")

    state = user.get("state", USER_STATES["ACTIVE"])
    name = user.get("name", "Farmer")

    # AWAITING NAME
    if state == USER_STATES["AWAITING_NAME"] and msg_type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": USER_STATES["ACTIVE"]})
        welcome_msg = (
            f"✅ *Welcome, {clean_name}!*\n\n"
            f"What would you like to do?\n\n"
            f"• Send a *photo* to detect diseases\n"
            f"• Type *menu* for all options"
        )
        return send_whatsapp(phone, welcome_msg)

    # EXPERT MENU HANDLER
    if state == USER_STATES["EXPERT_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, 
                "🤖 *AI Advisor*\n\n"
                "Ask me anything about tobacco farming.\n\n"
                "Type your question below (or *cancel* to go back):")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
            return send_whatsapp(phone, 
                "👨‍🌾 *Talk to an Agronomist*\n\n"
                "Describe your farming issue. A human expert will respond soon.\n\n"
                "Type your message (or *cancel* to go back):")
        else:
            return send_whatsapp(phone, "❌ Please choose 1 or 2 (or *0* for Main Menu).")
    
    # DASHBOARD MENU HANDLER
    if state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            # History
            history = get_user_history(phone)
            if not history:
                msg = "📋 *No scan history yet.*\n\nSend a photo to start!"
                send_whatsapp(phone, msg)
                # Return to dashboard menu
                stats = get_user_statistics(phone)
                return send_dashboard_menu(phone, name, stats)
            else:
                msg = "📋 *YOUR SCAN HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, h in enumerate(history[:5], 1):
                    msg += f"{i}. *{h.get('disease', 'Unknown')}* - {h.get('confidence', 0):.1f}%\n"
                    msg += f"   📅 {h.get('date', 'Unknown')}\n\n"
                send_whatsapp(phone, trim_message(msg))
                # Return to dashboard menu
                stats = get_user_statistics(phone)
                return send_dashboard_menu(phone, name, stats)
        elif cmd == "2":
            # Tip
            tip = get_gemini_tip()
            send_whatsapp(phone, f"💡 *Daily Tip*\n\n{tip}")
            # Return to dashboard menu
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "3":
            # Fact
            fact = get_gemini_fact()
            send_whatsapp(phone, f"🎲 *Did You Know?*\n\n{fact}")
            # Return to dashboard menu
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        else:
            return send_whatsapp(phone, "❌ Please choose 1, 2, or 3 (or *0* for Main Menu).")

    # AWAITING AI QUESTION
    if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
        answer = ask_ai_advisor(content)
        send_whatsapp(phone, trim_message(answer))
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # FARMING PRACTICES SUBMENU HANDLER
    if state == USER_STATES["FARMING_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Static guides for quick response
        static_guides = {
            "1": PLANTING_GUIDE,
            "2": FERTILIZER_GUIDE,
            "3": HARVESTING_GUIDE,
            "4": CURING_GUIDE,
            "5": MARKETING_GUIDE
        }
        
        if cmd in static_guides:
            send_whatsapp(phone, static_guides[cmd])
            # Stay in farming menu
            return send_farming_menu(phone)
        elif cmd == "6":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, 
                "🤖 *AI Advisor*\n\n"
                "Ask me anything about tobacco farming.\n\n"
                "Type your question below (or *cancel* to go back):")
        else:
            send_whatsapp(phone, "❌ Please choose 1-6 (or *0* for Main Menu).")
            return send_farming_menu(phone)

    # LEAF GRADING
    if state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Processing grading image from {phone}")
        send_whatsapp(phone, f"🔍 Analyzing leaf quality, {name}...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            debug_log("❌ Download failed")
            send_whatsapp(phone, "❌ Failed to download image. Please try again.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        grade, analysis = grade_leaf_with_ai(image_bytes)
        if analysis:
            send_whatsapp(phone, trim_message(analysis))
        else:
            send_whatsapp(phone, "❌ Could not analyze the image. Please try again.")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        gc.collect()
        return

    # DISEASE DETECTION (image)
    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Processing disease detection from {phone}")
        send_whatsapp(phone, f"🔍 Downloading your image, {name}...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            debug_log("❌ Download failed")
            send_whatsapp(phone, "❌ Failed to download image. Please try again.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        send_whatsapp(phone, f"✅ Image downloaded! Running AI analysis...")
        
        result = call_huggingface_detection(image_bytes)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        
        if not result:
            debug_log("❌ Detection failed")
            send_whatsapp(phone, "❌ AI analysis failed. Please try another photo.")
            return send_main_menu(phone)
        
        disease = result["disease"]
        confidence = result["confidence"]
        confidence_msg = get_confidence_message(confidence)
        
        debug_log(f"✅ Detection result: {disease} ({confidence:.1f}%)")
        log_detection(phone, name, disease, confidence)
        
        if result["low_confidence"]:
            response = f"⚠️ *Low Confidence ({confidence:.1f}%)*\n\n{confidence_msg}\n\nPlease upload a clearer photo."
        elif result["is_healthy"]:
            response = f"🎉 *Healthy Leaf Detected!*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}\n\nGreat job!"
        else:
            response = f"📊 *{disease} DETECTED*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}\n\n*Treatment:*\n{result['treatment']}"
        
        send_whatsapp(phone, trim_message(response))
        
        if not result["is_healthy"] and not result["low_confidence"]:
            offline_advice = get_offline_disease_advice(disease)
            send_whatsapp(phone, trim_message(offline_advice) + "\n\nType *ai your question* for more advice")
        
        send_main_menu(phone)
        gc.collect()
        return

    # AWAITING FEEDBACK
    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Feedback cancelled.")
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"📝 *Feedback from {name}*\n{phone}\n\n{content}")
            send_whatsapp(phone, "✅ Thank you! Your feedback has been sent.")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # AWAITING EXPERT
    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Expert request cancelled.")
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"🚨 *EXPERT REQUEST from {name}*\n{phone}\n\n{content}")
            send_whatsapp(phone, "👨‍🌾 Your request has been sent. An expert will contact you soon.")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # TEXT COMMANDS
    if msg_type == "text":
        cmd = content.lower().strip()
        
        # MAIN MENU
        if cmd in ["menu", "0", "main"]:
            return send_main_menu(phone)
        
        # 1. DISEASE DETECTION
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            send_whatsapp(phone, 
                "📸 *Disease Detection*\n\n"
                "Send a clear photo of the tobacco leaf.\n\n"
                "Tips: Good lighting, close-up, steady camera")
        
        # 2. FARMING PRACTICES
        elif cmd in ["2", "farming"]:
            save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        
        # 3. MY DASHBOARD
        elif cmd in ["3", "dashboard"]:
            stats = get_user_statistics(phone)
            save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
            return send_dashboard_menu(phone, name, stats)
        
        # 4. LEAF GRADING
        elif cmd in ["4", "grade"]:
            save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
            send_whatsapp(phone, 
                "🏷️ *LEAF QUALITY GRADING*\n\n"
                "Send a clear photo of your cured leaf.\n\n"
                "I'll analyze: grade, color, damage\n\n"
                "Tips: Good lighting, flat surface")
        
        # 5. EXPERT HELP
        elif cmd in ["5", "expert"]:
            save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        
        # 6. FEEDBACK
        elif cmd in ["6", "feedback"]:
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            send_whatsapp(phone, 
                "📝 *Send Feedback*\n\n"
                "Type your message below (or *cancel*):")
        
        # AI ADVISOR (direct)
        elif cmd.startswith("ai "):
            question = cmd[3:].strip()
            if question:
                send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
                answer = ask_ai_advisor(question)
                send_whatsapp(phone, trim_message(answer))
                return send_main_menu(phone)
            else:
                send_whatsapp(phone, "❓ Example: *ai how to prevent black shank*")
        
        # HELP
        elif cmd == "help":
            help_text = (
                "📚 *QUICK HELP*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• *menu* - Main menu\n"
                "• *1* - Disease detection\n"
                "• *2* - Farming practices\n"
                "• *3* - Dashboard\n"
                "• *4* - Leaf grading\n"
                "• *5* - Expert help\n"
                "• *6* - Feedback\n"
                "• *ai [question]* - Ask AI"
            )
            send_whatsapp(phone, help_text)
        
        else:
            send_whatsapp(phone, 
                "❓ Command not recognized.\n\n"
                "Type *menu* to see options")

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Main webhook endpoint"""
    if request.method == "GET":
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if verify_token == VERIFY_TOKEN:
            debug_log("✅ Webhook verified")
            return challenge, 200
        debug_log("❌ Webhook verification failed")
        return "Forbidden", 403
    
    try:
        data = request.json
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "statuses" in value:
            return jsonify({"status": "ignored"}), 200
        
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
            return jsonify({"status": "ignored"}), 200
        
        if msg_type in ["text", "image"]:
            handle_message(from_number, msg_type, content)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        debug_log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "firebase": db is not None,
        "huggingface_url": HF_SPACE_URL,
        "ai_provider": AI_PROVIDER if AI_API_KEY else "disabled",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    """Root endpoint"""
    return "🌿 Tobacco AI Assistant is running!"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting Tobacco AI Assistant on port {port}")
    debug_log(f"🤖 Using Hugging Face Space: {HF_SPACE_URL}")
    debug_log(f"🧠 Available Gemini models: {', '.join(GEMINI_MODELS)}")
    if AI_API_KEY and AI_API_KEY != "your_api_key_here":
        debug_log(f"✅ AI Advisor enabled with model fallback")
    else:
        debug_log(f"ℹ️ AI Advisor disabled - set AI_API_KEY environment variable")
    app.run(host="0.0.0.0", port=port, debug=False)
