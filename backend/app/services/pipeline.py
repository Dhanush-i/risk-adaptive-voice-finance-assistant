"""
Pipeline Orchestrator
======================
Orchestrates the full voice-to-payment pipeline:
  Audio → STT → Speaker Verification → Intent Classification → Fraud Detection → Auth Logic

Each stage produces structured output and is logged to the audit trail.
If any stage fails, the pipeline returns a detailed error without proceeding.
"""

import os
import sys
import time
import uuid
import datetime
from typing import Dict, Any, Optional, Tuple

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
        Process a voice command through the full pipeline.

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
                sv_result = sv.verify_speaker(user_id, audio_path)
                
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
            # Stage 4: Fraud Detection
            # ============================================================
            stage_start = time.time()
            try:
                fd = self.app_state.get("fraud_detector")
                if fd is None:
                    raise RuntimeError("Fraud Detector not loaded")

                # Build transaction features for fraud detection
                txn_features = {
                    "amount": transaction.amount_inr or 0,
                    "hour_of_day": datetime.datetime.now().hour,
                    "day_of_week": datetime.datetime.now().weekday(),
                    "transaction_frequency": self._get_user_txn_frequency(db, db_user_id),
                    "avg_transaction_amount": self._get_user_avg_amount(db, db_user_id),
                    "amount_deviation": 0,  # Calculated in fraud detector
                    "time_since_last_transaction": self._get_time_since_last_txn(db, db_user_id),
                    "is_new_recipient": 1 if transaction.recipient else 0,
                    "failed_auth_attempts": 0,
                }
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

        # Fraud Detection
        stage_start = time.time()
        fd = self.app_state.get("fraud_detector")
        if fd is None:
            fraud_result = {"risk_score": 1.0, "risk_tier": "High", "anomaly_flags": ["FRAUD_DETECTOR_UNAVAILABLE"]}
        else:
            txn_features = {
                "amount": transaction.amount_inr or 0,
                "hour_of_day": datetime.datetime.now().hour,
                "day_of_week": datetime.datetime.now().weekday(),
                "transaction_frequency": self._get_user_txn_frequency(db, db_user_id),
                "avg_transaction_amount": self._get_user_avg_amount(db, db_user_id),
                "amount_deviation": 0,
                "time_since_last_transaction": self._get_time_since_last_txn(db, db_user_id),
                "is_new_recipient": 1 if transaction.recipient else 0,
                "failed_auth_attempts": 0,
            }
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

    def _get_user_txn_frequency(self, db: Session, user_id: int) -> int:
        """Get number of transactions in last 24 hours."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        count = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= cutoff,
        ).count()
        return count

    def _get_user_avg_amount(self, db: Session, user_id: int) -> float:
        """Get user's average transaction amount."""
        from sqlalchemy import func
        result = db.query(func.avg(Transaction.amount_inr)).filter(
            Transaction.user_id == user_id,
            Transaction.amount_inr > 0,
        ).scalar()
        return float(result) if result else 100.0  # Default average

    def _get_time_since_last_txn(self, db: Session, user_id: int) -> int:
        """Get minutes since last transaction."""
        last_txn = db.query(Transaction).filter(
            Transaction.user_id == user_id,
        ).order_by(Transaction.created_at.desc()).first()

        if last_txn and last_txn.created_at:
            delta = datetime.datetime.utcnow() - last_txn.created_at
            return max(1, int(delta.total_seconds() / 60))
        return 1440  # Default: 24 hours ago

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
