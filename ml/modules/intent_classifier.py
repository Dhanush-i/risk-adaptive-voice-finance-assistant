"""
Intent Classification Module — LSTM-based Classifier
=====================================================
Classifies financial voice commands into intent categories with entity extraction.

Intents: send_money, check_balance, transaction_history, pay_bill
Entities: amount (float), recipient (str), bill_type (str)

Input:  Text string (from STT)
Output: { "intent": str, "confidence": float, "entities": { ... } }
"""

import os
import re
import json
import yaml
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, Any, List, Optional
from collections import Counter


class IntentLSTM(nn.Module):
    """LSTM-based intent classification network."""

    def __init__(self, vocab_size: int, embedding_dim: int, hidden_dim: int,
                 num_classes: int, num_layers: int = 2, dropout: float = 0.3):
        super().__init__()

        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embedding_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)  # *2 for bidirectional

    def forward(self, x):
        """
        Args:
            x: (batch_size, seq_length) — token indices

        Returns:
            (batch_size, num_classes) — logits
        """
        embedded = self.embedding(x)  # (batch, seq, embed_dim)
        lstm_out, (hidden, _) = self.lstm(embedded)

        # Concatenate final hidden states from both directions
        hidden_fwd = hidden[-2]  # Last layer forward
        hidden_bwd = hidden[-1]  # Last layer backward
        combined = torch.cat([hidden_fwd, hidden_bwd], dim=1)

        output = self.dropout(combined)
        output = self.fc(output)
        return output


class IntentClassifier:
    """Intent classification with entity extraction for financial commands."""

    INTENT_LABELS = ["send_money", "check_balance", "transaction_history", "pay_bill"]

    # Known entity patterns
    AMOUNT_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*(?:rupees?|rs\.?|inr|₹)?', re.IGNORECASE)
    NAME_PATTERN = re.compile(
        r'(?:to|for)\s+([a-zA-Z]+(?:\s[a-zA-Z]+)?)\s*(?:\'s)?',
        re.IGNORECASE
    )
    BILL_TYPES = [
        "electricity", "phone", "internet", "water", "gas",
        "mobile", "broadband", "dth", "credit card", "insurance",
    ]

    def __init__(self, config_path: str = "architecture/config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        ic_config = config["intent_classification"]
        self.vocab_size = ic_config["vocab_size"]
        self.embedding_dim = ic_config["embedding_dim"]
        self.hidden_dim = ic_config["hidden_dim"]
        self.num_layers = ic_config["num_layers"]
        self.dropout = ic_config["dropout"]
        self.max_seq_length = ic_config["max_seq_length"]
        self.model_path = ic_config["model_path"]
        self.vocab_path = ic_config["vocab_path"]

        self.model = None
        self.vocab = None
        self.device = torch.device("cpu")

    def load_model(self) -> None:
        """Load the trained intent classification model and vocabulary."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"[Intent] Model not found: {self.model_path}. Train it first!")

        if not os.path.exists(self.vocab_path):
            raise FileNotFoundError(f"[Intent] Vocab not found: {self.vocab_path}. Train it first!")

        # Load vocab
        with open(self.vocab_path, "r") as f:
            self.vocab = json.load(f)

        # Initialize model
        num_classes = len(self.INTENT_LABELS)
        self.model = IntentLSTM(
            vocab_size=self.vocab_size,
            embedding_dim=self.embedding_dim,
            hidden_dim=self.hidden_dim,
            num_classes=num_classes,
            num_layers=self.num_layers,
            dropout=self.dropout,
        )

        # Load weights
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

        print(f"[Intent] Model loaded from {self.model_path}")
        print(f"[Intent] Vocabulary size: {len(self.vocab)}")

    def tokenize(self, text: str) -> List[int]:
        """Convert text to token indices using the vocabulary."""
        if self.vocab is None:
            raise RuntimeError("[Intent] Vocabulary not loaded.")

        tokens = text.lower().strip().split()
        indices = [self.vocab.get(t, self.vocab.get("<UNK>", 1)) for t in tokens]

        # Pad or truncate
        if len(indices) < self.max_seq_length:
            indices += [0] * (self.max_seq_length - len(indices))  # PAD = 0
        else:
            indices = indices[:self.max_seq_length]

        return indices

    def extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """
        Extract entities (amount, recipient, bill_type) from the text based on intent.

        Args:
            text: Input text.
            intent: Classified intent.

        Returns:
            Dictionary of extracted entities.
        """
        entities = {}

        # Extract amount
        amount_match = self.AMOUNT_PATTERN.search(text)
        if amount_match:
            entities["amount"] = float(amount_match.group(1))
            entities["currency"] = "INR"

        # Extract recipient for send_money
        if intent == "send_money":
            name_match = self.NAME_PATTERN.search(text)
            if name_match:
                # Filter out common non-name words
                candidate = name_match.group(1).strip().lower()
                stop_words = {"my", "the", "a", "an", "for", "of", "in", "rs", "rupees", "account"}
                if candidate not in stop_words:
                    entities["recipient"] = candidate

        # Extract bill type for pay_bill
        if intent == "pay_bill":
            text_lower = text.lower()
            for bt in self.BILL_TYPES:
                if bt in text_lower:
                    entities["bill_type"] = bt
                    break

        return entities

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify the intent of a text command and extract entities.

        Args:
            text: Input text string.

        Returns:
            Dictionary with intent, confidence, and extracted entities.
        """
        if self.model is None:
            raise RuntimeError("[Intent] Model not loaded. Call load_model() first.")

        # Tokenize
        token_indices = self.tokenize(text)
        input_tensor = torch.tensor([token_indices], dtype=torch.long).to(self.device)

        # Predict
        with torch.no_grad():
            logits = self.model(input_tensor)
            probabilities = torch.softmax(logits, dim=1)
            confidence, predicted_idx = torch.max(probabilities, dim=1)

        intent = self.INTENT_LABELS[predicted_idx.item()]
        confidence_score = round(confidence.item(), 4)

        # Extract entities
        entities = self.extract_entities(text, intent)

        result = {
            "intent": intent,
            "confidence": confidence_score,
            "entities": entities,
        }

        print(f"[Intent] '{text}' → {intent} (conf: {confidence_score})")
        if entities:
            print(f"[Intent] Entities: {entities}")

        return result


# --- Standalone Test ---
if __name__ == "__main__":
    print("=" * 60)
    print("Intent Classifier — Standalone Test")
    print("=" * 60)

    # Test entity extraction without model
    classifier = IntentClassifier()

    test_texts = [
        ("send 500 rupees to rahul", "send_money"),
        ("what is my balance", "check_balance"),
        ("show last 5 transactions", "transaction_history"),
        ("pay electricity bill of 200 rupees", "pay_bill"),
    ]

    print("\n--- Entity Extraction Test ---")
    for text, intent in test_texts:
        entities = classifier.extract_entities(text, intent)
        print(f"  Text: '{text}'")
        print(f"  Intent: {intent}")
        print(f"  Entities: {entities}")
        print()

    print("✅ Entity extraction test completed!")
    print("\nNote: Full classification requires a trained model.")
    print("Run `python ml/scripts/train_intent_model.py` first.")
