"""
Payment API Routes
===================
Endpoints for Razorpay order creation, PIN verification, and payment verification.
"""

import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User, Transaction, AuditLog
from backend.app.schemas.schemas import (
    PinVerifyRequest, PinVerifyResponse,
    RazorpayOrderResponse, RazorpayPaymentVerification, RazorpayPaymentResponse,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_app_state():
    from backend.app.main import app_state
    return app_state


@router.post("/verify-pin", response_model=PinVerifyResponse)
async def verify_pin(
    request: PinVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify the user's PIN for a pending transaction.
    If successful and transaction is authorized, creates a Razorpay order.
    """
    app_state = get_app_state()

    # Get user
    user = db.query(User).filter_by(username=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get transaction
    transaction = db.query(Transaction).filter_by(
        id=request.transaction_id,
        user_id=user.id,
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status not in ("processing", "initiated"):
        raise HTTPException(
            status_code=400,
            detail=f"Transaction is not in a verifiable state (status: {transaction.status})"
        )

    # Verify PIN
    al = app_state.get("auth_logic")
    if al is None:
        raise HTTPException(status_code=500, detail="Auth logic not available")

    pin_valid = al.validate_pin(request.pin, user.pin_hash)

    if not pin_valid:
        # Log failed attempt
        log = AuditLog(
            transaction_id=transaction.id,
            user_id=user.id,
            event_type="pin_verification",
            event_data={"success": False},
            severity="warning",
        )
        db.add(log)
        db.commit()

        return PinVerifyResponse(
            success=False,
            message="❌ Invalid PIN. Please try again.",
        )

    # PIN verified — update transaction
    transaction.auth_passed = True

    # Log success
    log = AuditLog(
        transaction_id=transaction.id,
        user_id=user.id,
        event_type="pin_verification",
        event_data={"success": True},
        severity="info",
    )
    db.add(log)
    db.commit()

    return PinVerifyResponse(
        success=True,
        message="✅ PIN verified successfully. Proceed to payment.",
    )


@router.post("/create-order")
async def create_razorpay_order(
    transaction_id: int,
    user_id: str,
    db: Session = Depends(get_db),
):
    """
    Create a Razorpay order for an authorized transaction.
    Called after PIN verification succeeds.
    """
    app_state = get_app_state()

    # Get user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get transaction
    transaction = db.query(Transaction).filter_by(
        id=transaction_id,
        user_id=user.id,
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if not transaction.auth_passed:
        raise HTTPException(status_code=403, detail="PIN verification required before creating order")

    if transaction.amount_inr <= 0:
        raise HTTPException(status_code=400, detail="Transaction amount must be positive")

    # Check Razorpay
    rp = app_state.get("razorpay_service")
    if rp is None or not rp.is_configured():
        raise HTTPException(status_code=503, detail="Razorpay is not configured. Add keys to .env")

    # Safety check: max amount
    config = app_state.get("config")
    max_amount = config.razorpay_max_amount_paise / 100 if config else 1000
    if transaction.amount_inr > max_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Amount ₹{transaction.amount_inr} exceeds maximum ₹{max_amount}"
        )

    try:
        # Create Razorpay order
        order = rp.create_order(
            amount_inr=transaction.amount_inr,
            receipt=f"txn_{transaction.id}",
            notes={
                "transaction_id": str(transaction.id),
                "user": user.username,
                "intent": transaction.intent or "",
                "recipient": transaction.recipient or "",
            },
        )

        # Update transaction with order ID
        transaction.razorpay_order_id = order["order_id"]
        transaction.payment_status = "created"

        # Log
        log = AuditLog(
            transaction_id=transaction.id,
            user_id=user.id,
            event_type="razorpay_order",
            event_data=order,
            severity="info",
        )
        db.add(log)
        db.commit()

        return {
            "order_id": order["order_id"],
            "amount_paise": order["amount_paise"],
            "amount_inr": order["amount_inr"],
            "currency": order["currency"],
            "key_id": order["key_id"],
            "status": order["status"],
            "transaction_id": transaction.id,
            "user_display_name": user.display_name,
            "recipient": transaction.recipient,
        }

    except Exception as e:
        transaction.payment_status = "failed"
        transaction.error_message = f"Razorpay order failed: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create Razorpay order: {str(e)}")


@router.post("/verify-payment", response_model=RazorpayPaymentResponse)
async def verify_payment(
    verification: RazorpayPaymentVerification,
    db: Session = Depends(get_db),
):
    """
    Verify a Razorpay payment after frontend checkout completion.
    Validates the payment signature and marks transaction as completed.
    """
    app_state = get_app_state()

    rp = app_state.get("razorpay_service")
    if rp is None or not rp.is_configured():
        raise HTTPException(status_code=503, detail="Razorpay is not configured")

    # Find transaction by order ID
    transaction = db.query(Transaction).filter_by(
        razorpay_order_id=verification.razorpay_order_id,
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found for this order")

    # Verify signature
    is_valid = rp.verify_payment_signature(
        order_id=verification.razorpay_order_id,
        payment_id=verification.razorpay_payment_id,
        signature=verification.razorpay_signature,
    )

    if is_valid:
        # Payment verified!
        transaction.razorpay_payment_id = verification.razorpay_payment_id
        transaction.razorpay_signature = verification.razorpay_signature
        transaction.payment_status = "captured"
        transaction.status = "completed"
        transaction.completed_at = datetime.datetime.utcnow()

        # Deduct from user balance (demo tracking)
        user = db.query(User).filter_by(id=transaction.user_id).first()
        if user:
            user.balance = max(0, user.balance - transaction.amount_inr)
            
            # Trigger adaptive learning
            fd = app_state.get("fraud_detector")
            if fd:
                fd.learn(transaction={"amount": transaction.amount_inr}, user_id=user.username)

        # Log
        log = AuditLog(
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            event_type="payment_verified",
            event_data={
                "payment_id": verification.razorpay_payment_id,
                "order_id": verification.razorpay_order_id,
                "amount_inr": transaction.amount_inr,
            },
            severity="info",
        )
        db.add(log)
        db.commit()

        return RazorpayPaymentResponse(
            success=True,
            payment_id=verification.razorpay_payment_id,
            order_id=verification.razorpay_order_id,
            amount_inr=transaction.amount_inr,
            status="captured",
            message=f"✅ Payment of ₹{transaction.amount_inr} completed successfully!",
        )
    else:
        # Signature invalid
        transaction.payment_status = "failed"
        transaction.status = "failed"
        transaction.error_message = "Payment signature verification failed"

        log = AuditLog(
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            event_type="payment_verification_failed",
            event_data={
                "payment_id": verification.razorpay_payment_id,
                "order_id": verification.razorpay_order_id,
            },
            severity="critical",
        )
        db.add(log)
        db.commit()

        return RazorpayPaymentResponse(
            success=False,
            payment_id=verification.razorpay_payment_id,
            order_id=verification.razorpay_order_id,
            status="failed",
            message="❌ Payment verification failed. Signature mismatch.",
        )
