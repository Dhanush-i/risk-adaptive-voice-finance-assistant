"""
Shared Tokenizer — Text Normalization
=======================================
Provides consistent text preprocessing for both training and inference
in the intent classification pipeline.

Steps:
  1. Lowercase
  2. Strip surrounding whitespace
  3. Remove punctuation (except currency symbols)
  4. Split digit-word boundaries ("500rupees" → "500 rupees")
  5. Collapse multiple spaces
"""

import re
from typing import List


# Remove punctuation but keep digits and currency symbols (₹)
_PUNCT_RE = re.compile(r"[^\w\s₹]", re.UNICODE)

# Insert space between digit and letter boundaries
# "500rupees" → "500 rupees", "rs500" → "rs 500"
_DIGIT_WORD_RE = re.compile(r"(\d)([a-zA-Z])")
_WORD_DIGIT_RE = re.compile(r"([a-zA-Z])(\d)")

# Collapse multiple whitespace
_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """
    Normalize text for intent classification tokenization.

    Args:
        text: Raw input text.

    Returns:
        Cleaned, lowercase text with consistent spacing.

    Examples:
        >>> normalize_text("Send 500rupees to Rahul!")
        'send 500 rupees to rahul'
        >>> normalize_text("What's my balance?")
        'whats my balance'
        >>> normalize_text("  Pay ₹200 for electricity  ")
        'pay ₹200 for electricity'
    """
    text = text.lower().strip()
    text = _PUNCT_RE.sub("", text)
    text = _DIGIT_WORD_RE.sub(r"\1 \2", text)
    text = _WORD_DIGIT_RE.sub(r"\1 \2", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def tokenize_text(text: str) -> List[str]:
    """
    Normalize and split text into tokens.

    Args:
        text: Raw input text.

    Returns:
        List of normalized tokens.
    """
    return normalize_text(text).split()
