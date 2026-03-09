"""
Tobacco AI Assistant - Render WhatsApp Bot
Handles all WhatsApp logic, calls Hugging Face for ML detection
"""
import os
import json
import random
import requests
from flask import Flask, request, jsonify
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import gc

# ==============================
# INITIALIZATION
# ==============================
app = Flask(__name__)

# Load environment variables
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://saintsoulider-tobacco-ai.hf.space")  # Your Hugging Face Space URL

def debug_log(message):
    """Print debug with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

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
# CONSTANTS & CONTENT
# ==============================
USER_STATES = {
    "AWAITING_NAME": "awaiting_name",
    "ACTIVE": "active",
    "WAITING_IMAGE": "waiting_image",
    "AWAITING_FEEDBACK": "awaiting_feedback",
    "AWAITING_EXPERT": "awaiting_expert"
}

# Educational Guides
GUIDES = {
    "planting": """🌱 *PLANTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Bed size: 1m wide x 10m long
• Plant population: 15,000 plants/ha
• Spacing: 1.1-1.2m between ridges
• Transplant: 6-8 weeks after sowing
• Water immediately after planting""",

    "fertilizer": """🧪 *FERTILIZER GUIDE*
━━━━━━━━━━━━━━━━━━
• Basal: Compound L (5:14:7) 400-600 kg/ha
• Top dressing 1: Ammonium Nitrate 150-200 kg/ha
• Top dressing 2: Potassium Nitrate 100-150 kg/ha
• Apply when soil is moist
• Never place fertilizer directly under plant""",

    "harvesting": """🌾 *HARVESTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Harvest from bottom upward (priming)
• 2-3 leaves per priming, 4-6 primings total
• Curing phases:
  1. Yellowing: 32-38°C (48 hrs)
  2. Leaf drying: 38-52°C (48 hrs)
  3. Midrib drying: 52-60°C (24 hrs)
  4. Killing out: 60-71°C (6 hrs)""",

    "marketing": """💰 *MARKETING 2026*
━━━━━━━━━━━━━━━━━━
• Opening: March 2026
• Biometric ID REQUIRED
• Register before February 2026
• Grades: A (Premium), B (Good), C (Fair), D (Low)
• Payment within 24 hours"""
}

# Daily Tips
TIPS = [
    "🚜 Rotate tobacco with maize or beans to prevent soil-borne diseases",
    "💧 Water in the morning to reduce humidity and prevent fungal growth",
    "🔍 Check fields weekly for early signs of disease",
    "🌱 Transplant seedlings in the evening to reduce shock",
    "🧪 Test soil before applying fertilizer",
    "🌿 Remove sucker growth weekly",
    "☀️ Harvest leaves when dry to prevent rot",
    "📊 Keep records of disease outbreaks",
    "🧤 Wash hands after handling infected plants"
]

# Fun Facts
FACTS = [
    "🌱 Tobacco is related to tomatoes and potatoes!",
    "🍃 Zimbabwe produces world-class flue-cured tobacco",
    "📜 Tobacco has been cultivated for over 8,000 years",
    "🌿 One plant can produce up to 30 leaves",
    "🌍 Tobacco is grown in over 100 countries"
]

# Confidence threshold (used for messaging)
CONFIDENCE_THRESHOLD = 25.0

# ==============================
# HELPER FUNCTIONS
# ==============================
def send_whatsapp(to, text):
    """Send WhatsApp message"""
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

def download_image(media_id):
    """Download image from WhatsApp"""
    try:
        debug_log(f"📥 Downloading media ID: {media_id}")
        
        # Get media URL
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
        debug_log(f"✅ Got media URL: {media_url[:50]}...")
        
        if not media_url:
            return None
        
        # Download image
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
    """
    Call Hugging Face Space for ML detection
    Uses the /predict endpoint with image upload
    """
    try:
        debug_log("🔄 Calling Hugging Face ML service...")
        
        # Prepare the image for upload
        files = {
            'file': ('image.jpg', image_bytes, 'image/jpeg')
        }
        
        # Make request to Hugging Face Space
        response = requests.post(
            f"{HF_SPACE_URL}/predict",
            files=files,
            timeout=30  # 30 second timeout (HF takes ~13s)
        )
        
        if response.status_code == 200:
            result = response.json()
            debug_log(f"✅ HF Response: {result}")
            
            if result.get("success"):
                return {
                    "disease": result.get("disease"),
                    "confidence": result.get("confidence"),
                    "treatment": result.get("treatment"),
                    "is_healthy": result.get("is_healthy", False),
                    "low_confidence": result.get("low_confidence", False)
                }
            else:
                debug_log(f"❌ HF returned error: {result.get('error')}")
                return None
        else:
            debug_log(f"❌ HF HTTP error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        debug_log("❌ HF request timed out (30s)")
        return None
    except Exception as e:
        debug_log(f"❌ HF call error: {e}")
        return None

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
# MESSAGE HANDLER
# ==============================
def handle_message(phone, msg_type, content):
    """Main message handler"""
    debug_log(f"📨 Handling message: type={msg_type}, phone={phone}")
    
    user = get_user(phone)
    nav = "\n\n---\n0️⃣ Menu"
    
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
        return send_whatsapp(phone, 
            f"✅ *Welcome, {clean_name}!*\n\n"
            f"What would you like to do?\n\n"
            f"• Send a *photo* to detect diseases\n"
            f"• Type *menu* for all options")

    # WAITING FOR IMAGE
    if state == USER_STATES["WAITING_IMAGE"] and msg_type == "image":
        debug_log(f"📸 Processing image from {phone}")
        send_whatsapp(phone, f"🔍 Downloading your image, {name}...")
        
        image_bytes = download_image(content)
        if not image_bytes:
            debug_log("❌ Download failed")
            send_whatsapp(phone, "❌ Failed to download image. Please try again." + nav)
            save_user(phone, {"state": USER_STATES["ACTIVE"]})
            return
        
        debug_log(f"✅ Downloaded {len(image_bytes)} bytes")
        send_whatsapp(phone, f"✅ Image downloaded! Running AI analysis on cloud...")
        
        # Call Hugging Face for detection instead of local model
        result = call_huggingface_detection(image_bytes)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        
        if not result:
            debug_log("❌ Detection failed")
            send_whatsapp(phone, "❌ AI analysis failed. Please try another photo with good lighting." + nav)
            return
        
        disease = result["disease"]
        confidence = result["confidence"]
        
        debug_log(f"✅ Detection result: {disease} ({confidence:.1f}%)")
        log_detection(phone, name, disease, confidence)
        
        # Format response based on detection result
        if result["low_confidence"]:
            send_whatsapp(phone, 
                f"⚠️ *Low Confidence ({confidence:.1f}%)*\n\n"
                f"Please upload a clearer, closer photo of the tobacco leaf with good lighting.\n\n"
                f"Tips:\n"
                f"• Hold camera steady\n"
                f"• Show affected area clearly\n"
                f"• Use natural light" + nav)
        
        elif result["is_healthy"]:
            send_whatsapp(phone, 
                f"🎉 *Healthy Leaf Detected!*\n\n"
                f"Confidence: {confidence:.1f}%\n\n"
                f"Great job! Keep up your good farming practices:\n"
                f"• Continue regular monitoring\n"
                f"• Maintain field hygiene\n"
                f"• Follow your fertilization schedule" + nav)
        
        else:
            send_whatsapp(phone, 
                f"📊 *DISEASE DETECTED*\n\n"
                f"*Disease:* {disease}\n"
                f"*Confidence:* {confidence:.1f}%\n\n"
                f"*Recommended Treatment:*\n{result['treatment']}" + nav)
        return

    # AWAITING FEEDBACK
    if state == USER_STATES["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Feedback cancelled." + nav)
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"📝 *Feedback from {name}*\n{phone}\n\n{content}")
            send_whatsapp(phone, "✅ Thank you! Your feedback has been sent." + nav)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return

    # AWAITING EXPERT
    if state == USER_STATES["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() == "cancel":
            send_whatsapp(phone, "Expert request cancelled." + nav)
        else:
            if ADMIN_PHONE:
                send_whatsapp(ADMIN_PHONE, f"🚨 *EXPERT REQUEST from {name}*\n{phone}\n\n{content}")
            send_whatsapp(phone, "👨‍🌾 Your request has been sent to an agronomist. They will contact you soon." + nav)
        save_user(phone, {"state": USER_STATES["ACTIVE"]})
        return

    # MAIN MENU COMMANDS (ACTIVE state)
    if msg_type == "text":
        cmd = content.lower().strip()
        
        if cmd in ["menu", "0"]:
            menu = (
                "🌿 *MAIN MENU*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ *Disease Detection* - Send photo\n"
                "2️⃣ *Planting Guide* - Nursery to field\n"
                "3️⃣ *Fertilizer Guide* - Application rates\n"
                "4️⃣ *Harvesting Guide* - Priming & curing\n"
                "5️⃣ *Marketing Guide* - Selling tips\n"
                "6️⃣ *Scan History* - Past diagnoses\n"
                "7️⃣ *Daily Tip* - Farming advice\n"
                "8️⃣ *Fun Fact* - Did you know?\n"
                "9️⃣ *Feedback* - Send comments\n"
                "🔟 *Talk to Expert* - Ask agronomist\n\n"
                "Reply with the number (e.g., *1*)"
            )
            send_whatsapp(phone, menu)
        
        elif cmd in ["1", "detect"]:
            save_user(phone, {"state": USER_STATES["WAITING_IMAGE"]})
            send_whatsapp(phone, 
                "📸 *Disease Detection*\n\n"
                "Please send a clear photo of the tobacco leaf.\n\n"
                "📝 *Tips for best results:*\n"
                "• Good lighting (natural light)\n"
                "• Close-up of affected area\n"
                "• Hold camera steady\n"
                "• Plain background")
        
        elif cmd in ["2", "planting"]:
            send_whatsapp(phone, GUIDES["planting"] + nav)
        
        elif cmd in ["3", "fertilizer"]:
            send_whatsapp(phone, GUIDES["fertilizer"] + nav)
        
        elif cmd in ["4", "harvesting"]:
            send_whatsapp(phone, GUIDES["harvesting"] + nav)
        
        elif cmd in ["5", "marketing"]:
            send_whatsapp(phone, GUIDES["marketing"] + nav)
        
        elif cmd in ["6", "history"]:
            history = get_user_history(phone)
            if not history:
                send_whatsapp(phone, "📋 *No scan history yet.*\n\nSend a photo to start detecting diseases!" + nav)
            else:
                msg = "📋 *YOUR SCAN HISTORY*\n━━━━━━━━━━━━━━━━━━\n"
                for i, h in enumerate(history[:5], 1):
                    msg += f"{i}. *{h.get('disease', 'Unknown')}* - {h.get('confidence', 0):.1f}%\n"
                    msg += f"   📅 {h.get('date', 'Unknown')}\n\n"
                msg += nav
                send_whatsapp(phone, msg)
        
        elif cmd in ["7", "tip"]:
            send_whatsapp(phone, f"💡 *Daily Tip*\n\n{random.choice(TIPS)}" + nav)
        
        elif cmd in ["8", "fact"]:
            send_whatsapp(phone, f"🎲 *Fun Fact*\n\n{random.choice(FACTS)}" + nav)
        
        elif cmd in ["9", "feedback"]:
            save_user(phone, {"state": USER_STATES["AWAITING_FEEDBACK"]})
            send_whatsapp(phone, 
                "📝 *Send Feedback*\n\n"
                "Type your message below (or *cancel* to go back):")
        
        elif cmd in ["10", "expert"]:
            save_user(phone, {"state": USER_STATES["AWAITING_EXPERT"]})
            send_whatsapp(phone, 
                "👨‍🌾 *Talk to an Expert*\n\n"
                "Describe your farming issue below. An agronomist will contact you soon.\n\n"
                "(Type *cancel* to go back)")
        
        elif cmd == "help":
            send_whatsapp(phone, 
                "📚 *HELP*\n━━━━━━━━━━━━━━━━━━\n"
                "• *menu* - Show main menu\n"
                "• *detect* - Start detection\n"
                "• *history* - View past scans\n"
                "• *tip* - Daily farming tip\n"
                "• *fact* - Fun fact\n"
                "• *feedback* - Send comments\n"
                "• *expert* - Talk to agronomist\n"
                "• *help* - Show this message")
        
        else:
            send_whatsapp(phone, 
                "❓ Command not recognized.\n\n"
                "Type *menu* to see all options or *help* for commands.")

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Main webhook endpoint"""
    # Webhook verification
    if request.method == "GET":
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if verify_token == VERIFY_TOKEN:
            debug_log("✅ Webhook verified")
            return challenge, 200
        debug_log("❌ Webhook verification failed")
        return "Forbidden", 403
    
    # Handle incoming messages
    try:
        data = request.json
        
        # Extract message data safely
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        # Ignore status updates
        if "statuses" in value:
            return jsonify({"status": "ignored"}), 200
        
        # Get messages
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200
        
        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")
        
        # Extract content based on type
        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            content = msg.get("image", {}).get("id", "")
        else:
            return jsonify({"status": "ignored"}), 200
        
        # Process message
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
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    """Root endpoint"""
    return "🌿 Tobacco AI Assistant is running! (Using Hugging Face for ML)"

# ==============================
# START THE APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_log(f"🚀 Starting Tobacco AI Assistant on port {port}")
    debug_log(f"🤖 Using Hugging Face Space: {HF_SPACE_URL}")
    app.run(host="0.0.0.0", port=port, debug=False)
