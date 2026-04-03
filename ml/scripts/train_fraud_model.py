"""
Fraud Model Training Script
=============================
Trains the Isolation Forest (unsupervised) + Random Forest (supervised) ensemble
on the synthetic fraud dataset.

Usage: python ml/scripts/train_fraud_model.py
"""

import os
import yaml
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, f1_score, accuracy_score,
)


def train():
    """Main training function for fraud detection models."""
    print("=" * 60)
    print("Fraud Detection — Training Pipeline")
    print("=" * 60)

    # Load config
    with open("architecture/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    fd_config = config["fraud_detection"]
    seed = config["project"]["seed"]

    np.random.seed(seed)

    # Load dataset
    dataset_path = fd_config["dataset_path"]
    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset not found at {dataset_path}")
        print("Run `python ml/scripts/generate_fraud_dataset.py` first!")
        return

    df = pd.read_csv(dataset_path)
    print(f"\n[Data] Loaded {len(df)} samples from {dataset_path}")
    print(f"  Fraudulent: {df['is_fraudulent'].sum()} ({100 * df['is_fraudulent'].mean():.1f}%)")
    print(f"  Legitimate: {(1 - df['is_fraudulent']).sum():.0f} ({100 * (1 - df['is_fraudulent'].mean()):.1f}%)")

    # Feature columns
    feature_cols = [
        "amount", "hour_of_day", "day_of_week", "transaction_frequency",
        "avg_transaction_amount", "amount_deviation", "time_since_last_transaction",
        "is_new_recipient", "failed_auth_attempts",
    ]

    X = df[feature_cols].values
    y = df["is_fraudulent"].values

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    print(f"\n[Split] Train: {len(X_train)}, Test: {len(X_test)}")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # --- Train Isolation Forest (unsupervised anomaly detection) ---
    print(f"\n[Training] Isolation Forest...")

    iso_forest = IsolationForest(
        n_estimators=fd_config["isolation_forest"]["n_estimators"],
        contamination=fd_config["isolation_forest"]["contamination"],
        random_state=fd_config["isolation_forest"]["random_state"],
        n_jobs=-1,
    )
    iso_forest.fit(X_train_scaled)

    # Evaluate Isolation Forest
    if_predictions = iso_forest.predict(X_test_scaled)
    # Convert: -1 (anomaly) -> 1 (fraud), 1 (normal) -> 0 (legit)
    if_labels = (if_predictions == -1).astype(int)

    if_acc = accuracy_score(y_test, if_labels)
    if_f1 = f1_score(y_test, if_labels, zero_division=0)
    print(f"  Isolation Forest — Accuracy: {if_acc:.4f}, F1: {if_f1:.4f}")

    # --- Train Random Forest (supervised classification) ---
    print(f"\n[Training] Random Forest...")

    rf_classifier = RandomForestClassifier(
        n_estimators=fd_config["random_forest"]["n_estimators"],
        max_depth=fd_config["random_forest"]["max_depth"],
        random_state=fd_config["random_forest"]["random_state"],
        class_weight="balanced",
        n_jobs=-1,
    )
    rf_classifier.fit(X_train_scaled, y_train)

    # Evaluate Random Forest
    rf_predictions = rf_classifier.predict(X_test_scaled)
    rf_proba = rf_classifier.predict_proba(X_test_scaled)[:, 1]

    rf_acc = accuracy_score(y_test, rf_predictions)
    rf_f1 = f1_score(y_test, rf_predictions, zero_division=0)
    rf_auc = roc_auc_score(y_test, rf_proba)

    print(f"  Random Forest — Accuracy: {rf_acc:.4f}, F1: {rf_f1:.4f}, AUC: {rf_auc:.4f}")

    # --- Ensemble Evaluation ---
    print(f"\n[Ensemble] Evaluating combined model...")

    # Isolation Forest risk scores (0-1)
    if_scores = iso_forest.decision_function(X_test_scaled)
    if_risk = np.clip(0.5 - if_scores, 0, 1)

    # Random Forest risk scores (probability of fraud)
    rf_risk = rf_proba

    # Weighted ensemble
    ensemble_risk = 0.4 * if_risk + 0.6 * rf_risk

    # Apply thresholds
    low_max = fd_config["risk_thresholds"]["low_max"]
    med_max = fd_config["risk_thresholds"]["medium_max"]

    ensemble_pred = (ensemble_risk > 0.5).astype(int)

    ens_acc = accuracy_score(y_test, ensemble_pred)
    ens_f1 = f1_score(y_test, ensemble_pred, zero_division=0)
    ens_auc = roc_auc_score(y_test, ensemble_risk)

    print(f"  Ensemble — Accuracy: {ens_acc:.4f}, F1: {ens_f1:.4f}, AUC: {ens_auc:.4f}")

    # --- Detailed Results ---
    print(f"\n{'=' * 60}")
    print("Classification Report (Random Forest):")
    print(classification_report(y_test, rf_predictions, target_names=["Legitimate", "Fraudulent"]))

    print("Confusion Matrix (Random Forest):")
    print(confusion_matrix(y_test, rf_predictions))

    # Feature importance
    print("\nFeature Importance (Random Forest):")
    importances = rf_classifier.feature_importances_
    for name, imp in sorted(zip(feature_cols, importances), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {name:30s} {imp:.4f} {bar}")

    # Risk tier distribution
    tiers = []
    for r in ensemble_risk:
        if r <= low_max:
            tiers.append("Low")
        elif r <= med_max:
            tiers.append("Medium")
        else:
            tiers.append("High")

    from collections import Counter
    tier_dist = Counter(tiers)
    print(f"\nRisk Tier Distribution (Test Set):")
    for tier in ["Low", "Medium", "High"]:
        count = tier_dist.get(tier, 0)
        pct = 100 * count / len(tiers)
        print(f"  {tier:8s}: {count:5d} ({pct:.1f}%)")

    # --- Save Models ---
    os.makedirs(os.path.dirname(fd_config["model_path"]), exist_ok=True)

    models = {
        "isolation_forest": iso_forest,
        "random_forest": rf_classifier,
    }
    joblib.dump(models, fd_config["model_path"])
    print(f"\n[Save] Models saved to {fd_config['model_path']}")

    joblib.dump(scaler, fd_config["scaler_path"])
    print(f"[Save] Scaler saved to {fd_config['scaler_path']}")

    # Final status
    print(f"\n{'=' * 60}")
    if ens_auc >= 0.85:
        print(f"[OK] Training successful! Ensemble AUC = {ens_auc:.4f}")
    else:
        print(f"[WARN] Ensemble AUC = {ens_auc:.4f}. Consider tuning hyperparameters.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    train()
