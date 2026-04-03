# Risk-Adaptive Voice-Based Financial Assistant — Project Blueprint

## North Star
A voice-first financial assistant that listens to spoken commands, verifies the speaker's identity,
classifies intent, assesses fraud risk, and executes **real payments via Razorpay** — all gated by
an adaptive authentication policy.

## Architecture: A.N.T. 3-Layer Model
1. **Access Layer** — Voice input capture (browser MediaRecorder API), STT (Whisper), Speaker Verification (ECAPA-TDNN)
2. **Negotiation Layer** — Intent Classification (LSTM), Fraud Detection (IsolationForest + RandomForest), Auth Logic (risk tiers)
3. **Transaction Layer** — Razorpay Orders API, Payment Verification, Transaction Logging

## Protocol: B.L.A.S.T.
- **B**lueprint — Project structure, configs, schemas (Phase 0)
- **L**ogic — ML models & training pipelines (Phase 1)
- **A**rchitect — Backend API & orchestration (Phase 2-3)
- **S**tylize — Frontend UI & UX (Phase 4)
- **T**rigger — Deployment, testing, demo (Phase 5)

---

## Pipeline Flow

```
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌───────────────┐    ┌───────────┐    ┌──────────┐
│  Audio   │───▶│   STT    │───▶│   Speaker    │───▶│    Intent     │───▶│   Fraud   │───▶│   Auth   │
│  Input   │    │ (Whisper)│    │ Verification │    │ Classification│    │ Detection │    │  Logic   │
└──────────┘    └──────────┘    └──────────────┘    └───────────────┘    └───────────┘    └──────────┘
                                                                                               │
                                                                                               ▼
                                                                                    ┌──────────────────┐
                                                                                    │  Razorpay Payment │
                                                                                    │  (if authorized)  │
                                                                                    └──────────────────┘
```

---

## Data Schemas

### STT Output
```json
{
  "transcript": "send 5 rupees to rahul",
  "language": "en",
  "confidence": 0.94
}
```

### Speaker Verification Output
```json
{
  "speaker_id": "user_001",
  "similarity_score": 0.87,
  "verified": true
}
```

### Intent Classification Output
```json
{
  "intent": "send_money",
  "confidence": 0.92,
  "entities": {
    "amount": 5.0,
    "currency": "INR",
    "recipient": "rahul"
  }
}
```

### Fraud Detection Output
```json
{
  "risk_score": 0.23,
  "risk_tier": "Low",
  "anomaly_flags": []
}
```

### Auth Decision Output
```json
{
  "auth_required": "pin_only",
  "risk_tier": "Low",
  "proceed": true,
  "message": "Please enter your PIN to confirm the transaction."
}
```

### Razorpay Transaction Output
```json
{
  "order_id": "order_XXXXXXX",
  "payment_id": "pay_XXXXXXX",
  "amount": 500,
  "currency": "INR",
  "status": "captured",
  "recipient": "rahul",
  "timestamp": "2026-04-02T23:40:00+05:30"
}
```

---

## Integration List
1. **OpenAI Whisper** — Speech-to-text (pretrained, `whisper-base`)
2. **SpeechBrain** — Speaker verification (ECAPA-TDNN, pretrained on VoxCeleb)
3. **PyTorch** — Intent classification (custom LSTM)
4. **scikit-learn** — Fraud detection (IsolationForest + RandomForest)
5. **Razorpay Python SDK** — Payment processing (Orders API, Payment Capture)
6. **Razorpay Checkout.js** — Frontend payment widget
7. **FastAPI** — Backend REST API
8. **SQLite + SQLAlchemy** — Data persistence
9. **React + Vite** — Frontend SPA

## Behavioral Rules
1. **Never bypass fraud detection** — Every transaction must pass through the full pipeline
2. **Never store raw PINs** — All PINs are bcrypt hashed
3. **Never process payment without speaker verification** — SV must pass before any payment
4. **Log everything** — All pipeline stages produce structured logs for audit
5. **Fail safe** — If any ML module errors, default to HIGH risk (block transaction)
6. **Razorpay signature verification** — Always verify payment signatures server-side
