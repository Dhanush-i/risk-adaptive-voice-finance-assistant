"""
Auth API Routes
================
Endpoints for user authentication — login and register with JWT tokens.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import bcrypt

from backend.app.db.database import get_db
from backend.app.db.models import User, SpeakerProfile
from backend.app.core.security import create_access_token
from backend.app.schemas.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """Login with username and PIN."""
    username: str
    pin: str


class RegisterRequest(BaseModel):
    """Register a new account."""
    username: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    pin: str = Field(min_length=4, max_length=6)


class AuthResponse(BaseModel):
    """Auth response with JWT token and user info."""
    token: str
    user: UserResponse


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate with username + PIN. Returns a JWT token.
    """
    user = db.query(User).filter_by(username=request.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or PIN")

    # Verify PIN using bcrypt
    if not bcrypt.checkpw(
        request.pin.encode("utf-8"),
        user.pin_hash.encode("utf-8") if isinstance(user.pin_hash, str) else user.pin_hash,
    ):
        raise HTTPException(status_code=401, detail="Invalid username or PIN")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Check speaker enrollment
    profile = db.query(SpeakerProfile).filter_by(user_id=user.id).first()
    enrolled = profile.is_enrolled if profile else False

    # Create JWT token
    token = create_access_token(user.id, user.username)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            balance=user.balance,
            is_active=user.is_active,
            speaker_enrolled=enrolled,
        ),
    )


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account and return a JWT token.
    """
    # Check if username exists
    existing = db.query(User).filter_by(username=request.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{request.username}' already exists")

    # Hash PIN (also used as password for simplicity)
    pin_hash = bcrypt.hashpw(
        request.pin.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

    password_hash = pin_hash  # Use same hash for password

    # Create user
    user = User(
        username=request.username,
        display_name=request.display_name,
        password_hash=password_hash,
        pin_hash=pin_hash,
        balance=10000.0,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create empty speaker profile
    profile = SpeakerProfile(
        user_id=user.id,
        embedding_path=f"storage/speaker_profiles/{request.username}.npy",
        num_enrollment_samples=0,
        is_enrolled=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    # Create JWT token
    token = create_access_token(user.id, user.username)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            balance=user.balance,
            is_active=user.is_active,
            speaker_enrolled=False,
        ),
    )
