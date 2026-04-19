"""
Pipeline Orchestrator
======================
Orchestrates the full voice-to-payment pipeline:
  Audio → STT → Speaker Verification → Intent Classification → Fraud Detection → Auth Logic

Each stage produces structured output and is logged to the audit trail.
If any stage fails, the pipeline returns a detailed error without proceeding.

Supports both batch mode (returns all stages at once) and streaming mode
(yields SSE events as each stage completes).
"""

import os
import sys
import json
import time
import uuid
import datetime
from typing import Dict, Any, Optional, Tuple, AsyncGenerator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy.orm import Session
from backend.app.db.models import Transaction, AuditLog
from backend.app.schemas.schemas import PipelineStageResult, AuthDecision


class PipelineOrchestrator:
    """
    Orchestrates the full ML pipeline for voice-based transactions.

    Stages:
      1. STT — transcribe audio to text
      2. Speaker Verification — verify speaker identity
      3. Intent Classification — classify command and extract entities
      4. Fraud Detection — assess transaction risk
      5. Auth Decision — determine authentication requirements
    """

    # Minimum confidence for STT — below this triggers clarify response
    STT_MIN_CONFIDENCE = 0.3

    def __init__(self, app_state: dict):
        """
        Initialize with references to loaded ML models from app_state.

        Args:
            app_state: Dictionary containing loaded ML models and services.
        """
        self.app_state = app_state

    def _log_stage(
        self, db: Session, transaction_id: int, user_id: int,
        event_type: str, event_data: dict, severity: str = "info"
    ):
        """Log a pipeline stage to the audit trail."""
        log = AuditLog(
            transaction_id=transaction_id,
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
            severity=severity,
        )
        db.add(log)
        db.flush()

    def _ensure_stt_loaded(self):
        """Lazy-load STT model if not already loaded."""
        if self.app_state.get("stt") is None:
            from ml.modules.stt import SpeechToText
            stt = SpeechToText(config_path="architecture/config.yaml")
            stt.load_model()
            self.app_state["stt"] = stt

    def _ensure_sv_loaded(self):
        """Lazy-load Speaker Verification model if not already loaded."""
        if self.app_state.get("speaker_verification") is None:
            from ml.modules.speaker_verification import SpeakerVerification
            sv = SpeakerVerification(config_path="architecture/config.yaml")
            sv.load_model()
            self.app_state["speaker_verification"] = sv

    async def process_voice_command(
        self,
        audio_path: str,
        user_id: str,
        db_user_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Process a voice command through the full pipeline (batch mode).

        Args:
            audio_path: Path to the uploaded audio file.
            user_id: Username/speaker ID for verification.
            db_user_id: Database user ID.
            db: Database session.

        Returns:
            Pipeline result with all stage outputs and auth decision.
        """
        stages = []
        transaction = None

        try:
            # Create transaction record
            transaction = Transaction(
                user_id=db_user_id,
                amount_inr=0,  # Will be updated after intent classification
                status="initiated",
                payment_status="pending",
            )
            db.add(transaction)
            db.flush()

            # ============================================================
            # Stage 1: Speech-to-Text
            # ============================================================
            stage_start = time.time()
            try:
                self._ensure_stt_loaded()
                stt = self.app_state["stt"]
                stt_result = stt.transcribe(audio_path)

                # Check for low confidence or empty transcript → clarify
                transcript = stt_result.get("transcript", "").strip()
                confidence = stt_result.get("confidence", 0.0)

                if not transcript or confidence < self.STT_MIN_CONFIDENCE:
                    stage_time = (time.time() - stage_start) * 1000
                    stages.append(PipelineStageResult(
                        stage="stt", success=False,
                        data={"error": "Low confidence", "transcript": transcript, "confidence": confidence},
                        duration_ms=round(stage_time, 2),
                    ))
                    # Don't create a failed transaction — return clarify signal
                    transaction.status = "clarify"
                    db.commit()
                    return {
                        "transaction_id": transaction.id,
                        "stages": [s.model_dump() for s in stages],
                        "auth_decision": None,
                        "razorpay_order": None,
                        "status": "clarify",
                        "message": "Could not understand, please try again",
                    }

                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="stt",
                    success=True,
                    data=stt_result,
                    duration_ms=round(stage_time, 2),
                ))

                transaction.transcript = stt_result["transcript"]
                self._log_stage(db, transaction.id, db_user_id, "stt", stt_result)

            except Exception as e:
                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="stt", success=False,
                    data={"error": str(e)}, duration_ms=round(stage_time, 2),
                ))
                self._log_stage(db, transaction.id, db_user_id, "stt",
                                {"error": str(e)}, severity="error")
                transaction.status = "failed"
                transaction.error_message = f"STT failed: {e}"
                db.commit()
                return self._build_error_response(transaction.id, stages, "Speech recognition failed")

            # ============================================================
            # Stage 2: Speaker Verification (with Anti-Spoofing/Liveness)
            # ============================================================
            stage_start = time.time()
            try:
                self._ensure_sv_loaded()
                sv = self.app_state["speaker_verification"]
                sv_result = sv.verify_speaker(user_id, audio_path, authenticated_user_id=user_id)
                
                # Zero-Shot Liveness Detection (Anti-Replay Attack)
                liveness_result = sv.check_liveness(audio_path)
                sv_result.update(liveness_result)

                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="speaker_verification",
                    success=True,
                    data=sv_result,
                    duration_ms=round(stage_time, 2),
                ))

                transaction.sv_similarity = sv_result["similarity_score"]
                transaction.sv_verified = sv_result["verified"]
                self._log_stage(db, transaction.id, db_user_id, "sv", sv_result)

            except Exception as e:
                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="speaker_verification", success=False,
                    data={"error": str(e)}, duration_ms=round(stage_time, 2),
                ))
                self._log_stage(db, transaction.id, db_user_id, "sv",
                                {"error": str(e)}, severity="error")
                # SV failure doesn't stop the pipeline — auth logic handles it
                sv_result = {
                    "speaker_id": user_id,
                    "similarity_score": 0.0,
                    "verified": False,
                    "error": str(e),
                }
                transaction.sv_verified = False

            # ============================================================
            # Stage 3: Intent Classification
            # ============================================================
            stage_start = time.time()
            try:
                ic = self.app_state.get("intent_classifier")
                if ic is None:
                    raise RuntimeError("Intent Classifier not loaded")

                intent_result = ic.classify(stt_result["transcript"])

                # --- QR keyword override (must be BEFORE out_of_scope check) ---
                _transcript_lower = (stt_result.get("transcript", "") or "").lower()
                if any(kw in _transcript_lower for kw in ["qr", "scanner", "scan code", "open camera"]):
                    intent_result["intent"] = "scan_qr"

                # Handle out_of_scope intent
                if intent_result.get("intent") == "out_of_scope":
                    stage_time = (time.time() - stage_start) * 1000
                    stages.append(PipelineStageResult(
                        stage="intent_classification", success=True,
                        data=intent_result, duration_ms=round(stage_time, 2),
                    ))
                    transaction.intent = "out_of_scope"
                    transaction.status = "clarify"
                    db.commit()
                    return {
                        "transaction_id": transaction.id,
                        "stages": [s.model_dump() for s in stages],
                        "auth_decision": None,
                        "razorpay_order": None,
                        "status": "clarify",
                        "message": "I didn't understand that as a financial command. Try saying something like 'send 500 rupees to Rahul'.",
                    }

                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="intent_classification",
                    success=True,
                    data=intent_result,
                    duration_ms=round(stage_time, 2),
                ))

                transaction.intent = intent_result["intent"]
                transaction.intent_confidence = intent_result["confidence"]

                # Extract amount from entities
                entities = intent_result.get("entities", {})
                amount = entities.get("amount", 0)
                transaction.amount_inr = amount if amount else 0
                transaction.recipient = entities.get("recipient")
                transaction.bill_type = entities.get("bill_type")

                self._log_stage(db, transaction.id, db_user_id, "intent", intent_result)

            except Exception as e:
                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="intent_classification", success=False,
                    data={"error": str(e)}, duration_ms=round(stage_time, 2),
                ))
                self._log_stage(db, transaction.id, db_user_id, "intent",
                                {"error": str(e)}, severity="error")
                transaction.status = "failed"
                transaction.error_message = f"Intent classification failed: {e}"
                db.commit()
                return self._build_error_response(transaction.id, stages, "Could not understand command")

            # ============================================================
            # Non-payment intent handling
            # ============================================================
            intent_name = intent_result.get("intent", "")
            _transcript_lower = (stt_result.get("transcript", "") or "").lower()
            if any(kw in _transcript_lower for kw in ["qr", "scanner", "scan code", "open camera"]):
                intent_result["intent"] = "scan_qr"
                intent_name = "scan_qr"
                transaction.intent = "scan_qr"

            if intent_name in ("check_balance", "transaction_history", "scan_qr"):
                transaction.status = "completed"
                db.commit()
                return {
                    "transaction_id": transaction.id,
                    "stages": [s.model_dump() for s in stages],
                    "auth_decision": None,
                    "razorpay_order": None,
                    "status": "info_response",
                    "intent": intent_name,
                    "message": self._get_info_message(intent_name),
                }

            # Contact validation for payment intents
            _recipient = entities.get("recipient", "")
            _contact_ok = self._check_contact(_recipient)
            intent_result["contact_found"] = _contact_ok
            intent_result["prompt_qr"] = bool(_recipient) and not _contact_ok

            # If recipient not in contacts → ask user to scan QR instead
            if bool(_recipient) and not _contact_ok:
                transaction.status = "clarify"
                db.commit()
                return {
                    "transaction_id": transaction.id,
                    "stages": [s.model_dump() for s in stages],
                    "auth_decision": None,
                    "razorpay_order": None,
                    "status": "unknown_recipient",
                    "intent": intent_name,
                    "recipient": _recipient,
                    "amount": entities.get("amount", 0),
                    "message": f"'{_recipient}' is not in your contacts. Would you like to scan their QR code instead?",
                }

            # ============================================================
            # Stage 4: Fraud Detection
            # ============================================================
            stage_start = time.time()
            try:
                fd = self.app_state.get("fraud_detector")
                if fd is None:
                    # Rule-based fallback instead of crashing
                    print("[Pipeline] Fraud Detector not loaded — using rule-based fallback")
                    fraud_result = self._rule_based_fraud_check(transaction, db, db_user_id)
                else:
                    # Build transaction features for fraud detection
                    txn_features = {
                        "amount": transaction.amount_inr or 0,
                        "hour_of_day": datetime.datetime.now().hour,
                        "day_of_week": datetime.datetime.now().weekday(),
                        "transaction_frequency": self._get_user_txn_frequency(db, db_user_id),
                        "avg_transaction_amount": self._get_user_avg_amount(db, db_user_id),
                        "amount_deviation": 0,
                        "time_since_last_transaction": self._get_time_since_last_txn(db, db_user_id),
                        "is_new_recipient": 1 if (transaction.recipient and not self._check_contact(transaction.recipient)) else 0,
                        "failed_auth_attempts": 0,
                    }

                    # Use adaptive profile if available
                    adaptive = fd.get_adaptive_features(user_id)
                    if adaptive.get("avg_transaction_amount"):
                        txn_features["avg_transaction_amount"] = adaptive["avg_transaction_amount"]

                    # Calculate amount deviation
                    avg = txn_features["avg_transaction_amount"]
                    if avg > 0:
                        txn_features["amount_deviation"] = abs(txn_features["amount"] - avg) / avg

                    fraud_result = fd.predict(txn_features)

                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="fraud_detection",
                    success=True,
                    data=fraud_result,
                    duration_ms=round(stage_time, 2),
                ))

                transaction.risk_score = fraud_result["risk_score"]
                transaction.risk_tier = fraud_result["risk_tier"]
                transaction.anomaly_flags = fraud_result["anomaly_flags"]

                self._log_stage(db, transaction.id, db_user_id, "fraud", fraud_result)

            except Exception as e:
                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="fraud_detection", success=False,
                    data={"error": str(e)}, duration_ms=round(stage_time, 2),
                ))
                self._log_stage(db, transaction.id, db_user_id, "fraud",
                                {"error": str(e)}, severity="error")
                # Default to HIGH risk on fraud detection failure (fail-safe)
                fraud_result = {
                    "risk_score": 1.0,
                    "risk_tier": "High",
                    "anomaly_flags": ["FRAUD_DETECTION_ERROR"],
                }
                transaction.risk_score = 1.0
                transaction.risk_tier = "High"

            # ============================================================
            # Stage 5: Auth Decision
            # ============================================================
            stage_start = time.time()
            try:
                al = self.app_state.get("auth_logic")
                if al is None:
                    raise RuntimeError("Auth Logic not loaded")

                auth_result = al.evaluate(
                    fraud_result=fraud_result,
                    sv_result=sv_result,
                    intent_result=intent_result,
                )

                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="auth_decision",
                    success=True,
                    data=auth_result,
                    duration_ms=round(stage_time, 2),
                ))

                transaction.auth_method = auth_result["auth_required"]

                if not auth_result["proceed"]:
                    transaction.status = "blocked"
                    transaction.payment_status = "blocked"
                else:
                    transaction.status = "processing"

                self._log_stage(db, transaction.id, db_user_id, "auth", auth_result)

            except Exception as e:
                stage_time = (time.time() - stage_start) * 1000
                stages.append(PipelineStageResult(
                    stage="auth_decision", success=False,
                    data={"error": str(e)}, duration_ms=round(stage_time, 2),
                ))
                transaction.status = "failed"
                transaction.error_message = f"Auth decision failed: {e}"
                db.commit()
                return self._build_error_response(transaction.id, stages, "Authentication error")

            # ============================================================
            # Build Response
            # ============================================================
            db.commit()

            auth_decision = AuthDecision(
                auth_required=auth_result["auth_required"],
                risk_tier=auth_result["risk_tier"],
                proceed=auth_result["proceed"],
                message=auth_result["message"],
                details=auth_result.get("details"),
            )

            return {
                "transaction_id": transaction.id,
                "stages": [s.model_dump() for s in stages],
                "auth_decision": auth_decision.model_dump(),
                "razorpay_order": None,  # Created after PIN verification
                "status": transaction.status,
                "message": auth_result["message"],
            }

        except Exception as e:
            if transaction:
                transaction.status = "failed"
                transaction.error_message = str(e)
                db.commit()
            return self._build_error_response(
                transaction.id if transaction else 0, stages, f"Pipeline error: {e}"
            )

    async def process_voice_command_streaming(
        self,
        audio_path: str,
        user_id: str,
        db_user_id: int,
        db: Session,
    ) -> AsyncGenerator[str, None]:
        """
        Process a voice command and yield SSE events as each stage completes.

        Yields:
            SSE-formatted strings: "data: {...}\\n\\n"
        """
        transaction = Transaction(
            user_id=db_user_id,
            amount_inr=0,
            status="initiated",
            payment_status="pending",
        )
        db.add(transaction)
        db.flush()

        sv_result = None
        stt_result = None
        intent_result = None
        fraud_result = None

        def emit(stage: str, success: bool, data: dict, duration_ms: float, is_final: bool = False):
            payload = {
                "stage": stage,
                "success": success,
                "data": data,
                "duration_ms": round(duration_ms, 2),
                "is_final": is_final,
                "transaction_id": transaction.id,
            }
            return f"data: {json.dumps(payload)}\n\n"

        # Stage 1: STT
        stage_start = time.time()
        try:
            self._ensure_stt_loaded()
            stt = self.app_state["stt"]
            stt_result = stt.transcribe(audio_path)
            stage_time = (time.time() - stage_start) * 1000

            transcript = stt_result.get("transcript", "").strip()
            confidence = stt_result.get("confidence", 0.0)

            if not transcript or confidence < self.STT_MIN_CONFIDENCE:
                yield emit("stt", False, {"error": "Low confidence", "transcript": transcript, "confidence": confidence}, stage_time)
                transaction.status = "clarify"
                db.commit()
                yield emit("final", False, {"status": "clarify", "message": "Could not understand, please try again"}, 0, is_final=True)
                return

            transaction.transcript = transcript
            self._log_stage(db, transaction.id, db_user_id, "stt", stt_result)
            yield emit("stt", True, stt_result, stage_time)
        except Exception as e:
            stage_time = (time.time() - stage_start) * 1000
            yield emit("stt", False, {"error": str(e)}, stage_time)
            transaction.status = "failed"
            transaction.error_message = f"STT failed: {e}"
            db.commit()
            yield emit("final", False, {"status": "failed", "message": "Speech recognition failed"}, 0, is_final=True)
            return

        # Stage 2: Speaker Verification
        stage_start = time.time()
        try:
            self._ensure_sv_loaded()
            sv = self.app_state["speaker_verification"]
            sv_result = sv.verify_speaker(user_id, audio_path, authenticated_user_id=user_id)
            liveness_result = sv.check_liveness(audio_path)
            sv_result.update(liveness_result)
            stage_time = (time.time() - stage_start) * 1000
            transaction.sv_similarity = sv_result["similarity_score"]
            transaction.sv_verified = sv_result["verified"]
            self._log_stage(db, transaction.id, db_user_id, "sv", sv_result)
            yield emit("speaker_verification", True, sv_result, stage_time)
        except Exception as e:
            stage_time = (time.time() - stage_start) * 1000
            sv_result = {"speaker_id": user_id, "similarity_score": 0.0, "verified": False, "error": str(e)}
            transaction.sv_verified = False
            yield emit("speaker_verification", False, sv_result, stage_time)

        # Stage 3: Intent Classification
        stage_start = time.time()
        try:
            ic = self.app_state.get("intent_classifier")
            if ic is None:
                raise RuntimeError("Intent Classifier not loaded")
            intent_result = ic.classify(stt_result["transcript"])
            stage_time = (time.time() - stage_start) * 1000

            if intent_result.get("intent") == "out_of_scope":
                yield emit("intent_classification", True, intent_result, stage_time)
                transaction.intent = "out_of_scope"
                transaction.status = "clarify"
                db.commit()
                yield emit("final", False, {"status": "clarify", "message": "I didn't understand that as a financial command."}, 0, is_final=True)
                return

            transaction.intent = intent_result["intent"]
            transaction.intent_confidence = intent_result["confidence"]
            entities = intent_result.get("entities", {})
            transaction.amount_inr = entities.get("amount", 0) or 0
            transaction.recipient = entities.get("recipient")
            transaction.bill_type = entities.get("bill_type")
            self._log_stage(db, transaction.id, db_user_id, "intent", intent_result)
            yield emit("intent_classification", True, intent_result, stage_time)
        except Exception as e:
            stage_time = (time.time() - stage_start) * 1000
            yield emit("intent_classification", False, {"error": str(e)}, stage_time)
            transaction.status = "failed"
            db.commit()
            yield emit("final", False, {"status": "failed", "message": "Could not understand command"}, 0, is_final=True)
            return

        # Non-payment intent handling
        intent_name = intent_result.get("intent", "")
        _transcript_lower = (stt_result.get("transcript", "") or "").lower()
        if any(kw in _transcript_lower for kw in ["qr", "scanner", "scan code", "open camera"]):
            intent_result["intent"] = "scan_qr"
            intent_name = "scan_qr"
            transaction.intent = "scan_qr"

        if intent_name in ("check_balance", "transaction_history", "scan_qr"):
            transaction.status = "completed"
            db.commit()
            yield emit("final", True, {
                "transaction_id": transaction.id,
                "status": "info_response",
                "intent": intent_name,
                "message": self._get_info_message(intent_name),
            }, 0, is_final=True)
            return

        # Contact validation for payment intents
        _recipient = entities.get("recipient", "")
        _contact_ok = self._check_contact(_recipient)
        intent_result["contact_found"] = _contact_ok
        intent_result["prompt_qr"] = bool(_recipient) and not _contact_ok

        # Stage 4: Fraud Detection
        stage_start = time.time()
        try:
            fd = self.app_state.get("fraud_detector")
            if fd is None:
                fraud_result = self._rule_based_fraud_check(transaction, db, db_user_id)
            else:
                txn_features = {
                    "amount": transaction.amount_inr or 0,
                    "hour_of_day": datetime.datetime.now().hour,
                    "day_of_week": datetime.datetime.now().weekday(),
                    "transaction_frequency": self._get_user_txn_frequency(db, db_user_id),
                    "avg_transaction_amount": self._get_user_avg_amount(db, db_user_id),
                    "amount_deviation": 0,
                    "time_since_last_transaction": self._get_time_since_last_txn(db, db_user_id),
                    "is_new_recipient": 1 if (transaction.recipient and not self._check_contact(transaction.recipient)) else 0,
                    "failed_auth_attempts": 0,
                }
                adaptive = fd.get_adaptive_features(user_id)
                if adaptive.get("avg_transaction_amount"):
                    txn_features["avg_transaction_amount"] = adaptive["avg_transaction_amount"]
                avg = txn_features["avg_transaction_amount"]
                if avg > 0:
                    txn_features["amount_deviation"] = abs(txn_features["amount"] - avg) / avg
                fraud_result = fd.predict(txn_features)

            stage_time = (time.time() - stage_start) * 1000
            transaction.risk_score = fraud_result["risk_score"]
            transaction.risk_tier = fraud_result["risk_tier"]
            transaction.anomaly_flags = fraud_result.get("anomaly_flags", [])
            self._log_stage(db, transaction.id, db_user_id, "fraud", fraud_result)
            yield emit("fraud_detection", True, fraud_result, stage_time)
        except Exception as e:
            stage_time = (time.time() - stage_start) * 1000
            fraud_result = {"risk_score": 1.0, "risk_tier": "High", "anomaly_flags": ["FRAUD_DETECTION_ERROR"]}
            transaction.risk_score = 1.0
            transaction.risk_tier = "High"
            yield emit("fraud_detection", False, fraud_result, stage_time)

        # Stage 5: Auth Decision
        stage_start = time.time()
        try:
            al = self.app_state.get("auth_logic")
            if al is None:
                raise RuntimeError("Auth Logic not loaded")
            auth_result = al.evaluate(fraud_result=fraud_result, sv_result=sv_result, intent_result=intent_result)
            stage_time = (time.time() - stage_start) * 1000
            transaction.auth_method = auth_result["auth_required"]
            if not auth_result["proceed"]:
                transaction.status = "blocked"
                transaction.payment_status = "blocked"
            else:
                transaction.status = "processing"
            self._log_stage(db, transaction.id, db_user_id, "auth", auth_result)
            yield emit("auth_decision", True, auth_result, stage_time)
        except Exception as e:
            stage_time = (time.time() - stage_start) * 1000
            auth_result = {"auth_required": "block", "risk_tier": "High", "proceed": False, "message": str(e)}
            transaction.status = "failed"
            yield emit("auth_decision", False, auth_result, stage_time)

        db.commit()

        # Final event with complete response
        auth_decision = AuthDecision(
            auth_required=auth_result["auth_required"],
            risk_tier=auth_result["risk_tier"],
            proceed=auth_result["proceed"],
            message=auth_result["message"],
            details=auth_result.get("details"),
        )
        final_data = {
            "transaction_id": transaction.id,
            "auth_decision": auth_decision.model_dump(),
            "status": transaction.status,
            "message": auth_result["message"],
        }
        yield emit("final", True, final_data, 0, is_final=True)

    def process_text_command(
        self,
        text: str,
        user_id: str,
        db_user_id: int,
        db: Session,
        sv_override: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a text command (skips STT, optionally skips SV).
        Useful for testing and for text-based fallback.

        Args:
            text: The command text.
            user_id: Username.
            db_user_id: Database user ID.
            db: Database session.
            sv_override: If True, skip speaker verification (for text input).
        """
        stages = []

        # Create transaction
        transaction = Transaction(
            user_id=db_user_id,
            transcript=text,
            amount_inr=0,
            status="initiated",
            payment_status="pending",
        )
        db.add(transaction)
        db.flush()

        # STT stage (skipped for text input)
        stages.append(PipelineStageResult(
            stage="stt", success=True,
            data={"transcript": text, "language": "en", "confidence": 1.0, "source": "text_input"},
            duration_ms=0,
        ))

        # SV stage (skipped or mock for text input)
        if sv_override:
            sv_result = {
                "speaker_id": user_id,
                "similarity_score": 1.0,
                "verified": True,
                "note": "text_input_override",
            }
        else:
            sv_result = {
                "speaker_id": user_id,
                "similarity_score": 0.0,
                "verified": False,
                "note": "no_audio_for_sv",
            }
        stages.append(PipelineStageResult(
            stage="speaker_verification", success=True,
            data=sv_result, duration_ms=0,
        ))
        transaction.sv_similarity = sv_result["similarity_score"]
        transaction.sv_verified = sv_result["verified"]

        # Intent Classification
        stage_start = time.time()
        ic = self.app_state.get("intent_classifier")
        if ic is None:
            transaction.status = "failed"
            transaction.error_message = "Intent Classifier not loaded"
            db.commit()
            return self._build_error_response(transaction.id, stages, "Intent classifier not available")

        intent_result = ic.classify(text)

        # --- QR keyword override (must be BEFORE out_of_scope check) ---
        _text_lower = text.lower()
        if any(kw in _text_lower for kw in ["qr", "scanner", "scan code", "open camera"]):
            intent_result["intent"] = "scan_qr"

        # Handle out_of_scope
        if intent_result.get("intent") == "out_of_scope":
            stage_time = (time.time() - stage_start) * 1000
            stages.append(PipelineStageResult(
                stage="intent_classification", success=True,
                data=intent_result, duration_ms=round(stage_time, 2),
            ))
            transaction.intent = "out_of_scope"
            transaction.status = "clarify"
            db.commit()
            return {
                "transaction_id": transaction.id,
                "stages": [s.model_dump() for s in stages],
                "auth_decision": None,
                "razorpay_order": None,
                "status": "clarify",
                "message": "I didn't understand that as a financial command. Try saying something like 'send 500 rupees to Rahul'.",
            }

        stage_time = (time.time() - stage_start) * 1000
        stages.append(PipelineStageResult(
            stage="intent_classification", success=True,
            data=intent_result, duration_ms=round(stage_time, 2),
        ))

        transaction.intent = intent_result["intent"]
        transaction.intent_confidence = intent_result["confidence"]
        entities = intent_result.get("entities", {})
        amount = entities.get("amount", 0)
        transaction.amount_inr = amount if amount else 0
        transaction.recipient = entities.get("recipient")
        transaction.bill_type = entities.get("bill_type")

        # Non-payment intent handling
        intent_name = intent_result.get("intent", "")
        _text_lower = text.lower()
        if any(kw in _text_lower for kw in ["qr", "scanner", "scan code", "open camera"]):
            intent_result["intent"] = "scan_qr"
            intent_name = "scan_qr"
            transaction.intent = "scan_qr"

        if intent_name in ("check_balance", "transaction_history", "scan_qr"):
            transaction.status = "completed"
            db.commit()
            return {
                "transaction_id": transaction.id,
                "stages": [s.model_dump() for s in stages],
                "auth_decision": None,
                "razorpay_order": None,
                "status": "info_response",
                "intent": intent_name,
                "message": self._get_info_message(intent_name),
            }

        # Contact validation for payment intents
        _recipient = entities.get("recipient", "")
        _contact_ok = self._check_contact(_recipient)
        intent_result["contact_found"] = _contact_ok
        intent_result["prompt_qr"] = bool(_recipient) and not _contact_ok

        # If recipient not in contacts → ask user to scan QR instead
        if bool(_recipient) and not _contact_ok:
            transaction.status = "clarify"
            db.commit()
            return {
                "transaction_id": transaction.id,
                "stages": [s.model_dump() for s in stages],
                "auth_decision": None,
                "razorpay_order": None,
                "status": "unknown_recipient",
                "intent": intent_name,
                "recipient": _recipient,
                "amount": entities.get("amount", 0),
                "message": f"'{_recipient}' is not in your contacts. Would you like to scan their QR code instead?",
            }

        # Fraud Detection
        stage_start = time.time()
        fd = self.app_state.get("fraud_detector")
        if fd is None:
            fraud_result = self._rule_based_fraud_check(transaction, db, db_user_id)
        else:
            txn_features = {
                "amount": transaction.amount_inr or 0,
                "hour_of_day": datetime.datetime.now().hour,
                "day_of_week": datetime.datetime.now().weekday(),
                "transaction_frequency": self._get_user_txn_frequency(db, db_user_id),
                "avg_transaction_amount": self._get_user_avg_amount(db, db_user_id),
                "amount_deviation": 0,
                "time_since_last_transaction": self._get_time_since_last_txn(db, db_user_id),
                "is_new_recipient": 1 if (transaction.recipient and not self._check_contact(transaction.recipient)) else 0,
                "failed_auth_attempts": 0,
            }
            adaptive = fd.get_adaptive_features(user_id)
            if adaptive.get("avg_transaction_amount"):
                txn_features["avg_transaction_amount"] = adaptive["avg_transaction_amount"]
            avg = txn_features["avg_transaction_amount"]
            if avg > 0:
                txn_features["amount_deviation"] = abs(txn_features["amount"] - avg) / avg
            fraud_result = fd.predict(txn_features)

        stage_time = (time.time() - stage_start) * 1000
        stages.append(PipelineStageResult(
            stage="fraud_detection", success=True,
            data=fraud_result, duration_ms=round(stage_time, 2),
        ))
        transaction.risk_score = fraud_result["risk_score"]
        transaction.risk_tier = fraud_result["risk_tier"]
        transaction.anomaly_flags = fraud_result.get("anomaly_flags", [])

        # Auth Decision
        stage_start = time.time()
        al = self.app_state.get("auth_logic")
        if al is None:
            transaction.status = "failed"
            db.commit()
            return self._build_error_response(transaction.id, stages, "Auth logic not available")

        auth_result = al.evaluate(
            fraud_result=fraud_result,
            sv_result=sv_result,
            intent_result=intent_result,
        )
        stage_time = (time.time() - stage_start) * 1000
        stages.append(PipelineStageResult(
            stage="auth_decision", success=True,
            data=auth_result, duration_ms=round(stage_time, 2),
        ))

        transaction.auth_method = auth_result["auth_required"]
        if not auth_result["proceed"]:
            transaction.status = "blocked"
            transaction.payment_status = "blocked"
        else:
            transaction.status = "processing"

        db.commit()

        auth_decision = AuthDecision(
            auth_required=auth_result["auth_required"],
            risk_tier=auth_result["risk_tier"],
            proceed=auth_result["proceed"],
            message=auth_result["message"],
            details=auth_result.get("details"),
        )

        return {
            "transaction_id": transaction.id,
            "stages": [s.model_dump() for s in stages],
            "auth_decision": auth_decision.model_dump(),
            "razorpay_order": None,
            "status": transaction.status,
            "message": auth_result["message"],
        }

    # --- Helper methods ---

    def _rule_based_fraud_check(
        self, transaction: Transaction, db: Session, db_user_id: int
    ) -> Dict[str, Any]:
        """Rule-based fraud fallback when ML model isn't available."""
        amount = transaction.amount_inr or 0
        flags = []

        if amount > 5000:
            flags.append(f"HIGH_AMOUNT: ₹{amount}")
        if datetime.datetime.now().hour < 6:
            flags.append("UNUSUAL_HOUR")

        # Unknown recipient check
        if transaction.recipient and not self._check_contact(transaction.recipient):
            flags.append("UNKNOWN_RECIPIENT")

        risk_score = 0.2
        if flags:
            risk_score = 0.5

        return {
            "risk_score": risk_score,
            "risk_tier": "Medium" if flags else "Low",
            "anomaly_flags": flags,
            "details": {"source": "rule_based_fallback"},
        }

    # Intents that count as real financial transactions
    PAYMENT_INTENTS = ["send_money", "pay_bill"]

    def _get_user_txn_frequency(self, db: Session, user_id: int) -> int:
        """Get number of PAYMENT transactions in last 24 hours."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        count = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= cutoff,
            Transaction.intent.in_(self.PAYMENT_INTENTS),
        ).count()
        return count

    def _get_user_avg_amount(self, db: Session, user_id: int) -> float:
        """Get user's average PAYMENT transaction amount."""
        from sqlalchemy import func
        result = db.query(func.avg(Transaction.amount_inr)).filter(
            Transaction.user_id == user_id,
            Transaction.amount_inr > 0,
            Transaction.intent.in_(self.PAYMENT_INTENTS),
        ).scalar()
        return float(result) if result else 100.0  # Default average

    def _get_time_since_last_txn(self, db: Session, user_id: int) -> int:
        """Get minutes since last PAYMENT transaction."""
        last_txn = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.intent.in_(self.PAYMENT_INTENTS),
        ).order_by(Transaction.created_at.desc()).first()

        if last_txn and last_txn.created_at:
            delta = datetime.datetime.utcnow() - last_txn.created_at
            return max(1, int(delta.total_seconds() / 60))
        return 1440  # Default: 24 hours ago

    # --- Known contacts (matches frontend ContactsList) ---
    KNOWN_CONTACTS = [
        "rahul", "priya", "amit", "sneha", "vikram",
        "ananya", "rohan", "deepa", "arjun", "kavya",
        "dhanush", "jahnavi", "ravi", "kundan", "jathin", "balaram",
    ]

    def _check_contact(self, recipient_name: str) -> bool:
        """Check if a recipient name matches a known contact (fuzzy first-name match)."""
        if not recipient_name:
            return True  # No recipient = not a concern
        name_lower = recipient_name.strip().lower()
        for contact in self.KNOWN_CONTACTS:
            if contact in name_lower or name_lower in contact:
                return True
        return False

    def _get_info_message(self, intent: str) -> str:
        """Get user-facing message for non-payment intents."""
        if intent == "check_balance":
            return "Here is your current balance."
        elif intent == "transaction_history":
            return "Switching to your transaction history."
        elif intent == "scan_qr":
            return "Opening QR code scanner..."
        return ""

    def _build_error_response(self, txn_id: int, stages: list, message: str) -> Dict[str, Any]:
        """Build an error response."""
        return {
            "transaction_id": txn_id,
            "stages": [s.model_dump() for s in stages],
            "auth_decision": AuthDecision(
                auth_required="block",
                risk_tier="High",
                proceed=False,
                message=message,
            ).model_dump(),
            "razorpay_order": None,
            "status": "failed",
            "message": message,
        }
