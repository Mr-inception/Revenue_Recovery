"""
Step 3: Decision engine.
Maps root_cause -> one bounded action. Enforces stopping rules (max retries, cooldown).
"""
from datetime import datetime, timedelta, timezone

MAX_RETRIES = 3
COOLDOWN_HOURS = {
    "CARD_ISSUE": 6,
    "FUNDS_ISSUE": 24,      # give salary/funds time to arrive
    "TRANSIENT_ERROR": 1,   # retry soon, likely to succeed
    "MANDATE_ISSUE": 12,
    "ABANDONMENT": 2,
}

ACTION_MAP = {
    "CARD_ISSUE": "SEND_RECOVERY_LINK",
    "FUNDS_ISSUE": "SEND_RECOVERY_LINK",
    "TRANSIENT_ERROR": "RETRY_PAYMENT",
    "MANDATE_ISSUE": "RETRY_MANDATE",
    "ABANDONMENT": "SEND_NUDGE",
    "UNKNOWN": "ESCALATE_HUMAN",
}


def decide(record):
    """
    Mutates and returns record with: action, action_reason, next_eligible_at.
    Enforces max retries; cooldown is applied by the orchestrator between attempts.
    """
    root_cause = record.get("root_cause", "UNKNOWN")
    retry_count = record.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        record["action"] = "STOP_MAX_RETRIES"
        record["action_reason"] = f"Reached max retries ({MAX_RETRIES})"
        record["status"] = "exhausted"
        return record

    action = ACTION_MAP.get(root_cause, "ESCALATE_HUMAN")
    cooldown = COOLDOWN_HOURS.get(root_cause, 24)

    record["action"] = action
    record["action_reason"] = f"root_cause={root_cause}, attempt={retry_count + 1}/{MAX_RETRIES}"
    record["next_eligible_at"] = (
        datetime.now(timezone.utc) + timedelta(hours=cooldown)
    ).isoformat()

    return record


if __name__ == "__main__":
    import json
    with open("data/transactions.json") as f:
        batch = json.load(f)

    for r in batch[:5]:
        r["root_cause"] = "CARD_ISSUE"  # manual test value
        decide(r)
        print(r["transaction_id"], "->", r["action"], "|", r["action_reason"])
