"""
Auth Logic Module — Risk-Adaptive Policy Engine
=================================================
Determines the authentication method required based on the fraud risk tier.

Risk Tiers:
  - Low  → PIN only → proceed to Razorpay payment
  - Medium → Step-up (PIN + voice re-confirmation) → proceed to Razorpay payment
  - High → Block transaction + Alert (no payment initiated)

Speaker Verification Rules:
  - SV similarity < 0.35 → BLOCK (likely impostor)
  - SV similarity < threshold (0.45) but >= 0.35 → STEP-UP (uncertain, re-verify)
  - SV similarity >= threshold → PASS (verified speaker)

Input:  Fraud detection output + speaker verification output
Output: { "auth_required": str, "risk_tier": str, "proceed": bool, "message": str }
"""

import yaml
from typing import Dict, Any, Optional


class AuthLogic:
    """Risk-adaptive authentication policy engine."""

    # Hard block threshold — below this similarity, the voice is definitely wrong
    SV_HARD_BLOCK_THRESHOLD = 0.35

    def __init__(self, config_path: str = "architecture/config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        self.risk_tiers = config["auth"]["risk_tiers"]
        self.pin_hash_rounds = config["auth"]["pin_hash_rounds"]
        self.sv_threshold = config["speaker_verification"]["similarity_threshold"]

    def evaluate(
        self,
        fraud_result: Dict[str, Any],
        sv_result: Dict[str, Any],
        intent_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate the authentication requirements based on pipeline results.

        Args:
            fraud_result: Output from FraudDetector.predict()
            sv_result: Output from SpeakerVerification.verify_speaker()
            intent_result: Optional output from IntentClassifier.classify()

        Returns:
            Authentication decision with required method, proceed flag, and message.
        """

        risk_tier = fraud_result.get("risk_tier", "High")
        risk_score = fraud_result.get("risk_score", 1.0)
        anomaly_flags = fraud_result.get("anomaly_flags", [])

        speaker_verified = sv_result.get("verified", False)
        similarity_score = sv_result.get("similarity_score", 0.0)
        speaker_id = sv_result.get("speaker_id", "unknown")

        # --- Liveness / Anti-Spoofing Check ---
        is_live = sv_result.get("is_live", True)
        hfe_ratio = sv_result.get("hfe_ratio", 1.0)
        if not is_live:
            risk_tier = "High"
            risk_score = max(risk_score, 0.95)
            anomaly_flags.insert(0, f"SPOOF_DETECTED (HFE: {hfe_ratio:.3f})")

        # --- Speaker Verification Check ---
        sv_error = sv_result.get("error") or sv_result.get("note")
        sv_not_enrolled = (
            sv_error is not None
            or "no_audio_for_sv" in str(sv_error or "")
            or "not_enrolled" in str(sv_error or "")
            or "text_input_override" in str(sv_error or "")
            or (similarity_score == 0.0 and not speaker_verified)
        )

        intent = intent_result.get("intent", "") if intent_result else ""
        is_payment_intent = intent in ("send_money", "pay_bill")

        if not speaker_verified and not sv_not_enrolled and is_payment_intent:
            # Genuine SV mismatch for a payment — enrolled user, wrong voice
            if similarity_score < self.SV_HARD_BLOCK_THRESHOLD:
                # Hard block: similarity is way too low — likely an impostor
                risk_tier = "High"
                risk_score = max(risk_score, 0.90)
                anomaly_flags.insert(0, f"SV_MISMATCH_BLOCK ({similarity_score:.2f})")
            else:
                # Soft mismatch: similarity is borderline — require step-up
                if risk_tier == "Low":
                    risk_tier = "Medium"
                risk_score = max(risk_score, 0.55)
                anomaly_flags.insert(0, f"SV_MISMATCH ({similarity_score:.2f})")

        if not speaker_verified and sv_not_enrolled:
            # No enrollment or SV error — bump risk to Medium but don't block
            if risk_tier == "Low":
                risk_tier = "Medium"
                risk_score = max(risk_score, 0.35)

        # --- Risk-based Auth Decision ---
        tier_config = self.risk_tiers.get(risk_tier.lower(), self.risk_tiers["high"])
        auth_method = tier_config["auth_method"]

        if risk_tier == "Low":
            message = (
                f"✅ Low risk transaction (score: {risk_score:.2f}). "
                f"Speaker verified ({speaker_id}, similarity: {similarity_score:.2f}). "
                f"Please enter your PIN to confirm."
            )
            proceed = True

        elif risk_tier == "Medium":
            message = (
                f"⚠️ Medium risk detected (score: {risk_score:.2f}). "
                f"Step-up authentication required: PIN + voice re-confirmation."
            )
            if anomaly_flags:
                message += f"\nFlags: {', '.join(anomaly_flags[:3])}"
            proceed = True  # Can proceed after step-up auth

        else:  # High
            message = (
                f"🚫 High risk transaction blocked (score: {risk_score:.2f}). "
                f"Multiple security concerns detected."
            )
            if anomaly_flags:
                message += f"\nFlags: {', '.join(anomaly_flags[:5])}"
            message += "\nPlease contact support or try with a smaller amount."
            proceed = False

        # --- Add transaction details if intent is available ---
        details = {
            "speaker_id": speaker_id,
            "similarity_score": similarity_score,
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "anomaly_flags": anomaly_flags,
        }

        if intent_result:
            entities = intent_result.get("entities", {})
            amount = entities.get("amount")
            recipient = entities.get("recipient")

            if amount and proceed:
                message += f"\n\nTransaction: ₹{amount}"
                if recipient:
                    message += f" to {recipient}"

            details["intent"] = intent_result.get("intent")
            details["intent_confidence"] = intent_result.get("confidence")
            details["entities"] = entities

        return {
            "auth_required": auth_method,
            "risk_tier": risk_tier,
            "proceed": proceed,
            "message": message,
            "details": details,
        }

    def validate_pin(self, pin_input: str, stored_hash: str) -> bool:
        """Validate a PIN against a stored bcrypt hash."""
        import bcrypt
        return bcrypt.checkpw(
            pin_input.encode("utf-8"),
            stored_hash.encode("utf-8") if isinstance(stored_hash, str) else stored_hash,
        )

    def hash_pin(self, pin: str) -> str:
        """Hash a PIN using bcrypt."""
        import bcrypt
        salt = bcrypt.gensalt(rounds=self.pin_hash_rounds)
        return bcrypt.hashpw(pin.encode("utf-8"), salt).decode("utf-8")


# --- Standalone Test ---
if __name__ == "__main__":
    print("=" * 60)
    print("Auth Logic — Standalone Test")
    print("=" * 60)

    auth = AuthLogic()

    scenarios = [
        {
            "name": "Low Risk — Verified Speaker",
            "fraud": {"risk_score": 0.15, "risk_tier": "Low", "anomaly_flags": []},
            "sv": {"speaker_id": "user_001", "similarity_score": 0.89, "verified": True},
            "intent": {"intent": "send_money", "confidence": 0.95, "entities": {"amount": 5.0, "recipient": "rahul"}},
        },
        {
            "name": "Medium Risk — Verified Speaker",
            "fraud": {"risk_score": 0.55, "risk_tier": "Medium", "anomaly_flags": ["UNUSUAL_HOUR"]},
            "sv": {"speaker_id": "user_001", "similarity_score": 0.72, "verified": True},
            "intent": {"intent": "send_money", "confidence": 0.88, "entities": {"amount": 500.0, "recipient": "unknown"}},
        },
        {
            "name": "Voice Mismatch — LOW similarity (SHOULD BLOCK)",
            "fraud": {"risk_score": 0.10, "risk_tier": "Low", "anomaly_flags": []},
            "sv": {"speaker_id": "user_001", "similarity_score": 0.08, "verified": False},
            "intent": {"intent": "send_money", "confidence": 0.92, "entities": {"amount": 100.0, "recipient": "rahul"}},
        },
        {
            "name": "Voice Mismatch — BORDERLINE similarity (SHOULD STEP-UP)",
            "fraud": {"risk_score": 0.10, "risk_tier": "Low", "anomaly_flags": []},
            "sv": {"speaker_id": "user_001", "similarity_score": 0.38, "verified": False},
            "intent": {"intent": "send_money", "confidence": 0.92, "entities": {"amount": 100.0, "recipient": "rahul"}},
        },
        {
            "name": "Non-payment intent — SV mismatch (should still work)",
            "fraud": {"risk_score": 0.10, "risk_tier": "Low", "anomaly_flags": []},
            "sv": {"speaker_id": "user_001", "similarity_score": 0.08, "verified": False},
            "intent": {"intent": "check_balance", "confidence": 0.95, "entities": {}},
        },
    ]

    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        result = auth.evaluate(
            fraud_result=scenario["fraud"],
            sv_result=scenario["sv"],
            intent_result=scenario["intent"],
        )
        print(f"  Auth Required: {result['auth_required']}")
        print(f"  Risk Tier:     {result['risk_tier']}")
        print(f"  Proceed:       {result['proceed']}")
        print(f"  Message:       {result['message'][:100]}...")

    print(f"\n✅ Auth Logic test completed!")
