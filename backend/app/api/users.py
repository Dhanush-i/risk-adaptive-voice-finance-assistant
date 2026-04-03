"""
User API Routes
================
Endpoints for user management — create, get, balance check.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import bcrypt

from backend.app.db.database import get_db
from backend.app.db.models import User, SpeakerProfile
from backend.app.schemas.schemas import UserCreate, UserResponse, UserLogin

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/login", response_model=UserResponse)
async def login_user(
    request: UserLogin,
    db: Session = Depends(get_db),
):
    """Log into a user account with username and password."""
    user = db.query(User).filter_by(username=request.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Hash verification
    if not bcrypt.checkpw(request.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Check speaker enrollment
    profile = db.query(SpeakerProfile).filter_by(user_id=user.id).first()
    enrolled = profile.is_enrolled if profile else False

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        balance=user.balance,
        is_active=user.is_active,
        speaker_enrolled=enrolled,
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
):
    """Create a new user account."""
    # Check if username exists
    existing = db.query(User).filter_by(username=request.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{request.username}' already exists")

    # Hash Password
    password_hash = bcrypt.hashpw(
        request.password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

    # Hash PIN
    pin_hash = bcrypt.hashpw(
        request.pin.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

    # Create user
    user = User(
        username=request.username,
        display_name=request.display_name,
        password_hash=password_hash,
        pin_hash=pin_hash,
        balance=10000.0,  # Demo starting balance
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

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        balance=user.balance,
        is_active=user.is_active,
        speaker_enrolled=False,
    )


@router.get("/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    db: Session = Depends(get_db),
):
    """Get user info by username."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    # Check if speaker is enrolled
    profile = db.query(SpeakerProfile).filter_by(user_id=user.id).first()
    enrolled = profile.is_enrolled if profile else False

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        balance=user.balance,
        is_active=user.is_active,
        speaker_enrolled=enrolled,
    )


@router.get("/{username}/balance")
async def get_balance(
    username: str,
    db: Session = Depends(get_db),
):
    """Get user's current balance."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    return {
        "username": user.username,
        "display_name": user.display_name,
        "balance": user.balance,
        "currency": "INR",
    }
