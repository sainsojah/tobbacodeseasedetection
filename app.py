"""
Tobacco AI Assistant - Render WhatsApp Bot
Fixed: Model fallback, cooldown enforcement, single progress messages
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

# COMPLETE MODEL LIST WITH FALLBACKS
GEMINI_MODELS = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-pro',
    'models/gemini-1.5-flash',      # Added as fallback
    'models/gemini-1.5-pro',        # Added as fallback
    'models/gemini-3.1-pro-preview',
    'models/gemini-3.1-flash-lite-preview',
    'models/gemini-2.0-flash',
    'models/gemini-2.0-flash-lite',
    'models/gemini-flash-latest',
    'models/gemini-pro-latest'
]

# Spam prevention - cooldown dictionary with timestamp
LAST_SCAN = {}
COOLDOWN_SECONDS = 20  

# Configuration
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 800,
}

vision_config = {
    "temperature": 0.7,
    "max_output_tokens": 800,
    "top_p": 0.8
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

# Disease advice cache
DISEASE_ADVICE_CACHE = {
    "Black Shank": "💧 *Black Shank*\n• Improve soil drainage\n• Remove infected plants\n• Apply Ridomil fungicide\n• Rotate with maize next season",
    "Black Spot": "🔴 *Black Spot*\n• Apply copper fungicide\n• Remove infected leaves\n• Improve air circulation\n• Avoid overhead watering",
    "Early Blight": "🍂 *Early Blight*\n• Apply Mancozeb fungicide\n• Remove lower leaves\n• Space plants properly\n• Rotate crops",
    "Late Blight": "🌧️ *Late Blight*\n• Remove plants immediately\n• Apply Ridomil Gold\n• Use disease-free transplants\n• Avoid excessive moisture",
    "Leaf Mold": "🍃 *Leaf Mold*\n• Apply sulfur fungicide\n• Improve ventilation\n• Reduce humidity\n• Space plants wider",
    "Leaf Spot": "📌 *Leaf Spot*\n• Apply copper fungicide\n• Remove affected leaves\n• Avoid wetting leaves\n• Improve air flow",
    "Powdery Mildew": "⚪ *Powdery Mildew*\n• Apply sulfur spray\n• Reduce nitrogen\n• Improve air circulation\n• Water at base only",
    "Tobacco Mosaic Virus": "⚠️ *TMV - NO CURE*\n• Remove infected plants NOW\n• Wash hands with milk/soap\n• Disinfect tools\n• Use resistant varieties next season",
    "Spider Mites": "🕷️ *Spider Mites*\n• Apply miticide\n• Maintain humidity\n• Avoid water stress\n• Check undersides of leaves",
    "Healthy": "🌿 *Healthy Leaf*\n• Continue good practices\n• Monitor regularly\n• Maintain balanced fertilizer\n• Keep up with watering schedule"
}

# Severity-specific advice
SEVERITY_ADVICE = {
    "Mild": "🟢 *Mild* - Early stage. Monitor closely.",
    "Moderate": "🟡 *Moderate* - Take action now to prevent spread.",
    "Severe": "🔴 *Severe* - Act immediately! Remove affected plants."
}

# WhatsApp safe limit
WHATSAPP_SAFE_LIMIT = 3500  # 4096 is max, using 3500 for safety

def trim_message(text, max_length=WHATSAPP_SAFE_LIMIT):
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
# USER STATES
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
# DISEASE KNOWLEDGE BASE
# ==============================
DISEASE_KNOWLEDGE_BASE = {
    "Black Shank": {
        "cause": "Phytophthora fungus in waterlogged soil",
        "treatment": "Remove infected plants, apply Ridomil fungicide",
        "prevention": "Crop rotation with maize, use resistant varieties, improve drainage",
        "symptoms": "Black lesions on stem, wilting, stunted growth"
    },
    "Black Spot": {
        "cause": "Fungal infection (Cercospora nicotianae)",
        "treatment": "Apply copper-based fungicides, remove infected leaves",
        "prevention": "Improve air circulation, avoid overhead irrigation",
        "symptoms": "Dark circular spots on leaves with yellow halos"
    },
    "Early Blight": {
        "cause": "Alternaria fungus",
        "treatment": "Apply Mancozeb or chlorothalonil, remove lower leaves",
        "prevention": "Crop rotation, proper spacing, avoid working in wet fields",
        "symptoms": "Target-like rings on lower leaves, yellowing"
    },
    "Late Blight": {
        "cause": "Phytophthora infestans (water mold)",
        "treatment": "Remove infected plants immediately, apply Ridomil Gold",
        "prevention": "Avoid excessive moisture, use disease-free transplants",
        "symptoms": "Water-soaked lesions, white fungal growth under leaves"
    },
    "Leaf Mold": {
        "cause": "Passalora fulva fungus in high humidity",
        "treatment": "Apply sulfur-based fungicides, improve ventilation",
        "prevention": "Reduce humidity, proper plant spacing",
        "symptoms": "Yellow spots on upper leaf, mold on underside"
    },
    "Leaf Spot": {
        "cause": "Various fungal pathogens",
        "treatment": "Apply copper fungicides, remove affected leaves",
        "prevention": "Avoid overhead watering, improve air circulation",
        "symptoms": "Small circular spots, leaf yellowing"
    },
    "Powdery Mildew": {
        "cause": "Erysiphe fungus",
        "treatment": "Apply sulfur or potassium bicarbonate",
        "prevention": "Avoid high nitrogen, maintain good air flow",
        "symptoms": "White powdery coating on leaves"
    },
    "Tobacco Mosaic Virus": {
        "cause": "TMV virus (highly contagious)",
        "treatment": "NO CURE - remove infected plants immediately",
        "prevention": "Wash hands with milk/soap, use resistant varieties, disinfect tools",
        "symptoms": "Mottled yellow-green pattern, leaf distortion"
    },
    "Spider Mites": {
        "cause": "Tiny arachnids (Tetranychus species)",
        "treatment": "Apply miticides or insecticidal soap",
        "prevention": "Maintain humidity, avoid water stress",
        "symptoms": "Stippling on leaves, fine webbing"
    }
}

# ==============================
# STATIC GUIDES
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

MARKETING_GUIDE = f"""💰 *MARKETING {datetime.now().year}*
━━━━━━━━━━━━━━━━━━
• Opening: March {datetime.now().year}
• Biometric ID REQUIRED
• Register before February {datetime.now().year}
• Grades: A (Premium), B (Good), C (Fair), D (Low)
• Payment within 24 hours
• Documents: ID, TIMB registration, grower number"""

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
        return "✔️ High Accuracy"
    elif confidence > 60:
        return "⚠️ Medium Accuracy"
    else:
        return "❓ Low Accuracy"

# ==============================
# SEVERITY ESTIMATION
# ==============================
def estimate_severity(disease_area, leaf_area):
    """Calculate severity based on disease area vs leaf area"""
    if leaf_area == 0:
        return "Unknown"
    
    ratio = (disease_area / leaf_area) * 100
    
    if ratio < 10:
        return "Mild"
    elif ratio < 40:
        return "Moderate"
    else:
        return "Severe"

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
        return f"ℹ️ Ask *ai {disease}* for advice"

# ==============================
# IMPROVED AI ADVISOR WITH MODEL FALLBACK LOOP
# ==============================
def ask_ai_advisor(question):
    """AI advisor with complete model fallback loop"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured"
    
    # Check cache first
    for disease in DISEASE_ADVICE_CACHE.keys():
        if disease.lower() in question.lower():
            return f"📚 *{disease}*\n\n{DISEASE_ADVICE_CACHE[disease]}"
    
    # Try each model in sequence - COMPLETE FALLBACK
    for model_name in GEMINI_MODELS:
        try:
            debug_log(f"🔄 Trying: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            prompt = f"""You are a Zimbabwe tobacco expert. Answer concisely.

Question: {question}

Keep it under 100 words. Use bullet points. End with a complete sentence."""
            
            response = model.generate_content(prompt)
            
            if response and response.text:
                answer = response.text.strip()
                debug_log(f"✅ Success with {model_name}")
                return answer
                
        except Exception as e:
            debug_log(f"⚠️ {model_name} failed: {str(e)[:50]}")
            continue
    
    return "⚠️ Service busy. Try *menu* for guides."

# ==============================
# AI VISION ANALYSIS WITH MODEL FALLBACK
# ==============================
def ai_leaf_analysis(image_bytes):
    """AI vision analysis with complete model fallback"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None
    
    # Try each vision-capable model
    vision_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-pro-vision']
    
    for model_name in vision_models:
        try:
            if model_name not in GEMINI_MODELS:
                continue
                
            debug_log(f"🔬 Vision trying: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """Analyze this tobacco leaf. Keep it brief:

🌿 Diagnosis:
🔍 Symptoms:
📊 Severity:
💡 Advice:"""
            
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                debug_log(f"✅ Vision success with {model_name}")
                return response.text.strip()
                
        except Exception as e:
            debug_log(f"⚠️ Vision {model_name} failed")
            continue
    
    return None

# ==============================
# DAILY TIP (Cached)
# ==============================
tip_cache = {}
def get_gemini_tip():
    """Generate or return cached daily tip"""
    today = datetime.now().strftime("%Y-%m-%d")
    if today in tip_cache:
        return tip_cache[today]
    
    tips = [
        "🌱 Rotate crops with maize to prevent soil diseases. This breaks pest cycles naturally.",
        "💧 Water early morning to prevent fungal growth. Leaves dry before evening.",
        "🔍 Check fields weekly for early disease signs. Early detection saves crops.",
        "🧪 Test soil pH before fertilizing. Tobacco needs pH 5.5-6.5 for optimal growth.",
        "🌿 Remove infected leaves immediately to prevent disease spread."
    ]
    
    tip = random.choice(tips)
    tip_cache[today] = tip
    return tip

# ==============================
# FUN FACT (Cached)
# ==============================
fact_cache = {}
def get_gemini_fact():
    """Generate or return cached fact"""
    today = datetime.now().strftime("%Y-%m-%d")
    if today in fact_cache:
        return fact_cache[today]
    
    facts = [
        "🌍 Zimbabwe exports tobacco to over 50 countries worldwide.",
        "👨‍🌾 Tobacco farming supports over 500,000 Zimbabwean families.",
        "💰 Tobacco is Zimbabwe's 2nd largest foreign currency earner.",
        "🌱 Tobacco is related to tomatoes and potatoes - same family!",
        "🔥 Curing turns tobacco leaves from green to gold in 6-7 days."
    ]
    
    fact = random.choice(facts)
    fact_cache[today] = fact
    return fact

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
    """Send WhatsApp message with safety trimming"""
    if not text:
        text = "Processing..."
    
    safe_text = trim_message(text)
    
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
        response = requests.post(url, json=payload, headers=headers, timeout=35)
        debug_log(f"📤 Sent {len(safe_text)} chars: {response.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ Send error: {e}")
        return False

def send_whatsapp_with_retry(to, text, max_retries=2):
    """Send WhatsApp with retry logic"""
    for attempt in range(max_retries):
        if send_whatsapp(to, text):
            return True
        time.sleep(1)
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

def log_detection(phone, name, disease, confidence, severity=None):
    """Log detection to Firebase"""
    if not db:
        return
    try:
        data = {
            "phone": phone,
            "name": name,
            "disease": disease,
            "confidence": confidence,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        if severity:
            data["severity"] = severity
        
        db.collection("detections").add(data)
        debug_log(f"📊 Logged: {disease} ({confidence:.1f}%)")
    except Exception as e:
        debug_log(f"❌ Log error: {e}")

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
        
        if img_resp.status_code == 200:
            debug_log(f"✅ Downloaded: {len(img_resp.content)} bytes")
            return img_resp.content
        return None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

# ==============================
# IMPROVED HUGGINGFACE DETECTION WITH BETTER ERROR HANDLING
# ==============================
def call_huggingface_detection(image_bytes):
    """Call Hugging Face Space with better error handling"""
    try:
        debug_log("🔄 HF detection...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(
            f"{HF_SPACE_URL}/predict",
            files=files,
            timeout=35
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                # Calculate severity if bounding box available
                severity = "Unknown"
                if result.get("bbox") and result.get("leaf_area"):
                    severity = estimate_severity(result.get("bbox"), result.get("leaf_area"))
                elif result.get("confidence", 0) > 0:
                    # Approximate severity from confidence
                    conf = result.get("confidence", 0)
                    if conf > 85:
                        severity = "Moderate"
                    elif conf > 60:
                        severity = "Mild"
                    else:
                        severity = "Unknown"
                
                return {
                    "disease": result.get("disease", "Unknown"),
                    "confidence": result.get("confidence", 0),
                    "treatment": result.get("treatment", ""),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False),
                    "severity": severity,
                    "bbox": result.get("bbox")
                }
        return None
    except requests.exceptions.Timeout:
        debug_log("❌ HF timeout")
        return None
    except Exception as e:
        debug_log(f"❌ HF error: {e}")
        return None

# ==============================
# MENU FUNCTIONS
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
# FIXED MESSAGE HANDLER - NO DUPLICATE MESSAGES, STRONG COOLDOWN
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
        send_whatsapp(phone, f"✅ Hi {clean_name}! Send photo to detect diseases or type *menu*")
        return

    # EXPERT MENU
    if state == USER_STATES["EXPERT_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
            send_whatsapp(phone, "👨‍🌾 Describe issue (or *cancel*):")
        else:
            send_whatsapp(phone, "❌ Choose 1, 2, or 0")
    
    # DASHBOARD MENU
    elif state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
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
                for h in history[:3]:
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
            send_whatsapp(phone, "❌ Choose 1-3 or 0")

    # AWAITING AI QUESTION
    elif state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        send_whatsapp(phone, f"🤔 Thinking...")
        answer = ask_ai_advisor(content)
        send_whatsapp(phone, answer)
        time.sleep(2)  # Brief pause
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # FARMING MENU
    elif state == USER_STATES["FARMING_MENU"] and msg_type == "text":
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
            send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        else:
            return send_farming_menu(phone)

    # LEAF GRADING
    elif state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Grading")
        send_whatsapp(phone, f"🔍 Analyzing...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Use AI vision for grading
        analysis = ai_leaf_analysis(image_bytes)
        if analysis:
            send_whatsapp(phone, f"📊 *Grade Results*\n{analysis}")
        else:
            send_whatsapp(phone, "❌ Grading failed")
        
        # Cleanup
        del image_bytes
        gc.collect()
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(2)
        send_main_menu(phone)
        return

    # FIXED DISEASE DETECTION - STRONG COOLDOWN, NO DUPLICATES
    elif state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        
        # ===== STRONG COOLDOWN ENFORCEMENT =====
        current_time = time.time()
        if phone in LAST_SCAN:
            time_since_last = current_time - LAST_SCAN[phone]
            if time_since_last < COOLDOWN_SECONDS:
                wait_time = int(COOLDOWN_SECONDS - time_since_last)
                debug_log(f"⚠️ Cooldown: {phone} needs to wait {wait_time}s")
                return send_whatsapp(phone, f"⏱️ Please wait {wait_time} seconds between scans.")
        
        # Update last scan time
        LAST_SCAN[phone] = current_time
        # =======================================
        
        debug_log(f"📸 Detection from {phone}")
        
        # Single progress message
        send_whatsapp(phone, f"📷 Processing image...")
        
        # Download image
        image_bytes = download_image(content)
        if not image_bytes:
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Get HF detection
        send_whatsapp(phone, f"🔍 Analyzing with AI model...")
        hf_result = call_huggingface_detection(image_bytes)
        
        if not hf_result:
            send_whatsapp(phone, "❌ Analysis failed. Please try another photo.")
            cleanup_memory(image_bytes)
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            time.sleep(2)
            return send_main_menu(phone)
        
        disease = hf_result["disease"]
        confidence = hf_result["confidence"]
        severity = hf_result.get("severity", "Unknown")
        
        # Build response
        if hf_result["low_confidence"] or confidence < 50:
            response = f"❓ *UNCLEAR DETECTION*\n━━━━━━━━━━━━━━━━━━\n⚠️ Confidence: {confidence:.0f}%\n\n📸 Please send a clearer photo for better accuracy."
        elif hf_result["is_healthy"]:
            response = f"🌿 *HEALTHY LEAF*\n━━━━━━━━━━━━━━━━━━\n✅ Confidence: {confidence:.0f}%\n\n💚 Great job! Your plant looks healthy."
        else:
            response = f"🌿 *{disease.upper()}*\n━━━━━━━━━━━━━━━━━━\n📊 Confidence: {confidence:.0f}%\n"
            
            if severity != "Unknown":
                response += f"{SEVERITY_ADVICE.get(severity, '')}\n"
            
            # Add cached advice
            if disease in DISEASE_ADVICE_CACHE:
                response += f"\n💡 *Advice:*\n{DISEASE_ADVICE_CACHE[disease]}"
            elif hf_result["treatment"]:
                response += f"\n💡 *Treatment:*\n{hf_result['treatment']}"
        
        # Send result
        send_whatsapp(phone, response)
        
        # Log detection
        log_detection(phone, name, disease, confidence, severity)
        
        # Cleanup
        cleanup_memory(image_bytes, hf_result)
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(3)  # Brief pause
        send_main_menu(phone)
        return

    # AWAITING FEEDBACK
    elif state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                admin_msg = (
                    f"📝 *FEEDBACK*\n"
                    f"━━━━━━━━━━\n"
                    f"👤 {name}\n"
                    f"📱 {phone}\n"
                    f"📅 {datetime.now().strftime('%d %b %H:%M')}\n\n"
                    f"💬 {content}"
                )
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "✅ Thanks for your feedback!")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(1)
        return send_main_menu(phone)

    # AWAITING EXPERT
    elif state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                admin_msg = (
                    f"🚨 *EXPERT REQUEST*\n"
                    f"━━━━━━━━━━\n"
                    f"👤 {name}\n"
                    f"📱 {phone}\n"
                    f"📅 {datetime.now().strftime('%d %b %H:%M')}\n\n"
                    f"💬 {content}"
                )
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "✅ Expert will contact you soon.")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(1)
        return send_main_menu(phone)

    # TEXT COMMANDS
    elif msg_type == "text":
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
                time.sleep(2)
                return send_main_menu(phone)
        elif cmd == "help":
            help_text = (
                "📚 *COMMANDS*\n"
                "• menu - Main menu\n"
                "• 1-6 - Options\n"
                "• ai [question] - Ask AI"
            )
            send_whatsapp(phone, help_text)
        else:
            send_whatsapp(phone, "Type *menu* for options")

def get_user_history(phone, limit=3):
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
                    data["date"] = ts.strftime("%d %b")
            history.append(data)
        return history
    except Exception as e:
        debug_log(f"❌ History error: {e}")
        return []

def cleanup_memory(*args):
    """Delete objects and force garbage collection"""
    for obj in args:
        if obj:
            try:
                del obj
            except:
                pass
    gc.collect()

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
    return jsonify({
        "status": "healthy",
        "firebase": db is not None,
        "cooldown": f"{COOLDOWN_SECONDS}s",
        "admin": bool(ADMIN_PHONE),
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI is running!"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting on port {port}")
    debug_log(f"📱 Admin: {'✅' if ADMIN_PHONE else '❌'}")
    debug_log(f"🤖 AI: {'✅' if AI_API_KEY else '❌'}")
    debug_log(f"⏱️ Cooldown: {COOLDOWN_SECONDS}s")
    app.run(host="0.0.0.0", port=port, debug=False)
