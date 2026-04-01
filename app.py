"""
Tobacco AI Assistant - Render WhatsApp Bot
With PayNow Payments (USD & ZWG)
Minimum donation: $0.50 USD / 15 ZWG
All payment methods supported
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
# PAYNOW LIBRARY - Correct import
# ==============================
try:
    from paynow import Paynow
    PAYNOW_AVAILABLE = True
    print("✅ Paynow library imported successfully")
except ImportError as e:
    PAYNOW_AVAILABLE = False
    print(f"⚠️ Paynow library import error: {e}")
    print("⚠️ Payments will be disabled. Install with: pip install paynow")

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

# PayNow Credentials (separate for USD and ZWG)
PAYNOW_USD_API_KEY = os.environ.get("PAYNOW_USD_API_KEY")
PAYNOW_USD_MERCHANT_ID = os.environ.get("PAYNOW_USD_MERCHANT_ID")
PAYNOW_ZWG_API_KEY = os.environ.get("PAYNOW_ZWG_API_KEY")
PAYNOW_ZWG_MERCHANT_ID = os.environ.get("PAYNOW_ZWG_MERCHANT_ID")
RESULT_URL = os.environ.get("RESULT_URL")  # where PayNow sends payment status

# ==============================
# PAYNOW INSTANCES
# ==============================
paynow_usd = None
paynow_zwg = None

if PAYNOW_AVAILABLE:
    try:
        if PAYNOW_USD_API_KEY and PAYNOW_USD_MERCHANT_ID:
            paynow_usd = Paynow(
                PAYNOW_USD_MERCHANT_ID, 
                PAYNOW_USD_API_KEY, 
                RESULT_URL, 
                RESULT_URL
            )
            debug_log("✅ PayNow USD initialized")
        else:
            debug_log("⚠️ PayNow USD credentials missing")
            
        if PAYNOW_ZWG_API_KEY and PAYNOW_ZWG_MERCHANT_ID:
            paynow_zwg = Paynow(
                PAYNOW_ZWG_MERCHANT_ID, 
                PAYNOW_ZWG_API_KEY, 
                RESULT_URL, 
                RESULT_URL
            )
            debug_log("✅ PayNow ZWG initialized")
        else:
            debug_log("⚠️ PayNow ZWG credentials missing")
            
        if not paynow_usd and not paynow_zwg:
            debug_log("⚠️ No PayNow credentials provided. Payments will be disabled.")
    except Exception as e:
        debug_log(f"❌ PayNow initialization error: {e}")
        PAYNOW_AVAILABLE = False
else:
    debug_log("⚠️ Paynow library not installed. Payments disabled.")

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

# Spam prevention
LAST_SCAN = {}

# Generation configs
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 1000,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

vision_config = {"temperature": 0.7, "max_output_tokens": 800, "top_p": 0.8}
tip_config = {"temperature": 0.8, "max_output_tokens": 600}
fact_config = {"temperature": 0.9, "max_output_tokens": 600}

def trim_message(text, max_length=3000):
    if not text:
        return "No response available."
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

# ==============================
# HTTP SESSION
# ==============================
def create_session_with_retries():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=["POST", "GET"])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=5)
    session.mount('https://', adapter)
    return session

http_session = create_session_with_retries()

# ==============================
# FIREBASE
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
    "DASHBOARD_MENU": "dashboard_menu",
    "WAITING_AI_VISION": "waiting_ai_vision",
    "WAITING_AI_VISION_DISEASE": "waiting_ai_vision_disease",
    "WAITING_AI_VISION_CURING": "waiting_ai_vision_curing",
    "PAYMENT_MENU": "payment_menu",
    "PAYMENT_CURRENCY": "payment_currency",
    "PAYMENT_METHOD": "payment_method",
    "PAYMENT_AMOUNT": "payment_amount",
    "PAYMENT_INNBUCKS_CODE": "payment_innbucks_code",
    "PAYMENT_PROCESSING": "payment_processing"
}

# ==============================
# PAYMENT METHODS
# ==============================
PAYMENT_METHODS = {
    "USD": [
        "EcoCash USD",
        "InnBucks USD",
        "Zimswitch USD",
        "Internet/Mobile Banking USD",
        "POS2U USD",
        "Visa/Mastercard USD"
    ],
    "ZWG": [
        "EcoCash ZWG",
        "OneMoney ZWG",
        "Telecash ZWG",
        "Zimswitch ZWG",
        "Internet/Mobile Banking ZWG",
        "POS2U ZWG",
        "Visa/Mastercard ZWG"
    ]
}

METHOD_TYPE = {
    "EcoCash USD": {"type": "mobile", "method": "ecocash", "currency": "USD"},
    "InnBucks USD": {"type": "mobile", "method": "innbucks", "currency": "USD"},
    "Zimswitch USD": {"type": "link", "currency": "USD"},
    "Internet/Mobile Banking USD": {"type": "link", "currency": "USD"},
    "POS2U USD": {"type": "link", "currency": "USD"},
    "Visa/Mastercard USD": {"type": "link", "currency": "USD"},
    "EcoCash ZWG": {"type": "mobile", "method": "ecocash", "currency": "ZWG"},
    "OneMoney ZWG": {"type": "mobile", "method": "onemoney", "currency": "ZWG"},
    "Telecash ZWG": {"type": "mobile", "method": "telecash", "currency": "ZWG"},
    "Zimswitch ZWG": {"type": "link", "currency": "ZWG"},
    "Internet/Mobile Banking ZWG": {"type": "link", "currency": "ZWG"},
    "POS2U ZWG": {"type": "link", "currency": "ZWG"},
    "Visa/Mastercard ZWG": {"type": "link", "currency": "ZWG"}
}

MIN_AMOUNT_USD = 0.50
MIN_AMOUNT_ZWG = 15

# ==============================
# PAYMENT FUNCTIONS
# ==============================
def get_paynow_instance(currency):
    """Return the correct PayNow instance for the currency"""
    if currency == "USD":
        return paynow_usd
    elif currency == "ZWG":
        return paynow_zwg
    return None

def start_mobile_payment(phone, name, amount, currency, method, innbucks_code=None):
    """Initiate mobile payment using the appropriate PayNow instance"""
    paynow = get_paynow_instance(currency)
    if not paynow:
        return False, f"PayNow {currency} not configured"

    reference = f"Ref-{phone.replace('+', '')}-{currency}"
    email = f"{phone}@tobacco.ai"

    payment = paynow.create_payment(reference, email)
    payment.add("Tobacco AI Service", amount)

    try:
        if method == 'innbucks' and innbucks_code:
            response = paynow.send_mobile(payment, phone, method, innbucks_code)
        else:
            response = paynow.send_mobile(payment, phone, method)

        if response.success:
            poll_url = response.poll_url
            debug_log(f"✅ {currency} payment initiated: {reference}")
            return True, poll_url
        else:
            debug_log(f"❌ {currency} payment failed")
            return False, "Payment initiation failed. Please try again."
    except Exception as e:
        debug_log(f"❌ {currency} payment exception: {e}")
        return False, f"Error: {str(e)}"

def generate_payment_link(phone, name, amount, currency, method_name):
    """Generate a payment link using the appropriate PayNow instance"""
    paynow = get_paynow_instance(currency)
    if not paynow:
        return False, f"PayNow {currency} not configured"

    reference = f"Ref-{phone.replace('+', '')}-{currency}"
    email = f"{phone}@tobacco.ai"

    payment = paynow.create_payment(reference, email)
    payment.add("Tobacco AI Service", amount)

    response = paynow.send(payment)

    if response.success:
        link = response.redirect_url
        debug_log(f"✅ {currency} payment link generated")
        return True, link
    else:
        return False, "Could not generate payment link. Please try again."

# ==============================
# DISEASE KNOWLEDGE BASE
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
# USER STATISTICS
# ==============================
def get_user_statistics(phone):
    """Get detailed statistics for a user"""
    if not db:
        return {
            "total_scans": 0,
            "hf_scans": 0,
            "ai_vision_scans": 0,
            "curing_scans": 0,
            "top_disease": "None",
            "healthy_count": 0
        }
    
    try:
        docs = db.collection("detections").where("phone", "==", phone).stream()
        total_scans = 0
        hf_scans = 0
        ai_vision_scans = 0
        curing_scans = 0
        disease_counts = {}
        healthy_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            total_scans += 1
            detection_type = data.get("detection_type", "hf_disease")
            
            if detection_type == "hf_disease":
                hf_scans += 1
            elif detection_type == "ai_vision_disease":
                ai_vision_scans += 1
            elif detection_type == "ai_vision_curing":
                curing_scans += 1
            
            disease = data.get("disease", "Unknown")
            if detection_type != "ai_vision_curing":
                if disease == "Healthy" or "healthy" in disease.lower():
                    healthy_count += 1
                else:
                    disease_counts[disease] = disease_counts.get(disease, 0) + 1
        
        top_disease = "None"
        if disease_counts:
            top_disease = max(disease_counts, key=disease_counts.get)
        
        return {
            "total_scans": total_scans,
            "hf_scans": hf_scans,
            "ai_vision_scans": ai_vision_scans,
            "curing_scans": curing_scans,
            "top_disease": top_disease,
            "healthy_count": healthy_count
        }
    except Exception as e:
        debug_log(f"❌ Stats error: {e}")
        return {
            "total_scans": 0,
            "hf_scans": 0,
            "ai_vision_scans": 0,
            "curing_scans": 0,
            "top_disease": "None",
            "healthy_count": 0
        }

# ==============================
# AI FUNCTIONS (condensed for space - keep all from previous)
# ==============================
def get_confidence_message(confidence):
    if confidence > 85:
        return "✔ *High Accuracy*"
    elif confidence > 60:
        return "⚠ *Medium Accuracy*"
    else:
        return "❗ *Low Accuracy - please retake photo*"

def estimate_severity(disease_area, leaf_area):
    if leaf_area == 0:
        return "Unknown"
    ratio = (disease_area / leaf_area) * 100
    if ratio < 10:
        return "Mild"
    elif ratio < 40:
        return "Moderate"
    else:
        return "Severe"

def get_offline_disease_advice(disease):
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
# MENU FUNCTIONS
# ==============================
def send_main_menu(phone):
    menu = (
        "🌿 *TOBACCO AI MAIN MENU*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Disease Detection* - Send photo\n"
        "2️⃣ *Farming Practices* - Guides & AI advice\n"
        "3️⃣ *My Dashboard* - Stats, History, Tips\n"
        "4️⃣ *Leaf Grading* - Quality assessment\n"
        "5️⃣ *AI Vision* - Disease/Curing analysis\n"
        "6️⃣ *Expert Help* - Agronomist & AI\n"
        "7️⃣ *Feedback* - Send comments\n"
        "8️⃣ *Payments* - Donate / Buy services\n\n"
        "Reply with number (e.g., *1*)\n"
        "Or type *help* for commands"
    )
    return send_whatsapp(phone, menu)

def send_farming_menu(phone):
    farming_menu = (
        "🌱 *FARMING PRACTICES*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Planting Guide*\n"
        "2️⃣ *Fertilizer Guide*\n"
        "3️⃣ *Harvesting Guide*\n"
        "4️⃣ *Curing Guide*\n"
        "5️⃣ *Marketing Guide*\n"
        "6️⃣ *Ask AI*\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, farming_menu)

def send_dashboard_menu(phone, name, stats):
    dashboard = (
        "📊 *MY DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Farmer:* {name}\n"
        f"📱 *Phone:* {phone}\n\n"
        f"📊 *Total Activities:* {stats['total_scans']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔬 *HF Detections:* {stats['hf_scans']}\n"
        f"👁️ *AI Vision Disease:* {stats['ai_vision_scans']}\n"
        f"🔥 *Curing Monitors:* {stats['curing_scans']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🦠 *Most Common:* {stats['top_disease']}\n"
        f"🌿 *Healthy Leaves:* {stats['healthy_count']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *View History*\n"
        "2️⃣ *Daily Tip*\n"
        "3️⃣ *Fun Fact*\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, dashboard)

def send_expert_menu(phone):
    expert_menu = (
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *AI Advisor* - Ask anything\n"
        "2️⃣ *Human Expert* - Talk to agronomist\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, expert_menu)

def send_ai_vision_menu(phone):
    menu = (
        "🔬 *AI VISION OPTIONS*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Disease Detection* - AI analyzes leaf for diseases\n"
        "2️⃣ *Curing Monitor* - Check curing progress\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, menu)

def send_currency_menu(phone):
    menu = (
        "💰 *SELECT CURRENCY*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *USD* - US Dollar (min $0.50)\n"
        "2️⃣ *ZWG* - Zimbabwe Gold (min 15 ZWG)\n\n"
        "0️⃣ Main Menu\n\n"
        "Reply with number"
    )
    return send_whatsapp(phone, menu)

def send_methods_menu(phone, currency):
    methods = PAYMENT_METHODS.get(currency, [])
    if not methods:
        send_whatsapp(phone, f"❌ No payment methods available for {currency}.")
        return False
    menu = f"💳 *PAYMENT METHODS ({currency})*\n━━━━━━━━━━━━━━━━━━\n"
    for i, method in enumerate(methods, 1):
        menu += f"{i}️⃣ *{method}*\n"
    menu += "\n0️⃣ Main Menu\n\nReply with number"
    return send_whatsapp(phone, menu)

def send_amount_request(phone, currency, method_name):
    min_amount = MIN_AMOUNT_USD if currency == "USD" else MIN_AMOUNT_ZWG
    msg = (
        f"💰 *ENTER AMOUNT ({currency})*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Payment method: {method_name}\n"
        f"Minimum: {min_amount} {currency}\n\n"
        f"Type the amount (e.g., 10.50)\n"
        f"Type *cancel* to go back."
    )
    return send_whatsapp(phone, msg)

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
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
        response = requests.post(url, json=payload, headers=headers, timeout=35)
        debug_log(f"📤 WhatsApp sent to {to}: {response.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ WhatsApp send error: {e}")
        return False

def send_whatsapp_with_retry(to, text, max_retries=3):
    for attempt in range(max_retries):
        if send_whatsapp(to, text):
            return True
        time.sleep(1)
    return False

def get_user(phone):
    if not db:
        return None
    try:
        doc = db.collection("users").document(phone).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        debug_log(f"❌ Firebase get error: {e}")
        return None

def save_user(phone, data):
    if not db:
        return False
    try:
        db.collection("users").document(phone).set(data, merge=True)
        return True
    except Exception as e:
        debug_log(f"❌ Firebase save error: {e}")
        return False

def download_image(media_id):
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
    try:
        debug_log("🔄 Calling Hugging Face ML service...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(
            f"{HF_SPACE_URL}/predict",
            files=files,
            timeout=35
        )
        if response.status_code == 200:
            result = response.json()
            debug_log(f"✅ HF Response received")
            if result.get("success"):
                severity = "Unknown"
                if result.get("bbox") and result.get("leaf_area"):
                    severity = estimate_severity(result.get("bbox"), result.get("leaf_area"))
                return {
                    "disease": result.get("disease"),
                    "confidence": result.get("confidence"),
                    "treatment": result.get("treatment"),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False),
                    "severity": severity
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

def get_user_history(phone, limit=10):
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

# ==============================
# SIMPLIFIED AI FUNCTIONS (placeholder - use your full versions)
# ==============================
def ask_ai_advisor(question):
    return "AI advisor is being updated. Please try again later."

def ai_vision_disease_detection(image_bytes, phone, name):
    return "disease", "AI Vision analysis coming soon."

def ai_vision_curing_monitoring(image_bytes, phone, name):
    return "curing", "AI Curing analysis coming soon."

def grade_leaf_with_ai(image_bytes, phone, name):
    return "Grade", "Leaf grading coming soon."

def log_hf_detection(phone, name, disease, confidence, severity=None):
    pass

def get_gemini_tip():
    return "🌱 Check your fields regularly for early signs of disease."

def get_gemini_fact():
    return "🍃 Zimbabwe is one of Africa's largest tobacco producers."

# ==============================
# MAIN MESSAGE HANDLER (condensed for space - use your full version)
# ==============================
def handle_message(phone, msg_type, content):
    debug_log(f"📨 Handling: type={msg_type}, phone={phone}")
    
    user = get_user(phone)
    
    if not user:
        save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, "🌿 *Welcome to Tobacco AI!*\n\nPlease enter your *name* to continue:")

    state = user.get("state", USER_STATES["ACTIVE"])
    name = user.get("name", "Farmer")

    # AWAITING NAME
    if state == USER_STATES["AWAITING_NAME"] and msg_type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": USER_STATES["ACTIVE"]})
        return send_whatsapp(phone, f"✅ *Welcome, {clean_name}!*\n\nSend a photo to detect diseases or type *menu*.")

    # ==============================
    # PAYMENT HANDLERS
    # ==============================
    if state == USER_STATES["PAYMENT_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd in ["1", "2"]:
            currency = "USD" if cmd == "1" else "ZWG"
            save_user(phone, {"state": USER_STATES["PAYMENT_CURRENCY"], "payment_currency": currency})
            return send_methods_menu(phone, currency)
        else:
            return send_whatsapp(phone, "❌ Please choose 1 or 2 (or 0 to cancel).")

    if state == USER_STATES["PAYMENT_CURRENCY"] and msg_type == "text":
        try:
            method_index = int(content.strip()) - 1
            currency = user.get("payment_currency")
            methods = PAYMENT_METHODS.get(currency, [])
            if 0 <= method_index < len(methods):
                method_name = methods[method_index]
                method_info = METHOD_TYPE[method_name]
                save_user(phone, {
                    "state": USER_STATES["PAYMENT_AMOUNT"],
                    "payment_currency": currency,
                    "payment_method_name": method_name,
                    "payment_method_info": method_info
                })
                return send_amount_request(phone, currency, method_name)
            else:
                send_whatsapp(phone, "❌ Invalid selection.")
                return send_methods_menu(phone, currency)
        except ValueError:
            send_whatsapp(phone, "❌ Please enter a number.")
            return send_methods_menu(phone, currency)

    if state == USER_STATES["PAYMENT_AMOUNT"] and msg_type == "text":
        if content.lower().strip() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        try:
            amount = float(content.strip())
            currency = user.get("payment_currency")
            method_name = user.get("payment_method_name")
            method_info = user.get("payment_method_info")
            min_amount = MIN_AMOUNT_USD if currency == "USD" else MIN_AMOUNT_ZWG
            if amount < min_amount:
                send_whatsapp(phone, f"❌ Minimum amount is {min_amount} {currency}.")
                return send_amount_request(phone, currency, method_name)

            if method_info["type"] == "mobile":
                mobile_method = method_info["method"]
                if mobile_method == "innbucks":
                    save_user(phone, {
                        "state": USER_STATES["PAYMENT_INNBUCKS_CODE"],
                        "payment_currency": currency,
                        "payment_amount": amount,
                        "payment_method_name": method_name,
                        "payment_mobile_method": mobile_method
                    })
                    return send_whatsapp(phone,
                        "🔑 *InnBucks Payment*\n\n"
                        "1. Open your InnBucks app\n"
                        "2. Generate an *Authorization Code*\n"
                        "3. Type that code here\n\n"
                        "Type *cancel* to go back.")
                else:
                    save_user(phone, {"state": USER_STATES["PAYMENT_PROCESSING"]})
                    success, result = start_mobile_payment(phone, name, amount, currency, mobile_method)
                    if success:
                        save_user(phone, {"pending_payment": result, "payment_status": "pending"})
                        send_whatsapp(phone,
                            f"💸 *{method_name} Payment Initiated*\n\n"
                            f"Amount: {amount:.2f} {currency}\n\n"
                            f"Please check your phone for the PIN prompt and authorize.\n"
                            f"We'll notify you once confirmed.")
                    else:
                        send_whatsapp(phone, f"❌ Payment failed: {result}")
                        save_user(phone, {"state": USER_STATES["ACTIVE"]})
                        send_main_menu(phone)
            else:
                success, link = generate_payment_link(phone, name, amount, currency, method_name)
                if success:
                    send_whatsapp(phone,
                        f"💳 *{method_name} Payment Link*\n\n"
                        f"Amount: {amount:.2f} {currency}\n\n"
                        f"Click to pay: {link}\n\n"
                        f"After payment, you'll receive confirmation.")
                    save_user(phone, {"pending_payment": link, "payment_status": "link_sent"})
                    time.sleep(5)
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
                else:
                    send_whatsapp(phone, f"❌ Could not create payment link: {link}")
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
        except ValueError:
            send_whatsapp(phone, "❌ Invalid amount.")
            return send_amount_request(phone, currency, method_name)

    if state == USER_STATES["PAYMENT_INNBUCKS_CODE"] and msg_type == "text":
        if content.lower().strip() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        code = content.strip()
        currency = user.get("payment_currency")
        amount = user.get("payment_amount")
        mobile_method = user.get("payment_mobile_method")
        if not all([currency, amount, mobile_method]):
            send_whatsapp(phone, "⚠️ Session expired. Please start over.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        success, result = start_mobile_payment(phone, name, amount, currency, mobile_method, code)
        if success:
            save_user(phone, {"pending_payment": result, "payment_status": "pending"})
            send_whatsapp(phone,
                f"💸 *InnBucks Payment Initiated*\n\n"
                f"Amount: {amount:.2f} {currency}\n\n"
                f"Please authorize in your InnBucks app.")
        else:
            send_whatsapp(phone, f"❌ Payment failed: {result}")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)

    # TEXT COMMANDS
    if msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd in ["menu", "0", "main"]:
            return send_main_menu(phone)
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            return send_whatsapp(phone, "📸 Send a clear photo of the tobacco leaf.")
        elif cmd in ["2", "farming"]:
            save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        elif cmd in ["3", "dashboard"]:
            stats = get_user_statistics(phone)
            save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
            return send_dashboard_menu(phone, name, stats)
        elif cmd in ["4", "grade"]:
            save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
            return send_whatsapp(phone, "🏷️ Send a clear photo of your cured leaf for grading.")
        elif cmd in ["5", "vision"]:
            save_user(phone, {"state": USER_STATES["WAITING_AI_VISION"]})
            return send_ai_vision_menu(phone)
        elif cmd in ["6", "expert"]:
            save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        elif cmd in ["7", "feedback"]:
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            return send_whatsapp(phone, "📝 Type your feedback below (or *cancel*):")
        elif cmd in ["8", "pay", "payment", "donate"]:
            save_user(phone, {"state": USER_STATES["PAYMENT_MENU"]})
            return send_currency_menu(phone)
        elif cmd == "help":
            help_text = (
                "📚 *QUICK HELP*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• *menu* - Main menu\n"
                "• *1* - Disease detection\n"
                "• *2* - Farming practices\n"
                "• *3* - Dashboard\n"
                "• *4* - Leaf grading\n"
                "• *5* - AI Vision\n"
                "• *6* - Expert help\n"
                "• *7* - Feedback\n"
                "• *8* - Payments\n"
                "• *ai [question]* - Ask AI"
            )
            return send_whatsapp(phone, help_text)
        else:
            return send_whatsapp(phone, "❓ Command not recognized.\n\nType *menu* to see options")

# ==============================
# PAYNOW CALLBACK
# ==============================
@app.route("/paynow_update", methods=["POST"])
def paynow_update():
    data = request.form
    debug_log(f"PayNow callback: {data}")
    status = data.get("status")
    reference = data.get("reference")
    
    if reference and reference.startswith("Ref-"):
        parts = reference.split("-")
        if len(parts) >= 2:
            phone = parts[1]
            if status and status.lower() == "paid":
                debug_log(f"✅ Payment confirmed for {phone}")
                if db:
                    try:
                        user_ref = db.collection("users").document(phone)
                        user_ref.update({
                            "premium": True,
                            "premium_since": firestore.SERVER_TIMESTAMP,
                            "payment_status": "completed"
                        })
                        user_ref.update({"pending_payment": firestore.DELETE_FIELD})
                    except Exception as e:
                        debug_log(f"❌ Firebase update error: {e}")
                send_whatsapp(phone, "🎉 *PAYMENT RECEIVED!*\n\nThank you for your support!")
    return "OK", 200

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
    return jsonify({
        "status": "healthy",
        "firebase": db is not None,
        "paynow_usd_configured": bool(paynow_usd),
        "paynow_zwg_configured": bool(paynow_zwg),
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant with Payments is running!"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting Tobacco AI Assistant on port {port}")
    debug_log(f"💰 PayNow USD: {'Configured' if paynow_usd else 'Not configured'}")
    debug_log(f"💰 PayNow ZWG: {'Configured' if paynow_zwg else 'Not configured'}")
    app.run(host="0.0.0.0", port=port, debug=False)
