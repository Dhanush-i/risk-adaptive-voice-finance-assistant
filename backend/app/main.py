"""
FastAPI Application — Entry Point
===================================
Main application setup with CORS, lifespan, and route registration.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.config import get_config
from backend.app.db.database import init_db, create_tables


# --- App State (ML models & services loaded at startup) ---
app_state = {
    "config": None,
    "razorpay_service": None,
    "stt": None,
    "speaker_verification": None,
    "intent_classifier": None,
    "fraud_detector": None,
    "auth_logic": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — runs on startup and shutdown.
    Loads config, initializes DB, and loads ML models.
    """
    print("=" * 60)
    print("🚀 Starting Risk-Adaptive Voice Finance Assistant")
    print("=" * 60)

    # Load config
    config = get_config()
    app_state["config"] = config
    print(f"[Startup] Config loaded: {config.project_name}")

    # Initialize database
    engine, _ = init_db(config.database_url)
    create_tables(engine)
    print("[Startup] Database initialized.")

    # Initialize Razorpay
    from backend.app.services.razorpay_service import RazorpayService
    rp_service = RazorpayService(
        key_id=config.razorpay_key_id,
        key_secret=config.razorpay_key_secret,
        currency=config.razorpay_currency,
    )
    app_state["razorpay_service"] = rp_service

    if rp_service.is_configured():
        print("[Startup] ✅ Razorpay configured")
    else:
        print("[Startup] ⚠️  Razorpay keys not set — update .env")

    # Load ML models (lazy — will be loaded on first request or explicitly)
    # We don't load STT and SV here because they take time and memory
    # They'll be loaded when needed

    # Load lightweight models immediately
    try:
        from ml.modules.intent_classifier import IntentClassifier
        ic = IntentClassifier(config_path="architecture/config.yaml")
        ic.load_model()
        app_state["intent_classifier"] = ic
        print("[Startup] ✅ Intent Classifier loaded")
    except Exception as e:
        print(f"[Startup] ⚠️  Intent Classifier not loaded: {e}")

    try:
        from ml.modules.fraud_detector import FraudDetector
        fd = FraudDetector(config_path="architecture/config.yaml")
        fd.load_model()
        app_state["fraud_detector"] = fd
        print("[Startup] ✅ Fraud Detector loaded")
    except Exception as e:
        print(f"[Startup] ⚠️  Fraud Detector not loaded: {e}")

    try:
        from ml.modules.auth_logic import AuthLogic
        al = AuthLogic(config_path="architecture/config.yaml")
        app_state["auth_logic"] = al
        print("[Startup] ✅ Auth Logic loaded")
    except Exception as e:
        print(f"[Startup] ⚠️  Auth Logic not loaded: {e}")

    print("\n" + "=" * 60)
    print("✅ Application ready!")
    print("=" * 60 + "\n")

    yield  # App runs here

    # Cleanup on shutdown
    print("\n[Shutdown] Cleaning up...")
    print("[Shutdown] Done.")


# --- Create FastAPI App ---
app = FastAPI(
    title="Risk-Adaptive Voice Finance Assistant",
    description="Voice-based financial transactions with ML-powered fraud detection and Razorpay payments.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS Middleware ---
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "models_loaded": {
            "intent_classifier": app_state["intent_classifier"] is not None,
            "fraud_detector": app_state["fraud_detector"] is not None,
            "auth_logic": app_state["auth_logic"] is not None,
            "stt": app_state["stt"] is not None,
            "speaker_verification": app_state["speaker_verification"] is not None,
        },
        "razorpay_configured": (
            app_state["razorpay_service"].is_configured()
            if app_state["razorpay_service"] else False
        ),
        "database": "connected",
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — API info."""
    return {
        "name": "Risk-Adaptive Voice Finance Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# --- Register Routers ---
from backend.app.api import voice, payments, users, transactions
app.include_router(voice.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
