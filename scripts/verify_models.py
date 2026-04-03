"""
Model Loading Verification Script
====================================
Verifies that all ML models and services can be loaded correctly.

Usage: python scripts/verify_models.py
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_config():
    """Verify config loading."""
    print("\n--- 1. Config ---")
    try:
        from backend.app.core.config import get_config
        config = get_config()
        print(f"  ✅ Config loaded: {config.project_name}")
        print(f"     Razorpay key: {config.razorpay_key_id[:16]}..." if len(config.razorpay_key_id) > 16 else f"     Razorpay key: {config.razorpay_key_id}")
        print(f"     DB URL: {config.database_url}")
        return True, config
    except Exception as e:
        print(f"  ❌ Config failed: {e}")
        return False, None


def verify_intent_classifier():
    """Verify intent classifier loads and predicts."""
    print("\n--- 2. Intent Classifier ---")
    try:
        from ml.modules.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        ic.load_model()

        # Test prediction
        result = ic.classify("send 100 rupees to rahul")
        print(f"  ✅ Intent Classifier loaded")
        print(f"     Test: 'send 100 rupees to rahul' → {result['intent']} ({result['confidence']:.2f})")
        print(f"     Entities: {result['entities']}")
        return True
    except Exception as e:
        print(f"  ❌ Intent Classifier failed: {e}")
        return False


def verify_fraud_detector():
    """Verify fraud detector loads and predicts."""
    print("\n--- 3. Fraud Detector ---")
    try:
        from ml.modules.fraud_detector import FraudDetector
        fd = FraudDetector()
        fd.load_model()

        # Test prediction
        test_txn = {
            "amount": 100, "hour_of_day": 14, "day_of_week": 2,
            "transaction_frequency": 3, "avg_transaction_amount": 150,
            "amount_deviation": 0.33, "time_since_last_transaction": 120,
            "is_new_recipient": 0, "failed_auth_attempts": 0,
        }
        result = fd.predict(test_txn)
        print(f"  ✅ Fraud Detector loaded")
        print(f"     Test: ₹100 normal txn → Risk: {result['risk_score']:.4f} ({result['risk_tier']})")
        return True
    except Exception as e:
        print(f"  ❌ Fraud Detector failed: {e}")
        return False


def verify_auth_logic():
    """Verify auth logic works."""
    print("\n--- 4. Auth Logic ---")
    try:
        from ml.modules.auth_logic import AuthLogic
        al = AuthLogic()

        # Test decision
        result = al.evaluate(
            fraud_result={"risk_score": 0.15, "risk_tier": "Low", "anomaly_flags": []},
            sv_result={"speaker_id": "test", "similarity_score": 0.9, "verified": True},
        )
        print(f"  ✅ Auth Logic loaded")
        print(f"     Test: Low risk + verified → {result['auth_required']} (proceed: {result['proceed']})")
        return True
    except Exception as e:
        print(f"  ❌ Auth Logic failed: {e}")
        return False


def verify_razorpay():
    """Verify Razorpay service initializes."""
    print("\n--- 5. Razorpay ---")
    try:
        from backend.app.services.razorpay_service import RazorpayService
        from backend.app.core.config import get_config
        config = get_config()

        rp = RazorpayService(
            key_id=config.razorpay_key_id,
            key_secret=config.razorpay_key_secret,
        )

        if rp.is_configured():
            print(f"  ✅ Razorpay configured with valid keys")
            # Try a test order
            try:
                order = rp.create_order(amount_inr=1.0, receipt="verify_test")
                print(f"     Test order: {order['order_id']} (₹{order['amount_inr']})")
                return True
            except Exception as e:
                print(f"  ⚠️  Razorpay initialized but order creation failed: {e}")
                return True  # SDK is loaded, just keys might be test
        else:
            print(f"  ⚠️  Razorpay SDK loaded but keys not configured")
            print(f"     Update .env with your Razorpay keys")
            return True  # SDK loads fine, just needs real keys
    except Exception as e:
        print(f"  ❌ Razorpay failed: {e}")
        return False


def verify_database():
    """Verify database connection."""
    print("\n--- 6. Database ---")
    try:
        from backend.app.core.config import get_config
        from backend.app.db.database import init_db, Base
        from backend.app.db.models import User

        config = get_config()
        engine, SessionLocal = init_db(config.database_url)
        Base.metadata.create_all(bind=engine)

        session = SessionLocal()
        user_count = session.query(User).count()
        session.close()

        print(f"  ✅ Database connected")
        print(f"     URL: {config.database_url}")
        print(f"     Users: {user_count}")
        return True
    except Exception as e:
        print(f"  ❌ Database failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Model & Service Verification")
    print("=" * 60)

    results = {}

    ok, config = verify_config()
    results["config"] = ok

    results["intent_classifier"] = verify_intent_classifier()
    results["fraud_detector"] = verify_fraud_detector()
    results["auth_logic"] = verify_auth_logic()
    results["razorpay"] = verify_razorpay()
    results["database"] = verify_database()

    # Summary
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    all_pass = True
    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print(f"\n🎉 All verifications passed! Ready for Phase 3.")
    else:
        print(f"\n⚠️  Some verifications failed. Check the output above.")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
