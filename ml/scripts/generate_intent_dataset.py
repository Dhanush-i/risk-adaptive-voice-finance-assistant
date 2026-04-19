"""
Intent Dataset Generator (v3 — Augmented + Out-of-Scope)
==========================================================
Generates financial command dataset with:
  - 5 intent classes: send_money, check_balance, transaction_history, pay_bill, out_of_scope
  - Back-translation augmentation (English ↔ Hindi finance terms)
  - Whisper transcription artifacts
  - 500 samples per class

Output: CSV file at ml/data/intent_dataset.csv
"""

import os
import csv
import random
import yaml
from typing import List, Tuple


def load_config(config_path: str = "architecture/config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# --- Template Definitions ---

SEND_MONEY_TEMPLATES = [
    "send {amount} rupees to {name}",
    "transfer {amount} to {name}",
    "pay {name} {amount} rupees",
    "send {amount} rs to {name}",
    "transfer {amount} rs to {name}",
    "give {amount} rupees to {name}",
    "send money to {name} {amount} rupees",
    "wire {amount} to {name}",
    "make a payment of {amount} to {name}",
    "please send {amount} rupees to {name}",
    "i want to send {amount} to {name}",
    "can you transfer {amount} rupees to {name}",
    "please transfer {amount} rs to {name}",
    "send {name} {amount} rupees",
    "pay {amount} to {name}",
    "i need to send {amount} rupees to {name}",
    "quickly send {amount} to {name}",
    "transfer money to {name} amount {amount}",
    "make payment {amount} rupees to {name}",
    "send {amount} inr to {name}",
    "please pay {amount} rupees to {name}",
    "i'd like to transfer {amount} to {name}",
    "could you send {amount} to {name}",
    "payment of {amount} to {name} please",
    "transfer {amount} rupees to {name}'s account",
    "send {amount} to {name} please",
    "{name} ko {amount} rupees bhejo",
    "pay {amount} rupees {name} ko",
    "please do a transfer of {amount} to {name}",
    "i want to pay {name} {amount}",
    "send {name} {amount}",
    "kindly transfer {amount} to {name}",
    "do transfer {amount} to {name}",
    "just send {amount} to {name}",
    "transfer {amount} rupees {name}",
    "send some money to {name} {amount} rupees",
    "pay {name} an amount of {amount} rupees",
    "can you please send {amount} rs to {name}",
    "i want to transfer {amount} to {name} right now",
    "initiate a transfer of {amount} rupees to {name}",
    "forward {amount} to {name}",
    "move {amount} to {name}'s account",
    "process payment of {amount} to {name}",
    # Whisper transcription artifacts
    "send {amount} rupee to {name}",
    "transfer {amount} rupes to {name}",
    "please send {amount} rupee's to {name}",
    "sand {amount} rupees to {name}",
    "sent {amount} to {name}",
]

CHECK_BALANCE_TEMPLATES = [
    "what is my balance",
    "check my balance",
    "show my account balance",
    "how much money do i have",
    "what's my account balance",
    "tell me my balance",
    "show balance",
    "my current balance",
    "how much is in my account",
    "what's my current balance",
    "balance check",
    "display my balance",
    "account balance please",
    "can you show my balance",
    "i want to check my balance",
    "what is my current account balance",
    "how much do i have in my account",
    "please tell me my balance",
    "show me how much money i have",
    "what is the balance in my account",
    "check account balance",
    "balance inquiry",
    "what's left in my account",
    "remaining balance",
    "available balance please",
    "how much balance do i have",
    "tell me the balance",
    "what's my remaining balance",
    "i want to know my balance",
    "balance please",
    "show account balance",
    "whats my balance",
    "balance kitna hai",
    "mera balance batao",
    "how much money is left",
    "what is the available balance",
    "check balance please",
    "can you check my balance",
    "display account balance",
    "what do i have in my account",
    "total balance",
    "current balance check",
    "my balance",
    "show me my balance",
    "i need to check my balance",
    "how much money is in my account",
]

TRANSACTION_HISTORY_TEMPLATES = [
    "show my recent transactions",
    "transaction history",
    "show last {n} transactions",
    "recent payments",
    "what were my last transactions",
    "show me my payment history",
    "display recent transactions",
    "list my transactions",
    "show past transactions",
    "my recent activity",
    "what did i pay recently",
    "show my last {n} payments",
    "recent transaction history",
    "give me my transaction details",
    "what are my recent transactions",
    "show recent activity",
    "past {n} transactions please",
    "can you show my transaction history",
    "list recent payments",
    "show me what i spent recently",
    "my payment history please",
    "display last {n} transactions",
    "what transactions did i make",
    "show all recent transactions",
    "i want to see my transactions",
    "show my previous transactions",
    "show transaction history",
    "recent transaction list",
    "what payments did i make",
    "my transactions",
    "previous transactions",
    "show transactions",
    "transaction list",
    "payment history",
    "last few transactions",
    "history of my payments",
    "show me recent activity",
    "what have i paid recently",
    "display my transactions",
    "view my transactions",
    "i want to see payment history",
    "show my recent payments",
    "recent activity please",
    "last transactions",
    "show previous payments",
]

PAY_BILL_TEMPLATES = [
    "pay my {bill_type} bill",
    "pay {bill_type} bill of {amount} rupees",
    "pay {amount} for {bill_type}",
    "settle my {bill_type} bill",
    "pay {bill_type} bill",
    "please pay my {bill_type} bill of {amount}",
    "i want to pay my {bill_type} bill",
    "pay {amount} rupees for {bill_type} bill",
    "settle {bill_type} bill of {amount}",
    "make {bill_type} bill payment",
    "pay {bill_type} recharge of {amount}",
    "{bill_type} bill payment of {amount} rupees",
    "recharge {bill_type} for {amount}",
    "pay my {bill_type} dues",
    "clear my {bill_type} bill of {amount}",
    "i need to pay {bill_type} bill",
    "please settle {bill_type} bill",
    "make payment for {bill_type} {amount} rupees",
    "pay {amount} rs for my {bill_type}",
    "{bill_type} payment {amount} please",
    "pay the {bill_type} bill",
    "settle {bill_type} dues of {amount}",
    "i want to pay {bill_type} bill of {amount}",
    "{bill_type} bill of {amount} rupees",
    "clear {bill_type} bill",
    "please pay {bill_type} bill {amount}",
    "make {bill_type} payment of {amount}",
    "pay {bill_type} {amount} rupees",
    "{bill_type} recharge {amount}",
    "pay for my {bill_type}",
    "can you pay my {bill_type} bill",
    "pay {amount} for my {bill_type} bill",
    "process {bill_type} payment",
    "pay {bill_type} charges",
    "{bill_type} bill pay {amount}",
]

OUT_OF_SCOPE_TEMPLATES = [
    "hello there",
    "hi how are you",
    "good morning",
    "what's the weather like today",
    "tell me a joke",
    "who is the prime minister of india",
    "what time is it",
    "play some music",
    "set an alarm for 7 am",
    "remind me to buy groceries",
    "what is the meaning of life",
    "calculate 25 times 43",
    "search for flights to delhi",
    "book a cab to the airport",
    "order food from swiggy",
    "translate hello to hindi",
    "open youtube",
    "read me the news",
    "what is bitcoin price today",
    "how to make chai",
    "help me with homework",
    "write an email to my boss",
    "turn on the lights",
    "call mom",
    "navigate to nearest hospital",
    "this is a test sentence",
    "random words here nothing",
    "i am just testing this app",
    "blah blah blah",
    "hmm let me think",
    "okay thanks bye",
    "never mind forget it",
    "the quick brown fox jumps",
    "what can you do",
    "are you an ai",
    "tell me about yourself",
    "do you know any recipes",
    "how tall is mount everest",
    "when was india independent",
    "who won the cricket match",
    "subscribe to my channel",
    "like and share this video",
    "download the app now",
    "click the link below",
    "testing one two three",
]

# --- Entity Values ---

NAMES = [
    "rahul", "priya", "amit", "sneha", "vikram", "ananya", "rohan", "deepa",
    "arjun", "kavya", "sanjay", "meera", "karthik", "divya", "suresh",
    "pooja", "manish", "lakshmi", "ravi", "nisha", "arun", "swati",
    "ganesh", "rekha", "varun", "neha", "rajesh", "sunita", "mohit", "isha",
    "danish", "dhanush", "harish", "kumar", "ram", "sita", "vivek", "anu",
    "sachin", "anil", "ashok", "geeta", "bhavna", "vijay", "pankaj", "seema",
]

AMOUNTS = [1, 2, 5, 10, 15, 20, 25, 50, 75, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000]

BILL_TYPES = [
    "electricity", "phone", "internet", "water", "gas",
    "mobile", "broadband", "dth", "credit card", "insurance",
]

HISTORY_COUNTS = [3, 5, 7, 10, 15, 20]

# --- Back-Translation Substitution Table ---
BACK_TRANSLATION_TABLE = {
    "send": ["bhejo", "bhej do", "transfer karo"],
    "money": ["paisa", "rupees", "paise"],
    "transfer": ["bhejo", "send karo", "transfer karo"],
    "balance": ["balance", "paisa kitna", "kitna hai"],
    "pay": ["pay karo", "bharo", "de do"],
    "check": ["dekho", "check karo", "batao"],
    "account": ["khata", "account"],
    "bill": ["bill", "bijli bill", "phone bill"],
    "show": ["dikhao", "batao", "show karo"],
    "please": ["kripya", "please"],
    "rupees": ["rupaye", "rs", "rupee"],
    "transactions": ["transactions", "lenden"],
    "history": ["history", "purana record"],
    "payment": ["payment", "bhugtan"],
    "recent": ["haal ka", "recent", "abhi ka"],
}


def augment_text(text: str) -> str:
    """Apply random augmentation: filler words, word drops, minor typos."""
    words = text.split()

    # 20% chance: add filler word
    if random.random() < 0.2:
        fillers = ["um", "uh", "like", "okay", "so", "well", "actually", "basically"]
        pos = random.randint(0, len(words))
        words.insert(pos, random.choice(fillers))

    # 10% chance: drop a non-essential word
    if random.random() < 0.1 and len(words) > 3:
        drop_candidates = [i for i, w in enumerate(words) if w in ("please", "can", "you", "kindly", "do", "just", "the", "a", "my")]
        if drop_candidates:
            words.pop(random.choice(drop_candidates))

    return " ".join(words)


def back_translate(text: str) -> str:
    """
    Heuristic back-translation: randomly substitute some English words
    with their Hindi/colloquial equivalents and vice versa.
    """
    words = text.split()
    result = []
    for w in words:
        if w in BACK_TRANSLATION_TABLE and random.random() < 0.3:
            result.append(random.choice(BACK_TRANSLATION_TABLE[w]))
        else:
            result.append(w)
    return " ".join(result)


def generate_send_money(num_samples: int) -> List[Tuple[str, str]]:
    samples = []
    for _ in range(num_samples):
        template = random.choice(SEND_MONEY_TEMPLATES)
        name = random.choice(NAMES)
        amount = random.choice(AMOUNTS)
        text = template.format(name=name, amount=amount)
        r = random.random()
        if r < 0.2:
            text = augment_text(text)
        elif r < 0.35:
            text = back_translate(text)
        samples.append((text, "send_money"))
    return samples


def generate_check_balance(num_samples: int) -> List[Tuple[str, str]]:
    samples = []
    for _ in range(num_samples):
        text = random.choice(CHECK_BALANCE_TEMPLATES)
        r = random.random()
        if r < 0.2:
            text = augment_text(text)
        elif r < 0.35:
            text = back_translate(text)
        samples.append((text, "check_balance"))
    return samples


def generate_transaction_history(num_samples: int) -> List[Tuple[str, str]]:
    samples = []
    for _ in range(num_samples):
        template = random.choice(TRANSACTION_HISTORY_TEMPLATES)
        if "{n}" in template:
            n = random.choice(HISTORY_COUNTS)
            text = template.format(n=n)
        else:
            text = template
        r = random.random()
        if r < 0.2:
            text = augment_text(text)
        elif r < 0.35:
            text = back_translate(text)
        samples.append((text, "transaction_history"))
    return samples


def generate_pay_bill(num_samples: int) -> List[Tuple[str, str]]:
    samples = []
    for _ in range(num_samples):
        template = random.choice(PAY_BILL_TEMPLATES)
        bill_type = random.choice(BILL_TYPES)
        amount = random.choice(AMOUNTS)
        text = template.format(bill_type=bill_type, amount=amount)
        r = random.random()
        if r < 0.2:
            text = augment_text(text)
        elif r < 0.35:
            text = back_translate(text)
        samples.append((text, "pay_bill"))
    return samples


def generate_out_of_scope(num_samples: int) -> List[Tuple[str, str]]:
    """Generate out-of-scope samples from templates and augmentations."""
    samples = []
    for _ in range(num_samples):
        text = random.choice(OUT_OF_SCOPE_TEMPLATES)
        if random.random() < 0.3:
            text = augment_text(text)
        samples.append((text, "out_of_scope"))
    return samples


def generate_dataset(num_samples: int = 2500, output_path: str = "ml/data/intent_dataset.csv") -> str:
    """
    Generate the full intent dataset.

    Args:
        num_samples: Total number of samples (divided equally among 5 classes).
        output_path: Output CSV path.
    """
    random.seed(42)

    samples_per_class = num_samples // 5
    remainder = num_samples % 5

    all_samples = []
    all_samples.extend(generate_send_money(samples_per_class + (1 if remainder > 0 else 0)))
    all_samples.extend(generate_check_balance(samples_per_class + (1 if remainder > 1 else 0)))
    all_samples.extend(generate_transaction_history(samples_per_class + (1 if remainder > 2 else 0)))
    all_samples.extend(generate_pay_bill(samples_per_class + (1 if remainder > 3 else 0)))
    all_samples.extend(generate_out_of_scope(samples_per_class))

    random.shuffle(all_samples)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "intent"])
        writer.writerows(all_samples)

    print(f"[Intent Dataset] Generated {len(all_samples)} samples -> {output_path}")

    from collections import Counter
    dist = Counter([s[1] for s in all_samples])
    for intent, count in sorted(dist.items()):
        print(f"  {intent}: {count} samples")

    return output_path


if __name__ == "__main__":
    config = load_config()
    ic_config = config["intent_classification"]

    output = generate_dataset(
        num_samples=ic_config["num_samples"],
        output_path=ic_config["dataset_path"],
    )
    print(f"\n[OK] Dataset saved to: {output}")
