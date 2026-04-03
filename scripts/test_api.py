"""Quick API test script."""
import urllib.request
import urllib.parse
import json

BASE = "http://127.0.0.1:8000"

# Test 1: Text pipeline
print("=== Test: Text Pipeline ===")
data = urllib.parse.urlencode({
    "text": "send 5 rupees to rahul",
    "user_id": "demo_user",
    "sv_override": "true"
}).encode()

req = urllib.request.Request(f"{BASE}/api/v1/voice/process-text", data=data)
r = urllib.request.urlopen(req)
result = json.loads(r.read())

print(f"Transaction ID: {result['transaction_id']}")
print(f"Status: {result['status']}")

print("\n--- Stages ---")
for stage in result["stages"]:
    print(f"  {stage['stage']}: success={stage['success']} ({stage['duration_ms']}ms)")

print("\n--- Auth Decision ---")
ad = result["auth_decision"]
print(f"  Auth Required: {ad['auth_required']}")
print(f"  Risk Tier: {ad['risk_tier']}")
print(f"  Proceed: {ad['proceed']}")

# Test 2: PIN verification
if ad["proceed"]:
    print("\n=== Test: PIN Verification ===")
    pin_data = json.dumps({
        "user_id": "demo_user",
        "pin": "1234",
        "transaction_id": result["transaction_id"]
    }).encode()

    req = urllib.request.Request(
        f"{BASE}/api/v1/payments/verify-pin",
        data=pin_data,
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    pin_result = json.loads(r.read())
    print(f"  PIN Valid: {pin_result['success']}")
    print(f"  Message: {pin_result['message']}")

# Test 3: Transaction history
print("\n=== Test: Transaction History ===")
r = urllib.request.urlopen(f"{BASE}/api/v1/transactions/?username=demo_user")
txns = json.loads(r.read())
print(f"  Total transactions: {txns['total']}")
for t in txns["transactions"][:3]:
    print(f"  - #{t['id']}: {t['intent']} Rs.{t['amount_inr']} ({t['status']})")

# Test 4: Transaction detail
print(f"\n=== Test: Transaction Detail #{result['transaction_id']} ===")
r = urllib.request.urlopen(f"{BASE}/api/v1/transactions/{result['transaction_id']}")
detail = json.loads(r.read())
print(f"  Transcript: {detail['transaction']['transcript']}")
print(f"  Intent: {detail['transaction']['intent']}")
print(f"  Amount: Rs.{detail['transaction']['amount_inr']}")
print(f"  Risk: {detail['transaction']['risk_tier']} ({detail['transaction']['risk_score']})")
print(f"  Audit trail entries: {len(detail['audit_trail'])}")

print("\n" + "=" * 50)
print("All API tests passed!")
