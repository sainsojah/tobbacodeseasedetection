"""
Tobacco AI Assistant - WhatsApp Bot
"""

import os
import json
import random
import requests
import time
import base64
import re
import gc
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai

# ==============================
# PAYNOW LIBRARY
# ==============================
try:
    from paynow import Paynow
    PAYNOW_AVAILABLE = True
except ImportError:
    PAYNOW_AVAILABLE = False
    print("⚠️ Paynow library not installed. Payments will be disabled.")

# ==============================
# INITIALIZATION
# ==============================
app = Flask(__name__)

def debug_log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# Load environment variables
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsouldier-tobacco-ai.hf.space")
AI_API_KEY = os.environ.get("AI_API_KEY")

# PayNow Credentials
PAYNOW_USD_API_KEY = os.environ.get("PAYNOW_USD_API_KEY")
PAYNOW_USD_MERCHANT_ID = os.environ.get("PAYNOW_USD_MERCHANT_ID")
PAYNOW_ZWG_API_KEY = os.environ.get("PAYNOW_ZWG_API_KEY")
PAYNOW_ZWG_MERCHANT_ID = os.environ.get("PAYNOW_ZWG_MERCHANT_ID")
RESULT_URL = os.environ.get("RESULT_URL")

# ==============================
# PAYNOW INSTANCES
# ==============================
paynow_usd = None
paynow_zwg = None

if PAYNOW_AVAILABLE:
    if PAYNOW_USD_API_KEY and PAYNOW_USD_MERCHANT_ID:
        try:
            paynow_usd = Paynow(PAYNOW_USD_MERCHANT_ID, PAYNOW_USD_API_KEY, RESULT_URL, RESULT_URL)
            debug_log("✅ PayNow USD initialized")
        except Exception as e:
            debug_log(f"❌ PayNow USD init failed: {e}")
    if PAYNOW_ZWG_API_KEY and PAYNOW_ZWG_MERCHANT_ID:
        try:
            paynow_zwg = Paynow(PAYNOW_ZWG_MERCHANT_ID, PAYNOW_ZWG_API_KEY, RESULT_URL, RESULT_URL)
            debug_log("✅ PayNow ZWG initialized")
        except Exception as e:
            debug_log(f"❌ PayNow ZWG init failed: {e}")

# Configure Google Generative AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    debug_log("✅ Google Generative AI configured")

# Gemini Models
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
generation_config = {"temperature": 0.7, "top_p": 0.8, "top_k": 10, "max_output_tokens": 1000}
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
    return text[:max_length-3] + "..." if len(text) > max_length else text

# ==============================
# HTTP SESSION
# ==============================
def create_session_with_retries():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=["POST", "GET"])
    session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=5))
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
    "AWAITING_NAME": "awaiting_name", "ACTIVE": "active",
    "WAITING_IMAGE": "waiting_image", "AWAITING_FEEDBACK": "awaiting_feedback",
    "AWAITING_EXPERT": "awaiting_expert", "AWAITING_AI_QUESTION": "awaiting_ai_question",
    "FARMING_MENU": "farming_menu", "WAITING_GRADE_IMAGE": "waiting_grade_image",
    "EXPERT_MENU": "expert_menu", "DASHBOARD_MENU": "dashboard_menu",
    "WAITING_AI_VISION": "waiting_ai_vision",
    "WAITING_AI_VISION_DISEASE": "waiting_ai_vision_disease",
    "WAITING_AI_VISION_CURING": "waiting_ai_vision_curing",
    "PAYMENT_MENU": "payment_menu", "PAYMENT_CURRENCY": "payment_currency",
    "PAYMENT_METHOD": "payment_method", "PAYMENT_AMOUNT": "payment_amount",
    "PAYMENT_INNBUCKS_CODE": "payment_innbucks_code", "PAYMENT_PROCESSING": "payment_processing"
}

# ==============================
# PAYMENT METHODS
# ==============================
PAYMENT_METHODS = {
    "USD": ["EcoCash USD", "InnBucks USD", "Zimswitch USD", "Internet/Mobile Banking USD", "POS2U USD", "Visa/Mastercard USD"],
    "ZWG": ["EcoCash ZWG", "OneMoney ZWG", "Telecash ZWG", "Zimswitch ZWG", "Internet/Mobile Banking ZWG", "POS2U ZWG", "Visa/Mastercard ZWG"]
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
# PAYMENT QUEUE & TRACKING
# ==============================
PAYMENT_QUEUE = {}
PROCESSED_PAYMENTS = set()
SENT_MESSAGES = set()
PAYMENT_TIMEOUT_MINUTES = 5

def format_phone(phone):
    """Ensure phone number is in 263 format for EcoCash."""
    phone = phone.replace("+", "").strip()
    if phone.startswith("0"):
        return "263" + phone[1:]
    return phone

def send_safe(phone, text):
    """Prevent duplicate identical messages to same recipient."""
    key = f"{phone}:{hash(text)}"
    if key in SENT_MESSAGES:
        debug_log(f"⏭️ Duplicate message skipped: {text[:30]}...")
        return
    SENT_MESSAGES.add(key)
    send_whatsapp_with_retry(phone, text)

def get_paynow_instance(currency):
    return paynow_usd if currency == "USD" else paynow_zwg

def start_mobile_payment(phone, name, amount, currency, method, innbucks_code=None):
    paynow = get_paynow_instance(currency)
    if not paynow:
        return False, f"PayNow {currency} not configured"
    
    formatted_phone = format_phone(phone)
    reference = f"Ref-{formatted_phone}-{currency}-{int(time.time())}"
    payment = paynow.create_payment(reference, f"{formatted_phone}@tobacco.ai")
    payment.add("Tobacco AI Service", amount)
    
    try:
        debug_log(f"📱 Initiating {method} payment: {amount} {currency} for {formatted_phone}")
        if method == 'innbucks' and innbucks_code:
            response = paynow.send_mobile(payment, formatted_phone, method, innbucks_code)
        else:
            response = paynow.send_mobile(payment, formatted_phone, method)
        
        # Log the raw response attributes
        debug_log(f"PayNow response - success: {response.success}, poll_url: {response.poll_url}, error: {response.error}")
        
        if response.success:
            PAYMENT_QUEUE[reference] = {
                "phone": phone,
                "poll_url": response.poll_url,
                "status": "pending",
                "start_time": datetime.now(),
                "currency": currency,
                "amount": amount,
                "method": method
            }
            if db:
                db.collection("users").document(phone).update({
                    "pending_payment_ref": reference,
                    "payment_status": "pending",
                    "last_payment_attempt": firestore.SERVER_TIMESTAMP
                })
            return True, response.poll_url
        else:
            error_msg = response.error or "Payment initiation failed (no error message from PayNow)"
            debug_log(f"❌ PayNow error: {error_msg}")
            return False, error_msg
    except Exception as e:
        # Catch any exception and log full details
        error_msg = f"PayNow exception: {type(e).__name__} - {str(e)}"
        debug_log(f"❌ {error_msg}")
        return False, error_msg

def generate_payment_link(phone, name, amount, currency, method_name):
    paynow = get_paynow_instance(currency)
    if not paynow:
        return False, f"PayNow {currency} not configured"
    
    formatted_phone = format_phone(phone)
    reference = f"Ref-{formatted_phone}-{currency}-{int(time.time())}"
    payment = paynow.create_payment(reference, f"{formatted_phone}@tobacco.ai")
    payment.add("Tobacco AI Service", amount)
    
    try:
        debug_log(f"🔗 Generating payment link: {amount} {currency}")
        response = paynow.send(payment)
        debug_log(f"PayNow link response - success: {response.success}, redirect_url: {response.redirect_url}, error: {response.error}")
        
        if response.success:
            PAYMENT_QUEUE[reference] = {
                "phone": phone,
                "poll_url": None,
                "status": "pending",
                "start_time": datetime.now(),
                "currency": currency,
                "amount": amount,
                "method": method_name,
                "is_link": True
            }
            if db:
                db.collection("users").document(phone).update({
                    "pending_payment_ref": reference,
                    "payment_status": "pending",
                    "last_payment_attempt": firestore.SERVER_TIMESTAMP
                })
            return True, response.redirect_url
        else:
            error_msg = response.error or "Could not generate payment link"
            debug_log(f"❌ PayNow link error: {error_msg}")
            return False, error_msg
    except Exception as e:
        error_msg = f"PayNow link exception: {type(e).__name__} - {str(e)}"
        debug_log(f"❌ {error_msg}")
        return False, error_msg

# ==============================
# BACKGROUND POLLING THREAD
# ==============================
def poll_payments():
    debug_log("🔄 Payment polling thread started")
    while True:
        try:
            for ref, data in list(PAYMENT_QUEUE.items()):
                if data["status"] != "pending":
                    continue
                if data.get("is_link"):
                    continue

                elapsed = (datetime.now() - data["start_time"]).total_seconds()
                if elapsed > PAYMENT_TIMEOUT_MINUTES * 60:
                    debug_log(f"⏰ Payment {ref} timed out")
                    data["status"] = "timeout"
                    send_safe(data["phone"], f"⏳ Payment of {data['amount']:.2f} {data['currency']} timed out. Please try again.")
                    continue

                try:
                    res = requests.get(data["poll_url"], timeout=10)
                    result = res.json()
                    if result.get("status") == "paid" and ref not in PROCESSED_PAYMENTS:
                        PROCESSED_PAYMENTS.add(ref)
                        data["status"] = "paid"
                        phone = data["phone"]
                        amount = data["amount"]
                        currency = data["currency"]
                        
                        if db:
                            db.collection("users").document(phone).update({
                                "premium": True,
                                "payment_status": "completed",
                                "pending_payment_ref": firestore.DELETE_FIELD
                            })
                        
                        send_safe(phone, f"🎉 Payment of {amount:.2f} {currency} received! Thank you for your support.")
                        debug_log(f"✅ Payment confirmed via polling: {ref}")
                except Exception as e:
                    debug_log(f"Polling error for {ref}: {e}")
            
            time.sleep(5)
        except Exception as e:
            debug_log(f"❌ Polling loop error: {e}")
            time.sleep(10)

polling_thread = threading.Thread(target=poll_payments, daemon=True)
polling_thread.start()

# ==============================
# DISEASE KNOWLEDGE BASE
# ==============================
DISEASE_KNOWLEDGE_BASE = {
    "Black Shank": {"cause": "Phytophthora fungus in waterlogged soil", "treatment": "Remove infected plants, apply Ridomil fungicide", "prevention": "Crop rotation, use resistant varieties"},
    "Black Spot": {"cause": "Fungal infection (Cercospora nicotianae)", "treatment": "Apply copper-based fungicides", "prevention": "Improve air circulation"},
    "Early Blight": {"cause": "Alternaria fungus", "treatment": "Apply Mancozeb or chlorothalonil", "prevention": "Crop rotation, proper spacing"},
    "Late Blight": {"cause": "Phytophthora infestans", "treatment": "Remove infected plants, apply Ridomil Gold", "prevention": "Avoid excessive moisture"},
    "Tobacco Mosaic Virus": {"cause": "TMV virus", "treatment": "NO CURE - remove infected plants", "prevention": "Wash hands, use resistant varieties"},
    "Spider Mites": {"cause": "Tiny arachnids", "treatment": "Apply miticides or insecticidal soap", "prevention": "Maintain humidity"}
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
• Water immediately after planting"""

FERTILIZER_GUIDE = """🧪 *FERTILIZER GUIDE*
━━━━━━━━━━━━━━━━━━
• Basal: Compound L (5:14:7) 400-600 kg/ha
• Top dressing 1: Ammonium Nitrate 150-200 kg/ha
• Top dressing 2: Potassium Nitrate 100-150 kg/ha
• Apply when soil is moist
• Test soil pH (target 5.5-6.5)"""

HARVESTING_GUIDE = """🌾 *HARVESTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Harvest from bottom upward (priming)
• 2-3 leaves per harvest, 4-6 primings total
• Priming 1 (Sand leaves): 60-65 days
• Priming 2-3 (Cutters): Best quality
• Priming 6 (Tips): Highest nicotine"""

CURING_GUIDE = """🔥 *CURING GUIDE*
━━━━━━━━━━━━━━━━━━
Yellowing (32-38°C, 48hrs, 85-90% humidity)
Leaf drying (38-52°C, 48hrs, 70-80% humidity)
Midrib drying (52-60°C, 24hrs, 50-60% humidity)
Killing out (60-71°C, 6hrs, 30-40% humidity)"""

MARKETING_GUIDE = f"""💰 *MARKETING {datetime.now().year}*
━━━━━━━━━━━━━━━━━━
• Opening: March {datetime.now().year}
• Biometric ID REQUIRED
• Grades: A (Premium), B (Good), C (Fair), D (Low)
• Payment within 24 hours"""

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
    if not text:
        text = "Processing..."
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
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
        url_resp = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, timeout=10)
        if url_resp.status_code != 200:
            return None
        media_url = url_resp.json().get("url")
        if not media_url:
            return None
        img_resp = requests.get(media_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, timeout=30)
        return img_resp.content if img_resp.status_code == 200 else None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

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
    return "Severe"

def get_offline_disease_advice(disease):
    if disease in DISEASE_KNOWLEDGE_BASE:
        info = DISEASE_KNOWLEDGE_BASE[disease]
        return f"""📚 *{disease} - Quick Reference*

🔍 *Cause:* {info['cause']}
💊 *Treatment:* {info['treatment']}
🛡️ *Prevention:* {info['prevention']}"""
    return f"ℹ️ For advice on {disease}, type *ai your question*"

def call_huggingface_detection(image_bytes):
    try:
        debug_log("🔄 Calling Hugging Face ML service...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(f"{HF_SPACE_URL}/predict", files=files, timeout=35)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                severity = estimate_severity(result.get("bbox", 0), result.get("leaf_area", 1)) if result.get("bbox") else "Unknown"
                return {
                    "disease": result.get("disease"),
                    "confidence": result.get("confidence"),
                    "treatment": result.get("treatment"),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False),
                    "severity": severity
                }
        return None
    except Exception as e:
        debug_log(f"❌ HF call error: {e}")
        return None
    finally:
        gc.collect()

def log_hf_detection(phone, name, disease, confidence, severity=None):
    if not db:
        return
    try:
        data = {"phone": phone, "name": name, "disease": disease, "confidence": confidence, "detection_type": "hf_disease", "timestamp": firestore.SERVER_TIMESTAMP}
        if severity:
            data["severity"] = severity
        db.collection("detections").add(data)
        debug_log(f"📊 Logged: {disease} ({confidence:.1f}%)")
    except Exception as e:
        debug_log(f"❌ Log error: {e}")

def get_user_history(phone, limit=10):
    if not db:
        return []
    try:
        docs = db.collection("detections").where("phone", "==", phone).order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("timestamp") and hasattr(data["timestamp"], "strftime"):
                data["date"] = data["timestamp"].strftime("%d %b %Y")
            history.append(data)
        return history
    except Exception as e:
        debug_log(f"❌ History error: {e}")
        return []

def get_user_statistics(phone):
    if not db:
        return {"total_scans": 0, "hf_scans": 0, "ai_vision_scans": 0, "curing_scans": 0, "top_disease": "None", "healthy_count": 0}
    try:
        docs = db.collection("detections").where("phone", "==", phone).stream()
        total = hf = ai = curing = healthy = 0
        diseases = {}
        for doc in docs:
            data = doc.to_dict()
            total += 1
            dt = data.get("detection_type", "hf_disease")
            if dt == "hf_disease":
                hf += 1
            elif dt == "ai_vision_disease":
                ai += 1
            elif dt == "ai_vision_curing":
                curing += 1
            disease = data.get("disease", "Unknown")
            if dt != "ai_vision_curing":
                if "healthy" in disease.lower():
                    healthy += 1
                else:
                    diseases[disease] = diseases.get(disease, 0) + 1
        top = max(diseases, key=diseases.get) if diseases else "None"
        return {"total_scans": total, "hf_scans": hf, "ai_vision_scans": ai, "curing_scans": curing, "top_disease": top, "healthy_count": healthy}
    except Exception as e:
        debug_log(f"❌ Stats error: {e}")
        return {"total_scans": 0, "hf_scans": 0, "ai_vision_scans": 0, "curing_scans": 0, "top_disease": "None", "healthy_count": 0}

# ==============================
# AI FUNCTIONS
# ==============================
def ask_ai_advisor(question):
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured."
    
    disease_found = next((d for d in DISEASE_KNOWLEDGE_BASE.keys() if d.lower() in question.lower()), None)
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    current_month = datetime.now().strftime("%B")
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(2)
            debug_log(f"🔄 Trying: {model_name}")
            model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config, safety_settings=safety_settings)
            prompt = f"""You are a Zimbabwe tobacco expert. Today: {current_date}. Use CURRENT {current_year} data only.
Question: {question}
Keep response under 500 words. Use bullet points. End with complete sentence."""
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:50]}")
            continue
    
    if disease_found:
        return get_offline_disease_advice(disease_found)
    return "⚠️ AI service unavailable. Please try again later."

def ai_vision_disease_detection(image_bytes, phone, name):
    if not AI_API_KEY:
        return None, "AI vision not configured"
    
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(2)
            model = genai.GenerativeModel(model_name=model_name, generation_config=vision_config, safety_settings=safety_settings)
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            prompt = """Analyze this tobacco leaf:

🌿 *AI VISION ANALYSIS*
• Detected Disease: [Name]
• Confidence: [High/Medium/Low]
• Symptoms: [2-3 symptoms]
• Severity: [Mild/Moderate/Severe]
• Action: [One sentence]"""
            response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_data}])
            if response and response.text:
                analysis = response.text.strip()
                disease = "Unknown"
                for line in analysis.split('\n'):
                    if "Detected Disease:" in line:
                        disease = line.split(":")[-1].strip()
                        break
                if db:
                    db.collection("detections").add({"phone": phone, "name": name, "disease": disease, "analysis": analysis[:500], "detection_type": "ai_vision_disease", "timestamp": firestore.SERVER_TIMESTAMP})
                return "disease", analysis
        except Exception as e:
            debug_log(f"❌ Vision error: {e}")
            continue
    return None, "⚠️ AI Vision unavailable"

def ai_vision_curing_monitoring(image_bytes, phone, name):
    if not AI_API_KEY:
        return None, "AI vision not configured"
    
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(2)
            model = genai.GenerativeModel(model_name=model_name, generation_config=vision_config, safety_settings=safety_settings)
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            prompt = """Assess curing progress:

🔥 *CURING REPORT*
• Stage: [Yellowing/Leaf Drying/Midrib Drying/Killing Out/Complete]
• Color: [Description]
• Moisture: [Wet/Optimal/Dry]
• Recommendations: [Next steps]"""
            response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_data}])
            if response and response.text:
                analysis = response.text.strip()
                stage = "Unknown"
                for line in analysis.split('\n'):
                    if "Stage:" in line:
                        stage = line.split(":")[-1].strip()
                        break
                if db:
                    db.collection("detections").add({"phone": phone, "name": name, "curing_stage": stage, "analysis": analysis[:500], "detection_type": "ai_vision_curing", "timestamp": firestore.SERVER_TIMESTAMP})
                return "curing", analysis
        except Exception as e:
            debug_log(f"❌ Curing error: {e}")
            continue
    return None, "⚠️ Curing monitor unavailable"

def grade_leaf_with_ai(image_bytes, phone, name):
    if not AI_API_KEY:
        return None, "AI grading not configured"
    
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(2)
            model = genai.GenerativeModel(model_name=model_name, generation_config=vision_config, safety_settings=safety_settings)
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            prompt = """Grade this tobacco leaf:

📊 *LEAF GRADE*
• Grade: [A/B/C/D]
• Color: [Description]
• Texture: [Oily/Dry/Brittle]
• Damage: [None/Minor/Moderate]
• Value: [Premium/Good/Fair/Poor]"""
            response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_data}])
            if response and response.text:
                analysis = response.text.strip()
                grade = "Unknown"
                for line in analysis.split('\n'):
                    if "Grade:" in line:
                        grade = line.split(":")[-1].strip().split()[0] if line.split(":")[-1].strip() else "Unknown"
                        break
                if db:
                    db.collection("detections").add({"phone": phone, "name": name, "grade": grade, "analysis": analysis[:500], "detection_type": "leaf_grading", "timestamp": firestore.SERVER_TIMESTAMP})
                return "Grade", analysis
        except Exception as e:
            debug_log(f"❌ Grading error: {e}")
            continue
    return None, "⚠️ Grading unavailable"

def get_gemini_tip():
    if not AI_API_KEY:
        return random.choice(["🌱 Rotate crops to prevent diseases.", "💧 Water in the morning to reduce humidity.", "🔍 Check fields weekly for early signs."])
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(0.5)
            current_month = datetime.now().strftime("%B")
            season = "rainy/planting" if current_month in ["Nov","Dec","Jan","Feb","Mar"] else "harvesting/curing" if current_month in ["Apr","May","Jun","Jul"] else "land preparation"
            model = genai.GenerativeModel(model_name=model_name, generation_config=tip_config, safety_settings=safety_settings)
            prompt = f"One practical farming tip for Zimbabwe tobacco farmers during {season} season. 3-4 sentences. Start with emoji. End with complete sentence."
            response = model.generate_content(prompt)
            if response and response.text:
                tip = response.text.strip()
                return tip if tip[-1] in '.!?' else tip + '.'
        except Exception:
            continue
    return "🌱 Monitor your fields daily for early disease signs."

def get_gemini_fact():
    if not AI_API_KEY:
        return random.choice(["🌱 Tobacco is related to tomatoes!", "🍃 Zimbabwe produces world-class tobacco.", "📜 Tobacco cultivated for 8,000 years."])
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(0.5)
            model = genai.GenerativeModel(model_name=model_name, generation_config=fact_config, safety_settings=safety_settings)
            prompt = f"One interesting fact about Zimbabwe tobacco farming for {datetime.now().year}. 3-4 sentences. Start with emoji. End with complete sentence."
            response = model.generate_content(prompt)
            if response and response.text:
                fact = response.text.strip()
                return fact if fact[-1] in '.!?' else fact + '.'
        except Exception:
            continue
    return "🌱 Zimbabwe's tobacco industry employs over 500,000 people."

# ==============================
# MENU FUNCTIONS
# ==============================
def send_main_menu(phone):
    menu = ("🌿 *TOBACCO AI MAIN MENU*\n━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ *Disease Detection* - Send photo\n"
            "2️⃣ *Farming Practices* - Guides & AI advice\n"
            "3️⃣ *My Dashboard* - Stats, History, Tips\n"
            "4️⃣ *Leaf Grading* - Quality assessment\n"
            "5️⃣ *AI Vision* - Disease/Curing analysis\n"
            "6️⃣ *Expert Help* - Agronomist & AI\n"
            "7️⃣ *Feedback* - Send comments\n"
            "8️⃣ *Payments* - Donate\n"
            "Reply with number or *help*")
    return send_whatsapp(phone, menu)

def send_farming_menu(phone):
    menu = ("🌱 *FARMING PRACTICES*\n━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ *Planting Guide*\n2️⃣ *Fertilizer Guide*\n3️⃣ *Harvesting Guide*\n"
            "4️⃣ *Curing Guide*\n5️⃣ *Marketing Guide*\n6️⃣ *Ask AI*\n\n0️⃣ Main Menu")
    return send_whatsapp(phone, menu)

def send_dashboard_menu(phone, name, stats):
    dashboard = (f"📊 *MY DASHBOARD*\n━━━━━━━━━━━━━━━━━━\n👤 {name}\n📱 {phone}\n\n"
                 f"📊 Total: {stats['total_scans']}\n🔬 HF: {stats['hf_scans']}\n👁️ AI Vision: {stats['ai_vision_scans']}\n🔥 Curing: {stats['curing_scans']}\n"
                 f"🦠 Most Common: {stats['top_disease']}\n🌿 Healthy: {stats['healthy_count']}\n━━━━━━━━━━━━━━━━━━\n"
                 "1️⃣ History\n2️⃣ Daily Tip\n3️⃣ Fun Fact\n\n0️⃣ Main Menu")
    return send_whatsapp(phone, dashboard)

def send_expert_menu(phone):
    menu = ("👨‍🌾 *EXPERT HELP*\n━━━━━━━━━━━━━━━━━━\n1️⃣ *AI Advisor*\n2️⃣ *Human Expert*\n\n0️⃣ Main Menu")
    return send_whatsapp(phone, menu)

def send_ai_vision_menu(phone):
    menu = ("🔬 *AI VISION*\n━━━━━━━━━━━━━━━━━━\n1️⃣ *Disease Detection*\n2️⃣ *Curing Monitor*\n\n0️⃣ Main Menu")
    return send_whatsapp(phone, menu)

def send_currency_menu(phone):
    menu = ("💰 *SELECT CURRENCY*\n━━━━━━━━━━━━━━━━━━\n1️⃣ *USD* (min $0.50)\n2️⃣ *ZWG* (min 15)\n\n0️⃣ Main Menu")
    return send_whatsapp(phone, menu)

def send_methods_menu(phone, currency):
    methods = PAYMENT_METHODS.get(currency, [])
    if not methods:
        send_whatsapp(phone, f"❌ No methods for {currency}")
        return False
    menu = f"💳 *PAYMENT ({currency})*\n━━━━━━━━━━━━━━━━━━\n"
    for i, m in enumerate(methods, 1):
        menu += f"{i}️⃣ *{m}*\n"
    menu += "\n0️⃣ Main Menu"
    return send_whatsapp(phone, menu)

def send_amount_request(phone, currency, method):
    min_amt = MIN_AMOUNT_USD if currency == "USD" else MIN_AMOUNT_ZWG
    msg = f"💰 *ENTER AMOUNT ({currency})*\n━━━━━━━━━━━━━━━━━━\nMethod: {method}\nMinimum: {min_amt} {currency}\n\nType amount or *cancel*"
    return send_whatsapp(phone, msg)

# ==============================
# MAIN HANDLER
# ==============================
def handle_message(phone, msg_type, content):
    debug_log(f"📨 {msg_type} from {phone}")
    user = get_user(phone)
    
    if not user:
        save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, "🌿 *Welcome!* Please enter your *name*:")
    
    state = user.get("state", USER_STATES["ACTIVE"])
    name = user.get("name", "Farmer")
    
    # AWAITING NAME
    if state == USER_STATES["AWAITING_NAME"] and msg_type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": USER_STATES["ACTIVE"]})
        return send_whatsapp(phone, f"✅ *Welcome, {clean_name}!*\n\nSend a photo or type *menu*")
    
    # ========== PAYMENT HANDLERS ==========
    if state == USER_STATES["PAYMENT_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd in ["1", "2"]:
            currency = "USD" if cmd == "1" else "ZWG"
            save_user(phone, {"state": USER_STATES["PAYMENT_CURRENCY"], "payment_currency": currency})
            return send_methods_menu(phone, currency)
        return send_whatsapp(phone, "❌ Choose 1, 2, or 0")
    
    if state == USER_STATES["PAYMENT_CURRENCY"] and msg_type == "text":
        try:
            idx = int(content.strip()) - 1
            currency = user.get("payment_currency")
            methods = PAYMENT_METHODS.get(currency, [])
            if 0 <= idx < len(methods):
                method = methods[idx]
                save_user(phone, {"state": USER_STATES["PAYMENT_AMOUNT"], "payment_currency": currency, "payment_method_name": method, "payment_method_info": METHOD_TYPE[method]})
                return send_amount_request(phone, currency, method)
            return send_methods_menu(phone, currency)
        except:
            return send_methods_menu(phone, user.get("payment_currency"))
    
    if state == USER_STATES["PAYMENT_AMOUNT"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        try:
            amount = float(content.strip())
            currency = user.get("payment_currency")
            method = user.get("payment_method_name")
            info = user.get("payment_method_info")
            min_amt = MIN_AMOUNT_USD if currency == "USD" else MIN_AMOUNT_ZWG
            if amount < min_amt:
                send_whatsapp(phone, f"❌ Minimum {min_amt} {currency}")
                return send_amount_request(phone, currency, method)
            
            if info["type"] == "mobile" and info["method"] == "innbucks":
                save_user(phone, {"state": USER_STATES["PAYMENT_INNBUCKS_CODE"], "payment_currency": currency, "payment_amount": amount, "payment_mobile_method": info["method"]})
                return send_whatsapp(phone, "🔑 *InnBucks*\n1. Open InnBucks app\n2. Generate Authorization Code\n3. Type code here\n\nType *cancel*")
            elif info["type"] == "mobile":
                save_user(phone, {"state": USER_STATES["PAYMENT_PROCESSING"]})
                success, result = start_mobile_payment(phone, name, amount, currency, info["method"])
                if success:
                    send_safe(phone, f"💸 *EcoCash Payment*\nAmount: {amount:.2f} {currency}\n\n📲 Check your phone now\nEnter your EcoCash PIN to confirm")
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
                else:
                    send_whatsapp(phone, f"❌ Payment failed: {result}")
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
            else:
                success, link = generate_payment_link(phone, name, amount, currency, method)
                if success:
                    send_whatsapp(phone, f"💳 *{method}*\nAmount: {amount:.2f} {currency}\n\nPay here: {link}")
                    save_user(phone, {"pending_payment": link})
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
                else:
                    send_whatsapp(phone, f"❌ Payment failed: {link}")
                    save_user(phone, {"state": USER_STATES["ACTIVE"]})
                    send_main_menu(phone)
        except ValueError:
            send_whatsapp(phone, "❌ Invalid amount. Please enter a number (e.g., 1.00)")
            return send_amount_request(phone, currency, method)
        except Exception as e:
            send_whatsapp(phone, f"❌ An unexpected error occurred: {str(e)}")
            debug_log(f"❌ Amount handler error: {e}")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
    
    if state == USER_STATES["PAYMENT_INNBUCKS_CODE"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        code = content.strip()
        currency = user.get("payment_currency")
        amount = user.get("payment_amount")
        method = user.get("payment_mobile_method")
        success, result = start_mobile_payment(phone, name, amount, currency, method, code)
        if success:
            send_safe(phone, f"💸 *InnBucks*\nAmount: {amount:.2f} {currency}\n\nAuthorize in app")
        else:
            send_whatsapp(phone, f"❌ {result}")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
    
    # NEW: Check payment status command
    if msg_type == "text" and content.lower().strip() in ["status", "payment status"]:
        pending_ref = user.get("pending_payment_ref")
        if pending_ref and pending_ref in PAYMENT_QUEUE:
            data = PAYMENT_QUEUE[pending_ref]
            if data["status"] == "paid":
                send_whatsapp(phone, f"✅ Your payment of {data['amount']:.2f} {data['currency']} was successful!")
            elif data["status"] == "pending":
                elapsed = (datetime.now() - data["start_time"]).seconds // 60
                send_whatsapp(phone, f"⏳ Payment is still pending. Please check your phone for PIN prompt. ({elapsed} min ago)")
            else:
                send_whatsapp(phone, "No recent payment found. Type *8* to make a donation.")
        else:
            send_whatsapp(phone, "No active payment session. Type *8* to make a donation.")
        return
    
    # ========== EXISTING HANDLERS (UNCHANGED) ==========
    if state == USER_STATES["EXPERT_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, "🤖 Ask anything about tobacco farming (or *cancel*):")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
            return send_whatsapp(phone, "👨‍🌾 Describe your issue. Expert will respond (or *cancel*):")
        return send_whatsapp(phone, "❌ Choose 1, 2, or 0")
    
    if state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            history = get_user_history(phone, 8)
            if not history:
                msg = "📋 No history yet."
            else:
                msg = "📋 *HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, h in enumerate(history[:8], 1):
                    t = h.get("detection_type", "")
                    if t == "hf_disease":
                        msg += f"{i}. 🔬 {h.get('disease')} - {h.get('confidence',0):.0f}%\n"
                    elif t == "ai_vision_disease":
                        msg += f"{i}. 👁️ {h.get('disease')}\n"
                    elif t == "ai_vision_curing":
                        msg += f"{i}. 🔥 {h.get('curing_stage')}\n"
                    elif t == "leaf_grading":
                        msg += f"{i}. 📊 Grade {h.get('grade')}\n"
                    if h.get('date'):
                        msg += f"   📅 {h.get('date')}\n"
            send_whatsapp(phone, trim_message(msg, 1500))
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "2":
            send_whatsapp(phone, f"💡 *Daily Tip*\n\n{get_gemini_tip()}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "3":
            send_whatsapp(phone, f"🎲 *Did You Know?*\n\n{get_gemini_fact()}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        return send_whatsapp(phone, "❌ Choose 1, 2, 3, or 0")
    
    if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        send_whatsapp(phone, "🤔 Thinking...")
        result = ask_ai_advisor(content)
        send_whatsapp_with_retry(phone, result)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)
    
    if state == USER_STATES["FARMING_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        guides = {"1": PLANTING_GUIDE, "2": FERTILIZER_GUIDE, "3": HARVESTING_GUIDE, "4": CURING_GUIDE, "5": MARKETING_GUIDE}
        if cmd in guides:
            send_whatsapp(phone, guides[cmd])
            return send_farming_menu(phone)
        elif cmd == "6":
            save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
            return send_whatsapp(phone, "🤖 Ask anything (or *cancel*):")
        return send_farming_menu(phone)
    
    if state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
        send_whatsapp(phone, f"🔍 Analyzing leaf, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Failed to download image")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        grade, analysis = grade_leaf_with_ai(img, phone, name)
        if analysis:
            send_whatsapp_with_retry(phone, analysis)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        gc.collect()
        return
    
    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        if phone in LAST_SCAN and time.time() - LAST_SCAN[phone] < 5:
            return send_whatsapp(phone, "⏱️ Please wait 5 seconds")
        LAST_SCAN[phone] = time.time()
        send_whatsapp(phone, f"🔍 Analyzing, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Download failed")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        result = call_huggingface_detection(img)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        if not result:
            send_whatsapp(phone, "❌ Analysis failed")
            return send_main_menu(phone)
        
        disease, conf, sev = result["disease"], result["confidence"], result.get("severity", "Unknown")
        conf_msg = get_confidence_message(conf)
        log_hf_detection(phone, name, disease, conf, sev)
        
        if conf < 50:
            resp = f"⚠️ *Low Confidence ({conf:.1f}%)*\n\n{conf_msg}\n\nTry AI Vision (type *5*)"
        elif result["is_healthy"]:
            resp = f"🎉 *Healthy Leaf!*\n\nConfidence: {conf:.1f}%\n{conf_msg}"
        else:
            resp = f"📊 *{disease} DETECTED*\n\nConfidence: {conf:.1f}%\n{conf_msg}"
            if sev != "Unknown":
                resp += f"\nSeverity: *{sev}*"
            resp += f"\n\n*Treatment:*\n{result['treatment']}"
        send_whatsapp(phone, resp)
        if not result["is_healthy"] and not result["low_confidence"] and conf >= 50:
            send_whatsapp(phone, get_offline_disease_advice(disease))
        send_main_menu(phone)
        gc.collect()
        return
    
    if state == USER_STATES["WAITING_AI_VISION"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": USER_STATES["WAITING_AI_VISION_DISEASE"]})
            return send_whatsapp(phone, "🔬 Send clear photo of leaf for disease analysis")
        elif cmd == "2":
            save_user(phone, {"state": USER_STATES["WAITING_AI_VISION_CURING"]})
            return send_whatsapp(phone, "🔥 Send photo of curing leaf")
        return send_whatsapp(phone, "❌ Choose 1, 2, or 0")
    
    if state == USER_STATES["WAITING_AI_VISION_DISEASE"] and msg_type == "image":
        send_whatsapp(phone, f"🔬 Analyzing, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Download failed")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        _, analysis = ai_vision_disease_detection(img, phone, name)
        if analysis:
            send_whatsapp_with_retry(phone, analysis)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        gc.collect()
        return
    
    if state == USER_STATES["WAITING_AI_VISION_CURING"] and msg_type == "image":
        send_whatsapp(phone, f"🔥 Analyzing curing, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Download failed")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        _, analysis = ai_vision_curing_monitoring(img, phone, name)
        if analysis:
            send_whatsapp_with_retry(phone, analysis)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        gc.collect()
        return
    
    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                msg = f"📝 *FEEDBACK*\n👤 {name}\n📱 {phone}\n💬 {content}"
                send_whatsapp(ADMIN_PHONE, msg)
            send_whatsapp(phone, "✅ Thank you!")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)
    
    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE:
                msg = f"🚨 *EXPERT REQUEST*\n👤 {name}\n📱 {phone}\n💬 {content}"
                send_whatsapp(ADMIN_PHONE, msg)
            send_whatsapp(phone, "👨‍🌾 Request sent! Expert will respond within 24-48 hours")
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)
    
    # TEXT COMMANDS
    if msg_type == "text":
        cmd = content.lower().strip()
        if cmd in ["menu", "0", "main"]:
            return send_main_menu(phone)
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            return send_whatsapp(phone, "📸 Send clear photo of leaf")
        elif cmd in ["2", "farming"]:
            save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        elif cmd in ["3", "dashboard"]:
            stats = get_user_statistics(phone)
            save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
            return send_dashboard_menu(phone, name, stats)
        elif cmd in ["4", "grade"]:
            save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
            return send_whatsapp(phone, "🏷️ Send photo of cured leaf")
        elif cmd in ["5", "vision"]:
            save_user(phone, {"state": USER_STATES["WAITING_AI_VISION"]})
            return send_ai_vision_menu(phone)
        elif cmd in ["6", "expert"]:
            save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        elif cmd in ["7", "feedback"]:
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            return send_whatsapp(phone, "📝 Type feedback (or *cancel*):")
        elif cmd in ["8", "pay", "payment", "donate"]:
            save_user(phone, {"state": USER_STATES["PAYMENT_MENU"]})
            return send_currency_menu(phone)
        elif cmd.startswith("ai "):
            q = cmd[3:].strip()
            if q:
                send_whatsapp(phone, "🤔 Thinking...")
                result = ask_ai_advisor(q)
                send_whatsapp_with_retry(phone, result)
                return send_main_menu(phone)
        elif cmd == "help":
            help_text = ("📚 *HELP*\n━━━━━━━━━━━━━━━━━━\n"
                        "• *menu* - Main menu\n• *1* - Detect\n• *2* - Guides\n• *3* - Dashboard\n"
                        "• *4* - Grade\n• *5* - AI Vision\n• *6* - Expert\n• *7* - Feedback\n"
                        "• *8* - Payments\n• *ai [question]* - Ask AI\n• *status* - Check payment")
            return send_whatsapp(phone, help_text)
        else:
            return send_whatsapp(phone, "❓ Type *menu* for options")

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403
    try:
        data = request.json
        msg = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        if msg:
            m = msg[0]
            from_num = m.get("from")
            m_type = m.get("type")
            content = m.get("text", {}).get("body", "") if m_type == "text" else m.get("image", {}).get("id", "") if m_type == "image" else None
            if content:
                handle_message(from_num, m_type, content)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        debug_log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/paynow_update", methods=["POST"])
def paynow_update():
    data = request.form
    debug_log(f"PayNow webhook: {dict(data)}")
    status = data.get("status")
    ref = data.get("reference", "")
    if ref.startswith("Ref-") and status == "paid" and ref not in PROCESSED_PAYMENTS:
        PROCESSED_PAYMENTS.add(ref)
        parts = ref.split("-")
        if len(parts) >= 2:
            phone = parts[1]
            debug_log(f"✅ Payment confirmed via webhook: {phone}")
            if db:
                db.collection("users").document(phone).update({"premium": True, "payment_status": "completed", "pending_payment_ref": firestore.DELETE_FIELD})
            send_safe(phone, "🎉 *PAYMENT RECEIVED!* Thank you for your support!")
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "paynow_usd": bool(paynow_usd), "paynow_zwg": bool(paynow_zwg)}), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting on port {port}")
    debug_log(f"💰 PayNow USD: {'Yes' if paynow_usd else 'No'}")
    debug_log(f"💰 PayNow ZWG: {'Yes' if paynow_zwg else 'No'}")
    app.run(host="0.0.0.0", port=port, debug=False)
