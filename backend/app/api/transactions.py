"""
Transaction API Routes
=======================
Endpoints for transaction history and details.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.db.database import get_db
from backend.app.db.models import User, Transaction, AuditLog

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/")
async def list_transactions(
    username: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """Get transaction history for a user."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    query = db.query(Transaction).filter_by(user_id=user.id)

    if status:
        query = query.filter_by(status=status)

    total = query.count()

    transactions = query.order_by(
        Transaction.created_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "transactions": [
            {
                "id": t.id,
                "transcript": t.transcript,
                "intent": t.intent,
                "amount_inr": t.amount_inr,
                "recipient": t.recipient,
                "risk_tier": t.risk_tier,
                "risk_score": t.risk_score,
                "auth_method": t.auth_method,
                "payment_status": t.payment_status,
                "status": t.status,
                "razorpay_order_id": t.razorpay_order_id,
                "razorpay_payment_id": t.razorpay_payment_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in transactions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed transaction info including audit trail."""
    transaction = db.query(Transaction).filter_by(id=transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Get audit logs for this transaction
    logs = db.query(AuditLog).filter_by(
        transaction_id=transaction_id
    ).order_by(AuditLog.created_at.asc()).all()

    return {
        "transaction": {
            "id": transaction.id,
            "user_id": transaction.user_id,
            "transcript": transaction.transcript,
            "intent": transaction.intent,
            "intent_confidence": transaction.intent_confidence,
            "amount_inr": transaction.amount_inr,
            "recipient": transaction.recipient,
            "bill_type": transaction.bill_type,
            "risk_score": transaction.risk_score,
            "risk_tier": transaction.risk_tier,
            "anomaly_flags": transaction.anomaly_flags,
            "sv_similarity": transaction.sv_similarity,
            "sv_verified": transaction.sv_verified,
            "auth_method": transaction.auth_method,
            "auth_passed": transaction.auth_passed,
            "payment_status": transaction.payment_status,
            "razorpay_order_id": transaction.razorpay_order_id,
            "razorpay_payment_id": transaction.razorpay_payment_id,
            "status": transaction.status,
            "error_message": transaction.error_message,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
        },
        "audit_trail": [
            {
                "event_type": log.event_type,
                "event_data": log.event_data,
                "severity": log.severity,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
