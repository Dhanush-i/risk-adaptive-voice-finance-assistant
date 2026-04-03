"""
Comprehensive Test Suite
=========================
Tests all ML modules, API endpoints, database operations, and integration flow.

Usage: python scripts/test_all.py
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import subprocess
import signal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Pre-import heavy modules to avoid Windows import locks
# (when server is running in another process and sharing .pyc files)
try:
    import numpy
    import torch
    import sklearn
except ImportError:
    pass

PASS = 0
FAIL = 0
TESTS = []

API_BASE = "http://127.0.0.1:8000"


def test(name):
    """Decorator to register and run a test."""
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_test(name, func):
    """Run a single test and track results."""
    global PASS, FAIL
    try:
        func()
        PASS += 1
        print(f"  ✅ {name}")
        return True
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}: {e}")
        return False


# ================================================================
# UNIT TESTS — ML Modules
# ================================================================

@test("Config loads correctly")
def test_config():
    from backend.app.core.config import get_config
    config = get_config()
    assert config.project_name, "Project name is empty"
    assert config.database_url, "DB URL is empty"
    assert config.razorpay_currency == "INR", f"Currency is {config.razorpay_currency}"


@test("Intent dataset exists")
def test_intent_dataset():
    path = "ml/data/intent_dataset.csv"
    assert os.path.exists(path), f"File not found: {path}"
    lines = sum(1 for _ in open(path)) - 1
    assert lines >= 400, f"Too few samples: {lines}"


@test("Fraud dataset exists")
def test_fraud_dataset():
    path = "ml/data/fraud_dataset.csv"
    assert os.path.exists(path), f"File not found: {path}"
    lines = sum(1 for _ in open(path)) - 1
    assert lines >= 9000, f"Too few samples: {lines}"


@test("Intent model loads and classifies")
def test_intent_classifier():
    from ml.modules.intent_classifier import IntentClassifier
    ic = IntentClassifier()
    ic.load_model()
    result = ic.classify("send 100 rupees to rahul")
    assert result["intent"] == "send_money", f"Wrong intent: {result['intent']}"
    assert result["confidence"] > 0.5, f"Low confidence: {result['confidence']}"
    assert result["entities"].get("amount") == 100.0, f"Wrong amount: {result['entities']}"


@test("Intent classifier handles all intents")
def test_intent_all_classes():
    from ml.modules.intent_classifier import IntentClassifier
    ic = IntentClassifier()
    ic.load_model()

    tests = [
        ("send 50 to priya", "send_money"),
        ("what is my balance", "check_balance"),
        ("show last 5 transactions", "transaction_history"),
        ("pay electricity bill", "pay_bill"),
    ]
    for text, expected in tests:
        result = ic.classify(text)
        assert result["intent"] == expected, f"'{text}' → {result['intent']} (expected {expected})"


@test("Fraud model loads and predicts")
def test_fraud_detector():
    from ml.modules.fraud_detector import FraudDetector
    fd = FraudDetector()
    fd.load_model()

    # Normal transaction
    normal = {
        "amount": 100, "hour_of_day": 14, "day_of_week": 2,
        "transaction_frequency": 3, "avg_transaction_amount": 150,
        "amount_deviation": 0.33, "time_since_last_transaction": 120,
        "is_new_recipient": 0, "failed_auth_attempts": 0,
    }
    result = fd.predict(normal)
    assert "risk_score" in result, "Missing risk_score"
    assert result["risk_tier"] in ("Low", "Medium", "High"), f"Invalid tier: {result['risk_tier']}"


@test("Fraud detector flags suspicious transactions")
def test_fraud_suspicious():
    from ml.modules.fraud_detector import FraudDetector
    fd = FraudDetector()
    fd.load_model()

    suspicious = {
        "amount": 5000, "hour_of_day": 3, "day_of_week": 1,
        "transaction_frequency": 15, "avg_transaction_amount": 200,
        "amount_deviation": 24.0, "time_since_last_transaction": 2,
        "is_new_recipient": 1, "failed_auth_attempts": 3,
    }
    result = fd.predict(suspicious)
    assert len(result["anomaly_flags"]) > 0, "No anomaly flags for suspicious txn"


@test("Auth logic — low risk allows proceed")
def test_auth_low():
    from ml.modules.auth_logic import AuthLogic
    al = AuthLogic()
    result = al.evaluate(
        fraud_result={"risk_score": 0.1, "risk_tier": "Low", "anomaly_flags": []},
        sv_result={"speaker_id": "test", "similarity_score": 0.9, "verified": True},
    )
    assert result["proceed"] is True, "Should proceed on low risk"
    assert result["auth_required"] == "pin_only", f"Expected pin_only, got {result['auth_required']}"


@test("Auth logic — high risk blocks")
def test_auth_high():
    from ml.modules.auth_logic import AuthLogic
    al = AuthLogic()
    result = al.evaluate(
        fraud_result={"risk_score": 0.9, "risk_tier": "High", "anomaly_flags": ["HIGH_AMOUNT"]},
        sv_result={"speaker_id": "test", "similarity_score": 0.8, "verified": True},
    )
    assert result["proceed"] is False, "Should block on high risk"
    assert result["auth_required"] == "block", f"Expected block, got {result['auth_required']}"


@test("Auth logic — SV failure blocks")
def test_auth_sv_fail():
    from ml.modules.auth_logic import AuthLogic
    al = AuthLogic()
    result = al.evaluate(
        fraud_result={"risk_score": 0.1, "risk_tier": "Low", "anomaly_flags": []},
        sv_result={"speaker_id": "test", "similarity_score": 0.1, "verified": False},
    )
    assert result["proceed"] is False, "Should block when SV fails"


@test("PIN hashing and validation")
def test_pin_hash():
    from ml.modules.auth_logic import AuthLogic
    al = AuthLogic()
    hashed = al.hash_pin("1234")
    assert al.validate_pin("1234", hashed), "Valid PIN should match"
    assert not al.validate_pin("0000", hashed), "Wrong PIN should not match"


@test("Entity extraction — amounts")
def test_entity_amounts():
    from ml.modules.intent_classifier import IntentClassifier
    ic = IntentClassifier()
    entities = ic.extract_entities("send 500 rupees to rahul", "send_money")
    assert entities.get("amount") == 500.0, f"Expected 500, got {entities.get('amount')}"
    assert entities.get("recipient") == "rahul", f"Expected rahul, got {entities.get('recipient')}"


@test("Entity extraction — bill types")
def test_entity_bills():
    from ml.modules.intent_classifier import IntentClassifier
    ic = IntentClassifier()
    entities = ic.extract_entities("pay electricity bill of 200 rupees", "pay_bill")
    assert entities.get("bill_type") == "electricity", f"Expected electricity, got {entities.get('bill_type')}"
    assert entities.get("amount") == 200.0, f"Expected 200, got {entities.get('amount')}"


# ================================================================
# DATABASE TESTS
# ================================================================

@test("Database tables exist")
def test_db_tables():
    from backend.app.core.config import get_config
    from backend.app.db.database import init_db, Base
    from backend.app.db.models import User, Transaction, SpeakerProfile, AuditLog

    config = get_config()
    engine, SessionLocal = init_db(config.database_url)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    user_count = session.query(User).count()
    assert user_count >= 1, f"Expected at least 1 user, got {user_count}"
    session.close()


@test("Demo user exists with correct data")
def test_demo_user():
    from backend.app.core.config import get_config
    from backend.app.db.database import init_db
    from backend.app.db.models import User

    config = get_config()
    _, SessionLocal = init_db(config.database_url)
    session = SessionLocal()

    user = session.query(User).filter_by(username="demo_user").first()
    assert user is not None, "Demo user not found"
    assert user.display_name == "Demo User", f"Wrong name: {user.display_name}"
    assert user.balance >= 0, f"Negative balance: {user.balance}"
    assert user.pin_hash, "PIN hash is empty"
    session.close()


# ================================================================
# API TESTS (requires running server)
# ================================================================

def api_get(path):
    r = urllib.request.urlopen(f"{API_BASE}{path}")
    return json.loads(r.read())


def api_post_form(path, data):
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"{API_BASE}{path}", data=encoded)
    r = urllib.request.urlopen(req)
    return json.loads(r.read())


def api_post_json(path, data):
    encoded = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=encoded,
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read())


@test("API: Health check")
def test_api_health():
    result = api_get("/health")
    assert result["status"] == "ok", f"Health status: {result['status']}"
    assert result["models_loaded"]["intent_classifier"] is True, "IC not loaded"
    assert result["models_loaded"]["fraud_detector"] is True, "FD not loaded"


@test("API: Get user")
def test_api_get_user():
    result = api_get("/api/v1/users/demo_user")
    assert result["username"] == "demo_user"
    assert result["balance"] >= 0


@test("API: Get balance")
def test_api_balance():
    result = api_get("/api/v1/users/demo_user/balance")
    assert result["currency"] == "INR"
    assert "balance" in result


@test("API: Text pipeline — send money")
def test_api_pipeline_send():
    result = api_post_form("/api/v1/voice/process-text", {
        "text": "send 5 rupees to rahul",
        "user_id": "demo_user",
        "sv_override": "true",
    })
    assert result["transaction_id"] > 0, "No transaction ID"
    assert len(result["stages"]) >= 4, f"Only {len(result['stages'])} stages"

    # Check intent was classified correctly
    intent_stage = next((s for s in result["stages"] if s["stage"] == "intent_classification"), None)
    assert intent_stage is not None, "No intent stage"
    assert intent_stage["data"]["intent"] == "send_money"
    assert intent_stage["data"]["entities"]["amount"] == 5.0


@test("API: Text pipeline — check balance")
def test_api_pipeline_balance():
    result = api_post_form("/api/v1/voice/process-text", {
        "text": "what is my balance",
        "user_id": "demo_user",
        "sv_override": "true",
    })
    intent_stage = next((s for s in result["stages"] if s["stage"] == "intent_classification"), None)
    assert intent_stage["data"]["intent"] == "check_balance"


@test("API: PIN verification — correct PIN")
def test_api_pin_correct():
    # First create a transaction
    pipeline = api_post_form("/api/v1/voice/process-text", {
        "text": "send 1 rupee to test",
        "user_id": "demo_user",
        "sv_override": "true",
    })
    txn_id = pipeline["transaction_id"]

    result = api_post_json("/api/v1/payments/verify-pin", {
        "user_id": "demo_user",
        "pin": "1234",
        "transaction_id": txn_id,
    })
    assert result["success"] is True, f"PIN verification failed: {result['message']}"


@test("API: PIN verification — wrong PIN")
def test_api_pin_wrong():
    pipeline = api_post_form("/api/v1/voice/process-text", {
        "text": "send 2 rupees to test",
        "user_id": "demo_user",
        "sv_override": "true",
    })
    txn_id = pipeline["transaction_id"]

    result = api_post_json("/api/v1/payments/verify-pin", {
        "user_id": "demo_user",
        "pin": "0000",
        "transaction_id": txn_id,
    })
    assert result["success"] is False, "Wrong PIN should fail"


@test("API: Transaction history")
def test_api_txn_history():
    result = api_get("/api/v1/transactions/?username=demo_user")
    assert "transactions" in result
    assert result["total"] >= 1, "Should have at least 1 transaction"


@test("API: Transaction detail with audit trail")
def test_api_txn_detail():
    history = api_get("/api/v1/transactions/?username=demo_user&limit=1")
    if history["transactions"]:
        txn_id = history["transactions"][0]["id"]
        detail = api_get(f"/api/v1/transactions/{txn_id}")
        assert "transaction" in detail
        assert "audit_trail" in detail
        assert detail["transaction"]["id"] == txn_id


@test("API: 404 for unknown user")
def test_api_404():
    try:
        api_get("/api/v1/users/nonexistent_user_xyz")
        assert False, "Should have thrown 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"


# ================================================================
# MAIN
# ================================================================

def check_server():
    """Check if the backend server is running."""
    try:
        urllib.request.urlopen(f"{API_BASE}/health", timeout=2)
        return True
    except Exception:
        return False


def main():
    global PASS, FAIL

    print("=" * 60)
    print("🧪 VoicePay — Comprehensive Test Suite")
    print("=" * 60)

    # Run unit tests (no server needed)
    print("\n── Unit Tests ──────────────────────────────")
    unit_tests = [t for t in TESTS if not t[0].startswith("API:")]
    for name, func in unit_tests:
        run_test(name, func)

    # Run API tests (server needed)
    print("\n── API Tests ───────────────────────────────")
    server_running = check_server()
    server_proc = None

    if not server_running:
        print("  ⏳ Starting backend server for API tests...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for server to be ready
        for _ in range(15):
            time.sleep(1)
            if check_server():
                break
        else:
            print("  ❌ Could not start server!")
            FAIL += len([t for t in TESTS if t[0].startswith("API:")])

    if check_server():
        api_tests = [t for t in TESTS if t[0].startswith("API:")]
        for name, func in api_tests:
            run_test(name, func)
    else:
        print("  ⚠️  Server not available — skipping API tests")

    # Cleanup
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    # Summary
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"Test Results: {PASS}/{total} passed")
    print(f"{'=' * 60}")

    if FAIL == 0:
        print(f"\n🎉 All {total} tests passed!")
    else:
        print(f"\n⚠️  {FAIL} test(s) failed")

    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
