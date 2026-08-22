"""
Step 1: Generate a synthetic batch of failed/at-risk transactions.
Mimics what you'd see from Razorpay Payments/Subscriptions APIs in production.
Run: python 01_generate_data.py
Output: data/transactions.json
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

random.seed(42)  # reproducible batch

FAILURE_TYPES = [
    "card_declined",
    "insufficient_funds",
    "gateway_timeout",
    "subscription_mandate_failed",
    "checkout_abandoned",
]

# Realistic-ish failure reason codes per type (mirrors Razorpay error codes)
FAILURE_CODES = {
    "card_declined": ["BAD_REQUEST_ERROR", "CARD_DECLINED_BY_ISSUER", "PROCESSOR_ERROR"],
    "insufficient_funds": ["INSUFFICIENT_FUNDS"],
    "gateway_timeout": ["GATEWAY_ERROR", "TIMEOUT", "UNCATEGORIZED_DECLINE"],
    "subscription_mandate_failed": ["MANDATE_REJECTED", "MANDATE_EXPIRED"],
    "checkout_abandoned": ["USER_DROPPED_OFF"],
}

FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohan",
               "Kavya", "Arjun", "Neha", "Karan", "Divya", "Sanjay", "Pooja"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Reddy", "Gupta", "Nair", "Singh",
              "Patel", "Rao", "Mehta"]


def generate_safe_phone():
    """Generates a 10-digit Indian mobile number, avoiding Razorpay's
    'recurring digits' fraud-check rejection (e.g. 9999999999)."""
    while True:
        number = f"{random.randint(70,99)}{random.randint(10000000,99999999)}"
        # reject if any single digit repeats 5+ times in a row
        if not any(str(d) * 5 in number for d in range(10)):
            return f"+91{number}"


def generate_record():
    failure_type = random.choices(
        FAILURE_TYPES,
        weights=[0.25, 0.20, 0.15, 0.15, 0.25],  # roughly realistic distribution
        k=1,
    )[0]
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    email = name.lower().replace(" ", ".") + f"{random.randint(1,999)}@example.com"
    is_subscription = failure_type == "subscription_mandate_failed" or random.random() < 0.2

    record = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:14]}",
        "customer_name": name,
        "customer_email": email,
        "customer_contact": generate_safe_phone(),
        "amount": random.choice([49900, 99900, 149900, 249900, 499900, 999900]),  # paise
        "currency": "INR",
        "failure_type": failure_type,
        "failure_code": random.choice(FAILURE_CODES[failure_type]),
        "is_subscription": is_subscription,
        "subscription_id": f"sub_{uuid.uuid4().hex[:14]}" if is_subscription else None,
        "created_at": (datetime.now(timezone.utc) - timedelta(
            hours=random.randint(1, 96))).isoformat(),
        "retry_count": 0,
        "status": "pending",
    }
    return record


def main():
    import os
    os.makedirs("data", exist_ok=True)

    batch = [generate_record() for _ in range(65)]  # >50 as the bar requires

    with open("data/transactions.json", "w") as f:
        json.dump(batch, f, indent=2)

    print(f"✅ Generated {len(batch)} synthetic transactions -> data/transactions.json")
    # quick distribution check
    from collections import Counter
    counts = Counter(r["failure_type"] for r in batch)
    for k, v in counts.items():
        print(f"   {k}: {v}")


if __name__ == "__main__":
    main()