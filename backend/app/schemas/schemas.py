"""
Pydantic Schemas — Request/Response Models
============================================
Type-safe request and response schemas for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================
# STT Schemas
# ============================================================

class STTResponse(BaseModel):
    """Speech-to-Text transcription result."""
    transcript: str
    language: str = "en"
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================
# Speaker Verification Schemas
# ============================================================

class SVEnrollRequest(BaseModel):
    """Speaker enrollment request."""
    user_id: str
    # Audio files are sent as multipart form data, not in JSON body

class SVEnrollResponse(BaseModel):
    """Speaker enrollment result."""
    speaker_id: str
    num_samples: int
    success: bool
    message: str

class SVVerifyResponse(BaseModel):
    """Speaker verification result."""
    speaker_id: str
    similarity_score: float
    verified: bool


# ============================================================
# Intent Classification Schemas
# ============================================================

class IntentEntities(BaseModel):
    """Extracted entities from intent classification."""
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    recipient: Optional[str] = None
    bill_type: Optional[str] = None

class IntentResponse(BaseModel):
    """Intent classification result."""
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: IntentEntities = IntentEntities()


# ============================================================
# Fraud Detection Schemas
# ============================================================

class FraudResponse(BaseModel):
    """Fraud detection result."""
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_tier: str  # Low, Medium, High
    anomaly_flags: List[str] = []
    details: Optional[Dict[str, Any]] = None


# ============================================================
# Auth Schemas
# ============================================================

class AuthDecision(BaseModel):
    """Authentication decision from the policy engine."""
    auth_required: str  # pin_only, step_up, block
    risk_tier: str
    proceed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class PinVerifyRequest(BaseModel):
    """PIN verification request."""
    user_id: str
    pin: str
    transaction_id: int

class PinVerifyResponse(BaseModel):
    """PIN verification result."""
    success: bool
    message: str


# ============================================================
# Razorpay Schemas
# ============================================================

class RazorpayOrderRequest(BaseModel):
    """Request to create a Razorpay order."""
    amount_inr: float = Field(gt=0, le=1000, description="Amount in INR (max ₹1000 for safety)")
    recipient: Optional[str] = None
    notes: Optional[Dict[str, str]] = None

class RazorpayOrderResponse(BaseModel):
    """Razorpay order creation result."""
    order_id: str
    amount_paise: int
    currency: str = "INR"
    key_id: str  # Public key for frontend checkout
    status: str

class RazorpayPaymentVerification(BaseModel):
    """Razorpay payment verification request (from frontend after checkout)."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class RazorpayPaymentResponse(BaseModel):
    """Payment verification result."""
    success: bool
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    amount_inr: Optional[float] = None
    status: str
    message: str


# ============================================================
# Pipeline / Transaction Schemas
# ============================================================

class PipelineRequest(BaseModel):
    """Full pipeline request (voice command processing)."""
    user_id: str
    # Audio is sent as multipart form data

class PipelineStageResult(BaseModel):
    """Result of a single pipeline stage."""
    stage: str  # stt, sv, intent, fraud, auth
    success: bool
    data: Dict[str, Any]
    duration_ms: Optional[float] = None

class PipelineResponse(BaseModel):
    """Full pipeline processing result."""
    transaction_id: int
    stages: List[PipelineStageResult]
    auth_decision: AuthDecision
    razorpay_order: Optional[RazorpayOrderResponse] = None
    status: str
    message: str


# ============================================================
# Transaction History Schemas
# ============================================================

class TransactionSummary(BaseModel):
    """Transaction summary for history view."""
    id: int
    amount_inr: float
    recipient: Optional[str]
    intent: Optional[str]
    risk_tier: Optional[str]
    payment_status: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionListResponse(BaseModel):
    """List of transactions."""
    transactions: List[TransactionSummary]
    total: int


# ============================================================
# User Schemas
# ============================================================

class UserCreate(BaseModel):
    """User registration request."""
    username: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    pin: str = Field(min_length=4, max_length=6)

class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str

class UserResponse(BaseModel):
    """User info response."""
    id: int
    username: str
    display_name: str
    balance: float
    is_active: bool
    speaker_enrolled: bool = False

    class Config:
        from_attributes = True


# ============================================================
# Health Check
# ============================================================

class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    models_loaded: Dict[str, bool] = {}
    database: str = "connected"
