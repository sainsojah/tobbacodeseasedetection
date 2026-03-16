"""
Tobacco AI Assistant - Render WhatsApp Bot
Fixed: Complete responses, admin feedback working, increased token limits
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
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")  # This will work with country code
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsouldier-tobacco-ai.hf.space")

# AI API Keys
AI_API_KEY = os.environ.get("AI_API_KEY")

# Configure Google Generative AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    debug_log("✅ Google Generative AI configured")

# CORRECT MODEL NAMES - Prioritize stable models first
GEMINI_MODELS = [
    'models/gemini-2.5-flash',       # Newer model
    'models/gemini-2.5-pro',         # Newer pro model
    'models/gemini-3.1-pro-preview', # Preview model
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
    "max_output_tokens": 1000,  # Increased from 800 for longer responses
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

# Vision-specific config - INCREASED for complete grading
vision_config = {
    "temperature": 0.7,
    "max_output_tokens": 800,  # Increased from 500 for complete grading
    "top_p": 0.8
}

# Tip/Fact specific config - INCREASED for complete sentences
tip_config = {
    "temperature": 0.8,
    "max_output_tokens": 600,  # Increased from 300
}

fact_config = {
    "temperature": 0.9,
    "max_output_tokens": 600,  # Increased from 300
}

# Higher limit for trimming - only used as safety net
def trim_message(text, max_length=3000):
    """Trim message to safe WhatsApp length (only as safety net)"""
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
        return "✔ *High Accuracy*"
    elif confidence > 60:
        return "⚠ *Medium Accuracy*"
    else:
        return "❗ *Low Accuracy - please retake photo*"

# ==============================
# SEVERITY ESTIMATION FUNCTION
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
        return f"ℹ️ For specific advice on {disease}, please ask the AI advisor (type *ai your question*)"

# ==============================
# IMPROVED AI ADVISOR WITH CURRENT DATE
# ==============================
def ask_ai_advisor(question):
    """AI advisor with current date reference"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return "🤖 AI advisor not configured. Please add API key."
    
    # Check if question contains a known disease name
    disease_found = None
    for disease in DISEASE_KNOWLEDGE_BASE.keys():
        if disease.lower() in question.lower():
            disease_found = disease
            break
    
    # Get current date for context
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    current_month = datetime.now().strftime("%B")
    
    # Try each model in sequence until one works
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(1)
            debug_log(f"🔄 Trying Gemini model: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Prompt with current date instruction
            prompt = f"""You are a Zimbabwe tobacco expert. Today's date is {current_date} ({current_month} {current_year}).

Answer the following question using CURRENT information (2025-{current_year}) only. DO NOT reference 2024 or older data unless specifically asked about historical trends.

Question: {question}

IMPORTANT GUIDELINES:
1. Use ONLY current season data (2025-{current_year})
2. Keep response under 200 words total
3. Include key points only
4. Use bullet points for clarity
5. End with a complete sentence - DO NOT cut off mid-sentence

If asked about prices, volumes, or market conditions - provide estimates based on CURRENT {current_year} season projections."""

            # Generate response
            response = model.generate_content(prompt)
            
            if response and response.text:
                answer = response.text.strip()
                debug_log(f"✅ Success with model: {model_name} (response length: {len(answer)} chars)")
                return answer
            else:
                debug_log(f"⚠️ Empty response from {model_name}")
                continue
                
        except Exception as e:
            debug_log(f"❌ Error with {model_name}: {str(e)[:100]}")
            continue
    
    # If all models fail, use fallback
    debug_log(f"⚠️ All Gemini models failed, using fallback")
    if disease_found:
        return get_offline_disease_advice(disease_found)
    else:
        return f"⚠️ AI service temporarily unavailable. Please try again later or use the farming guides (type *menu*)."

# ==============================
# IMPROVED AI LEAF GRADING WITH BETTER RETRY LOGIC
# ==============================
def grade_leaf_with_ai(image_bytes):
    """Grade leaf using google.generativeai library with improved retry logic"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return None, "AI grading not configured"
    
    # Try each model in sequence
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(1)
            debug_log(f"🔄 Trying Gemini Vision with model: {model_name}")
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=vision_config,
                safety_settings=safety_settings
            )
            
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            # More detailed prompt for complete grading
            prompt = """Grade this tobacco leaf thoroughly. Provide a COMPLETE analysis with ALL fields filled:

📊 *LEAF GRADE RESULTS*
━━━━━━━━━━━━━━━━━━
• Grade (A/B/C/D): [Choose one - A=Premium, B=Good, C=Fair, D=Poor]
• Color: [Detailed color description with notes on uniformity]
• Texture: [Description - oily, dry, brittle, supple, etc.]
• Damage: [Any spots, tears, holes, or imperfections]
• Market Value: [Premium/Good/Fair/Poor with brief explanation]

IMPORTANT: Fill in ALL fields completely. Do not leave anything blank. End with a complete sentence."""

            # Try up to 3 attempts for this model with increasing timeouts
            for attempt in range(3):
                try:
                    response = model.generate_content([
                        prompt,
                        {"mime_type": "image/jpeg", "data": image_data}
                    ])
                    
                    if response and response.text:
                        analysis = response.text.strip()
                        
                        # Check if response seems complete (has all sections)
                        if len(analysis) > 100 and all(section in analysis for section in ['Grade', 'Color', 'Texture', 'Damage', 'Market']):
                            debug_log(f"✅ Complete grading with model: {model_name}")
                            return "Grade", analysis
                        elif len(analysis) > 50:
                            debug_log(f"⚠️ Partial grading from {model_name}, but sending anyway")
                            return "Grade", analysis
                        else:
                            debug_log(f"⚠️ Response too short from {model_name}, attempt {attempt+1}")
                            time.sleep(2)
                    else:
                        debug_log(f"⚠️ Empty response from {model_name}, attempt {attempt+1}")
                        time.sleep(2)
                        
                except Exception as e:
                    debug_log(f"⚠️ Attempt {attempt+1} failed for {model_name}: {str(e)[:100]}")
                    time.sleep(2)
                    continue
                
        except Exception as e:
            debug_log(f"❌ Error with {model_name}: {str(e)[:100]}")
            continue
    
    return None, "⚠️ Grading service temporarily unavailable. Please try again later."

# ==============================
# IMPROVED DAILY TIP
# ==============================
def get_gemini_tip():
    """Generate a fresh daily farming tip - COMPLETE sentences"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases. This breaks pest cycles and improves soil fertility for the next season.",
            "💧 Water in the morning to reduce humidity and prevent fungal growth. Evening watering can leave leaves wet overnight, promoting disease.",
            "🔍 Check fields weekly for early signs of disease. Early detection allows for quick treatment before problems spread."
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
            
            prompt = f"""ONE practical farming tip for Zimbabwe tobacco farmers during {season}. 

Requirements:
- 3-4 complete sentences
- Start with an emoji
- Include specific details
- End with a complete sentence (no cut-offs)
- Use {current_year} context only

Tip:"""
            response = model.generate_content(prompt)
            
            if response and response.text:
                tip = response.text.strip()
                # Ensure it ends with punctuation
                if tip and tip[-1] not in ['.', '!', '?']:
                    tip += '.'
                return tip
            else:
                continue
                
        except Exception:
            continue
    
    return random.choice([
        f"🌱 Monitor your fields daily for early disease signs this {datetime.now().year} season. Check both upper and lower leaves for spots or discoloration.",
        f"💧 Water early morning to prevent fungal growth during {datetime.now().year} planting. This allows leaves to dry before evening.",
        f"🔍 Check lower leaves regularly for pests and diseases in {datetime.now().year}. Problems often start there before spreading upward."
    ])

# ==============================
# IMPROVED FUN FACT
# ==============================
def get_gemini_fact():
    """Generate a fresh interesting fact - COMPLETE sentences"""
    if not AI_API_KEY or AI_API_KEY == "your_api_key_here":
        return random.choice([
            "🌱 Tobacco is related to tomatoes and potatoes! All three belong to the Solanaceae family, which is why they share similar pests and diseases.",
            "🍃 Zimbabwe produces world-class flue-cured tobacco known for its golden color and sweet flavor, making it highly sought after in international markets.",
            "📜 Tobacco has been cultivated for over 8,000 years, originally used for ceremonial and medicinal purposes by indigenous peoples."
        ])
    
    for model_name in GEMINI_MODELS:
        try:
            time.sleep(0.5)
            
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=fact_config,
                safety_settings=safety_settings
            )
            
            prompt = f"""ONE interesting fact about Zimbabwe tobacco farming for {datetime.now().year}.

Requirements:
- 3-4 complete sentences
- Start with an emoji
- Include specific details or statistics
- End with a complete sentence (no cut-offs)

Fact:"""
            response = model.generate_content(prompt)
            
            if response and response.text:
                fact = response.text.strip()
                # Ensure it ends with punctuation
                if fact and fact[-1] not in ['.', '!', '?']:
                    fact += '.'
                return fact
            else:
                continue
                
        except Exception:
            continue
    
    return random.choice([
        f"🌱 Zimbabwe's tobacco industry employs over 500,000 people in {datetime.now().year}. This includes farmers, laborers, and workers in processing and marketing sectors.",
        "📜 Tobacco has been cultivated in Zimbabwe for over 8,000 years, originally used for ceremonial purposes by ancient communities.",
        "🌍 Zimbabwe exports premium flue-cured tobacco to over 50 countries, with China, Belgium, and South Africa being the largest markets."
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
        response = requests.post(url, json=payload, headers=headers, timeout=35)
        debug_log(f"📤 WhatsApp sent to {to}: {response.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ WhatsApp send error: {e}")
        return False

def send_whatsapp_with_retry(to, text, max_retries=3):
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

# ==============================
# MENU FUNCTIONS
# ==============================
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
# MESSAGE HANDLER - WITH 20 SECOND DELAY
# ==============================
def handle_message(phone, msg_type, content):
    """Main message handler with improved response handling and 20s delay"""
    debug_log(f"📨 Handling message: type={msg_type}, phone={phone}")
    
    user = get_user(phone)
    
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
            history = get_user_history(phone)
            if not history:
                msg = "📋 *No scan history yet.*\n\nSend a photo to start!"
                send_whatsapp(phone, msg)
                stats = get_user_statistics(phone)
                return send_dashboard_menu(phone, name, stats)
            else:
                msg = "📋 *YOUR SCAN HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, h in enumerate(history[:5], 1):
                    msg += f"{i}. *{h.get('disease', 'Unknown')}* - {h.get('confidence', 0):.1f}%\n"
                    msg += f"   📅 {h.get('date', 'Unknown')}\n\n"
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

    # AWAITING AI QUESTION - WITH 20 SECOND DELAY
    if state == USER_STATES["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Send thinking message
        send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
        
        # Get response
        result = ask_ai_advisor(content)
        
        # Send the AI response
        send_whatsapp_with_retry(phone, result)
        
        # Wait 20 seconds to ensure user sees the full response
        debug_log(f"⏱️ Waiting 20 seconds before showing menu...")
        time.sleep(20)
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return send_main_menu(phone)

    # FARMING PRACTICES SUBMENU HANDLER
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

    # LEAF GRADING - WITH 20 SECOND DELAY
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
            send_whatsapp_with_retry(phone, analysis)
        else:
            send_whatsapp(phone, "❌ Could not analyze the image. Please try again.")
        
        debug_log(f"⏱️ Waiting 20 seconds before showing menu...")
        time.sleep(20)  # 20 second delay
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        send_main_menu(phone)
        gc.collect()
        return

    # DISEASE DETECTION - WITH SPAM PREVENTION AND 20 SECOND DELAY
    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        # Spam prevention - cooldown check
        current_time = time.time()
        if phone in LAST_SCAN:
            if current_time - LAST_SCAN[phone] < 5:
                debug_log(f"⚠️ Spam prevention: {phone} tried to send image too quickly")
                return send_whatsapp(phone, "⏱️ Please wait 5 seconds between scans.")
        
        # Update last scan time
        LAST_SCAN[phone] = current_time
        
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
        severity = result.get("severity", "Unknown")
        confidence_msg = get_confidence_message(confidence)
        
        debug_log(f"✅ Detection result: {disease} ({confidence:.1f}%) Severity: {severity}")
        log_detection(phone, name, disease, confidence)
        
        if result["low_confidence"]:
            response = f"⚠️ *Low Confidence ({confidence:.1f}%)*\n\n{confidence_msg}\n\nPlease upload a clearer photo."
        elif result["is_healthy"]:
            response = f"🎉 *Healthy Leaf Detected!*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}\n\nGreat job!"
        else:
            response = f"📊 *{disease} DETECTED*\n\nConfidence: {confidence:.1f}%\n{confidence_msg}"
            
            if severity != "Unknown":
                response += f"\nSeverity: *{severity}*"
            
            response += f"\n\n*Treatment:*\n{result['treatment']}"
        
        send_whatsapp(phone, response)
        
        if not result["is_healthy"] and not result["low_confidence"]:
            offline_advice = get_offline_disease_advice(disease)
            send_whatsapp(phone, offline_advice + "\n\nType *ai your question* for more advice")
        
        debug_log(f"⏱️ Waiting 20 seconds before showing menu...")
        time.sleep(20)  # 20 second delay
        send_main_menu(phone)
        gc.collect()
        return

    # AWAITING FEEDBACK - FIXED ADMIN NOTIFICATION
    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Feedback cancelled.")
        else:
            # Send feedback to admin - FIXED: Now starts a new chat with clear formatting
            if ADMIN_PHONE:
                admin_msg = (
                    f"📝 *NEW FEEDBACK RECEIVED*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *From:* {name}\n"
                    f"📱 *Phone:* {phone}\n"
                    f"📅 *Date:* {datetime.now().strftime('%d %b %Y at %H:%M')}\n\n"
                    f"💬 *Message:*\n{content}\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"Reply to this message to respond to the farmer."
                )
                # Send to admin - this creates a new chat thread
                send_whatsapp(ADMIN_PHONE, admin_msg)
                debug_log(f"📨 Feedback sent to admin: {ADMIN_PHONE}")
            
            # Thank the user
            send_whatsapp(phone, "✅ Thank you! Your feedback has been sent to our team. We appreciate your input!")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # AWAITING EXPERT - FIXED ADMIN NOTIFICATION
    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Expert request cancelled.")
        else:
            # Send expert request to admin - FIXED: Now starts a new chat with clear formatting
            if ADMIN_PHONE:
                admin_msg = (
                    f"🚨 *URGENT: EXPERT REQUEST*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Farmer:* {name}\n"
                    f"📱 *Phone:* {phone}\n"
                    f"📅 *Date:* {datetime.now().strftime('%d %b %Y at %H:%M')}\n\n"
                    f"💬 *Issue Description:*\n{content}\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"PLEASE RESPOND TO THIS FARMER ASAP.\n"
                    f"Reply to this message to contact them."
                )
                # Send to admin - this creates a new chat thread
                send_whatsapp(ADMIN_PHONE, admin_msg)
                debug_log(f"📨 Expert request sent to admin: {ADMIN_PHONE}")
            
            # Acknowledge the user
            send_whatsapp(phone, "👨‍🌾 Your request has been sent to our expert team. They will contact you within 24-48 hours. Thank you for your patience!")
        
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # TEXT COMMANDS - FIXED AI COMMAND WITH 20 SECOND DELAY
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
                result = ask_ai_advisor(question)
                send_whatsapp_with_retry(phone, result)
                
                # Wait 20 seconds before showing menu
                debug_log(f"⏱️ Waiting 20 seconds before showing menu...")
                time.sleep(20)
                return send_main_menu(phone)
            else:
                send_whatsapp(phone, "❓ Example: *ai how to prevent black shank*")
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
        "ai_provider": "gemini" if AI_API_KEY else "disabled",
        "current_year": datetime.now().year,
        "admin_configured": bool(ADMIN_PHONE),
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
    debug_log(f"📱 Admin phone: {ADMIN_PHONE if ADMIN_PHONE else 'Not configured'}")
    debug_log(f"📅 Current year: {datetime.now().year}")
    if AI_API_KEY and AI_API_KEY != "your_api_key_here":
        debug_log(f"✅ AI Advisor enabled with CURRENT YEAR focus and 20-second delay")
    else:
        debug_log(f"ℹ️ AI Advisor disabled - set AI_API_KEY environment variable")
    app.run(host="0.0.0.0", port=port, debug=False)
