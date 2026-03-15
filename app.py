"""
Tobacco AI Assistant - Simplified Two-Message Version
"""
import os
import json
import requests
import time
import base64
import io
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

# Disease advice
DISEASE_ADVICE = {
    "Black Shank": "💧 Improve drainage, remove infected plants, apply Ridomil",
    "Black Spot": "🔴 Apply copper fungicide, remove infected leaves",
    "Early Blight": "🍂 Apply Mancozeb, remove lower leaves, rotate crops",
    "Late Blight": "🌧️ Remove plants immediately, apply Ridomil Gold",
    "Tobacco Mosaic Virus": "⚠️ NO CURE - remove infected plants, wash hands",
    "Healthy": "🌿 Great job! Continue good practices"
}

# Firebase
db = None
if FIREBASE_CONFIG:
    try:
        cred = credentials.Certificate(json.loads(FIREBASE_CONFIG))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        debug_log("✅ Firebase connected")
    except: pass

# User states
STATES = {
    "AWAITING_NAME": "awaiting_name", "ACTIVE": "active", "WAITING_IMAGE": "waiting_image",
    "AWAITING_FEEDBACK": "awaiting_feedback", "AWAITING_EXPERT": "awaiting_expert",
    "AWAITING_AI": "awaiting_ai_question", "FARMING_MENU": "farming_menu",
    "WAITING_GRADE": "waiting_grade_image", "EXPERT_MENU": "expert_menu",
    "DASHBOARD_MENU": "dashboard_menu"
}

# Guides
GUIDES = {
    "1": "🌱 *PLANTING*\n• Spacing: 1.1-1.2m\n• Population: 15,000 plants/ha\n• Transplant: 6-8 weeks",
    "2": "🧪 *FERTILIZER*\n• Basal: Compound L 400-600 kg/ha\n• Top dress: Ammonium Nitrate 150-200 kg/ha",
    "3": "🌾 *HARVEST*\n• Harvest bottom up\n• 2-3 leaves per harvest\n• Priming 2-3 = Best quality",
    "4": "🔥 *CURING*\n• Yellowing: 32-38°C, 48hrs\n• Leaf drying: 38-52°C\n• Killing out: 60-71°C",
    "5": f"💰 *MARKETING {datetime.now().year}*\n• Opens: March {datetime.now().year}\n• Biometric ID required"
}

# Helpers
def send_whatsapp(to, text):
    if not text: return False
    try:
        r = session.post(f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
                        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
                        json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}},
                        timeout=15)
        debug_log(f"📤 Sent: {r.status_code}")
        return True
    except: return False

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

def log_detection(phone, name, disease, confidence):
    if not db: return
    try:
        db.collection("detections").add({"phone": phone, "name": name, "disease": disease, 
                                         "confidence": confidence, "timestamp": firestore.SERVER_TIMESTAMP})
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

# Detection functions
def detect_hf(image_bytes):
    try:
        debug_log("🔍 HF detection...")
        r = session.post(f"{HF_SPACE_URL}/predict", files={'file': ('image.jpg', image_bytes, 'image/jpeg')}, timeout=30)
        if r.status_code == 200:
            res = r.json()
            if res.get("success"):
                return {
                    "disease": res.get("disease", "Unknown"),
                    "confidence": res.get("confidence", 0),
                    "treatment": res.get("treatment", ""),
                    "is_healthy": res.get("is_healthy", False),
                    "low_confidence": res.get("low_confidence", False)
                }
    except: pass
    return None

def analyze_ai(image_bytes):
    if not AI_API_KEY: return None
    for model in ['models/gemini-2.5-flash', 'models/gemini-1.5-flash']:
        try:
            m = genai.GenerativeModel(model, generation_config=vision_config, safety_settings=safety)
            img_data = base64.b64encode(image_bytes).decode('utf-8')
            prompt = "Analyze this tobacco leaf. Give: 1) Symptoms (2-3) 2) Possible disease 3) One short advice. Keep it brief."
            resp = m.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_data}])
            if resp and resp.text: return resp.text.strip()
        except: continue
    return None

# Background processor - sends TWO messages
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
    
    if hf["low_confidence"] or conf < 50:
        msg1 = f"❓ *UNCLEAR DETECTION*\n⚠️ Confidence: {conf:.0f}%\n\n📸 Please send a clearer photo."
    elif hf["is_healthy"]:
        msg1 = f"🌿 *HEALTHY LEAF*\n✅ Confidence: {conf:.0f}%\n\n💚 Your plant looks healthy!"
    else:
        advice = DISEASE_ADVICE.get(disease, "Monitor closely")
        msg1 = f"🌿 *{disease}*\n📊 Confidence: {conf:.0f}%\n\n💡 *Advice:* {advice}"
    
    send_whatsapp(phone, msg1)
    log_detection(phone, name, disease, conf)
    
    # Step 2: AI Analysis (if confidence < 85% and not healthy)
    if conf < 85 and not hf["is_healthy"]:
        debug_log(f"🤖 AI for {phone}")
        send_whatsapp(phone, f"🔬 AI analyzing symptoms...")
        ai = analyze_ai(img_bytes)
        if ai:
            send_whatsapp(phone, f"🔬 *AI ANALYSIS*\n{ai}")
    
    time.sleep(2)
    send_main_menu(phone)

# Menu functions
def send_main_menu(phone):
    send_whatsapp(phone, 
        "🌿 *TOBACCO AI MAIN MENU*\n━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Disease Detection* - Send photo\n"
        "2️⃣ *Farming Practices* - Guides & AI advice\n"
        "3️⃣ *My Dashboard* - Stats & Tips\n"
        "4️⃣ *Leaf Grading* - Quality assessment\n"
        "5️⃣ *Expert Help* - Agronomist & AI\n"
        "6️⃣ *Feedback* - Send comments\n\n"
        "Reply with number (e.g., *1*)")

def send_farming_menu(phone):
    send_whatsapp(phone,
        "🌱 *FARMING PRACTICES*\n━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ Planting Guide\n2️⃣ Fertilizer Guide\n3️⃣ Harvesting Guide\n"
        "4️⃣ Curing Guide\n5️⃣ Marketing Guide\n6️⃣ Ask AI\n\n0️⃣ Main Menu")

def send_dashboard(phone, name, stats):
    send_whatsapp(phone,
        f"📊 *{name}'s DASHBOARD*\n━━━━━━━━━━━━━━━━━━\n"
        f"📝 Scans: {stats['scans']}\n🦠 Common: {stats['top']}\n🌿 Healthy: {stats['healthy']}\n"
        f"━━━━━━━━━━━━━━━━━━\n1️⃣ History\n2️⃣ Daily Tip\n3️⃣ Fun Fact\n\n0️⃣ Main Menu")

def send_expert_menu(phone):
    send_whatsapp(phone,
        "👨‍🌾 *EXPERT HELP*\n━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ AI Advisor\n2️⃣ Human Expert\n\n0️⃣ Main Menu")

# Message handler
def handle_message(phone, type, content):
    debug_log(f"📨 {type} from {phone}")
    
    user = get_user(phone)
    
    # New user
    if not user:
        save_user(phone, {"state": STATES["AWAITING_NAME"], "phone": phone})
        return send_whatsapp(phone, "🌿 Welcome! Please enter your *name*:")

    state = user.get("state", STATES["ACTIVE"])
    name = user.get("name", "Farmer")

    # Awaiting name
    if state == STATES["AWAITING_NAME"] and type == "text":
        save_user(phone, {"name": content.strip().title(), "state": STATES["ACTIVE"]})
        return send_whatsapp(phone, f"✅ Hi {content.strip().title()}! Send photo or type *menu*")

    # Menu handlers
    if state == STATES["EXPERT_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0": save_user(phone, {"state": STATES["ACTIVE"]}); return send_main_menu(phone)
        elif cmd == "1": save_user(phone, {"state": STATES["AWAITING_AI"]}); return send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        elif cmd == "2": save_user(phone, {"state": STATES["AWAITING_EXPERT"]}); return send_whatsapp(phone, "👨‍🌾 Describe issue (or *cancel*):")
        else: return send_whatsapp(phone, "❌ Choose 1, 2, or 0")

    if state == STATES["DASHBOARD_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0": save_user(phone, {"state": STATES["ACTIVE"]}); return send_main_menu(phone)
        elif cmd == "1": send_whatsapp(phone, "📋 History feature coming soon!")
        elif cmd == "2": send_whatsapp(phone, f"💡 *Tip*\n{random.choice(['🚜 Rotate crops', '💧 Water early morning', '🔍 Check fields weekly'])}")
        elif cmd == "3": send_whatsapp(phone, f"🎲 *Fact*\n{random.choice(['🌍 Exports to 50+ countries', '👨‍🌾 Supports 500k families', '💰 2nd largest forex earner'])}")
        else: return send_whatsapp(phone, "❌ Choose 1-3 or 0")
        stats = get_stats(phone)
        return send_dashboard(phone, name, stats)

    if state == STATES["AWAITING_AI"] and type == "text":
        if content.lower() == "cancel": save_user(phone, {"state": STATES["ACTIVE"]}); return send_main_menu(phone)
        send_whatsapp(phone, f"🤔 Thinking...")
        send_whatsapp(phone, f"AI advisor coming soon!")
        save_user(phone, {"state": STATES["ACTIVE"]})
        return send_main_menu(phone)

    if state == STATES["FARMING_MENU"] and type == "text":
        cmd = content.lower().strip()
        if cmd == "0": save_user(phone, {"state": STATES["ACTIVE"]}); return send_main_menu(phone)
        elif cmd in GUIDES: send_whatsapp(phone, GUIDES[cmd]); return send_farming_menu(phone)
        elif cmd == "6": save_user(phone, {"state": STATES["AWAITING_AI"]}); return send_whatsapp(phone, "🤖 Ask your question (or *cancel*):")
        else: return send_farming_menu(phone)

    if state == STATES["WAITING_GRADE"] and type == "image":
        send_whatsapp(phone, f"🔍 Analyzing...")
        img = download_image(content)
        if not img: send_whatsapp(phone, "❌ Download failed")
        else: send_whatsapp(phone, "📊 Grading coming soon!")
        save_user(phone, {"state": STATES["ACTIVE"]})
        time.sleep(1)
        return send_main_menu(phone)

    # Disease detection - main feature
    if state == STATES["WAITING_IMAGE"] and type == "image":
        # Cooldown
        now = time.time()
        if phone in LAST_SCAN and now - LAST_SCAN[phone] < COOLDOWN:
            wait = int(COOLDOWN - (now - LAST_SCAN[phone]))
            return send_whatsapp(phone, f"⏱️ Please wait {wait}s")
        LAST_SCAN[phone] = now
        
        send_whatsapp(phone, f"📷 Processing...")
        img = download_image(content)
        if not img:
            send_whatsapp(phone, "❌ Download failed")
            save_user(phone, {"state": STATES["ACTIVE"]})
            return send_main_menu(phone)
        
        # Process in background
        Thread(target=process_image, args=(phone, name, img), daemon=True).start()
        save_user(phone, {"state": STATES["ACTIVE"]})
        return

    # Feedback
    if state == STATES["AWAITING_FEEDBACK"] and type == "text":
        if content.lower() == "cancel": send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE: send_whatsapp(ADMIN_PHONE, f"📝 *Feedback* {phone}\n{content}")
            send_whatsapp(phone, "✅ Thanks!")
        save_user(phone, {"state": STATES["ACTIVE"]})
        return send_main_menu(phone)

    # Expert request
    if state == STATES["AWAITING_EXPERT"] and type == "text":
        if content.lower() == "cancel": send_whatsapp(phone, "Cancelled")
        else:
            if ADMIN_PHONE: send_whatsapp(ADMIN_PHONE, f"🚨 *Expert* {phone}\n{content}")
            send_whatsapp(phone, "✅ Expert will respond")
        save_user(phone, {"state": STATES["ACTIVE"]})
        return send_main_menu(phone)

    # Text commands
    if type == "text":
        cmd = content.lower().strip()
        if cmd in ["menu", "0"]: return send_main_menu(phone)
        elif cmd == "1": save_user(phone, {"state": STATES["WAITING_IMAGE"]}); send_whatsapp(phone, "📸 Send clear photo of leaf")
        elif cmd == "2": save_user(phone, {"state": STATES["FARMING_MENU"]}); return send_farming_menu(phone)
        elif cmd == "3": stats = get_stats(phone); save_user(phone, {"state": STATES["DASHBOARD_MENU"]}); return send_dashboard(phone, name, stats)
        elif cmd == "4": save_user(phone, {"state": STATES["WAITING_GRADE"]}); send_whatsapp(phone, "🏷️ Send photo of cured leaf")
        elif cmd == "5": save_user(phone, {"state": STATES["EXPERT_MENU"]}); return send_expert_menu(phone)
        elif cmd == "6": save_user(phone, {"state": STATES["AWAITING_FEEDBACK"]}); send_whatsapp(phone, "📝 Type feedback (or *cancel*):")
        elif cmd.startswith("ai "):
            q = cmd[3:].strip()
            if q: send_whatsapp(phone, f"🤔 Thinking..."); send_whatsapp(phone, f"AI advisor coming soon!"); time.sleep(1); return send_main_menu(phone)
        elif cmd == "help": send_whatsapp(phone, "📚 Commands: menu, 1-6, ai [question]")
        else: send_whatsapp(phone, "Type *menu* for options")

# Flask routes
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403
    
    try:
        data = request.json
        msg = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0]
        if not msg: return jsonify({"status": "ok"}), 200
        
        from_num = msg.get("from")
        msg_type = msg.get("type")
        
        if msg_type == "text": content = msg.get("text", {}).get("body", "")
        elif msg_type == "image": content = msg.get("image", {}).get("id", "")
        else: return jsonify({"status": "ok"}), 200
        
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
