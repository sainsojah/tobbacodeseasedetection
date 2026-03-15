"""
Tobacco AI Assistant - Two-Message Version (HF First, Then AI)
"""
import os
import json
import requests
import time
import base64
import io
import random
from threading import Thread
from flask import Flask, request, jsonify
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
import google.generativeai as genai
from PIL import Image

app = Flask(__name__)

def debug_log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# Load environment
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsouldier-tobacco-ai.hf.space")
AI_API_KEY = os.environ.get("AI_API_KEY")

# Configure AI
if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    debug_log("✅ Gemini configured")

# Cooldown
LAST_SCAN = {}
COOLDOWN = 5

# Persistent session
session = requests.Session()
session.mount('https://', HTTPAdapter(pool_connections=10, pool_maxsize=10))

# Vision config
vision_config = {"temperature": 0.7, "max_output_tokens": 300, "top_p": 0.8}
safety = [{"category": f"HARM_CATEGORY_{c}", "threshold": "BLOCK_MEDIUM_AND_ABOVE"} 
          for c in ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT"]]

# Disease advice - Professional format
DISEASE_ADVICE = {
    "Black Shank": "💧 *Black Shank*\n• Improve soil drainage immediately\n• Remove and destroy infected plants\n• Apply Ridomil fungicide\n• Rotate with maize next season",
    "Black Spot": "🔴 *Black Spot*\n• Apply copper-based fungicide\n• Remove all infected leaves\n• Improve air circulation\n• Avoid overhead watering",
    "Early Blight": "🍂 *Early Blight*\n• Apply Mancozeb fungicide\n• Remove lower leaves\n• Space plants properly\n• Practice crop rotation",
    "Late Blight": "🌧️ *Late Blight*\n• Remove infected plants IMMEDIATELY\n• Apply Ridomil Gold\n• Use disease-free transplants\n• Avoid excessive moisture",
    "Tobacco Mosaic Virus": "⚠️ *TMV - NO CURE*\n• Remove infected plants NOW\n• Wash hands with milk/soap\n• Disinfect all tools\n• Use resistant varieties next season",
    "Leaf Spot": "📌 *Leaf Spot*\n• Apply copper fungicide\n• Remove affected leaves\n• Avoid wetting leaves\n• Improve air circulation",
    "Powdery Mildew": "⚪ *Powdery Mildew*\n• Apply sulfur spray\n• Reduce nitrogen fertilizer\n• Improve air flow\n• Water at base only",
    "Spider Mites": "🕷️ *Spider Mites*\n• Apply miticide\n• Maintain humidity\n• Avoid water stress\n• Check leaf undersides",
    "Healthy": "🌿 *Healthy Leaf*\n• Continue good practices\n• Monitor regularly\n• Maintain balanced fertilizer\n• Keep up with watering schedule"
}

# Severity advice
SEVERITY_ADVICE = {
    "Mild": "🟢 *Mild* - Early stage. Monitor closely and begin treatment.",
    "Moderate": "🟡 *Moderate* - Take action now to prevent spread.",
    "Severe": "🔴 *Severe* - Act immediately! Remove affected plants."
}

# Firebase
db = None
if FIREBASE_CONFIG:
    try:
        cred = credentials.Certificate(json.loads(FIREBASE_CONFIG))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        debug_log("✅ Firebase connected")
    except Exception as e:
        debug_log(f"❌ Firebase error: {e}")

# User states
STATES = {
    "AWAITING_NAME": "awaiting_name", "ACTIVE": "active", "WAITING_IMAGE": "waiting_image",
    "AWAITING_FEEDBACK": "awaiting_feedback", "AWAITING_EXPERT": "awaiting_expert",
    "AWAITING_AI": "awaiting_ai_question", "FARMING_MENU": "farming_menu",
    "WAITING_GRADE": "waiting_grade_image", "EXPERT_MENU": "expert_menu",
    "DASHBOARD_MENU": "dashboard_menu"
}

# Full professional guides
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

GUIDES = {
    "1": PLANTING_GUIDE,
    "2": FERTILIZER_GUIDE,
    "3": HARVESTING_GUIDE,
    "4": CURING_GUIDE,
    "5": MARKETING_GUIDE
}

# Tips and facts
TIPS = [
    "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases. This breaks pest cycles naturally.",
    "💧 Water in the morning to reduce humidity and prevent fungal growth. Leaves dry before evening.",
    "🔍 Check fields weekly for early signs of disease. Early detection saves crops.",
    "🧪 Test soil pH before fertilizing. Tobacco needs pH 5.5-6.5 for optimal growth.",
    "🌿 Remove infected leaves immediately to prevent disease spread.",
    "🌱 Plant after good rains, not before - prevents damping off in seedlings.",
    "🔥 Monitor curing temperatures closely. Keep at 32-38°C for yellowing phase."
]

FACTS = [
    "🌍 Zimbabwe exports premium flue-cured tobacco to over 50 countries worldwide.",
    "👨‍🌾 Tobacco farming supports over 500,000 Zimbabwean families directly and indirectly.",
    "💰 Tobacco is Zimbabwe's 2nd largest foreign currency earner after gold.",
    "🌱 Tobacco is related to tomatoes and potatoes - all in the Solanaceae family!",
    "🔥 Curing turns tobacco leaves from green to gold in 6-7 days through careful temperature control.",
    "📜 Tobacco has been cultivated in Zimbabwe for over 100 years commercially.",
    "🌿 Zimbabwe's tobacco is known globally for its golden color and sweet flavor."
]

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
    if not text: return False
    try:
        r = session.post(f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
                        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
                        json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}},
                        timeout=15)
        debug_log(f"📤 Sent: {r.status_code}")
        return True
    except Exception as e:
        debug_log(f"❌ Send error: {e}")
        return False

def get_user(phone):
    if not db: return None
    try:
        doc = db.collection("users").document(phone).get()
        return doc.to_dict() if doc.exists else None
    except: return None

def save_user(phone, data):
    if not db: return False
    try:
        db.collection("users").document(phone).set(data, merge=True)
        return True
    except: return False

def log_detection(phone, name, disease, confidence, severity=None):
    if not db: return
    try:
        data = {"phone": phone, "name": name, "disease": disease, "confidence": confidence, 
                "timestamp": firestore.SERVER_TIMESTAMP}
        if severity: data["severity"] = severity
        db.collection("detections").add(data)
        debug_log(f"📊 Logged: {disease}")
    except: pass

def compress_image(img_bytes, size=768):
    try:
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ('RGBA','P'): img = img.convert('RGB')
        img.thumbnail((size, size))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except: return img_bytes

def download_image(media_id):
    try:
        debug_log(f"📥 Downloading: {media_id}")
        r = session.get(f"https://graph.facebook.com/v18.0/{media_id}", 
                       headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, timeout=10)
        if r.status_code != 200: return None
        media_url = r.json().get("url")
        if not media_url: return None
        img = session.get(media_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, timeout=30)
        return compress_image(img.content) if img.status_code == 200 else None
    except: return None

def get_stats(phone):
    if not db: return {"scans": 0, "top": "None", "healthy": 0}
    try:
        docs = db.collection("detections").where("phone", "==", phone).stream()
        scans, diseases, healthy = 0, {}, 0
        for doc in docs:
            data = doc.to_dict()
            scans += 1
            d = data.get("disease", "Unknown")
            if d == "Healthy": healthy += 1
            else: diseases[d] = diseases.get(d, 0) + 1
        top = max(diseases, key=diseases.get) if diseases else "None"
        return {"scans": scans, "top": top, "healthy": healthy}
    except: return {"scans": 0, "top": "None", "healthy": 0}

# ==============================
# DETECTION FUNCTIONS
# ==============================
def detect_hf(image_bytes):
    try:
        debug_log("🔍 HF detection...")
        r = session.post(f"{HF_SPACE_URL}/predict", files={'file': ('image.jpg', image_bytes, 'image/jpeg')}, timeout=30)
        if r.status_code == 200:
            res = r.json()
            if res.get("success"):
                # Estimate severity
                conf = res.get("confidence", 0)
                if conf > 85: severity = "Moderate"
                elif conf > 60: severity = "Mild"
                else: severity = "Unknown"
                
                return {
                    "disease": res.get("disease", "Unknown"),
                    "confidence": conf,
                    "treatment": res.get("treatment", ""),
                    "is_healthy": res.get("is_healthy", False),
                    "low_confidence": res.get("low_confidence", False),
                    "severity": severity
                }
    except Exception as e:
        debug_log(f"❌ HF error: {e}")
    return None

def analyze_ai(image_bytes):
    if not AI_API_KEY: return None
    for model in ['models/gemini-2.5-flash', 'models/gemini-1.5-flash']:
        try:
            m = genai.GenerativeModel(model, generation_config=vision_config, safety_settings=safety)
            img_data = base64.b64encode(image_bytes).decode('utf-8')
            prompt = """Analyze this tobacco leaf. Provide:
1. Visible symptoms (2-3 points)
2. Possible disease name
3. Severity level (Mild/Moderate/Severe)
4. One short actionable advice

Keep it concise and professional."""
            resp = m.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_data}])
            if resp and resp.text: return resp.text.strip()
        except: continue
    return None

# ==============================
# BACKGROUND PROCESSOR - TWO MESSAGES
# ==============================
def process_image(phone, name, img_bytes):
    # Step 1: HF Detection
    debug_log(f"🔍 HF for {phone}")
    hf = detect_hf(img_bytes)
    
    if not hf:
        send_whatsapp(phone, "❌ Analysis failed. Please try another photo.")
        return
    
    # Send first message (detection result)
    disease = hf["disease"]
    conf = hf["confidence"]
    severity = hf.get("severity", "Unknown")
    
    if hf["low_confidence"] or conf < 50:
        msg1 = (
            f"❓ *UNCLEAR DETECTION*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Confidence: {conf:.0f}%\n\n"
            f"📸 Please send a clearer photo with:\n"
            f"• Good lighting\n"
            f"• Close-up of the leaf\n"
            f"• In focus"
        )
    elif hf["is_healthy"]:
        msg1 = (
            f"🌿 *HEALTHY LEAF DETECTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ Confidence: {conf:.0f}%\n\n"
            f"💚 Great job, {name}! Your plant looks healthy.\n\n"
            f"Continue good farming practices:\n"
            f"• Regular monitoring\n"
            f"• Balanced fertilizer\n"
            f"• Proper watering"
        )
    else:
        msg1 = (
            f"🌿 *{disease.upper()} DETECTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Confidence: {conf:.0f}%\n"
        )
        if severity != "Unknown":
            msg1 += f"\n{SEVERITY_ADVICE.get(severity, '')}\n"
        if disease in DISEASE_ADVICE:
            msg1 += f"\n💡 *Advice:*\n{DISEASE_ADVICE[disease]}"
        elif hf["treatment"]:
            msg1 += f"\n💡 *Treatment:*\n{hf['treatment']}"
    
    send_whatsapp(phone, msg1)
    log_detection(phone, name, disease, conf, severity)
    
    # Step 2: AI Analysis (only if not healthy and confidence < 85%)
    if not hf["is_healthy"] and conf < 85:
        debug_log(f"🤖 AI for {phone}")
        send_whatsapp(phone, f"🔬 AI analyzing symptoms...")
        ai = analyze_ai(img_bytes)
        if ai:
            msg2 = f"🔬 *AI VERIFICATION*\n━━━━━━━━━━━━━━━━━━\n{ai}"
            send_whatsapp(phone, msg2)
    
    time.sleep(2)
    send_main_menu(phone)

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
    send_whatsapp(phone, menu)

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
        "0️⃣ Main Menu"
    )
    send_whatsapp(phone, menu)

def send_dashboard(phone, name, stats):
    dashboard = (
        "📊 *MY DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Farmer:* {name}\n"
        f"📱 *Phone:* {phone}\n\n"
        f"📝 *Total Scans:* {stats['scans']}\n"
        f"🦠 *Common Issue:* {stats['top']}\n"
        f"🌿 *Healthy Leaves:* {stats['healthy']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *View History*\n"
        "2️⃣ *Daily Tip*\n"
        "3️⃣ *Fun Fact*\n\n"
        "0️⃣ Main Menu"
    )
    send_whatsapp(phone, dashboard)

def send_expert_menu(phone):
    menu = (
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *AI Advisor* - Ask anything\n"
        "2️⃣ *Human Expert* - Talk to agronomist\n\n"
        "0️⃣ Main Menu"
    )
    send_whatsapp(phone, menu)

def get_user_history(phone, limit=5):
    if not db: return []
    try:
        docs = db.collection("detections").where("phone", "==", phone).order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("timestamp"):
                ts = data["timestamp"]
                if hasattr(ts, "strftime"):
                    data["date"] = ts.strftime("%d %b %Y")
            history.append(data)
        return history
    except: return []

# ==============================
# MESSAGE HANDLER
# ==============================
def handle_message(phone, type, content):
    debug_log(f"📨 {type} from {phone}")
    
    user = get_user(phone)
    
    # New user
    if not user:
        save_user(phone, {"state": STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, "🌿 *Welcome to Tobacco AI!*\n\nI help tobacco farmers detect diseases and learn best practices.\n\nPlease enter your *name* to continue:")

    state = user.get("state", STATES["ACTIVE"])
    name = user.get("name", "Farmer")

    # Awaiting name
    if state == STATES["AWAITING_NAME"] and type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": STATES["ACTIVE"]})
        welcome = f"✅ *Welcome, {clean_name}!*\n\nWhat would you like to do?\n\n• Send a *photo* to detect diseases\n• Type *menu* for all options"
        return send_whatsapp(phone, welcome)

    # Expert menu
    if state == STATES["EXPERT_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            save_user(phone, {"state": STATES["AWAITING_AI"]})
            return send_whatsapp(phone, "🤖 *AI Advisor*\n\nAsk me anything about tobacco farming.\n\nType your question below (or *cancel* to go back):")
        elif cmd == "2":
            save_user(phone, {"state": STATES["AWAITING_EXPERT"]})
            return send_whatsapp(phone, "👨‍🌾 *Talk to an Agronomist*\n\nDescribe your farming issue. A human expert will respond soon.\n\nType your message (or *cancel* to go back):")
        else:
            return send_whatsapp(phone, "❌ Please choose 1 or 2 (or *0* for Main Menu).")

    # Dashboard menu
    if state == STATES["DASHBOARD_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd == "1":
            history = get_user_history(phone)
            if not history:
                msg = "📋 *No scan history yet.*\n\nSend a photo to start!"
            else:
                msg = "📋 *YOUR SCAN HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, h in enumerate(history[:5], 1):
                    msg += f"{i}. *{h.get('disease', 'Unknown')}* - {h.get('confidence', 0):.1f}%\n"
                    if h.get('date'): msg += f"   📅 {h.get('date')}\n"
            send_whatsapp(phone, msg)
            stats = get_stats(phone)
            return send_dashboard(phone, name, stats)
        elif cmd == "2":
            tip = random.choice(TIPS)
            send_whatsapp(phone, f"💡 *Daily Tip*\n\n{tip}")
            stats = get_stats(phone)
            return send_dashboard(phone, name, stats)
        elif cmd == "3":
            fact = random.choice(FACTS)
            send_whatsapp(phone, f"🎲 *Did You Know?*\n\n{fact}")
            stats = get_stats(phone)
            return send_dashboard(phone, name, stats)
        else:
            return send_whatsapp(phone, "❌ Please choose 1, 2, or 3 (or *0* for Main Menu).")

    # Awaiting AI question
    if state == STATES["AWAITING_AI"] and type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
        # Simple response for now
        send_whatsapp(phone, f"📚 For farming advice, please check the *Farming Practices* menu (option 2).\n\nYou can also type *ai your question* for specific queries.")
        save_user(phone, {"state": STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # Farming menu
    if state == STATES["FARMING_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0":
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        elif cmd in GUIDES:
            send_whatsapp(phone, GUIDES[cmd])
            return send_farming_menu(phone)
        elif cmd == "6":
            save_user(phone, {"state": STATES["AWAITING_AI"]})
            return send_whatsapp(phone, "🤖 *AI Advisor*\n\nAsk me anything about tobacco farming.\n\nType your question below (or *cancel* to go back):")
        else:
            send_whatsapp(phone, "❌ Please choose 1-6 (or *0* for Main Menu).")
            return send_farming_menu(phone)

    # Leaf grading (simplified for now)
    if state == STATES["WAITING_GRADE"] and type == "image":
        send_whatsapp(phone, f"🔍 Analyzing leaf quality, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Failed to download image.")
        else:
            send_whatsapp(phone, "📊 *Leaf Grading*\n\nThis feature is being upgraded. Please use Disease Detection for now.")
        save_user(phone, {"state": STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # DISEASE DETECTION - MAIN FEATURE
    if state == STATES["WAITING_IMAGE"] and type == "image":
        # Cooldown
        now = time.time()
        if phone in LAST_SCAN and now - LAST_SCAN[phone] < COOLDOWN:
            wait = int(COOLDOWN - (now - LAST_SCAN[phone]))
            return send_whatsapp(phone, f"⏱️ Please wait {wait} seconds between scans.")
        LAST_SCAN[phone] = now
        
        send_whatsapp(phone, f"📷 Processing your image, {name}...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Failed to download image. Please try again.")
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Process in background - THIS SENDS TWO MESSAGES (HF first, then AI)
        Thread(target=process_image, args=(phone, name, img), daemon=True).start()
        
        # User will receive:
        # 1. "🔍 Analyzing with AI model..." (from process_image)
        # 2. HF detection result (after ~20s)
        # 3. AI analysis (after ~25s, if confidence < 85%)
        
        save_user(phone, {"state": STATES["ACTIVE"]})
        return

    # Feedback
    if state == STATES["AWAITING_FEEDBACK"] and type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Feedback cancelled.")
        else:
            if ADMIN_PHONE:
                admin_msg = f"📝 *FEEDBACK RECEIVED*\n━━━━━━━━━━━━━━━━━━\n👤 *From:* {name}\n📱 *Phone:* {phone}\n📅 *Date:* {datetime.now().strftime('%d %b %Y %H:%M')}\n\n💬 *Message:*\n{content}"
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "✅ Thank you! Your feedback has been sent to our team.")
        save_user(phone, {"state": STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # Expert request
    if state == STATES["AWAITING_EXPERT"] and type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Expert request cancelled.")
        else:
            if ADMIN_PHONE:
                admin_msg = f"🚨 *EXPERT REQUEST*\n━━━━━━━━━━━━━━━━━━\n👤 *Farmer:* {name}\n📱 *Phone:* {phone}\n📅 *Date:* {datetime.now().strftime('%d %b %Y %H:%M')}\n\n💬 *Issue:*\n{content}"
                send_whatsapp(ADMIN_PHONE, admin_msg)
            send_whatsapp(phone, "👨‍🌾 Your request has been sent. An expert will contact you soon.")
        save_user(phone, {"state": STATES["ACTIVE"]})
        time.sleep(2)
        return send_main_menu(phone)

    # Text commands
    if type == "text":
        cmd = content.lower().strip()
        
        if cmd in ["menu", "0", "main"]:
            return send_main_menu(phone)
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": STATES["WAITING_IMAGE"]})
            send_whatsapp(phone, "📸 *Disease Detection*\n\nSend a clear photo of the tobacco leaf.\n\nTips: Good lighting, close-up, steady camera")
        elif cmd in ["2", "farming"]:
            save_user(phone, {"state": STATES["FARMING_MENU"]})
            return send_farming_menu(phone)
        elif cmd in ["3", "dashboard"]:
            stats = get_stats(phone)
            save_user(phone, {"state": STATES["DASHBOARD_MENU"]})
            return send_dashboard(phone, name, stats)
        elif cmd in ["4", "grade"]:
            save_user(phone, {"state": STATES["WAITING_GRADE"]})
            send_whatsapp(phone, "🏷️ *LEAF QUALITY GRADING*\n\nSend a clear photo of your cured leaf.\n\nTips: Good lighting, flat surface")
        elif cmd in ["5", "expert"]:
            save_user(phone, {"state": STATES["EXPERT_MENU"]})
            return send_expert_menu(phone)
        elif cmd in ["6", "feedback"]:
            save_user(phone, {"state": STATES["AWAITING_FEEDBACK"]})
            send_whatsapp(phone, "📝 *Send Feedback*\n\nType your message below (or *cancel*):")
        elif cmd.startswith("ai "):
            question = cmd[3:].strip()
            if question:
                send_whatsapp(phone, f"🤔 AI Advisor is thinking...")
                send_whatsapp(phone, f"📚 For farming advice, please check the *Farming Practices* menu (option 2).")
                time.sleep(2)
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
            send_whatsapp(phone, "❓ Command not recognized.\n\nType *menu* to see options")

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
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "statuses" in value:
            return jsonify({"status": "ok"}), 200
        
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200
        
        msg = messages[0]
        from_num = msg.get("from")
        msg_type = msg.get("type")
        
        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            content = msg.get("image", {}).get("id", "")
        else:
            return jsonify({"status": "ok"}), 200
        
        handle_message(from_num, msg_type, content)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        debug_log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "firebase": db is not None}), 200

@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting on port {port}")
    debug_log(f"📱 Two-message mode: HF → AI")
    app.run(host="0.0.0.0", port=port, debug=False)
