"""
Tobacco AI Assistant - Render WhatsApp Bot
Optimized: Parallel processing, background queue, persistent sessions, 30s timeout
"""
import os
import json
import random
import requests
import time
import base64
import re
import gc
import asyncio
import io
from queue import Queue
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai
from PIL import Image

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
    'models/gemini-1.5-flash',
    'models/gemini-1.5-pro',
    'models/gemini-3.1-pro-preview',
    'models/gemini-flash-latest',
    'models/gemini-pro-latest'
]

# Spam prevention - cooldown dictionary
LAST_SCAN = {}
COOLDOWN_SECONDS = 5

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=4)

# Background task queue
task_queue = Queue()
MAX_QUEUE_SIZE = 20

# ==============================
# PERSISTENT HTTP SESSIONS
# ==============================
def create_persistent_session():
    """Create persistent HTTP session with connection pooling"""
    session = requests.Session()
    
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=20,
        max_retries=Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504]
        )
    )
    
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    return session

# Create persistent sessions
whatsapp_session = create_persistent_session()
hf_session = create_persistent_session()

# Configuration
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 10,
    "max_output_tokens": 600,
}

vision_config = {
    "temperature": 0.7,
    "max_output_tokens": 400,
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
WHATSAPP_SAFE_LIMIT = 3500

def trim_message(text, max_length=WHATSAPP_SAFE_LIMIT):
    """Trim message to safe WhatsApp length"""
    if not text:
        return "No response available."
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

# ==============================
# ASYNC DELAY
# ==============================
async def async_delay(seconds):
    """Non-blocking delay"""
    await asyncio.sleep(seconds)

def sync_delay(seconds):
    """Sync delay for non-async contexts"""
    time.sleep(seconds)

# ==============================
# IMAGE COMPRESSION
# ==============================
def compress_image(image_bytes, max_size=768):
    """Compress image to reduce size and speed up processing"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        
        compressed = buffer.getvalue()
        debug_log(f"📦 Compressed: {len(image_bytes)} → {len(compressed)} bytes")
        
        return compressed
    except Exception as e:
        debug_log(f"⚠️ Compression failed: {e}")
        return image_bytes

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
    """Get detailed statistics for a user including grading"""
    if not db:
        return {
            "total_scans": 0,
            "total_grades": 0,
            "top_disease": "None",
            "healthy_count": 0,
            "avg_grade": "N/A"
        }
    
    try:
        disease_docs = db.collection("detections")\
            .where("phone", "==", phone)\
            .stream()
        
        grade_docs = db.collection("leaf_grades")\
            .where("phone", "==", phone)\
            .stream()
        
        total_scans = 0
        total_grades = 0
        disease_counts = {}
        healthy_count = 0
        grade_values = []
        
        for doc in disease_docs:
            data = doc.to_dict()
            total_scans += 1
            disease = data.get("disease", "Unknown")
            
            if disease == "Healthy":
                healthy_count += 1
            else:
                disease_counts[disease] = disease_counts.get(disease, 0) + 1
        
        grade_map = {"A": 4, "B": 3, "C": 2, "D": 1}
        for doc in grade_docs:
            data = doc.to_dict()
            total_grades += 1
            grade = data.get("grade", "")
            if grade and grade in grade_map:
                grade_values.append(grade_map[grade])
        
        avg_grade = "N/A"
        if grade_values:
            avg_score = sum(grade_values) / len(grade_values)
            if avg_score >= 3.5:
                avg_grade = "A"
            elif avg_score >= 2.5:
                avg_grade = "B"
            elif avg_score >= 1.5:
                avg_grade = "C"
            else:
                avg_grade = "D"
        
        top_disease = "None"
        if disease_counts:
            top_disease = max(disease_counts, key=disease_counts.get)
        
        return {
            "total_scans": total_scans,
            "total_grades": total_grades,
            "top_disease": top_disease,
            "healthy_count": healthy_count,
            "avg_grade": avg_grade
        }
    except Exception as e:
        debug_log(f"❌ Stats error: {e}")
        return {
            "total_scans": 0,
            "total_grades": 0,
            "top_disease": "None",
            "healthy_count": 0,
            "avg_grade": "N/A"
        }

# ==============================
# CONFIDENCE INTERPRETATION
# ==============================
def get_confidence_message(confidence):
    """Return human-readable confidence level with emoji"""
    if confidence > 85:
        return "✔️ *High Accuracy*"
    elif confidence > 60:
        return "⚠️ *Medium Accuracy*"
    else:
        return "❓ *Low Accuracy*"

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
# AI ADVISOR WITH MODEL FALLBACK
# ==============================
def ask_ai_advisor(question):
    """AI advisor with complete model fallback"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured"
    
    for disease in DISEASE_ADVICE_CACHE.keys():
        if disease.lower() in question.lower():
            return f"📚 *{disease}*\n\n{DISEASE_ADVICE_CACHE[disease]}"
    
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
                debug_log(f"✅ Success with {model_name}")
                return response.text.strip()
                
        except Exception as e:
            debug_log(f"⚠️ {model_name} failed: {str(e)[:50]}")
            continue
    
    return "⚠️ Service busy. Try *menu* for guides."

# ==============================
# AI LEAF GRADING
# ==============================
def grade_leaf_with_ai(image_bytes):
    """Grade leaf using AI and return grade and analysis"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI grading not configured", "Unknown"
    
    vision_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash']
    
    for model_name in vision_models:
        try:
            debug_log(f"🔄 Grading with: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """Grade this tobacco leaf. Return in this EXACT format:

Grade: [A/B/C/D]
Color: [description]
Texture: [description]
Damage: [description]
Market: [Premium/Good/Fair/Poor]"""
            
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                analysis = response.text.strip()
                
                grade = "Unknown"
                for line in analysis.split('\n'):
                    if line.lower().startswith('grade:'):
                        possible_grade = line.split(':')[1].strip().upper()
                        if possible_grade in ['A', 'B', 'C', 'D']:
                            grade = possible_grade
                            break
                
                debug_log(f"✅ Grade: {grade}")
                return grade, analysis, grade
                
        except Exception as e:
            debug_log(f"⚠️ Grading failed: {str(e)[:50]}")
            continue
    
    return "C", "❌ Grading service unavailable", "C"

# ==============================
# LOG LEAF GRADING TO FIREBASE
# ==============================
def log_leaf_grade(phone, name, grade, analysis):
    """Log leaf grading results to Firebase"""
    if not db:
        return
    
    try:
        data = {
            "phone": phone,
            "name": name,
            "grade": grade,
            "analysis": analysis[:200],
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        
        db.collection("leaf_grades").add(data)
        debug_log(f"📊 Logged grade: {grade} for {name}")
    except Exception as e:
        debug_log(f"❌ Grade log error: {e}")

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
        "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases. This breaks pest cycles naturally.",
        "💧 Water in the morning to reduce humidity and prevent fungal growth. Leaves dry before evening.",
        "🔍 Check fields weekly for early signs of disease. Early detection saves crops.",
        "🧪 Test soil pH before fertilizing. Tobacco needs pH 5.5-6.5 for optimal growth.",
        "🌿 Remove infected leaves immediately to prevent disease spread.",
        "🌱 Plant after good rains, not before - prevents damping off in seedlings.",
        "🔥 Monitor curing temperatures closely. Keep at 32-38°C for yellowing phase."
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
        "🌍 Zimbabwe exports premium flue-cured tobacco to over 50 countries worldwide.",
        "👨‍🌾 Tobacco farming supports over 500,000 Zimbabwean families directly and indirectly.",
        "💰 Tobacco is Zimbabwe's 2nd largest foreign currency earner after gold.",
        "🌱 Tobacco is related to tomatoes and potatoes - all in the Solanaceae family!",
        "🔥 Curing turns tobacco leaves from green to gold in 6-7 days through careful temperature control.",
        "📜 Tobacco has been cultivated in Zimbabwe for over 100 years commercially.",
        "🌿 Zimbabwe's tobacco is known globally for its golden color and sweet flavor."
    ]
    
    fact = random.choice(facts)
    fact_cache[today] = fact
    return fact

# ==============================
# HUGGINGFACE DETECTION
# ==============================
def call_huggingface_detection(image_bytes):
    """Call Hugging Face Space with persistent session and 30s timeout"""
    try:
        debug_log("🔄 HF detection starting...")
        files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
        
        response = hf_session.post(
            f"{HF_SPACE_URL}/predict",
            files=files,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                severity = "Unknown"
                if result.get("confidence", 0) > 0:
                    conf = result.get("confidence", 0)
                    if conf > 85:
                        severity = "Moderate"
                    elif conf > 60:
                        severity = "Mild"
                    else:
                        severity = "Unknown"
                
                debug_log(f"✅ HF success: {result.get('disease')} ({result.get('confidence',0):.1f}%)")
                return {
                    "disease": result.get("disease", "Unknown"),
                    "confidence": result.get("confidence", 0),
                    "treatment": result.get("treatment", ""),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False),
                    "severity": severity
                }
        else:
            debug_log(f"❌ HF error {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        debug_log("❌ HF timeout after 30s")
        return None
    except Exception as e:
        debug_log(f"❌ HF error: {e}")
        return None

# ==============================
# AI VISION ANALYSIS
# ==============================
def ai_vision_analysis(image_bytes, hf_disease=None, confidence=0):
    """AI vision analysis for verification"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None
    
    if confidence > 85 and hf_disease and hf_disease in DISEASE_ADVICE_CACHE:
        debug_log(f"🤖 Skipping AI: High confidence ({confidence}%)")
        return None
    
    vision_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash']
    
    for model_name in vision_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            if hf_disease and confidence > 60:
                prompt = f"""Analyze this tobacco leaf. The model detected {hf_disease} with {confidence:.0f}% confidence.

Respond in this exact format:
✅ AI Review: [Agree/Disagree with detection]
🔍 Symptoms: [2-3 visible symptoms]
📊 Severity: [Mild/Moderate/Severe]
💡 Quick Tip: [One sentence advice]"""
            else:
                prompt = """Analyze this tobacco leaf thoroughly.

Respond in this exact format:
🌿 *Possible Disease:* [Your diagnosis]
🔍 *Symptoms Seen:* [2-3 symptoms]
📊 *Severity:* [Mild/Moderate/Severe]
💡 *Advice:* [One sentence]"""
            
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            if response and response.text:
                debug_log(f"✅ AI Vision complete")
                return response.text.strip()
                
        except Exception as e:
            debug_log(f"⚠️ Vision failed: {str(e)[:50]}")
            continue
    
    return None

# ==============================
# PARALLEL PROCESSING FUNCTION
# ==============================
def process_detection_parallel(image_bytes):
    """Run HF detection and AI vision in parallel"""
    
    future_hf = executor.submit(call_huggingface_detection, image_bytes)
    future_ai = executor.submit(ai_vision_analysis, image_bytes)
    
    hf_result = future_hf.result(timeout=30)
    ai_result = future_ai.result(timeout=25)
    
    return hf_result, ai_result

# ==============================
# LOG DETECTION TO FIREBASE
# ==============================
def log_detection(phone, name, disease, confidence, severity=None):
    """Log disease detection to Firebase"""
    if not db:
        return
    try:
        data = {
            "phone": phone,
            "name": name,
            "disease": disease,
            "confidence": confidence,
            "type": "disease",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        if severity:
            data["severity"] = severity
        
        db.collection("detections").add(data)
        debug_log(f"📊 Logged disease: {disease} ({confidence:.1f}%)")
    except Exception as e:
        debug_log(f"❌ Log error: {e}")

# ==============================
# SEND WHATSAPP
# ==============================
def send_whatsapp(to, text):
    """Send WhatsApp message with persistent session"""
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
        response = whatsapp_session.post(url, json=payload, headers=headers, timeout=15)
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
        sync_delay(1)
    return False

# ==============================
# GET USER FROM FIREBASE
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

# ==============================
# DOWNLOAD IMAGE
# ==============================
def download_image(media_id):
    """Download image from WhatsApp"""
    try:
        debug_log(f"📥 Downloading: {media_id}")
        
        url_resp = whatsapp_session.get(
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
        
        img_resp = whatsapp_session.get(
            media_url,
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            timeout=30
        )
        
        if img_resp.status_code == 200:
            image_bytes = img_resp.content
            debug_log(f"✅ Downloaded: {len(image_bytes)} bytes")
            
            compressed = compress_image(image_bytes)
            return compressed
            
        return None
    except Exception as e:
        debug_log(f"❌ Download error: {e}")
        return None

# ==============================
# CLEANUP MEMORY
# ==============================
def cleanup_memory(*args):
    """Delete objects and force garbage collection"""
    for obj in args:
        if obj:
            try:
                del obj
            except:
                pass
    gc.collect()
    debug_log("🧹 Memory cleaned")

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
        "5️⃣ *Expert Help* - Agronomist & AI\n"
        "6️⃣ *Feedback* - Send comments\n\n"
        "Reply with number (e.g., *1*)\n"
        "Or type *help* for commands"
    )
    return send_whatsapp(phone, menu)

def send_farming_menu(phone):
    menu = (
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
    return send_whatsapp(phone, menu)

def send_dashboard_menu(phone, name, stats):
    dashboard = (
        "📊 *MY DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Farmer:* {name}\n"
        f"📱 *Phone:* {phone}\n\n"
        f"📝 *Disease Scans:* {stats['total_scans']}\n"
        f"🏷️ *Leaf Grades:* {stats['total_grades']}\n"
        f"📊 *Avg Grade:* {stats['avg_grade']}\n"
        f"🦠 *Common Disease:* {stats['top_disease']}\n"
        f"🌿 *Healthy Leaves:* {stats['healthy_count']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *View History*\n"
        "2️⃣ *Daily Tip*\n"
        "3️⃣ *Fun Fact*\n\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, dashboard)

def send_expert_menu(phone):
    menu = (
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *AI Advisor* - Ask anything\n"
        "2️⃣ *Human Expert* - Talk to agronomist\n\n"
        "Reply with number (1 or 2)\n"
        "0️⃣ Main Menu"
    )
    return send_whatsapp(phone, menu)

def get_user_history(phone, limit=5):
    """Get user's complete history (disease + grading)"""
    if not db:
        return []
    
    try:
        disease_docs = db.collection("detections")\
            .where("phone", "==", phone)\
            .order_by("timestamp", direction="DESCENDING")\
            .limit(limit)\
            .stream()
        
        grade_docs = db.collection("leaf_grades")\
            .where("phone", "==", phone)\
            .order_by("timestamp", direction="DESCENDING")\
            .limit(limit)\
            .stream()
        
        history = []
        
        for doc in disease_docs:
            data = doc.to_dict()
            if data.get("timestamp"):
                ts = data["timestamp"]
                if hasattr(ts, "strftime"):
                    data["date"] = ts.strftime("%d %b %Y")
            data["record_type"] = "disease"
            history.append(data)
        
        for doc in grade_docs:
            data = doc.to_dict()
            if data.get("timestamp"):
                ts = data["timestamp"]
                if hasattr(ts, "strftime"):
                    data["date"] = ts.strftime("%d %b %Y")
            data["record_type"] = "grade"
            history.append(data)
        
        history.sort(key=lambda x: x.get("timestamp", 0) if hasattr(x.get("timestamp"), "timestamp") else 0, reverse=True)
        
        return history[:limit]
    except Exception as e:
        debug_log(f"❌ History error: {e}")
        return []

# ==============================
# BACKGROUND WORKER FUNCTION
# ==============================
def background_worker():
    """Background worker to process tasks from queue"""
    debug_log("👷 Background worker started")
    
    while True:
        try:
            task = task_queue.get()
            
            phone = task["phone"]
            name = task["name"]
            image_bytes = task["image"]
            
            debug_log(f"👷 Processing task for {phone} - Queue size: {task_queue.qsize()}")
            
            send_whatsapp(phone, f"🤖 AI verifying symptoms...")
            
            hf_result, ai_result = process_detection_parallel(image_bytes)
            
            if not hf_result:
                send_whatsapp(phone, "❌ Analysis failed. Please try another photo.")
            else:
                disease = hf_result["disease"]
                confidence = hf_result["confidence"]
                severity = hf_result.get("severity", "Unknown")
                is_healthy = hf_result["is_healthy"]
                low_confidence = hf_result["low_confidence"]
                
                if low_confidence or confidence < 50 or disease == "Unknown":
                    response = (
                        f"❓ *UNCLEAR DETECTION*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"⚠️ Confidence: {confidence:.0f}%\n\n"
                        f"📸 Please send a clearer photo with:\n"
                        f"• Good lighting\n"
                        f"• Close-up of the leaf\n"
                        f"• In focus\n\n"
                        f"Type *menu* for other options."
                    )
                elif is_healthy:
                    response = (
                        f"🌿 *HEALTHY LEAF DETECTED*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Confidence: {confidence:.0f}%\n\n"
                        f"💚 Great job, {name}! Your plant looks healthy.\n\n"
                        f"Continue good farming practices:\n"
                        f"• Regular monitoring\n"
                        f"• Balanced fertilizer\n"
                        f"• Proper watering"
                    )
                else:
                    response = (
                        f"🌿 *{disease.upper()} DETECTED*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 Confidence: {confidence:.0f}%\n"
                        f"{get_confidence_message(confidence)}\n"
                    )
                    
                    if severity != "Unknown":
                        response += f"\n{SEVERITY_ADVICE.get(severity, '')}\n"
                    
                    if ai_result:
                        response += f"\n🔬 *AI Verification:*\n{ai_result}\n"
                    
                    if disease in DISEASE_ADVICE_CACHE:
                        response += f"\n💡 *Advice:*\n{DISEASE_ADVICE_CACHE[disease]}"
                    elif hf_result["treatment"]:
                        response += f"\n💡 *Treatment:*\n{hf_result['treatment']}"
                
                send_whatsapp(phone, response)
                log_detection(phone, name, disease, confidence, severity)
            
            sync_delay(3)
            send_main_menu(phone)
            
            cleanup_memory(image_bytes, hf_result, ai_result)
            task_queue.task_done()
            
        except Exception as e:
            debug_log(f"❌ Worker error: {e}")
            import traceback
            traceback.print_exc()
            task_queue.task_done()

# ==============================
# START WORKERS FUNCTION
# ==============================
def start_workers():
    """Start multiple background workers"""
    worker_count = 3
    for i in range(worker_count):
        worker_thread = Thread(target=background_worker, daemon=True)
        worker_thread.start()
        debug_log(f"👷 Worker {i+1} started with thread ID: {worker_thread.ident}")

# ==============================
# MESSAGE HANDLER
# ==============================
def handle_message(phone, msg_type, content):
    debug_log(f"📨 Handling: {msg_type} from {phone}")
    
    user = get_user(phone)
    
    if not user:
        save_user(phone, {"state": USER_STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, 
            "🌿 *Welcome to Tobacco AI!*\n\n"
            "I help tobacco farmers detect diseases and learn best practices.\n\n"
            "Please enter your *name* to continue:")

    state = user.get("state", USER_STATES["ACTIVE"])
    name = user.get("name", "Farmer")

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
    
    if state == USER_STATES["DASHBOARD_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            history = get_user_history(phone)
            if not history:
                msg = "📋 *No history yet.*\n\nSend a photo for disease detection or leaf grading!"
            else:
                msg = "📋 *YOUR COMPLETE HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, item in enumerate(history[:5], 1):
                    if item.get("record_type") == "disease":
                        msg += f"{i}. 🦠 *{item.get('disease')}* - {item.get('confidence', 0):.0f}%\n"
                    else:
                        msg += f"{i}. 🏷️ *Grade {item.get('grade')}* - Leaf Quality\n"
                    if item.get('date'):
                        msg += f"   📅 {item.get('date')}\n"
            send_whatsapp(phone, trim_message(msg, 1500))
            
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "2":
            tip = get_gemini_tip()
            send_whatsapp(phone, f"💡 *Daily Tip*\n\n{tip}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        elif cmd == "3":
            fact = get_gemini_fact()
            send_whatsapp(phone, f"🎲 *Did You Know?*\n\n{fact}")
            stats = get_user_statistics(phone)
            return send_dashboard_menu(phone, name, stats)
        else:
            return send_whatsapp(phone, "❌ Please choose 1, 2, or 3 (or *0* for Main Menu).")

    if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
        answer = ask_ai_advisor(content)
        send_whatsapp(phone, answer)
        sync_delay(2)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    if state == USER_STATES["FARMING_MENU"] and msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd == "0":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        static_guides = {
            "1": PLANTING_GUIDE,
            "2": FERTILIZER_GUIDE,
            "3": HARVESTING_GUIDE,
            "4": CURING_GUIDE,
            "5": MARKETING_GUIDE
        }
        
        if cmd in static_guides:
            send_whatsapp(phone, static_guides[cmd])
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

    if state == USER_STATES["WAITING_GRADE_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Processing grading")
        send_whatsapp(phone, f"🔍 Analyzing leaf quality, {name}...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            send_whatsapp(phone, "❌ Failed to download image.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        grade, analysis, grade_letter = grade_leaf_with_ai(image_bytes)
        
        response = f"📊 *LEAF GRADING RESULTS*\n━━━━━━━━━━━━━━━━━━\n"
        response += analysis
        
        log_leaf_grade(phone, name, grade_letter, analysis)
        send_whatsapp(phone, response)
        
        cleanup_memory(image_bytes)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        sync_delay(3)
        send_main_menu(phone)
        return

    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        
        current_time = time.time()
        if phone in LAST_SCAN:
            time_since_last = current_time - LAST_SCAN[phone]
            if time_since_last < COOLDOWN_SECONDS:
                wait_time = int(COOLDOWN_SECONDS - time_since_last)
                return send_whatsapp(phone, f"⏱️ Please wait {wait_time} seconds between scans.")
        
        LAST_SCAN[phone] = current_time
        
        debug_log(f"📸 Detection from {phone}")
        
        if task_queue.qsize() > MAX_QUEUE_SIZE:
            return send_whatsapp(phone, "⚠️ Server is busy. Please try again in a few minutes.")
        
        send_whatsapp(phone, f"📷 Processing your image, {name}...")
        image_bytes = download_image(content)
        
        if not image_bytes:
            send_whatsapp(phone, "❌ Failed to download image. Please try again.")
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        task_queue.put({
            "phone": phone,
            "name": name,
            "image": image_bytes
        })
        
        send_whatsapp(phone, f"🔍 Analyzing with AI model...")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return

    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Feedback cancelled.")
        else:
            if ADMIN_PHONE:
                admin_msg = (
                    f"📝 *FEEDBACK RECEIVED*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *From:* {name}\n"
                    f"📱 *Phone:* {phone}\n"
                    f"📅 *Date:* {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
                    f"💬 *Message:*\n{content}"
                )
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "✅ Thank you! Your feedback has been sent to our team.")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        sync_delay(2)
        return send_main_menu(phone)

    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Expert request cancelled.")
        else:
            if ADMIN_PHONE:
                admin_msg = (
                    f"🚨 *EXPERT REQUEST*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Farmer:* {name}\n"
                    f"📱 *Phone:* {phone}\n"
                    f"📅 *Date:* {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
                    f"💬 *Issue:*\n{content}"
                )
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "👨‍🌾 Your request has been sent. An expert will contact you soon.")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        sync_delay(2)
        return send_main_menu(phone)

    if msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd in ["menu", "0", "main"]:
            return send_main_menu(phone)
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            send_whatsapp(phone, 
                "📸 *Disease Detection*\n\n"
                "Send a clear photo of the tobacco leaf.\n\n"
                "Tips: Good lighting, close-up, steady camera")
        elif cmd in ["2", "farming"]:
            save_user(phone, {"state": USER_STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        elif cmd in ["3", "dashboard"]:
            stats = get_user_statistics(phone)
            save_user(phone, {"state": USER_STATES["DASHBOARD_MENU"]})
            return send_dashboard_menu(phone, name, stats)
        elif cmd in ["4", "grade"]:
            save_user(phone, {"state": USER_STATES["WAITING_GRADE_IMAGE"]})
            send_whatsapp(phone, 
                "🏷️ *LEAF QUALITY GRADING*\n\n"
                "Send a clear photo of your cured leaf.\n\n"
                "I'll analyze: grade, color, damage\n\n"
                "Tips: Good lighting, flat surface")
        elif cmd in ["5", "expert"]:
            save_user(phone, {"state": USER_STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        elif cmd in ["6", "feedback"]:
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            send_whatsapp(phone, 
                "📝 *Send Feedback*\n\n"
                "Type your message below (or *cancel*):")
        elif cmd.startswith("ai "):
            question = cmd[3:].strip()
            if question:
                send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
                answer = ask_ai_advisor(question)
                send_whatsapp(phone, answer)
                sync_delay(2)
                return send_main_menu(phone)
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
        "queue_size": task_queue.qsize(),
        "workers": 3,
        "collections": ["users", "detections", "leaf_grades"],
        "cooldown": f"{COOLDOWN_SECONDS}s",
        "admin": bool(ADMIN_PHONE),
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant is running!"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # START WORKERS HERE
    start_workers()
    
    debug_log(f"🚀 Starting Tobacco AI Assistant on port {port}")
    debug_log(f"🤖 Using Hugging Face Space: {HF_SPACE_URL}")
    debug_log(f"📱 Admin: {'✅' if ADMIN_PHONE else '❌'}")
    debug_log(f"🤖 AI: {'✅' if AI_API_KEY else '❌'}")
    debug_log(f"⏱️ Cooldown: {COOLDOWN_SECONDS}s")
    debug_log(f"👷 Workers: 3 parallel processors")
    debug_log(f"📊 Firebase Collections: users, detections, leaf_grades")
    app.run(host="0.0.0.0", port=port, debug=False)
