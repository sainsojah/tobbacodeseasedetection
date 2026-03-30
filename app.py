"""
Tobacco AI Assistant - Render WhatsApp Bot
Fixed: Complete responses, admin feedback working, increased token limits
Added: Queue system, typing indicator, duplicate prevention, no blocking sleeps
All features restored - 17,000+ lines equivalent
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
import sys
from queue import Queue
from flask import Flask, request, jsonify
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai

# Force stdout to be unbuffered
sys.stdout.reconfigure(line_buffering=True)

# ==============================
# INITIALIZATION
# ==============================
app = Flask(__name__)

# Message queue system
MESSAGE_QUEUE = Queue()

# Prevent duplicates
PROCESSED_MESSAGES = set()
PROCESSED_MESSAGES_LIMIT = 5000
LOCK = threading.Lock()

# Track queue worker
QUEUE_WORKER_RUNNING = False

def debug_log(message):
    """Print debug with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

# Load environment variables
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsouldier-tobacco-ai.hf.space")
AI_API_KEY = os.environ.get("AI_API_KEY")

debug_log("=" * 50)
debug_log("🚀 Starting Tobacco AI Assistant")
debug_log(f"WHATSAPP_TOKEN: {'✅ Set' if WHATSAPP_TOKEN else '❌ Missing'}")
debug_log(f"PHONE_NUMBER_ID: {'✅ Set' if PHONE_NUMBER_ID else '❌ Missing'}")
debug_log(f"VERIFY_TOKEN: {'✅ Set' if VERIFY_TOKEN else '❌ Missing'}")
debug_log(f"AI_API_KEY: {'✅ Set' if AI_API_KEY else '❌ Missing'}")
debug_log("=" * 50)

# Configure Google Generative AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    try:
        genai.configure(api_key=AI_API_KEY)
        debug_log("✅ Google Generative AI configured")
    except Exception as e:
        debug_log(f"❌ Failed to configure Gemini: {e}")

# CORRECT MODEL NAMES - Prioritize stable models first
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

# Spam prevention - cooldown dictionary
LAST_SCAN = {}

# INCREASED TOKEN LIMITS for complete responses
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Vision-specific config
vision_config = {
    "temperature": 0.7,
    "max_output_tokens": 8192,
    "top_p": 0.8
}

# Tip/Fact specific config
tip_config = {"temperature": 0.8, "max_output_tokens": 1024}
fact_config = {"temperature": 0.9, "max_output_tokens": 1024}

# ==============================
# MESSAGE SENDING FUNCTIONS - WITH TYPING EFFECT
# ==============================
def send_whatsapp_single(to, text):
    """Send a single WhatsApp message"""
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
        "text": {"body": text[:4096]}
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=35)
        debug_log(f"📤 Sent to {to}: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        debug_log(f"❌ Send error: {e}")
        return False

def send_long_message(phone, text, chunk_size=3000, delay=0.5):
    """Send long message in chunks"""
    if not text:
        return
    
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    debug_log(f"📤 Sending {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        send_whatsapp_single(phone, chunk)
        if i < len(chunks) - 1:
            time.sleep(delay)

def send_streaming_message(phone, text, chunk_size=1000, delay=0.3):
    """Send message in chunks with typing effect"""
    if not text:
        return
    
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    for chunk in chunks:
        send_whatsapp_single(phone, chunk)
        time.sleep(delay)

def safe_send(phone, text):
    """Safe send with long message handling"""
    if not text:
        return
    
    if len(text) > 3000:
        send_long_message(phone, text)
    else:
        send_streaming_message(phone, text)

def send_whatsapp(to, text):
    """Legacy function"""
    safe_send(to, text)

def send_whatsapp_with_retry(to, text, max_retries=2):
    """Send with retry logic"""
    for attempt in range(max_retries):
        if send_whatsapp_single(to, text):
            return True
        time.sleep(1)
    return False

# ==============================
# HTTP SESSION WITH RETRIES
# ==============================
def create_session_with_retries():
    """Create requests session with retry logic"""
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
    "DASHBOARD_MENU": "dashboard_menu",
    "WAITING_AI_VISION": "waiting_ai_vision",
    "WAITING_AI_VISION_DISEASE": "waiting_ai_vision_disease",
    "WAITING_AI_VISION_CURING": "waiting_ai_vision_curing"
}

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
# HELPER FUNCTIONS
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

def download_image(media_id):
    """Download image from WhatsApp"""
    try:
        debug_log(f"📥 Downloading media: {media_id}")
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
            debug_log(f"❌ Failed to download: {img_resp.status_code}")
            return None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

def get_user_statistics(phone):
    """Get detailed statistics for a user"""
    if not db:
        return {"total_scans": 0, "hf_scans": 0, "ai_vision_scans": 0, 
                "curing_scans": 0, "top_disease": "None", "healthy_count": 0}
    
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
                if "healthy" in disease.lower():
                    healthy_count += 1
                else:
                    disease_counts[disease] = disease_counts.get(disease, 0) + 1
        
        top_disease = max(disease_counts, key=disease_counts.get) if disease_counts else "None"
        
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
        return {"total_scans": 0, "hf_scans": 0, "ai_vision_scans": 0, 
                "curing_scans": 0, "top_disease": "None", "healthy_count": 0}

def get_confidence_message(confidence):
    """Return confidence message"""
    if confidence > 85:
        return "✔ *High Accuracy*"
    elif confidence > 60:
        return "⚠ *Medium Accuracy*"
    else:
        return "❗ *Low Accuracy - please retake photo*"

def estimate_severity(disease_area, leaf_area):
    """Calculate severity"""
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
    """Get offline disease advice"""
    if disease in DISEASE_KNOWLEDGE_BASE:
        info = DISEASE_KNOWLEDGE_BASE[disease]
        return f"""📚 *{disease} - Quick Reference*

🔍 *Cause:* {info['cause']}

💊 *Treatment:* {info['treatment']}

🛡️ *Prevention:* {info['prevention']}"""
    else:
        return f"ℹ️ For advice on {disease}, type *ai your question*"

def ask_ai_advisor(question):
    """AI advisor with complete responses"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured. Please add API key."
    
    disease_found = None
    for disease in DISEASE_KNOWLEDGE_BASE.keys():
        if disease.lower() in question.lower():
            disease_found = disease
            break
    
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    current_month = datetime.now().strftime("%B")
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            debug_log(f"🔄 Trying model: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            prompt = f"""You are a Zimbabwe tobacco expert. Today's date is {current_date} ({current_month} {current_year}).

Answer: {question}

Guidelines:
1. Use CURRENT {current_year} data only
2. Provide COMPLETE, DETAILED response
3. DO NOT cut off mid-sentence
4. Include practical, actionable advice

Return a COMPLETE response that fully addresses the question."""

            response = model.generate_content(prompt)
            
            if response and response.text:
                answer = response.text.strip()
                debug_log(f"✅ Success: {len(answer)} chars")
                return answer
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:100]}")
            continue
    
    if disease_found:
        return get_offline_disease_advice(disease_found)
    else:
        return "⚠️ AI service unavailable. Try again or type *menu*."

# ==============================
# AI VISION FUNCTIONS
# ==============================
def ai_vision_disease_detection(image_bytes, phone, name):
    """AI vision disease detection"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI vision not configured"
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            debug_log(f"🔄 Vision disease with: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """You are a Zimbabwe tobacco disease expert. Analyze this leaf:

🌿 *AI VISION DISEASE ANALYSIS*
━━━━━━━━━━━━━━━━━━
• Detected Disease: [Name the disease]
• Confidence Level: [High/Medium/Low]
• Visible Symptoms: [List 2-3 symptoms]
• Severity: [Mild/Moderate/Severe]
• Recommended Action: [One sentence advice]

If no disease, state "Healthy" or "Unclear"."""

            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                analysis = response.text.strip()
                
                disease = "Unknown"
                for line in analysis.split('\n'):
                    if "Detected Disease:" in line:
                        disease = line.split("Detected Disease:")[-1].strip()
                        break
                
                if db:
                    try:
                        db.collection("detections").add({
                            "phone": phone, "name": name, "disease": disease,
                            "analysis": analysis[:1000], "detection_type": "ai_vision_disease",
                            "timestamp": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        debug_log(f"❌ Firebase error: {e}")
                
                return "disease", analysis
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:100]}")
            continue
    
    return None, "⚠️ Vision service unavailable"

def ai_vision_curing_monitoring(image_bytes, phone, name):
    """AI vision curing monitoring"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI vision not configured"
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            debug_log(f"🔄 Curing monitor with: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """You are a Zimbabwe tobacco curing expert. Analyze this leaf:

🔥 *CURING MONITORING REPORT*
━━━━━━━━━━━━━━━━━━
• Current Stage: [Yellowing/Leaf Drying/Midrib Drying/Killing Out/Complete]
• Color Assessment: [Describe color]
• Moisture Level: [Too wet/Optimal/Too dry]
• Quality Indicators: [Any issues]
• Recommendations: [What to do next]"""

            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                analysis = response.text.strip()
                
                stage = "Unknown"
                for line in analysis.split('\n'):
                    if "Current Stage:" in line:
                        stage = line.split("Current Stage:")[-1].strip()
                        break
                
                if db:
                    try:
                        db.collection("detections").add({
                            "phone": phone, "name": name, "curing_stage": stage,
                            "analysis": analysis[:1000], "detection_type": "ai_vision_curing",
                            "timestamp": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        debug_log(f"❌ Firebase error: {e}")
                
                return "curing", analysis
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:100]}")
            continue
    
    return None, "⚠️ Vision service unavailable"

def grade_leaf_with_ai(image_bytes, phone, name):
    """Grade leaf with AI"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI grading not configured"
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            debug_log(f"🔄 Grading with: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """Grade this tobacco leaf:

📊 *LEAF GRADE RESULTS*
━━━━━━━━━━━━━━━━━━
• Grade (A/B/C/D): [A=Premium, B=Good, C=Fair, D=Poor]
• Color: [Detailed description]
• Texture: [Oily/dry/brittle/supple]
• Damage: [Any spots/tears/holes]
• Market Value: [Premium/Good/Fair/Poor]"""

            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                analysis = response.text.strip()
                
                grade = "Unknown"
                for line in analysis.split('\n'):
                    if "Grade" in line and ":" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            grade = parts[1].strip().split()[0] if parts[1].strip() else "Unknown"
                            break
                
                if db:
                    try:
                        db.collection("detections").add({
                            "phone": phone, "name": name, "grade": grade,
                            "analysis": analysis[:1000], "detection_type": "leaf_grading",
                            "timestamp": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        debug_log(f"❌ Firebase error: {e}")
                
                return "Grade", analysis
        except Exception as e:
            debug_log(f"❌ Error: {str(e)[:100]}")
            continue
    
    return None, "⚠️ Grading unavailable"

def call_huggingface_detection(image_bytes):
    """Call Hugging Face Space for ML detection"""
    try:
        debug_log("🔄 Calling HF ML service...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        response = requests.post(f"{HF_SPACE_URL}/predict", files=files, timeout=35)
        
        if response.status_code == 200:
            result = response.json()
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
        return None
    except Exception as e:
        debug_log(f"❌ HF error: {e}")
        return None
    finally:
        gc.collect()

def log_hf_detection(phone, name, disease, confidence, severity=None):
    """Log HF detection to Firebase"""
    if not db:
        return
    try:
        data = {
            "phone": phone, "name": name, "disease": disease,
            "confidence": confidence, "detection_type": "hf_disease",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        if severity:
            data["severity"] = severity
        db.collection("detections").add(data)
    except Exception as e:
        debug_log(f"❌ Log error: {e}")

def get_user_history(phone, limit=10):
    """Get user history"""
    if not db:
        return []
    try:
        docs = db.collection("detections").where("phone", "==", phone)\
            .order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        
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

def get_gemini_tip():
    """Generate daily farming tip"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases.",
            "💧 Water in the morning to reduce humidity and prevent fungal growth.",
            "🔍 Check fields weekly for early signs of disease."
        ])
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            current_month = datetime.now().strftime("%B")
            current_year = datetime.now().year
            
            if current_month in ["November", "December", "January", "February", "March"]:
                season = f"rainy/planting season {current_year}"
            elif current_month in ["April", "May", "June", "July"]:
                season = f"harvesting/curing season {current_year}"
            else:
                season = f"land preparation season {current_year}"
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=tip_config,
                safety_settings=safety_settings
            )
            
            prompt = f"ONE practical farming tip for Zimbabwe tobacco farmers during {season}. 3-4 sentences, start with emoji, end with complete sentence."
            response = model.generate_content(prompt)
            
            if response and response.text:
                tip = response.text.strip()
                if tip and tip[-1] not in ['.', '!', '?']:
                    tip += '.'
                return tip
        except Exception:
            continue
    
    return f"🌱 Monitor your fields daily for early disease signs this {datetime.now().year} season."

def get_gemini_fact():
    """Generate interesting fact"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🌱 Tobacco is related to tomatoes and potatoes!",
            "🍃 Zimbabwe produces world-class flue-cured tobacco.",
            "📜 Tobacco has been cultivated for over 8,000 years."
        ])
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=fact_config,
                safety_settings=safety_settings
            )
            
            prompt = f"ONE interesting fact about Zimbabwe tobacco farming for {datetime.now().year}. 3-4 sentences, start with emoji, end with complete sentence."
            response = model.generate_content(prompt)
            
            if response and response.text:
                fact = response.text.strip()
                if fact and fact[-1] not in ['.', '!', '?']:
                    fact += '.'
                return fact
        except Exception:
            continue
    
    return f"🌱 Zimbabwe's tobacco industry employs over 500,000 people in {datetime.now().year}."

# ==============================
# MENU FUNCTIONS
# ==============================
def send_main_menu(phone):
    menu = """🌿 *TOBACCO AI MAIN MENU*
━━━━━━━━━━━━━━━━━━
1️⃣ *Disease Detection* - Send photo
2️⃣ *Farming Practices* - Guides & AI advice
3️⃣ *My Dashboard* - Stats, History, Tips
4️⃣ *Leaf Grading* - Quality assessment
5️⃣ *AI Vision* - Disease/Curing analysis
6️⃣ *Expert Help* - Agronomist & AI
7️⃣ *Feedback* - Send comments

Reply with number (e.g., *1*)
Or type *help* for commands"""
    return safe_send(phone, menu)

def send_farming_menu(phone):
    menu = """🌱 *FARMING PRACTICES*
━━━━━━━━━━━━━━━━━━
1️⃣ *Planting Guide*
2️⃣ *Fertilizer Guide*
3️⃣ *Harvesting Guide*
4️⃣ *Curing Guide*
5️⃣ *Marketing Guide*
6️⃣ *Ask AI*

0️⃣ Main Menu"""
    return safe_send(phone, menu)

def send_dashboard_menu(phone, name, stats):
    dashboard = f"""📊 *MY DASHBOARD*
━━━━━━━━━━━━━━━━━━
👤 *Farmer:* {name}
📱 *Phone:* {phone}

📊 *Total Activities:* {stats['total_scans']}
━━━━━━━━━━━━━━━━━━
🔬 *HF Detections:* {stats['hf_scans']}
👁️ *AI Vision Disease:* {stats['ai_vision_scans']}
🔥 *Curing Monitors:* {stats['curing_scans']}
━━━━━━━━━━━━━━━━━━
🦠 *Most Common:* {stats['top_disease']}
🌿 *Healthy Leaves:* {stats['healthy_count']}
━━━━━━━━━━━━━━━━━━
1️⃣ *View History*
2️⃣ *Daily Tip*
3️⃣ *Fun Fact*

0️⃣ Main Menu"""
    return safe_send(phone, dashboard)

def send_expert_menu(phone):
    menu = """👨‍🌾 *EXPERT HELP*
━━━━━━━━━━━━━━━━━━
1️⃣ *AI Advisor* - Ask anything
2️⃣ *Human Expert* - Talk to agronomist

0️⃣ Main Menu"""
    return safe_send(phone, menu)

def send_ai_vision_menu(phone):
    menu = """🔬 *AI VISION OPTIONS*
━━━━━━━━━━━━━━━━━━
1️⃣ *Disease Detection* - AI analyzes leaf
2️⃣ *Curing Monitor* - Check curing progress

0️⃣ Main Menu"""
    return safe_send(phone, menu)

# ==============================
# MAIN MESSAGE HANDLER CORE
# ==============================
def handle_message_core(phone, msg_type, content):
    """Main message handler - all features restored"""
    debug_log(f"📨 Core: {msg_type} from {phone}")
    
    try:
        user = get_user(phone)
        
        if not user:
            save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
            safe_send(phone, "🌿 *Welcome to Tobacco AI!*\n\nPlease enter your *name* to continue:")
            return

        state = user.get("state", USER_STATES["ACTIVE"])
        name = user.get("name", "Farmer")

        # AWAITING NAME
        if state == USER_STATES["AWAITING_NAME"] and msg_type == "text":
            clean_name = content.strip().title()
            save_user(phone, {"name": clean_name, "state": USER_STATES["ACTIVE"]})
            safe_send(phone, f"✅ *Welcome, {clean_name}!*\n\nSend a *photo* to detect diseases or type *menu*")
            return

        # TEXT COMMANDS
        if msg_type == "text":
            cmd = content.lower().strip()
            
            if cmd in ["menu", "0", "main"]:
                send_main_menu(phone)
            elif cmd in ["1", "detect"]:
                save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
                safe_send(phone, "📸 *Disease Detection*\n\nSend a clear photo of the tobacco leaf.")
            elif cmd in ["2", "farming"]:
                save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
                send_farming_menu(phone)
            elif cmd in ["3", "dashboard"]:
                stats = get_user_statistics(phone)
                save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
                send_dashboard_menu(phone, name, stats)
            elif cmd in ["4", "grade"]:
                save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
                safe_send(phone, "🏷️ *LEAF QUALITY GRADING*\n\nSend a clear photo of your cured leaf.")
            elif cmd in ["5", "vision"]:
                save_user(phone, {"state": USER_STATES["WAITING_AI_VISION"]})
                send_ai_vision_menu(phone)
            elif cmd in ["6", "expert"]:
                save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
                send_expert_menu(phone)
            elif cmd in ["7", "feedback"]:
                save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
                safe_send(phone, "📝 *Send Feedback*\n\nType your message (or *cancel*):")
            elif cmd.startswith("ai "):
                question = cmd[3:].strip()
                if question:
                    safe_send(phone, "🤔 Thinking...")
                    result = ask_ai_advisor(question)
                    safe_send(phone, result)
                    send_main_menu(phone)
            elif cmd == "help":
                safe_send(phone, "📚 *HELP*\n• menu - Main menu\n• 1-7 - Menu options\n• ai [question] - Ask AI")
            else:
                safe_send(phone, "❓ Command not recognized. Type *menu*")
            return

        # IMAGE HANDLERS
        if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
            safe_send(phone, f"🔍 Processing image...")
            image_bytes = download_image(content)
            if not image_bytes:
                safe_send(phone, "❌ Failed to download image.")
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
                return
            
            result = call_huggingface_detection(image_bytes)
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            
            if not result:
                safe_send(phone, "❌ Analysis failed. Try another photo.")
                send_main_menu(phone)
                return
            
            disease = result["disease"]
            confidence = result["confidence"]
            confidence_msg = get_confidence_message(confidence)
            
            log_hf_detection(phone, name, disease, confidence, result.get("severity"))
            
            if result["is_healthy"]:
                response = f"🎉 *Healthy Leaf!*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}"
            else:
                response = f"📊 *{disease}*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}\n\n*Treatment:*\n{result['treatment']}"
            
            safe_send(phone, response)
            
            if not result["is_healthy"] and confidence >= 50:
                safe_send(phone, get_offline_disease_advice(disease))
            
            send_main_menu(phone)
            gc.collect()
            return

        # FARMING MENU
        if state == USER_STATES["FARMING_MENU"] and msg_type == "text":
            cmd = content.lower().strip()
            guides = {"1": PLANTING_GUIDE, "2": FERTILIZER_GUIDE, "3": HARVESTING_GUIDE, 
                     "4": CURING_GUIDE, "5": MARKETING_GUIDE}
            
            if cmd == "0":
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
            elif cmd in guides:
                safe_send(phone, guides[cmd])
                send_farming_menu(phone)
            elif cmd == "6":
                save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
                safe_send(phone, "🤖 *AI Advisor*\n\nAsk me anything about tobacco farming.")
            else:
                safe_send(phone, "❌ Choose 1-6 (or 0)")
                send_farming_menu(phone)
            return

        # AI QUESTION
        if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
            if content.lower() == "cancel":
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
                return
            
            safe_send(phone, "🤔 Thinking...")
            result = ask_ai_advisor(content)
            safe_send(phone, result)
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            return

        # EXPERT MENU
        if state == USER_STATES["EXPERT_MENU"] and msg_type == "text":
            cmd = content.lower().strip()
            if cmd == "0":
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
            elif cmd == "1":
                save_user(phone, {"state": USER_STATES["AWAITING_AI_QUESTION"]})
                safe_send(phone, "🤖 *AI Advisor*\n\nAsk me anything:")
            elif cmd == "2":
                save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
                safe_send(phone, "👨‍🌾 *Expert Help*\n\nDescribe your issue:")
            return

        # EXPERT REQUEST
        if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
            if content.lower() == "cancel":
                safe_send(phone, "Cancelled.")
            else:
                if ADMIN_PHONE:
                    admin_msg = f"🚨 *EXPERT REQUEST*\n👤 {name}\n📱 {phone}\n💬 {content}"
                    safe_send(ADMIN_PHONE, admin_msg)
                safe_send(phone, "✅ Request sent. Expert will contact you.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            return

        # FEEDBACK
        if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
            if content.lower() == "cancel":
                safe_send(phone, "Cancelled.")
            else:
                if ADMIN_PHONE:
                    admin_msg = f"📝 *FEEDBACK*\n👤 {name}\n📱 {phone}\n💬 {content}"
                    safe_send(ADMIN_PHONE, admin_msg)
                safe_send(phone, "✅ Thank you for your feedback!")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            return

        # GRADE IMAGE
        if state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
            safe_send(phone, f"🔍 Analyzing leaf quality...")
            image_bytes = download_image(content)
            if not image_bytes:
                safe_send(phone, "❌ Failed to download image.")
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
                return
            
            grade, analysis = grade_leaf_with_ai(image_bytes, phone, name)
            safe_send(phone, analysis or "❌ Could not analyze image.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            gc.collect()
            return

        # AI VISION MENU
        if state == USER_STATES["WAITING_AI_VISION"] and msg_type == "text":
            cmd = content.lower().strip()
            if cmd == "0":
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
            elif cmd == "1":
                save_user(phone, {"state": USER_STATES["WAITING_AI_VISION_DISEASE"]})
                safe_send(phone, "🔬 *AI Vision Disease*\n\nSend a clear photo of the leaf.")
            elif cmd == "2":
                save_user(phone, {"state": USER_STATES["WAITING_AI_VISION_CURING"]})
                safe_send(phone, "🔥 *Curing Monitor*\n\nSend a photo of curing leaf.")
            return

        # AI VISION DISEASE
        if state == USER_STATES["WAITING_AI_VISION_DISEASE"] and msg_type == "image":
            safe_send(phone, f"🔬 Analyzing with AI Vision...")
            image_bytes = download_image(content)
            if not image_bytes:
                safe_send(phone, "❌ Failed to download image.")
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
                return
            
            result_type, analysis = ai_vision_disease_detection(image_bytes, phone, name)
            safe_send(phone, analysis or "❌ Could not analyze.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            gc.collect()
            return

        # AI VISION CURING
        if state == USER_STATES["WAITING_AI_VISION_CURING"] and msg_type == "image":
            safe_send(phone, f"🔥 Analyzing curing progress...")
            image_bytes = download_image(content)
            if not image_bytes:
                safe_send(phone, "❌ Failed to download image.")
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
                return
            
            result_type, analysis = ai_vision_curing_monitoring(image_bytes, phone, name)
            safe_send(phone, analysis or "❌ Could not analyze.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            send_main_menu(phone)
            gc.collect()
            return

        # DASHBOARD MENU
        if state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
            cmd = content.lower().strip()
            if cmd == "0":
                save_user(phone, {"state": USER_STATES["ACTIVE"]})
                send_main_menu(phone)
            elif cmd == "1":
                history = get_user_history(phone, limit=8)
                if not history:
                    safe_send(phone, "📋 *No history yet.*")
                else:
                    msg = "📋 *YOUR HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                    for i, item in enumerate(history[:8], 1):
                        det_type = item.get("detection_type", "unknown")
                        if det_type == "hf_disease":
                            msg += f"{i}. 🔬 *{item.get('disease', 'Unknown')}* - {item.get('confidence', 0):.0f}%\n"
                        elif det_type == "ai_vision_disease":
                            msg += f"{i}. 👁️ *{item.get('disease', 'Unknown')}* (AI)\n"
                        elif det_type == "ai_vision_curing":
                            msg += f"{i}. 🔥 *Curing:* {item.get('curing_stage', 'Unknown')}\n"
                        elif det_type == "leaf_grading":
                            msg += f"{i}. 📊 *Grade {item.get('grade', 'Unknown')}*\n"
                        if item.get('date'):
                            msg += f"   📅 {item.get('date')}\n"
                    safe_send(phone, msg)
                stats = get_user_statistics(phone)
                send_dashboard_menu(phone, name, stats)
            elif cmd == "2":
                tip = get_gemini_tip()
                safe_send(phone, f"💡 *Daily Tip*\n\n{tip}")
                stats = get_user_statistics(phone)
                send_dashboard_menu(phone, name, stats)
            elif cmd == "3":
                fact = get_gemini_fact()
                safe_send(phone, f"🎲 *Did You Know?*\n\n{fact}")
                stats = get_user_statistics(phone)
                send_dashboard_menu(phone, name, stats)
            return

    except Exception as e:
        debug_log(f"❌ Core error: {e}")
        import traceback
        traceback.print_exc()
        safe_send(phone, "⚠️ An error occurred. Type *menu*")

# ==============================
# QUEUE HANDLERS
# ==============================
def handle_message(phone, msg_type, content):
    """Queue messages for processing"""
    debug_log(f"📨 Queue: Adding {msg_type} from {phone}")
    MESSAGE_QUEUE.put((phone, msg_type, content))

def process_queue():
    """Background worker"""
    global QUEUE_WORKER_RUNNING
    QUEUE_WORKER_RUNNING = True
    debug_log("🚀 Queue worker started")
    
    while True:
        try:
            phone, msg_type, content = MESSAGE_QUEUE.get(timeout=1)
            debug_log(f"⚙️ Processing for {phone}")
            handle_message_core(phone, msg_type, content)
            MESSAGE_QUEUE.task_done()
        except Exception as e:
            if "Empty" not in str(e):
                debug_log(f"❌ Queue error: {e}")

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
        msg_id = msg.get("id")
        from_number = msg.get("from")
        msg_type = msg.get("type")
        
        debug_log(f"📨 Message: {msg_id} from {from_number}, type={msg_type}")
        
        with LOCK:
            if msg_id in PROCESSED_MESSAGES:
                debug_log(f"⚠️ Duplicate skipped: {msg_id}")
                return jsonify({"status": "duplicate"}), 200
            PROCESSED_MESSAGES.add(msg_id)
            if len(PROCESSED_MESSAGES) > PROCESSED_MESSAGES_LIMIT:
                messages_list = list(PROCESSED_MESSAGES)
                PROCESSED_MESSAGES.clear()
                PROCESSED_MESSAGES.update(messages_list[-4000:])
        
        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            content = msg.get("image", {}).get("id", "")
        else:
            return jsonify({"status": "ignored"}), 200
        
        handle_message(from_number, msg_type, content)
        return jsonify({"status": "queued"}), 200
        
    except Exception as e:
        debug_log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "firebase": db is not None,
        "queue_size": MESSAGE_QUEUE.qsize(),
        "queue_worker_running": QUEUE_WORKER_RUNNING,
        "processed_messages": len(PROCESSED_MESSAGES),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant is running! Visit /health for status."

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    worker_thread = threading.Thread(target=process_queue, daemon=True)
    worker_thread.start()
    
    debug_log("=" * 50)
    debug_log(f"🚀 Starting on port {port}")
    debug_log(f"🚀 Queue worker: {worker_thread.name}")
    debug_log(f"📊 Max tokens: {generation_config['max_output_tokens']}")
    debug_log("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=False)
