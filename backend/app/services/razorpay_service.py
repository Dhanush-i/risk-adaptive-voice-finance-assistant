"""
Razorpay Service — Payment Integration
========================================
Handles Razorpay order creation, payment verification, and signature validation.

Uses Razorpay Orders API for server-side order creation and
Razorpay Checkout.js on the frontend for payment collection.

Flow:
  1. Server creates order via Razorpay Orders API
  2. Frontend opens Razorpay Checkout with order_id
  3. User completes payment on Razorpay's secure page
  4. Frontend sends payment details back to server
  5. Server verifies signature and captures payment
"""

import hmac
import hashlib
import razorpay
from typing import Dict, Any, Optional


class RazorpayService:
    """Service for Razorpay payment operations."""

    def __init__(self, key_id: str, key_secret: str, currency: str = "INR"):
        """
        Initialize Razorpay client.

        Args:
            key_id: Razorpay API Key ID (starts with rzp_test_ or rzp_live_)
            key_secret: Razorpay API Key Secret
            currency: Default currency (INR)
        """
        self.key_id = key_id
        self.key_secret = key_secret
        self.currency = currency

        self.client = razorpay.Client(auth=(key_id, key_secret))
        print(f"[Razorpay] Client initialized (key: {key_id[:12]}...)")

    def create_order(
        self,
        amount_inr: float,
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Razorpay order.

        Args:
            amount_inr: Amount in INR (will be converted to paise).
            receipt: Optional receipt ID for tracking.
            notes: Optional key-value notes for the order.

        Returns:
            Razorpay order response with order_id, amount, status, etc.

        Raises:
            razorpay.errors.BadRequestError: If amount is invalid.
        """
        # Convert INR to paise (Razorpay expects amount in smallest currency unit)
        amount_paise = int(round(amount_inr * 100))

        if amount_paise <= 0:
            raise ValueError(f"Amount must be positive. Got: ₹{amount_inr}")

        order_data = {
            "amount": amount_paise,
            "currency": self.currency,
            "payment_capture": 1,  # Auto-capture
        }

        if receipt:
            order_data["receipt"] = receipt
        if notes:
            order_data["notes"] = notes

        print(f"[Razorpay] Creating order: ₹{amount_inr} ({amount_paise} paise)")

        order = self.client.order.create(data=order_data)

        print(f"[Razorpay] Order created: {order['id']} (status: {order['status']})")

        return {
            "order_id": order["id"],
            "amount_paise": order["amount"],
            "amount_inr": order["amount"] / 100,
            "currency": order["currency"],
            "status": order["status"],
            "key_id": self.key_id,  # Frontend needs this for Checkout.js
            "receipt": order.get("receipt"),
        }

    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """
        Verify Razorpay payment signature to confirm authenticity.

        The signature is a HMAC-SHA256 of "order_id|payment_id" using the key_secret.

        Args:
            order_id: Razorpay order ID.
            payment_id: Razorpay payment ID.
            signature: Razorpay signature from frontend callback.

        Returns:
            True if signature is valid, False otherwise.
        """
        try:
            # Method 1: Use Razorpay SDK's built-in verification
            self.client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
            print(f"[Razorpay] ✅ Signature verified for payment {payment_id}")
            return True
        except razorpay.errors.SignatureVerificationError:
            print(f"[Razorpay] ❌ Signature verification failed for payment {payment_id}")
            return False

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details from Razorpay.

        Args:
            payment_id: Razorpay payment ID.

        Returns:
            Payment details including status, amount, method, etc.
        """
        payment = self.client.payment.fetch(payment_id)

        return {
            "payment_id": payment["id"],
            "amount_inr": payment["amount"] / 100,
            "currency": payment["currency"],
            "status": payment["status"],  # captured, authorized, failed, etc.
            "method": payment.get("method"),  # card, upi, netbanking, etc.
            "email": payment.get("email"),
            "contact": payment.get("contact"),
            "order_id": payment.get("order_id"),
            "description": payment.get("description"),
            "created_at": payment.get("created_at"),
        }

    def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """
        Fetch order details from Razorpay.

        Args:
            order_id: Razorpay order ID.

        Returns:
            Order details including status, amount, payments.
        """
        order = self.client.order.fetch(order_id)

        return {
            "order_id": order["id"],
            "amount_inr": order["amount"] / 100,
            "currency": order["currency"],
            "status": order["status"],
            "attempts": order.get("attempts"),
            "created_at": order.get("created_at"),
        }

    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured with valid-looking keys."""
        return (
            self.key_id
            and self.key_secret
            and not self.key_id.startswith("RAZORPAY_")
            and not self.key_secret.startswith("RAZORPAY_")
            and len(self.key_id) > 10
        )


# --- Standalone Test ---
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backend.app.core.config import get_config

    print("=" * 60)
    print("Razorpay Service — Configuration Test")
    print("=" * 60)

    config = get_config()

    rp = RazorpayService(
        key_id=config.razorpay_key_id,
        key_secret=config.razorpay_key_secret,
        currency=config.razorpay_currency,
    )

    if rp.is_configured():
        print("\n✅ Razorpay is configured with valid keys!")
        print(f"   Key ID: {rp.key_id[:16]}...")

        # Try creating a test order (₹1)
        try:
            order = rp.create_order(
                amount_inr=1.0,
                receipt="test_receipt_001",
                notes={"purpose": "connectivity_test"},
            )
            print(f"\n✅ Test order created successfully!")
            print(f"   Order ID:  {order['order_id']}")
            print(f"   Amount:    ₹{order['amount_inr']}")
            print(f"   Status:    {order['status']}")
        except Exception as e:
            print(f"\n❌ Order creation failed: {e}")
            print("   This is expected if using placeholder keys.")
    else:
        print("\n⚠️  Razorpay keys not configured yet.")
        print("   Update .env with your actual Razorpay test keys:")
        print("   RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXX")
        print("   RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXX")
        print("\n   Razorpay will work once you add your keys!")

    print("\n✅ Razorpay service test completed!")
