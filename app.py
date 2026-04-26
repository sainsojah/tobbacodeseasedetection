"""
╔══════════════════════════════════════════════════════════════════╗
║           🌿 TOBACCO AI ASSISTANT — WhatsApp Bot                 ║
║                                                                  ║
║  Features:                                                       ║
║   • Option 1: ML Services (Hugging Face) — Disease & Curing      ║
║   • Option 5: AI Vision (Gemini)  — Disease & Curing             ║
║   • Payments: EcoCash USD & InnBucks USD (PayNow)                ║
║   • Firebase Firestore for user state & detection history        ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────
#  Standard library
# ─────────────────────────────────────────────
import os
import gc
import re
import json
import time
import base64
import random
import threading
from datetime import datetime

# ─────────────────────────────────────────────
#  Third-party
# ─────────────────────────────────────────────
import requests
from flask import Flask, request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# ─────────────────────────────────────────────
#  Optional: Paynow
# ─────────────────────────────────────────────
try:
    from paynow import Paynow
    PAYNOW_AVAILABLE = True
except ImportError:
    PAYNOW_AVAILABLE = False
    print("⚠️  Paynow library not installed. Payments will be disabled.")


# ══════════════════════════════════════════════
#  APP & LOGGING
# ══════════════════════════════════════════════

app = Flask(__name__)


def log(msg: str) -> None:
    """Timestamped console log."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ══════════════════════════════════════════════
#  ENVIRONMENT VARIABLES
# ══════════════════════════════════════════════

WHATSAPP_TOKEN      = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID     = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN        = os.environ.get("VERIFY_TOKEN")
FIREBASE_CONFIG     = os.environ.get("FIREBASE_CONFIG")
ADMIN_PHONE         = os.environ.get("ADMIN_PHONE_NUMBER")
HF_SPACE_URL        = os.environ.get("HF_SPACE_URL")        # Hugging Face Space URL
AI_API_KEY          = os.environ.get("AI_API_KEY")          # Gemini API key

# PayNow (USD only)
PAYNOW_USD_API_KEY      = os.environ.get("PAYNOW_USD_API_KEY")
PAYNOW_USD_MERCHANT_ID  = os.environ.get("PAYNOW_USD_MERCHANT_ID")
RESULT_URL              = os.environ.get("RESULT_URL")

MIN_AMOUNT_USD = 0.50


# ══════════════════════════════════════════════
#  USER STATE CONSTANTS
# ══════════════════════════════════════════════

STATE = {
    # Onboarding
    "AWAITING_NAME":            "awaiting_name",
    "ACTIVE":                   "active",

    # Image analysis
    "WAITING_IMAGE":            "waiting_image",
    "WAITING_ML_CURING":        "waiting_ml_curing",
    "WAITING_GRADE_IMAGE":      "waiting_grade_image",
    "WAITING_AI_VISION":        "waiting_ai_vision",
    "WAITING_AI_VISION_DISEASE":"waiting_ai_vision_disease",
    "WAITING_AI_VISION_CURING": "waiting_ai_vision_curing",

    # Menus
    "ML_MENU":          "ml_menu",
    "FARMING_MENU":     "farming_menu",
    "DASHBOARD_MENU":   "dashboard_menu",
    "EXPERT_MENU":      "expert_menu",
    "PAYMENT_MENU":     "payment_menu",

    # Payment steps
    "PAYMENT_AMOUNT":           "payment_amount",
    "PAYMENT_MOBILE_NUMBER":    "payment_mobile_number",
    "PAYMENT_OTP_CONFIRM":      "payment_otp_confirm",   # NEW: wait for user to confirm PIN
    "PAYMENT_INNBUCKS_CODE":    "payment_innbucks_code",

    # Text flows
    "AWAITING_FEEDBACK":        "awaiting_feedback",
    "AWAITING_EXPERT":          "awaiting_expert",
    "AWAITING_AI_QUESTION":     "awaiting_ai_question",
}

# Payment method metadata
PAYMENT_METHODS = {
    "1": {
        "name":    "EcoCash USD",
        "method":  "ecocash",
        "display": "EcoCash",
        "currency":"USD",
    },
    "2": {
        "name":    "InnBucks USD",
        "method":  "innbucks",
        "display": "InnBucks",
        "currency":"USD",
    },
}

# In-memory stores
PAYMENT_QUEUE      : dict = {}
PROCESSED_PAYMENTS : set  = set()
SENT_MESSAGES      : set  = set()
LAST_SCAN          : dict = {}

PAYMENT_TIMEOUT_MINUTES = 10


# ══════════════════════════════════════════════
#  SERVICE INITIALISATION
# ══════════════════════════════════════════════

# ── HTTP session with retries ──────────────────
def _build_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, backoff_factor=1,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=5)
    session.mount("https://", adapter)
    return session

http_session = _build_http_session()


# ── Firebase ───────────────────────────────────
db = None
if FIREBASE_CONFIG:
    try:
        cred = credentials.Certificate(json.loads(FIREBASE_CONFIG))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        log("✅ Firebase connected")
    except Exception as e:
        log(f"❌ Firebase error: {e}")


# ── Google Generative AI (Gemini) ──────────────
GEMINI_MODELS = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-pro-latest",
]

if AI_API_KEY and AI_API_KEY != "your_api_key_here":
    genai.configure(api_key=AI_API_KEY)
    log("✅ Gemini AI configured")

GENERATION_CONFIG = {"temperature": 0.7, "top_p": 0.8, "top_k": 10, "max_output_tokens": 1000}
VISION_CONFIG     = {"temperature": 0.7, "max_output_tokens": 800, "top_p": 0.8}
TIP_CONFIG        = {"temperature": 0.8, "max_output_tokens": 600}
FACT_CONFIG       = {"temperature": 0.9, "max_output_tokens": 600}
SAFETY_SETTINGS   = [
    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]


# ══════════════════════════════════════════════
#  STATIC KNOWLEDGE BASE
# ══════════════════════════════════════════════

DISEASE_KB = {
    "Black Shank":          {"cause": "Phytophthora fungus",     "treatment": "Remove plants, apply Ridomil",        "prevention": "Crop rotation"},
    "Black Spot":           {"cause": "Cercospora nicotianae",   "treatment": "Copper fungicides",                   "prevention": "Air circulation"},
    "Early Blight":         {"cause": "Alternaria fungus",       "treatment": "Mancozeb",                            "prevention": "Crop rotation"},
    "Late Blight":          {"cause": "Phytophthora infestans",  "treatment": "Remove plants, apply Ridomil Gold",   "prevention": "Avoid moisture"},
    "Tobacco Mosaic Virus": {"cause": "TMV virus",               "treatment": "NO CURE — remove plants immediately", "prevention": "Wash hands before handling"},
    "Spider Mites":         {"cause": "Tiny arachnids",          "treatment": "Miticides",                           "prevention": "Maintain humidity"},
}

PLANTING_GUIDE = """🌱 *PLANTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Bed size: 1 m wide x 10 m long
• Plant population: 15,000 plants/ha
• Spacing: 1.1-1.2 m between ridges
• Transplant: 6-8 weeks after sowing
• Water immediately after planting"""

FERTILIZER_GUIDE = """🧪 *FERTILIZER GUIDE*
━━━━━━━━━━━━━━━━━━
• Basal: Compound L (5:14:7) 400-600 kg/ha
• Top dress 1: Ammonium Nitrate 150-200 kg/ha
• Top dress 2: Potassium Nitrate 100-150 kg/ha
• Apply when soil is moist
• Target soil pH: 5.5-6.5"""

HARVESTING_GUIDE = """🌾 *HARVESTING GUIDE*
━━━━━━━━━━━━━━━━━━
• Harvest bottom-up (priming method)
• 2-3 leaves per harvest; 4-6 primings total
• Priming 1 (Sand leaves): 60-65 days
• Primings 2-3 (Cutters): Best quality
• Priming 6 (Tips): Highest nicotine content"""

CURING_GUIDE = """🔥 *CURING GUIDE*
━━━━━━━━━━━━━━━━━━
• Yellowing:     32-38C | 48 hrs | 85-90% RH
• Leaf drying:   38-52C | 48 hrs | 70-80% RH
• Midrib drying: 52-60C | 24 hrs | 50-60% RH
• Killing out:   60-71C |  6 hrs | 30-40% RH"""

MARKETING_GUIDE = f"""💰 *MARKETING {datetime.now().year}*
━━━━━━━━━━━━━━━━━━
• Opening: March {datetime.now().year}
• Biometric ID REQUIRED
• Grades: A (Premium) B (Good) C (Fair) D (Low)
• Payment within 24 hours"""


# ══════════════════════════════════════════════
#  UTILITY HELPERS
# ══════════════════════════════════════════════

def trim(text: str, limit: int = 3000) -> str:
    if not text:
        return "No response available."
    return text[:limit - 3] + "..." if len(text) > limit else text


def format_phone(phone: str) -> str:
    """Normalise a Zimbabwe phone number to 263XXXXXXXXX format."""
    phone = re.sub(r"[^0-9+]", "", phone).lstrip("+")
    if phone.startswith("0"):
        phone = "263" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "263" + phone
    elif not phone.startswith("263"):
        phone = "263" + phone
    return phone


def confidence_label(conf: float) -> str:
    if conf > 85: return "✔ *High Accuracy*"
    if conf > 60: return "⚠ *Medium Accuracy*"
    if conf > 10: return "❗ *Low Accuracy — please retake photo*"
    return "✔ Healthy"


def offline_disease_advice(disease: str) -> str:
    info = DISEASE_KB.get(disease)
    if info:
        return (
            f"📚 *{disease} — Quick Reference*\n\n"
            f"🔍 *Cause:* {info['cause']}\n"
            f"💊 *Treatment:* {info['treatment']}\n"
            f"🛡 *Prevention:* {info['prevention']}"
        )
    return f"ℹ️ For advice on {disease}, type *ai your question*"


# ══════════════════════════════════════════════
#  WHATSAPP MESSAGING
# ══════════════════════════════════════════════

def _send_whatsapp(to: str, text: str) -> bool:
    if not text:
        text = "Processing..."
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=35)
        log(f"📤 WhatsApp -> {to}: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"❌ WhatsApp send error: {e}")
        return False


def send_msg(phone: str, text: str, retries: int = 3) -> bool:
    for _ in range(retries):
        if _send_whatsapp(phone, text):
            return True
        time.sleep(1)
    return False


def send_once(phone: str, text: str) -> None:
    """Deduplicated send — skips identical recent messages."""
    key = f"{phone}:{hash(text)}"
    if key in SENT_MESSAGES:
        log(f"⏭️ Duplicate skipped: {text[:30]}...")
        return
    SENT_MESSAGES.add(key)
    send_msg(phone, text)


# ══════════════════════════════════════════════
#  FIREBASE HELPERS
# ══════════════════════════════════════════════

def get_user(phone: str):
    if not db:
        return None
    try:
        doc = db.collection("users").document(phone).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        log(f"❌ Firebase get error: {e}")
        return None


def save_user(phone: str, data: dict) -> bool:
    if not db:
        return False
    try:
        db.collection("users").document(phone).set(data, merge=True)
        return True
    except Exception as e:
        log(f"❌ Firebase save error: {e}")
        return False


def log_detection(phone: str, name: str, **kwargs) -> None:
    if not db:
        return
    try:
        record = {"phone": phone, "name": name, "timestamp": firestore.SERVER_TIMESTAMP}
        record.update(kwargs)
        db.collection("detections").add(record)
    except Exception as e:
        log(f"❌ Firestore log error: {e}")


def get_user_history(phone: str, limit: int = 10) -> list:
    if not db:
        return []
    try:
        docs = (
            db.collection("detections")
            .where("phone", "==", phone)
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        history = []
        for doc in docs:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts and hasattr(ts, "strftime"):
                data["date"] = ts.strftime("%d %b %Y")
            history.append(data)
        return history
    except Exception as e:
        log(f"❌ History error: {e}")
        return []


def get_user_stats(phone: str) -> dict:
    defaults = {"total_scans": 0, "hf_scans": 0, "ai_vision_scans": 0,
                "curing_scans": 0, "top_disease": "None", "healthy_count": 0}
    if not db:
        return defaults
    try:
        docs = db.collection("detections").where("phone", "==", phone).stream()
        total = hf = ai = curing = healthy = 0
        diseases: dict = {}
        for doc in docs:
            d = doc.to_dict()
            total += 1
            dtype = d.get("detection_type", "")
            if dtype == "hf_disease":                        hf += 1
            elif dtype == "ai_vision_disease":               ai += 1
            elif dtype in ("ai_vision_curing", "hf_curing"): curing += 1
            disease = d.get("disease", "")
            if dtype not in ("hf_curing", "ai_vision_curing"):
                if "healthy" in disease.lower(): healthy += 1
                elif disease: diseases[disease] = diseases.get(disease, 0) + 1
        return {
            "total_scans": total, "hf_scans": hf, "ai_vision_scans": ai,
            "curing_scans": curing, "healthy_count": healthy,
            "top_disease": max(diseases, key=diseases.get) if diseases else "None",
        }
    except Exception as e:
        log(f"❌ Stats error: {e}")
        return defaults


# ══════════════════════════════════════════════
#  IMAGE DOWNLOAD
# ══════════════════════════════════════════════

def download_image(media_id: str):
    try:
        log(f"📥 Fetching media ID: {media_id}")
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        url_resp = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers=headers, timeout=10,
        )
        if url_resp.status_code != 200:
            return None
        media_url = url_resp.json().get("url")
        if not media_url:
            return None
        img_resp = requests.get(media_url, headers=headers, timeout=30)
        return img_resp.content if img_resp.status_code == 200 else None
    except Exception as e:
        log(f"❌ Image download error: {e}")
        return None


# ══════════════════════════════════════════════
#  ML SERVICES  (Hugging Face)
# ══════════════════════════════════════════════

def hf_disease_detect(image_bytes: bytes):
    if not HF_SPACE_URL:
        return None
    try:
        log("🔄 HF disease detection...")
        r = requests.post(
            f"{HF_SPACE_URL}/predict",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=35,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                return {
                    "disease":        data.get("disease", "Unknown"),
                    "confidence":     data.get("confidence", 0),
                    "treatment":      data.get("treatment", "Consult agronomist."),
                    "is_healthy":     data.get("is_healthy", False),
                    "low_confidence": data.get("low_confidence", False),
                    "severity":       None,
                }
        log(f"HF disease non-200: {r.status_code}")
    except Exception as e:
        log(f"❌ HF disease error: {e}")
    return None


def hf_curing_detect(image_bytes: bytes):
    if not HF_SPACE_URL:
        return None
    try:
        log("🔄 HF curing detection...")
        r = requests.post(
            f"{HF_SPACE_URL}/predict_curing",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=35,
        )
        if r.status_code != 200:
            log(f"HF curing non-200: {r.status_code}")
            return None
        data = r.json()
        log(f"HF curing response: {json.dumps(data)}")

        # Format 1: {success, stage, confidence, advice}
        if data.get("success") and data.get("stage"):
            return {
                "stage":      data["stage"],
                "confidence": data.get("confidence", 0),
                "advice":     data.get("advice", ""),
            }
        # Format 2: {probabilities: {stage: prob}}
        if data.get("probabilities"):
            probs = data["probabilities"]
            top   = max(probs, key=probs.get)
            return {"stage": top, "confidence": probs[top], "advice": data.get("advice", f"Stage: {top}")}

        log(f"Unexpected curing structure — keys: {list(data.keys())}")
    except Exception as e:
        log(f"❌ HF curing error: {e}")
    return None


# ══════════════════════════════════════════════
#  AI VISION  (Gemini)
# ══════════════════════════════════════════════

def _gemini_vision(prompt: str, image_bytes: bytes):
    if not AI_API_KEY:
        return None
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(2)
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=VISION_CONFIG,
                safety_settings=SAFETY_SETTINGS,
            )
            response = model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": img_b64}]
            )
            if response and response.text:
                return response.text.strip()
        except Exception:
            continue
    return None


def gemini_disease(image_bytes: bytes, phone: str, name: str):
    prompt = (
        "Analyze this tobacco leaf image:\n\n"
        "🌿 *AI VISION ANALYSIS*\n"
        "• Detected Disease: [Name]\n"
        "• Confidence: [High/Medium/Low]\n"
        "• Symptoms: [2-3 symptoms]\n"
        "• Severity: [Mild/Moderate/Severe]\n"
        "• Action: [One concise sentence]"
    )
    analysis = _gemini_vision(prompt, image_bytes)
    if analysis:
        disease = "Unknown"
        for line in analysis.splitlines():
            if "Detected Disease:" in line:
                disease = line.split(":", 1)[-1].strip()
                break
        log_detection(phone, name, disease=disease, analysis=analysis[:500], detection_type="ai_vision_disease")
        return "disease", analysis
    return None, "⚠️ AI Vision unavailable"


def gemini_curing(image_bytes: bytes, phone: str, name: str):
    prompt = (
        "Assess the curing progress of this tobacco leaf:\n\n"
        "🔥 *CURING REPORT*\n"
        "• Stage: [Yellowing/Leaf Drying/Midrib Drying/Killing Out/Complete]\n"
        "• Color: [Description]\n"
        "• Moisture: [Wet/Optimal/Dry]\n"
        "• Recommendations: [Next steps]"
    )
    analysis = _gemini_vision(prompt, image_bytes)
    if analysis:
        stage = "Unknown"
        for line in analysis.splitlines():
            if "Stage:" in line:
                stage = line.split(":", 1)[-1].strip()
                break
        log_detection(phone, name, curing_stage=stage, analysis=analysis[:500], detection_type="ai_vision_curing")
        return "curing", analysis
    return None, "⚠️ Curing monitor unavailable"


def gemini_grade(image_bytes: bytes, phone: str, name: str):
    prompt = (
        "Grade this cured tobacco leaf:\n\n"
        "📊 *LEAF GRADE*\n"
        "• Grade: [A/B/C/D]\n"
        "• Color: [Description]\n"
        "• Texture: [Oily/Dry/Brittle]\n"
        "• Damage: [None/Minor/Moderate]\n"
        "• Value: [Premium/Good/Fair/Poor]"
    )
    analysis = _gemini_vision(prompt, image_bytes)
    if analysis:
        grade = "Unknown"
        for line in analysis.splitlines():
            if "Grade:" in line:
                parts = line.split(":", 1)[-1].strip().split()
                grade = parts[0] if parts else "Unknown"
                break
        log_detection(phone, name, grade=grade, analysis=analysis[:500], detection_type="leaf_grading")
        return "grade", analysis
    return None, "⚠️ Grading unavailable"


# ══════════════════════════════════════════════
#  AI TEXT  (Gemini — advisor, tips, facts)
# ══════════════════════════════════════════════

def _gemini_text(prompt: str, config: dict):
    if not AI_API_KEY:
        return None
    for model_name in GEMINI_MODELS[:3]:
        try:
            time.sleep(0.5)
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=config,
                safety_settings=SAFETY_SETTINGS,
            )
            r = model.generate_content(prompt)
            if r and r.text:
                return r.text.strip()
        except Exception:
            continue
    return None


def ask_ai_advisor(question: str) -> str:
    now    = datetime.now()
    prompt = (
        f"You are a Zimbabwe tobacco farming expert. Today: {now.strftime('%B %d, %Y')}.\n"
        f"Use only {now.year} data. Keep reply under 500 words. Use bullet points. "
        f"End with a complete sentence.\nQuestion: {question}"
    )
    result = _gemini_text(prompt, GENERATION_CONFIG)
    if result:
        return result
    for disease in DISEASE_KB:
        if disease.lower() in question.lower():
            return offline_disease_advice(disease)
    return "⚠️ AI service unavailable. Please try again later."


def get_daily_tip() -> str:
    month  = datetime.now().strftime("%B")
    season = (
        "rainy/planting"    if month in ("Nov","Dec","Jan","Feb","Mar") else
        "harvesting/curing" if month in ("Apr","May","Jun","Jul") else
        "land preparation"
    )
    tip = _gemini_text(
        f"Give one practical tip for Zimbabwe tobacco farmers during {season} season. "
        "3-4 sentences. Start with an emoji. End with a complete sentence.",
        TIP_CONFIG,
    )
    if tip:
        return tip if tip[-1] in ".!?" else tip + "."
    return "🌱 Monitor your fields daily for early signs of disease."


def get_fun_fact() -> str:
    fact = _gemini_text(
        f"Share one interesting fact about Zimbabwe tobacco farming for {datetime.now().year}. "
        "3-4 sentences. Start with an emoji. End with a complete sentence.",
        FACT_CONFIG,
    )
    if fact:
        return fact if fact[-1] in ".!?" else fact + "."
    return "🌱 Zimbabwe's tobacco industry employs over 500,000 people."


# ══════════════════════════════════════════════
#  PAYMENT — PayNow direct API
# ══════════════════════════════════════════════

def _paynow_initiate(phone: str, name: str, amount: float,
                     method: str, mobile: str, innbucks_code: str = None):
    """
    Initiate a PayNow mobile payment.
    Returns (success: bool, poll_url_or_error: str).
    """
    if not (PAYNOW_USD_API_KEY and PAYNOW_USD_MERCHANT_ID):
        return False, "PayNow USD not configured"

    reference = f"Ref-{format_phone(phone)}-USD-{int(time.time())}"
    payload = {
        "resulturl":      RESULT_URL,
        "returnurl":      RESULT_URL,
        "reference":      reference,
        "amount":         f"{amount:.2f}",
        "id":             PAYNOW_USD_MERCHANT_ID,
        "additionalinfo": "Tobacco AI Service",
        "authemail":      f"{mobile}@tobacco.ai",
        "method":         method,
        "mobile":         mobile,
    }
    if method == "innbucks" and innbucks_code:
        payload["innbuckscode"] = innbucks_code

    try:
        log(f"💳 PayNow {method} — {amount:.2f} USD -> {mobile}")
        r = requests.post(
            "https://www.paynow.co.zw/interface/remotepayment",
            data=payload,
            auth=(PAYNOW_USD_MERCHANT_ID, PAYNOW_USD_API_KEY),
            timeout=30,
        )
        # Parse PayNow key=value response
        result = {}
        for part in r.text.strip().split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.lower()] = v

        if result.get("status", "").lower() == "ok":
            poll_url = result.get("pollurl")
            if not poll_url:
                return False, "No poll URL returned from PayNow"
            PAYMENT_QUEUE[reference] = {
                "phone":      phone,
                "mobile":     mobile,
                "poll_url":   poll_url,
                "status":     "pending",
                "start_time": datetime.now(),
                "currency":   "USD",
                "amount":     amount,
                "method":     method,
            }
            if db:
                db.collection("users").document(phone).update({
                    "pending_payment_ref":  reference,
                    "payment_status":       "pending",
                    "last_payment_attempt": firestore.SERVER_TIMESTAMP,
                })
            return True, poll_url
        else:
            return False, result.get("error", "Unknown PayNow error")

    except Exception as e:
        return False, f"Payment error: {e}"


def _poll_payments_loop() -> None:
    """Background thread: polls PayNow every 5 s for status updates."""
    log("🔄 Payment polling thread started")
    while True:
        try:
            for ref, data in list(PAYMENT_QUEUE.items()):
                if data["status"] != "pending":
                    continue
                elapsed = (datetime.now() - data["start_time"]).total_seconds()
                if elapsed > PAYMENT_TIMEOUT_MINUTES * 60:
                    data["status"] = "timeout"
                    send_once(data["phone"],
                              f"⏳ Payment of ${data['amount']:.2f} USD timed out. "
                              "Please try again by typing *8*.")
                    continue
                try:
                    r = requests.get(data["poll_url"], timeout=10)
                    result = r.json()
                    if result.get("status") == "paid" and ref not in PROCESSED_PAYMENTS:
                        PROCESSED_PAYMENTS.add(ref)
                        data["status"] = "paid"
                        phn = data["phone"]
                        if db:
                            db.collection("users").document(phn).update({
                                "premium":             True,
                                "payment_status":      "completed",
                                "pending_payment_ref": firestore.DELETE_FIELD,
                            })
                        send_once(phn,
                                  f"🎉 *Payment of ${data['amount']:.2f} USD received!*\n"
                                  "Thank you for supporting Tobacco AI! 🌿")
                except Exception as e:
                    log(f"Polling error for {ref}: {e}")
            time.sleep(5)
        except Exception as e:
            log(f"❌ Polling loop error: {e}")
            time.sleep(10)


# Start payment polling in a daemon thread
threading.Thread(target=_poll_payments_loop, daemon=True).start()


# ══════════════════════════════════════════════
#  MENU BUILDERS
# ══════════════════════════════════════════════

def menu_main(phone: str) -> bool:
    return send_msg(phone,
        "🌿 *TOBACCO AI — MAIN MENU*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  ML Services       — Disease & Curing (HF)\n"
        "2️⃣  Farming Practices — Guides & AI advice\n"
        "3️⃣  My Dashboard      — Stats, History, Tips\n"
        "4️⃣  Leaf Grading      — Quality assessment\n"
        "5️⃣  AI Vision         — AI Disease & Curing\n"
        "6️⃣  Expert Help       — Agronomist & AI\n"
        "7️⃣  Feedback          — Send us comments\n"
        "8️⃣  Payments          — Donate / Support\n\n"
        "Reply with a number or type *help*"
    )


def menu_ml(phone: str) -> bool:
    return send_msg(phone,
        "🤖 *ML SERVICES  *\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  Disease Detection — send photo\n"
        "2️⃣  Curing Monitor    — send photo\n\n"
        "0️⃣  Main Menu"
    )


def menu_farming(phone: str) -> bool:
    return send_msg(phone,
        "🌱 *FARMING PRACTICES*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  Planting Guide\n"
        "2️⃣  Fertilizer Guide\n"
        "3️⃣  Harvesting Guide\n"
        "4️⃣  Curing Guide\n"
        "5️⃣  Marketing Guide\n"
        "6️⃣  Ask AI\n\n"
        "0️⃣  Main Menu"
    )


def menu_dashboard(phone: str, name: str, stats: dict) -> bool:
    return send_msg(phone,
        f"📊 *MY DASHBOARD*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 {name}  •  📱 {phone}\n\n"
        f"📊 Total scans:     {stats['total_scans']}\n"
        f"🔬 ML scans:        {stats['hf_scans']}\n"
        f"👁  AI Vision scans: {stats['ai_vision_scans']}\n"
        f"🔥 Curing scans:    {stats['curing_scans']}\n"
        f"🦠 Most common:     {stats['top_disease']}\n"
        f"🌿 Healthy results: {stats['healthy_count']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  Detection History\n"
        "2️⃣  Daily Tip\n"
        "3️⃣  Fun Fact\n\n"
        "0️⃣  Main Menu"
    )


def menu_expert(phone: str) -> bool:
    return send_msg(phone,
        "👨‍🌾 *EXPERT HELP*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  Ask AI Advisor\n"
        "2️⃣  Request Human Expert\n\n"
        "0️⃣  Main Menu"
    )


def menu_ai_vision(phone: str) -> bool:
    return send_msg(phone,
        "🔬 *AI VISION  *\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  Disease Detection — send photo\n"
        "2️⃣  Curing Monitor    — send photo\n\n"
        "0️⃣  Main Menu"
    )


def menu_payment(phone: str) -> bool:
    return send_msg(phone,
        "💳 *SUPPORT US — PAYMENT (USD)*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣  EcoCash USD\n"
        "2️⃣  InnBucks USD\n\n"
        "0️⃣  Main Menu"
    )


# ══════════════════════════════════════════════
#  PAYMENT FLOW HANDLERS
# ══════════════════════════════════════════════

def handle_payment_menu(phone: str, user: dict, cmd: str) -> None:
    """Step 1 — Choose payment method."""
    if cmd == "0":
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
    elif cmd in PAYMENT_METHODS:
        pm = PAYMENT_METHODS[cmd]
        save_user(phone, {"state": STATE["PAYMENT_AMOUNT"], "payment_method_key": cmd})
        send_msg(phone,
            f"💰 *ENTER AMOUNT (USD)*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Method:  {pm['name']}\n"
            f"Minimum: ${MIN_AMOUNT_USD:.2f} USD\n\n"
            "Type the amount (e.g. *1.00*) or *cancel*"
        )
    else:
        send_msg(phone, "❌ Please choose 1, 2, or 0")


def handle_payment_amount(phone: str, user: dict, text: str) -> None:
    """Step 2 — Enter donation amount."""
    if text.lower() == "cancel":
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return
    try:
        amount = float(text.strip())
    except ValueError:
        send_msg(phone, "❌ Invalid amount. Please enter a number, e.g. *1.50*")
        return

    pm = PAYMENT_METHODS.get(user.get("payment_method_key", "1"), PAYMENT_METHODS["1"])
    if amount < MIN_AMOUNT_USD:
        send_msg(phone, f"❌ Minimum amount is ${MIN_AMOUNT_USD:.2f} USD. Please try again.")
        return

    save_user(phone, {"payment_amount": amount})

    if pm["method"] == "innbucks":
        # InnBucks: ask for in-app authorization code
        save_user(phone, {"state": STATE["PAYMENT_INNBUCKS_CODE"]})
        send_msg(phone,
            "🔑 *InnBucks Authorization*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1. Open the InnBucks app\n"
            "2. Tap *Pay* → *Generate Authorization Code*\n"
            "3. Type the code here\n\n"
            "Type *cancel* to abort"
        )
    else:
        # EcoCash: ask for mobile number
        save_user(phone, {"state": STATE["PAYMENT_MOBILE_NUMBER"]})
        send_msg(phone,
            "📱 *Enter your EcoCash number*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Examples:\n"
            "  • 0771234567\n"
            "  • 263771234567\n\n"
            "Type *cancel* to abort"
        )


def handle_payment_mobile_number(phone: str, user: dict, text: str) -> None:
    """Step 3a (EcoCash) — Collect mobile number, send payment request, then guide user through PIN."""
    if text.lower() == "cancel":
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return

    cleaned = re.sub(r"[^0-9+]", "", text.strip())
    if not re.match(r"^(0|263|\+263)[7]\d{8}$", cleaned):
        send_msg(phone,
            "❌ Invalid Zimbabwe number.\n"
            "Please use format: *0771234567* or *263771234567*"
        )
        return

    mobile = format_phone(cleaned)
    amount = user.get("payment_amount", 0)
    pm     = PAYMENT_METHODS.get(user.get("payment_method_key", "1"), PAYMENT_METHODS["1"])

    # ── Initiate payment with PayNow ──────────
    success, result = _paynow_initiate(
        phone=phone, name=user.get("name", "Farmer"),
        amount=amount, method=pm["method"], mobile=mobile,
    )

    if not success:
        send_msg(phone, f"❌ Payment initiation failed: {result}\n\nPlease try again later.")
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return

    # ── Payment initiated — guide user to approve PIN ─────
    save_user(phone, {
        "state":          STATE["PAYMENT_OTP_CONFIRM"],
        "payment_mobile": mobile,
    })

    send_msg(phone,
        f"📲 *EcoCash Payment Request Sent!*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Amount:  *${amount:.2f} USD*\n"
        f"Number:  *{mobile}*\n\n"
        "📟 You will receive a *USSD pop-up* on your phone.\n\n"
        "👉 *Enter your EcoCash PIN* on the USSD screen to approve.\n\n"
        "Once you have approved, reply *PAID* to confirm.\n"
        "To cancel, type *cancel*."
    )


def handle_payment_otp_confirm(phone: str, user: dict, text: str) -> None:
    """
    Step 3b — OTP / PIN acknowledgement.

    EcoCash sends a USSD prompt directly to the user's phone.
    The user enters their PIN there (not here). We simply wait
    for them to tell us they've done it, or rely on background
    polling to catch the confirmation automatically.
    """
    cmd = text.strip().lower()

    if cmd == "cancel":
        send_msg(phone, "❌ Payment cancelled.")
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return

    if cmd == "paid":
        amount = user.get("payment_amount", 0)
        send_msg(phone,
            f"⏳ *Verifying payment…*\n\n"
            f"Amount: *${amount:.2f} USD*\n\n"
            "We are confirming with EcoCash. "
            "You will receive a message here once your payment is verified. 🌿"
        )
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return

    # User typed something else — remind them of what to do
    send_msg(phone,
        "⏳ *Waiting for your EcoCash PIN confirmation…*\n\n"
        "Steps:\n"
        "1. Check your phone for the USSD pop-up\n"
        "2. Enter your *EcoCash PIN*\n"
        "3. Once approved, reply *PAID* here\n\n"
        "To abort, type *cancel*."
    )


def handle_payment_innbucks_code(phone: str, user: dict, text: str) -> None:
    """Step 3b (InnBucks) — Collect authorization code and submit payment."""
    if text.lower() == "cancel":
        save_user(phone, {"state": STATE["ACTIVE"]})
        menu_main(phone)
        return

    code   = text.strip()
    amount = user.get("payment_amount", 0)
    mobile = format_phone(phone)  # InnBucks uses the account holder's own number

    success, result = _paynow_initiate(
        phone=phone, name=user.get("name", "Farmer"),
        amount=amount, method="innbucks", mobile=mobile,
        innbucks_code=code,
    )

    if success:
        send_msg(phone,
            f"✅ *InnBucks Payment Submitted!*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Amount: *${amount:.2f} USD*\n\n"
            "Please open InnBucks and authorize the payment. "
            "You will receive a confirmation here once verified. 🌿"
        )
    else:
        send_msg(phone, f"❌ InnBucks payment failed: {result}")

    save_user(phone, {"state": STATE["ACTIVE"]})
    menu_main(phone)


# ══════════════════════════════════════════════
#  CORE MESSAGE DISPATCHER
# ══════════════════════════════════════════════

def handle_message(phone: str, msg_type: str, content: str) -> None:
    log(f"📨 [{msg_type}] from {phone}")

    user = get_user(phone)

    # ── New user onboarding ────────────────────
    if not user:
        save_user(phone, {"state": STATE["AWAITING_NAME"], "phone": phone})
        send_msg(phone, "🌿 *Welcome to Tobacco AI!*\n\nPlease enter your *name* to get started:")
        return

    state = user.get("state", STATE["ACTIVE"])
    name  = user.get("name", "Farmer")

    # ── Onboarding: collect name ───────────────
    if state == STATE["AWAITING_NAME"] and msg_type == "text":
        clean_name = content.strip().title()
        save_user(phone, {"name": clean_name, "state": STATE["ACTIVE"]})
        send_msg(phone, f"✅ *Welcome, {clean_name}!*\n\nSend a photo of a leaf or type *menu* to begin.")
        return

    # ── Global: payment status check ──────────
    if msg_type == "text" and content.lower().strip() in ("status", "payment status"):
        ref = user.get("pending_payment_ref")
        if ref and ref in PAYMENT_QUEUE:
            d = PAYMENT_QUEUE[ref]
            if d["status"] == "paid":
                send_msg(phone, f"✅ Your payment of ${d['amount']:.2f} USD was successful!")
            elif d["status"] == "pending":
                mins = int((datetime.now() - d["start_time"]).total_seconds() // 60)
                send_msg(phone,
                    f"⏳ Payment still pending ({mins} min ago).\n"
                    "Please check your phone for the EcoCash USSD prompt."
                )
            else:
                send_msg(phone, "ℹ️ No active payment. Type *8* to donate.")
        else:
            send_msg(phone, "ℹ️ No recent payment found. Type *8* to donate.")
        return

    # ── Payment flow ───────────────────────────
    if state == STATE["PAYMENT_MENU"]         and msg_type == "text":
        handle_payment_menu(phone, user, content.strip()); return
    if state == STATE["PAYMENT_AMOUNT"]       and msg_type == "text":
        handle_payment_amount(phone, user, content); return
    if state == STATE["PAYMENT_MOBILE_NUMBER"] and msg_type == "text":
        handle_payment_mobile_number(phone, user, content); return
    if state == STATE["PAYMENT_OTP_CONFIRM"]  and msg_type == "text":
        handle_payment_otp_confirm(phone, user, content); return
    if state == STATE["PAYMENT_INNBUCKS_CODE"] and msg_type == "text":
        handle_payment_innbucks_code(phone, user, content); return

    # ── ML menu ────────────────────────────────
    if state == STATE["ML_MENU"] and msg_type == "text":
        cmd = content.strip()
        if   cmd == "0": save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone)
        elif cmd == "1": save_user(phone, {"state": STATE["WAITING_IMAGE"]}); send_msg(phone, "📸 Send a clear photo for *ML disease detection*")
        elif cmd == "2": save_user(phone, {"state": STATE["WAITING_ML_CURING"]}); send_msg(phone, "🔥 Send a photo for *ML curing stage analysis*")
        else: send_msg(phone, "❌ Choose 1, 2, or 0")
        return

    # ── ML disease ─────────────────────────────
    if state == STATE["WAITING_IMAGE"] and msg_type == "image":
        if phone in LAST_SCAN and time.time() - LAST_SCAN[phone] < 5:
            send_msg(phone, "⏱️ Please wait 5 seconds before sending another photo.")
            return
        LAST_SCAN[phone] = time.time()
        send_msg(phone, f"🔍 Analysing your leaf, {name}...")
        img = download_image(content)
        if not img:
            send_msg(phone, "❌ Could not download image. Please try again.")
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return

        result = hf_disease_detect(img)
        if not result:
            _, analysis = gemini_disease(img, phone, name)
            send_msg(phone, analysis if analysis and "⚠️" not in analysis
                     else "❌ Analysis failed. Please try again.")
        else:
            disease, conf = result["disease"], result["confidence"]
            log_detection(phone, name, disease=disease, confidence=conf,
                          severity=result.get("severity"), detection_type="hf_disease")
            if result["low_confidence"]:
                msg = (f"⚠️ *Low Confidence ({conf:.1f}%)*\n\n{confidence_label(conf)}\n\n"
                       "Try a clearer photo or use AI Vision (type *5*).")
            elif result["is_healthy"]:
                msg = f"🎉 *Healthy Leaf!*\n\nConfidence: {conf:.1f}%\n{confidence_label(conf)}"
            else:
                msg = (f"📊 *{disease} Detected*\n\nConfidence: {conf:.1f}%  {confidence_label(conf)}\n"
                       f"Severity: *{result.get('severity', 'Unknown')}*\n\n*Treatment:*\n{result['treatment']}")
            send_msg(phone, msg)
            if not result["is_healthy"] and not result["low_confidence"] and conf >= 50:
                send_msg(phone, offline_disease_advice(disease))

        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); gc.collect(); return

    # ── ML curing ──────────────────────────────
    if state == STATE["WAITING_ML_CURING"] and msg_type == "image":
        send_msg(phone, f"🔥 Analysing curing stage, {name}...")
        img = download_image(content)
        if not img:
            send_msg(phone, "❌ Download failed.")
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        result = hf_curing_detect(img)
        if result and result.get("stage"):
            log_detection(phone, name, curing_stage=result["stage"],
                          confidence=result["confidence"], detection_type="hf_curing")
            send_msg(phone,
                f"🍂 *Curing Stage: {result['stage']}*\n\n"
                f"Confidence: {result['confidence']:.1f}%\n\n"
                f"{result.get('advice', 'Monitor curing conditions carefully.')}"
            )
        else:
            send_msg(phone, "❌ Curing analysis failed. Please try again.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); gc.collect(); return

    # ── AI Vision menu ─────────────────────────
    if state == STATE["WAITING_AI_VISION"] and msg_type == "text":
        cmd = content.strip()
        if   cmd == "0": save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone)
        elif cmd == "1": save_user(phone, {"state": STATE["WAITING_AI_VISION_DISEASE"]}); send_msg(phone, "🔬 Send photo for *AI Vision disease detection*")
        elif cmd == "2": save_user(phone, {"state": STATE["WAITING_AI_VISION_CURING"]});  send_msg(phone, "🔥 Send photo for *AI Vision curing analysis*")
        else: send_msg(phone, "❌ Choose 1, 2, or 0")
        return

    if state == STATE["WAITING_AI_VISION_DISEASE"] and msg_type == "image":
        send_msg(phone, f"🔬 Analysing with AI Vision, {name}...")
        img = download_image(content)
        if not img:
            send_msg(phone, "❌ Download failed.")
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        _, analysis = gemini_disease(img, phone, name)
        send_msg(phone, analysis or "❌ AI Vision disease analysis failed.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); gc.collect(); return

    if state == STATE["WAITING_AI_VISION_CURING"] and msg_type == "image":
        send_msg(phone, f"🔥 Analysing curing with AI Vision, {name}...")
        img = download_image(content)
        if not img:
            send_msg(phone, "❌ Download failed.")
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        _, analysis = gemini_curing(img, phone, name)
        send_msg(phone, analysis or "❌ AI Vision curing analysis failed.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); gc.collect(); return

    # ── Leaf grading ───────────────────────────
    if state == STATE["WAITING_GRADE_IMAGE"] and msg_type == "image":
        send_msg(phone, f"🔍 Grading leaf, {name}...")
        img = download_image(content)
        if not img:
            send_msg(phone, "❌ Download failed.")
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        _, analysis = gemini_grade(img, phone, name)
        send_msg(phone, analysis or "❌ Grading unavailable. Please try again.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); gc.collect(); return

    # ── Expert menu ────────────────────────────
    if state == STATE["EXPERT_MENU"] and msg_type == "text":
        cmd = content.strip()
        if   cmd == "0": save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone)
        elif cmd == "1": save_user(phone, {"state": STATE["AWAITING_AI_QUESTION"]}); send_msg(phone, "🤖 Ask anything about tobacco farming (or *cancel*):")
        elif cmd == "2": save_user(phone, {"state": STATE["AWAITING_EXPERT"]});       send_msg(phone, "👨‍🌾 Describe your problem. An expert will respond in 24-48 hours (or *cancel*):")
        else: send_msg(phone, "❌ Choose 1, 2, or 0")
        return

    # ── Dashboard menu ─────────────────────────
    if state == STATE["DASHBOARD_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        if cmd == "1":
            history = get_user_history(phone, 8)
            if not history:
                send_msg(phone, "📋 No detection history yet.")
            else:
                lines = ["📋 *DETECTION HISTORY*\n━━━━━━━━━━━━━━━━━━"]
                for i, h in enumerate(history, 1):
                    dtype = h.get("detection_type", "")
                    if   dtype == "hf_disease":        lines.append(f"{i}. 🔬 {h.get('disease')} — {h.get('confidence', 0):.0f}%")
                    elif dtype == "ai_vision_disease":  lines.append(f"{i}. 👁  {h.get('disease')}")
                    elif dtype in ("ai_vision_curing", "hf_curing"): lines.append(f"{i}. 🔥 {h.get('curing_stage')}")
                    elif dtype == "leaf_grading":       lines.append(f"{i}. 📊 Grade {h.get('grade')}")
                    if h.get("date"):
                        lines.append(f"   📅 {h['date']}")
                send_msg(phone, trim("\n".join(lines), 1500))
        elif cmd == "2":
            send_msg(phone, f"💡 *Daily Tip*\n\n{get_daily_tip()}")
        elif cmd == "3":
            send_msg(phone, f"🎲 *Did You Know?*\n\n{get_fun_fact()}")
        else:
            send_msg(phone, "❌ Choose 1, 2, 3, or 0")
        stats = get_user_stats(phone)
        menu_dashboard(phone, name, stats)
        return

    # ── Farming menu ───────────────────────────
    GUIDES = {
        "1": PLANTING_GUIDE, "2": FERTILIZER_GUIDE, "3": HARVESTING_GUIDE,
        "4": CURING_GUIDE,   "5": MARKETING_GUIDE,
    }
    if state == STATE["FARMING_MENU"] and msg_type == "text":
        cmd = content.strip()
        if cmd == "0":
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        if cmd in GUIDES:
            send_msg(phone, GUIDES[cmd]); menu_farming(phone); return
        if cmd == "6":
            save_user(phone, {"state": STATE["AWAITING_AI_QUESTION"]})
            send_msg(phone, "🤖 Ask your farming question (or *cancel*):"); return
        menu_farming(phone)
        return

    # ── AI advisor ─────────────────────────────
    if state == STATE["AWAITING_AI_QUESTION"] and msg_type == "text":
        if content.lower() == "cancel":
            save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return
        send_msg(phone, "🤔 Thinking...")
        send_msg(phone, ask_ai_advisor(content))
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return

    # ── Feedback ───────────────────────────────
    if state == STATE["AWAITING_FEEDBACK"] and msg_type == "text":
        if content.lower() != "cancel":
            if ADMIN_PHONE:
                send_msg(ADMIN_PHONE, f"📝 *FEEDBACK*\n👤 {name} ({phone})\n💬 {content}")
            send_msg(phone, "✅ Thank you for your feedback!")
        else:
            send_msg(phone, "Cancelled.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return

    # ── Expert request ─────────────────────────
    if state == STATE["AWAITING_EXPERT"] and msg_type == "text":
        if content.lower() != "cancel":
            if ADMIN_PHONE:
                send_msg(ADMIN_PHONE, f"🚨 *EXPERT REQUEST*\n👤 {name} ({phone})\n💬 {content}")
            send_msg(phone, "👨‍🌾 Request sent! An expert will respond within 24-48 hours.")
        else:
            send_msg(phone, "Cancelled.")
        save_user(phone, {"state": STATE["ACTIVE"]}); menu_main(phone); return

    # ── Global text commands (ACTIVE state) ────
    if msg_type == "text":
        cmd = content.lower().strip()

        if   cmd in ("menu", "0", "main"):        menu_main(phone)
        elif cmd in ("1", "ml", "ml services"):   save_user(phone, {"state": STATE["ML_MENU"]}); menu_ml(phone)
        elif cmd in ("2", "farming"):             save_user(phone, {"state": STATE["FARMING_MENU"]}); menu_farming(phone)
        elif cmd in ("3", "dashboard"):
            stats = get_user_stats(phone)
            save_user(phone, {"state": STATE["DASHBOARD_MENU"]}); menu_dashboard(phone, name, stats)
        elif cmd in ("4", "grade"):
            save_user(phone, {"state": STATE["WAITING_GRADE_IMAGE"]})
            send_msg(phone, "🏷️ Send a photo of the cured leaf for quality grading")
        elif cmd in ("5", "vision"):              save_user(phone, {"state": STATE["WAITING_AI_VISION"]}); menu_ai_vision(phone)
        elif cmd in ("6", "expert"):              save_user(phone, {"state": STATE["EXPERT_MENU"]}); menu_expert(phone)
        elif cmd in ("7", "feedback"):
            save_user(phone, {"state": STATE["AWAITING_FEEDBACK"]})
            send_msg(phone, "📝 Type your feedback (or *cancel*):")
        elif cmd in ("8", "pay", "payment", "donate"):
            save_user(phone, {"state": STATE["PAYMENT_MENU"]}); menu_payment(phone)
        elif cmd.startswith("ai "):
            question = cmd[3:].strip()
            if question:
                send_msg(phone, "🤔 Thinking...")
                send_msg(phone, ask_ai_advisor(question))
                menu_main(phone)
        elif cmd == "help":
            send_msg(phone,
                "📚 *HELP*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• *1* — ML Services ( Disease & Curing)\n"
                "• *2* — Farming Practices\n"
                "• *3* — My Dashboard\n"
                "• *4* — Leaf Grading\n"
                "• *5* — AI Vision (detection and curing )\n"
                "• *6* — Expert Help\n"
                "• *7* — Feedback\n"
                "• *8* — Donate / Support\n"
                "• *ai [question]* — Ask AI anything\n"
                "• *status* — Check payment status"
            )
        else:
            send_msg(phone, "❓ Type *menu* to see options or *help* for all commands.")


# ══════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # Webhook verification (Meta challenge)
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403

    # Incoming messages
    try:
        data  = request.json
        msgs  = (data.get("entry", [{}])[0]
                 .get("changes", [{}])[0]
                 .get("value", {})
                 .get("messages", []))
        if msgs:
            m        = msgs[0]
            from_num = m.get("from")
            m_type   = m.get("type")
            content  = (m.get("text",  {}).get("body", "") if m_type == "text"  else
                        m.get("image", {}).get("id",   "") if m_type == "image" else None)
            if content:
                handle_message(from_num, m_type, content)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        log(f"❌ Webhook error: {e}")
        return jsonify({"status": "error"}), 500


@app.route("/paynow_update", methods=["POST"])
def paynow_update():
    """PayNow server-to-server payment notification."""
    data   = request.form
    ref    = data.get("reference", "")
    status = data.get("status", "")
    log(f"💳 PayNow webhook — ref: {ref}  status: {status}")

    if ref.startswith("Ref-") and status == "paid" and ref not in PROCESSED_PAYMENTS:
        PROCESSED_PAYMENTS.add(ref)
        parts = ref.split("-")
        if len(parts) >= 2:
            phn = parts[1]
            if db:
                db.collection("users").document(phn).update({
                    "premium":             True,
                    "payment_status":      "completed",
                    "pending_payment_ref": firestore.DELETE_FIELD,
                })
            send_once(phn, "🎉 *PAYMENT CONFIRMED!* Thank you for supporting Tobacco AI! 🌿")
    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "healthy",
        "firebase":  db is not None,
        "gemini":    bool(AI_API_KEY),
        "hf_space":  bool(HF_SPACE_URL),
        "paynow":    bool(PAYNOW_USD_API_KEY and PAYNOW_USD_MERCHANT_ID),
    }), 200


@app.route("/", methods=["GET"])
def home():
    return "🌿 Tobacco AI Assistant is running!", 200


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    log(f"🚀 Starting on port {port}")
    log(f"💰 PayNow USD  : {'✅' if PAYNOW_USD_API_KEY else '❌'}")
    log(f"🤖 Hugging Face: {'✅' if HF_SPACE_URL       else '❌'}")
    log(f"🔮 Gemini AI   : {'✅' if AI_API_KEY          else '❌'}")
    log(f"🔥 Firebase    : {'✅' if db                  else '❌'}")
    app.run(host="0.0.0.0", port=port, debug=False)
