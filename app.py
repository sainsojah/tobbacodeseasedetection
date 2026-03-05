"""
Tobacco AI Assistant - Main Entry Point
Extremely thin Flask app that delegates all logic to the core router
"""
import os
# Add src. prefix to ALL imports
from src.middleware.webhook_filter import filter_webhook_event
from src.core.router import Router
from src.config.firebase import init_firebase
from src.config.settings import VERIFY_TOKEN, validate_config
from src.utils.logger import Logger

# Initialize Flask app
app = Flask(__name__)

# Initialize logger
logger = Logger("tobacco-ai")

# Initialize router (will be created after Firebase)
router = None

@app.before_request
def before_request():
    """Initialize services before first request"""
    global router
    if router is None:
        try:
            # Validate configuration
            validate_config()
            
            # Initialize Firebase
            init_firebase()
            
            # Initialize router
            router = Router()
            
            logger.info("✅ System initialized successfully")
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
            raise

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Main webhook endpoint - handles all WhatsApp messages"""
    
    # Handle WhatsApp webhook verification (GET)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Webhook verified")
            return challenge, 200
        else:
            logger.warning("❌ Webhook verification failed")
            return "Forbidden", 403

    # Handle incoming messages (POST)
    try:
        # Log incoming request
        logger.debug(f"Webhook POST received: {request.get_json()}")
        
        # Step 1: Filter out non-message events (status updates, deliveries, etc.)
        filtered_data = filter_webhook_event(request.json)
        
        if not filtered_data:
            # This was a non-message event, ignore it
            logger.info("⏭️ Ignored non-message event")
            return jsonify({"status": "ignored"}), 200
        
        # Step 2: Extract message details
        from_number = filtered_data.get("from")
        msg_type = filtered_data.get("type")
        content = filtered_data.get("content")
        message_id = filtered_data.get("message_id")
        
        logger.info(f"📩 Processing {msg_type} message from {from_number}")
        
        # Step 3: Route to router for processing
        if router:
            response = router.route(from_number, msg_type, content)
        else:
            # Fallback if router not initialized
            logger.error("❌ Router not initialized")
            from infrastructure.whatsapp.client import WhatsAppClient
            whatsapp = WhatsAppClient()
            whatsapp.send_text(
                from_number,
                "❌ System is starting up. Please try again in a moment."
            )
            response = {"status": "starting"}
        
        logger.info(f"✅ Message processed: {response}")
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        # Try to notify user if possible
        try:
            if 'from_number' in locals():
                from infrastructure.whatsapp.client import WhatsAppClient
                whatsapp = WhatsAppClient()
                whatsapp.send_text(
                    from_number,
                    "❌ An error occurred. Our team has been notified. Please try again later."
                )
        except:
            pass
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Render"""
    status = {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "services": {
            "router": router is not None,
            "firebase": router is not None  # Router exists only if Firebase initialized
        }
    }
    
    if router is None:
        status["status"] = "starting"
        return jsonify(status), 503
    
    return jsonify(status), 200

@app.route("/", methods=["GET"])
def home():
    """Root endpoint - basic info"""
    return jsonify({
        "name": "Tobacco AI Assistant",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/webhook - WhatsApp webhook",
            "/health - Health check"
        ]
    }), 200

# For local development
if __name__ == "__main__":
    # CRITICAL: Bind to 0.0.0.0 and use PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)