"""
Fraud Dataset Generator
========================
Generates synthetic transaction data for fraud detection model training.

Features per transaction:
  - amount: Transaction amount in INR
  - hour_of_day: Hour when transaction occurred (0-23)
  - day_of_week: Day of week (0-6, Mon-Sun)
  - transaction_frequency: Number of transactions in last 24h
  - avg_transaction_amount: User's average transaction amount
  - amount_deviation: How much this amount deviates from user's average
  - time_since_last_transaction: Minutes since last transaction
  - is_new_recipient: Whether recipient is new (0/1)
  - failed_auth_attempts: Recent failed authentication attempts
  - is_fraudulent: Label (0 = legitimate, 1 = fraudulent)

Output: CSV file at ml/data/fraud_dataset.csv
"""

import os
import csv
import random
import yaml
import numpy as np
from typing import List, Dict


def load_config(config_path: str = "architecture/config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def generate_legitimate_transaction() -> Dict[str, float]:
    """Generate a legitimate transaction with normal patterns."""
    # Normal hours (8am - 10pm mostly)
    hour = random.choices(
        range(24),
        weights=[1, 1, 1, 1, 1, 1, 2, 3, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 3, 3, 2, 1],
        k=1
    )[0]

    # Normal amounts (₹10-₹500 range, occasionally higher)
    avg_amount = random.uniform(50, 300)
    amount = max(1, np.random.normal(avg_amount, avg_amount * 0.3))

    return {
        "amount": round(amount, 2),
        "hour_of_day": hour,
        "day_of_week": random.randint(0, 6),
        "transaction_frequency": random.randint(1, 8),
        "avg_transaction_amount": round(avg_amount, 2),
        "amount_deviation": round(abs(amount - avg_amount) / max(avg_amount, 1), 4),
        "time_since_last_transaction": random.randint(30, 1440),  # 30 min to 24 hours
        "is_new_recipient": random.choices([0, 1], weights=[0.8, 0.2], k=1)[0],
        "failed_auth_attempts": random.choices([0, 0, 0, 0, 1], k=1)[0],
        "is_fraudulent": 0,
    }


def generate_fraudulent_transaction() -> Dict[str, float]:
    """Generate a fraudulent transaction with suspicious patterns."""
    fraud_type = random.choice(["high_amount", "unusual_time", "rapid_fire", "new_recipient_high"])

    # Base values
    avg_amount = random.uniform(50, 300)

    if fraud_type == "high_amount":
        # Unusually high amount compared to average
        amount = avg_amount * random.uniform(5, 20)
        hour = random.randint(0, 23)
        freq = random.randint(1, 5)
        time_since = random.randint(10, 500)
        is_new = random.choices([0, 1], weights=[0.5, 0.5], k=1)[0]
        failed = random.randint(0, 2)

    elif fraud_type == "unusual_time":
        # Transactions at unusual hours (2am-5am)
        amount = max(1, np.random.normal(avg_amount * 2, avg_amount))
        hour = random.randint(1, 5)
        freq = random.randint(1, 10)
        time_since = random.randint(5, 200)
        is_new = random.choices([0, 1], weights=[0.4, 0.6], k=1)[0]
        failed = random.randint(0, 3)

    elif fraud_type == "rapid_fire":
        # Many transactions in quick succession
        amount = max(1, np.random.normal(avg_amount, avg_amount * 0.5))
        hour = random.randint(0, 23)
        freq = random.randint(8, 25)  # High frequency
        time_since = random.randint(1, 15)  # Very recent last transaction
        is_new = random.choices([0, 1], weights=[0.3, 0.7], k=1)[0]
        failed = random.randint(1, 4)

    else:  # new_recipient_high
        # High amount to new recipient
        amount = avg_amount * random.uniform(3, 10)
        hour = random.randint(0, 23)
        freq = random.randint(1, 5)
        time_since = random.randint(5, 300)
        is_new = 1  # Always new recipient
        failed = random.randint(0, 3)

    return {
        "amount": round(max(1, amount), 2),
        "hour_of_day": hour,
        "day_of_week": random.randint(0, 6),
        "transaction_frequency": freq,
        "avg_transaction_amount": round(avg_amount, 2),
        "amount_deviation": round(abs(amount - avg_amount) / max(avg_amount, 1), 4),
        "time_since_last_transaction": time_since,
        "is_new_recipient": is_new,
        "failed_auth_attempts": failed,
        "is_fraudulent": 1,
    }


def generate_dataset(num_samples: int = 10000, output_path: str = "ml/data/fraud_dataset.csv",
                     fraud_ratio: float = 0.1) -> str:
    """
    Generate the fraud detection dataset.

    Args:
        num_samples: Total number of samples.
        output_path: Path to save CSV file.
        fraud_ratio: Proportion of fraudulent transactions.

    Returns:
        Path to the generated CSV file.
    """
    random.seed(42)
    np.random.seed(42)

    num_fraud = int(num_samples * fraud_ratio)
    num_legit = num_samples - num_fraud

    print(f"[Fraud Dataset] Generating {num_samples} samples...")
    print(f"  Legitimate: {num_legit} ({100 * (1 - fraud_ratio):.0f}%)")
    print(f"  Fraudulent: {num_fraud} ({100 * fraud_ratio:.0f}%)")

    samples = []

    # Generate legitimate transactions
    for _ in range(num_legit):
        samples.append(generate_legitimate_transaction())

    # Generate fraudulent transactions
    for _ in range(num_fraud):
        samples.append(generate_fraudulent_transaction())

    # Shuffle
    random.shuffle(samples)

    # Save to CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "amount", "hour_of_day", "day_of_week", "transaction_frequency",
        "avg_transaction_amount", "amount_deviation", "time_since_last_transaction",
        "is_new_recipient", "failed_auth_attempts", "is_fraudulent",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)

    print(f"\n[Fraud Dataset] Saved -> {output_path}")

    # Print statistics
    amounts = [s["amount"] for s in samples]
    print(f"\n  Amount stats:")
    print(f"    Min:  Rs.{min(amounts):.2f}")
    print(f"    Max:  Rs.{max(amounts):.2f}")
    print(f"    Mean: Rs.{np.mean(amounts):.2f}")
    print(f"    Std:  Rs.{np.std(amounts):.2f}")

    return output_path


if __name__ == "__main__":
    config = load_config()
    fd_config = config["fraud_detection"]

    output = generate_dataset(
        num_samples=fd_config["num_samples"],
        output_path=fd_config["dataset_path"],
        fraud_ratio=fd_config["isolation_forest"]["contamination"],
    )
    print(f"\n[OK] Fraud dataset saved to: {output}")
