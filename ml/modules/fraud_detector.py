"""
Fraud Detection Module — Isolation Forest + Random Forest Ensemble
===================================================================
Detects potential fraud in financial transactions using anomaly detection
combined with supervised classification.

Pipeline:
  1. Isolation Forest → anomaly score (unsupervised)
  2. Random Forest → fraud probability (supervised)
  3. Ensemble → weighted risk score → risk tier mapping

Input:  Transaction feature dict
Output: { "risk_score": float, "risk_tier": str, "anomaly_flags": list }
"""

import os
import yaml
import numpy as np
import joblib
from typing import Dict, Any, List, Optional
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class FraudDetector:
    """Fraud detection using Isolation Forest + Random Forest ensemble."""

    FEATURE_NAMES = [
        "amount", "hour_of_day", "day_of_week", "transaction_frequency",
        "avg_transaction_amount", "amount_deviation", "time_since_last_transaction",
        "is_new_recipient", "failed_auth_attempts",
    ]

    PROFILES_DIR = "storage/user_profiles"

    def __init__(self, config_path: str = "architecture/config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        fd_config = config["fraud_detection"]
        self.if_config = fd_config["isolation_forest"]
        self.rf_config = fd_config["random_forest"]
        self.thresholds = fd_config["risk_thresholds"]
        self.model_path = fd_config["model_path"]
        self.scaler_path = fd_config["scaler_path"]
        self.config_path = config_path

        self.isolation_forest = None
        self.random_forest = None
        self.scaler = None
        
        # Adaptive tracking — loaded from persistent storage
        self.user_profiles = {}
        os.makedirs(self.PROFILES_DIR, exist_ok=True)

    def _auto_train(self) -> None:
        """Auto-trigger model training when model files don't exist."""
        print("[Fraud] Model not found — auto-training...")
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        # Generate dataset if needed
        dataset_path = "ml/data/fraud_dataset.csv"
        if not os.path.exists(dataset_path):
            print("[Fraud] Dataset not found — generating...")
            from ml.scripts.generate_fraud_dataset import generate_dataset
            generate_dataset()

        # Train the model
        from ml.scripts.train_fraud_model import train
        train()

    def load_model(self) -> None:
        """Load trained models and scaler from disk. Auto-trains if missing."""
        if not os.path.exists(self.model_path):
            self._auto_train()

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"[Fraud] Model still not found after auto-training: {self.model_path}"
            )

        models = joblib.load(self.model_path)
        self.isolation_forest = models["isolation_forest"]
        self.random_forest = models["random_forest"]

        if os.path.exists(self.scaler_path):
            self.scaler = joblib.load(self.scaler_path)

        print(f"[Fraud] Models loaded from {self.model_path}")

    def _extract_features(self, transaction: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from transaction dict."""
        features = []
        for name in self.FEATURE_NAMES:
            features.append(float(transaction.get(name, 0.0)))
        return np.array(features).reshape(1, -1)

    def _get_anomaly_flags(self, transaction: Dict[str, Any]) -> List[str]:
        """Identify specific anomaly flags based on rule-based checks."""
        flags = []

        amount = transaction.get("amount", 0)
        avg = transaction.get("avg_transaction_amount", 0)
        hour = transaction.get("hour_of_day", 12)
        freq = transaction.get("transaction_frequency", 0)
        time_since = transaction.get("time_since_last_transaction", 100)
        is_new = transaction.get("is_new_recipient", 0)
        failed = transaction.get("failed_auth_attempts", 0)

        # High amount deviation — only flag truly extreme amounts
        if avg > 0 and amount > avg * 5:
            flags.append(f"HIGH_AMOUNT_DEVIATION: ₹{amount:.0f} vs avg ₹{avg:.0f}")

        # Unusual hour (midnight to 5am)
        if hour >= 0 and hour <= 5:
            flags.append(f"UNUSUAL_HOUR: {hour}:00")

        # High frequency
        if freq > 15:
            flags.append(f"HIGH_FREQUENCY: {freq} transactions in 24h")

        # Rapid transactions — only flag if 5+ payments in quick succession
        if freq >= 5 and time_since < 2:
            flags.append(f"RAPID_TRANSACTION: {freq} payments, {time_since} min since last")

        # New recipient with high amount
        if is_new and avg > 0 and amount > avg * 3:
            flags.append(f"NEW_RECIPIENT_HIGH_AMOUNT: ₹{amount:.0f} to new recipient")

        # Multiple failed auth attempts
        if failed >= 2:
            flags.append(f"MULTIPLE_FAILED_AUTH: {failed} recent failures")

        return flags

    def _get_risk_tier(self, risk_score: float) -> str:
        """Map risk score to risk tier."""
        if risk_score <= self.thresholds["low_max"]:
            return "Low"
        elif risk_score <= self.thresholds["medium_max"]:
            return "Medium"
        else:
            return "High"

    def predict(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict fraud risk for a transaction.

        Args:
            transaction: Dictionary with transaction features.

        Returns:
            Risk assessment with score, tier, and anomaly flags.
        """
        if self.isolation_forest is None or self.random_forest is None:
            raise RuntimeError("[Fraud] Models not loaded. Call load_model() first.")

        # Extract and scale features
        features = self._extract_features(transaction)
        if self.scaler is not None:
            features_scaled = self.scaler.transform(features)
        else:
            features_scaled = features

        # Isolation Forest: anomaly score (-1 = anomaly, 1 = normal)
        if_score = self.isolation_forest.decision_function(features_scaled)[0]
        # Convert to 0-1 range (lower decision function = more anomalous)
        if_risk = max(0, min(1, 0.5 - if_score))

        # Random Forest: fraud probability
        rf_proba = self.random_forest.predict_proba(features_scaled)[0]
        rf_risk = rf_proba[1] if len(rf_proba) > 1 else 0.0

        # Ensemble: weighted combination
        risk_score = round(0.4 * if_risk + 0.6 * rf_risk, 4)

        # Get risk tier
        risk_tier = self._get_risk_tier(risk_score)

        # Get anomaly flags
        anomaly_flags = self._get_anomaly_flags(transaction)

        result = {
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "anomaly_flags": anomaly_flags,
            "details": {
                "isolation_forest_risk": round(if_risk, 4),
                "random_forest_risk": round(rf_risk, 4),
            }
        }

        print(f"[Fraud] Risk: {risk_score:.4f} ({risk_tier}) | Flags: {len(anomaly_flags)}")

        return result

    def predict_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict fraud risk for multiple transactions."""
        return [self.predict(t) for t in transactions]

    def _get_profile_path(self, user_id: str) -> str:
        """Get the JSON file path for a user's adaptive profile."""
        return os.path.join(self.PROFILES_DIR, f"{user_id}.json")

    def _load_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load a persisted user profile from disk."""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]

        path = self._get_profile_path(user_id)
        if os.path.exists(path):
            import json
            with open(path, "r") as f:
                profile = json.load(f)
            self.user_profiles[user_id] = profile
            return profile
        return None

    def _save_user_profile(self, user_id: str) -> None:
        """Persist a user profile to disk as JSON."""
        profile = self.user_profiles.get(user_id)
        if profile is None:
            return
        import json
        path = self._get_profile_path(user_id)
        with open(path, "w") as f:
            json.dump(profile, f, indent=2)

    def get_adaptive_features(self, user_id: str) -> Dict[str, float]:
        """
        Get dynamically adjusted features from the user's adaptive profile.
        Returns avg_transaction_amount and amount_deviation baseline if available.
        """
        profile = self._load_user_profile(user_id)
        if profile and profile.get("transaction_history"):
            history = profile["transaction_history"]
            avg = sum(history) / len(history)
            return {"avg_transaction_amount": avg}
        return {}

    def learn(self, transaction: Dict[str, Any], user_id: str = "demo_user") -> None:
        """
        Adaptive Learning: Update and persist the user's transaction profile
        with a newly verified legitimate transaction.
        """
        if user_id not in self.user_profiles:
            existing = self._load_user_profile(user_id)
            if existing is None:
                self.user_profiles[user_id] = {
                    "transaction_history": [],
                    "avg_amount": float(transaction.get("amount", 0)),
                    "total_transactions": 0,
                }
            
        profile = self.user_profiles[user_id]
        
        # Record the transaction
        amount = float(transaction.get("amount", 0))
        profile["transaction_history"].append(amount)
        
        # Keep only recent 50 for moving average
        if len(profile["transaction_history"]) > 50:
            profile["transaction_history"] = profile["transaction_history"][-50:]
            
        # Update running stats
        profile["total_transactions"] += 1
        profile["avg_amount"] = sum(profile["transaction_history"]) / len(profile["transaction_history"])
        
        # Persist to disk
        self._save_user_profile(user_id)
        
        print(f"[Fraud] Adaptive profile updated and saved for {user_id}.")
        print(f"        New Baseline Avg: ₹{profile['avg_amount']:.2f} over {profile['total_transactions']} txns.")


# --- Standalone Test ---
if __name__ == "__main__":
    print("=" * 60)
    print("Fraud Detector — Standalone Test (Rule-based only)")
    print("=" * 60)

    detector = FraudDetector()

    # Test anomaly flags without model
    test_transactions = [
        {
            "amount": 100, "hour_of_day": 14, "day_of_week": 2,
            "transaction_frequency": 3, "avg_transaction_amount": 150,
            "amount_deviation": 0.33, "time_since_last_transaction": 120,
            "is_new_recipient": 0, "failed_auth_attempts": 0,
        },
        {
            "amount": 5000, "hour_of_day": 3, "day_of_week": 1,
            "transaction_frequency": 15, "avg_transaction_amount": 200,
            "amount_deviation": 24.0, "time_since_last_transaction": 2,
            "is_new_recipient": 1, "failed_auth_attempts": 3,
        },
    ]

    for i, txn in enumerate(test_transactions):
        flags = detector._get_anomaly_flags(txn)
        print(f"\nTransaction {i + 1}:")
        print(f"  Amount: ₹{txn['amount']}")
        print(f"  Flags: {flags if flags else 'None (clean)'}")

    print("\n✅ Anomaly flag test completed!")
    print("\nNote: Full prediction requires trained models.")
    print("Run `python ml/scripts/train_fraud_model.py` first.")
