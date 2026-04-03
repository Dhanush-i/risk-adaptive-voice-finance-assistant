"""
Intent Model Training Script
=============================
Trains the LSTM-based intent classifier on the synthetic financial commands dataset.

Usage: python ml/scripts/train_intent_model.py
"""

import os
import csv
import json
import yaml
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from collections import Counter
from typing import List, Tuple, Dict
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ml.modules.intent_classifier import IntentLSTM, IntentClassifier


class IntentDataset(Dataset):
    """PyTorch dataset for intent classification."""

    def __init__(self, texts: List[str], labels: List[int], vocab: Dict[str, int], max_length: int):
        self.texts = texts
        self.labels = labels
        self.vocab = vocab
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx].lower().strip()
        tokens = text.split()
        indices = [self.vocab.get(t, self.vocab.get("<UNK>", 1)) for t in tokens]

        # Pad or truncate
        if len(indices) < self.max_length:
            indices += [0] * (self.max_length - len(indices))
        else:
            indices = indices[:self.max_length]

        return torch.tensor(indices, dtype=torch.long), torch.tensor(self.labels[idx], dtype=torch.long)


def build_vocab(texts: List[str], max_vocab_size: int = 2000) -> Dict[str, int]:
    """Build vocabulary from texts."""
    word_counts = Counter()
    for text in texts:
        tokens = text.lower().strip().split()
        word_counts.update(tokens)

    # Reserve special tokens
    vocab = {"<PAD>": 0, "<UNK>": 1}

    # Add most common words
    for word, _ in word_counts.most_common(max_vocab_size - 2):
        vocab[word] = len(vocab)

    return vocab


def load_dataset(dataset_path: str) -> Tuple[List[str], List[str]]:
    """Load the intent dataset from CSV."""
    texts, labels = [], []
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(row["intent"])
    return texts, labels


def train():
    """Main training function."""
    print("=" * 60)
    print("Intent Classification — Training Pipeline")
    print("=" * 60)

    # Load config
    with open("architecture/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    ic_config = config["intent_classification"]
    seed = config["project"]["seed"]

    # Set seeds
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Load dataset
    dataset_path = ic_config["dataset_path"]
    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset not found at {dataset_path}")
        print("Run `python ml/scripts/generate_intent_dataset.py` first!")
        return

    texts, label_strs = load_dataset(dataset_path)
    print(f"\n[Data] Loaded {len(texts)} samples from {dataset_path}")

    # Encode labels
    label_map = {label: idx for idx, label in enumerate(IntentClassifier.INTENT_LABELS)}
    labels = [label_map[l] for l in label_strs]

    # Build vocabulary
    vocab = build_vocab(texts, max_vocab_size=ic_config["vocab_size"])
    print(f"[Vocab] Built vocabulary with {len(vocab)} words")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=seed, stratify=labels
    )
    print(f"[Split] Train: {len(X_train)}, Test: {len(X_test)}")

    # Create datasets and dataloaders
    train_dataset = IntentDataset(X_train, y_train, vocab, ic_config["max_seq_length"])
    test_dataset = IntentDataset(X_test, y_test, vocab, ic_config["max_seq_length"])

    train_loader = DataLoader(train_dataset, batch_size=ic_config["batch_size"], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=ic_config["batch_size"])

    # Initialize model
    device = torch.device("cpu")
    model = IntentLSTM(
        vocab_size=ic_config["vocab_size"],
        embedding_dim=ic_config["embedding_dim"],
        hidden_dim=ic_config["hidden_dim"],
        num_classes=len(IntentClassifier.INTENT_LABELS),
        num_layers=ic_config["num_layers"],
        dropout=ic_config["dropout"],
    ).to(device)

    print(f"\n[Model] IntentLSTM — Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=ic_config["learning_rate"])
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    # Training loop
    print(f"\n[Training] Starting for {ic_config['epochs']} epochs...")
    best_f1 = 0.0
    best_model_state = None

    for epoch in range(1, ic_config["epochs"] + 1):
        model.train()
        total_loss = 0
        correct = 0
        total = 0

        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total += targets.size(0)
            correct += (predicted == targets).sum().item()

        scheduler.step()

        train_acc = 100 * correct / total
        avg_loss = total_loss / len(train_loader)

        # Evaluate every 5 epochs
        if epoch % 5 == 0 or epoch == ic_config["epochs"]:
            model.eval()
            all_preds, all_true = [], []
            with torch.no_grad():
                for inputs, targets in test_loader:
                    inputs, targets = inputs.to(device), targets.to(device)
                    outputs = model(inputs)
                    _, predicted = torch.max(outputs, 1)
                    all_preds.extend(predicted.cpu().numpy())
                    all_true.extend(targets.cpu().numpy())

            f1 = f1_score(all_true, all_preds, average="weighted")
            test_acc = 100 * np.mean(np.array(all_preds) == np.array(all_true))

            print(f"  Epoch {epoch:3d}/{ic_config['epochs']} | Loss: {avg_loss:.4f} | "
                  f"Train Acc: {train_acc:.1f}% | Test Acc: {test_acc:.1f}% | F1: {f1:.4f}")

            # Save best model
            if f1 > best_f1:
                best_f1 = f1
                best_model_state = model.state_dict().copy()
        else:
            print(f"  Epoch {epoch:3d}/{ic_config['epochs']} | Loss: {avg_loss:.4f} | Train Acc: {train_acc:.1f}%")

    # Final evaluation with best model
    print(f"\n{'=' * 60}")
    print(f"Best Weighted F1: {best_f1:.4f}")
    print(f"{'=' * 60}")

    if best_model_state is not None:
        model.load_state_dict(best_model_state)

    model.eval()
    all_preds, all_true = [], []
    with torch.no_grad():
        for inputs, targets in test_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            _, predicted = torch.max(outputs, 1)
            all_preds.extend(predicted.cpu().numpy())
            all_true.extend(targets.cpu().numpy())

    print("\nClassification Report:")
    print(classification_report(all_true, all_preds, target_names=IntentClassifier.INTENT_LABELS))

    print("Confusion Matrix:")
    cm = confusion_matrix(all_true, all_preds)
    print(cm)

    # Save model and vocab
    os.makedirs(os.path.dirname(ic_config["model_path"]), exist_ok=True)

    torch.save(best_model_state or model.state_dict(), ic_config["model_path"])
    print(f"\n[Save] Model saved to {ic_config['model_path']}")

    with open(ic_config["vocab_path"], "w") as f:
        json.dump(vocab, f, indent=2)
    print(f"[Save] Vocabulary saved to {ic_config['vocab_path']}")

    # Final status
    if best_f1 >= 0.85:
        print(f"\n[OK] Training successful! F1 = {best_f1:.4f} (target: >=0.85)")
    else:
        print(f"\n[WARN] F1 = {best_f1:.4f} is below target (0.85). Consider tuning hyperparameters.")


if __name__ == "__main__":
    train()
