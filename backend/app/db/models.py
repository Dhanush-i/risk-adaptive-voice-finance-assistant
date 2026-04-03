"""
Database Models — SQLAlchemy ORM
=================================
Defines the database schema for users, transactions, and speaker profiles.
"""

import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)  # bcrypt hashed password
    pin_hash = Column(String(255), nullable=False)  # bcrypt hashed PIN
    balance = Column(Float, default=10000.0)  # Demo balance in INR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="user", order_by="Transaction.created_at.desc()")
    speaker_profile = relationship("SpeakerProfile", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class SpeakerProfile(Base):
    """Speaker voice profile for verification."""
    __tablename__ = "speaker_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    embedding_path = Column(String(255), nullable=False)  # Path to .npy embedding file
    num_enrollment_samples = Column(Integer, default=0)
    is_enrolled = Column(Boolean, default=False)
    enrolled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="speaker_profile")

    def __repr__(self):
        return f"<SpeakerProfile(user_id={self.user_id}, enrolled={self.is_enrolled})>"


class Transaction(Base):
    """Transaction record — tracks all payment attempts and results."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Intent & entities
    transcript = Column(Text, nullable=True)
    intent = Column(String(50), nullable=True)
    intent_confidence = Column(Float, nullable=True)

    # Transaction details
    amount_inr = Column(Float, nullable=False)
    recipient = Column(String(100), nullable=True)
    bill_type = Column(String(50), nullable=True)

    # Risk assessment
    risk_score = Column(Float, nullable=True)
    risk_tier = Column(String(20), nullable=True)  # Low, Medium, High
    anomaly_flags = Column(JSON, nullable=True)

    # Speaker verification
    sv_similarity = Column(Float, nullable=True)
    sv_verified = Column(Boolean, nullable=True)

    # Auth
    auth_method = Column(String(20), nullable=True)  # pin_only, step_up, block
    auth_passed = Column(Boolean, default=False)

    # Razorpay
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)
    payment_status = Column(String(20), default="pending")  # pending, created, captured, failed, blocked

    # Metadata
    status = Column(String(20), default="initiated")  # initiated, processing, completed, failed, blocked
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, amount=₹{self.amount_inr}, status='{self.status}')>"


class AuditLog(Base):
    """Audit log for tracking all pipeline events."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # stt, sv, intent, fraud, auth, payment
    event_data = Column(JSON, nullable=True)
    severity = Column(String(20), default="info")  # info, warning, error, critical
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, type='{self.event_type}')>"
