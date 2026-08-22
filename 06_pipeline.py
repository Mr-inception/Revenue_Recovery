"""
Step 6: Orchestrate the full pipeline over a batch.
Run: python 06_pipeline.py
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import random
import importlib

diagnose_mod = importlib.import_module("02_diagnose")
decide_mod = importlib.import_module("03_decide")
execute_mod = importlib.import_module("04_execute")
audit_mod = importlib.import_module("05_audit_db")

# For demo purposes only: probability a sent recovery link/nudge actually
# gets paid. In production this would come from a Razorpay webhook
# (payment_link.paid event), not a random draw.
SIMULATED_SUCCESS_RATE = {
    "SEND_RECOVERY_LINK": 0.55,
    "SEND_NUDGE": 0.40,
    "RETRY_PAYMENT": 0.65,
    "RETRY_MANDATE": 0.45,
}


def simulate_outcome(record):
    """Clearly-flagged simulation of whether the action recovered money."""
    action = record.get("action")
    rate = SIMULATED_SUCCESS_RATE.get(action, 0)
    if random.random() < rate:
        record["money_recovered"] = record["amount"]
        record["status"] = "recovered"
    else:
        record["money_recovered"] = 0
        record["status"] = "not_recovered_yet"
    record["outcome_is_simulated"] = True
    return record


def run_pipeline(batch_path="data/transactions.json"):
    random.seed(42)  # reset every run so recovered-amount numbers are reproducible
    audit_mod.init_db()
    audit_mod.clear_audit_log()  # each run = one clean batch, not cumulative

    with open(batch_path) as f:
        batch = json.load(f)

    for record in batch:
        process_case(record)

    with open("data/results.json", "w") as f:
        json.dump(batch, f, indent=2)

    metrics = audit_mod.get_metrics()
    print("✅ Pipeline run complete")
    print(json.dumps(metrics, indent=2))
    return metrics


def process_case(record):
    """
    Diagnoses once (root cause doesn't change between attempts), then
    loops decide -> execute -> log until the case resolves (recovered),
    gets escalated, or hits the stopping rule (max retries). This is what
    actually exercises 03_decide.py's stopping/cooldown logic within a
    single batch run, instead of requiring separate pipeline invocations.
    """
    diagnose_mod.diagnose(record)

    while True:
        decide_mod.decide(record)

        if record["action"] == "STOP_MAX_RETRIES":
            audit_mod.log_record(record)
            break

        # NOTE: decide() sets next_eligible_at (a real cooldown window), but
        # this batch script processes the whole case history in one pass
        # rather than actually waiting hours between attempts — the cooldown
        # value is still recorded per attempt for audit purposes. A
        # production deployment would schedule the next attempt via a queue
        # instead of looping immediately.
        execute_mod.execute(record)
        simulate_outcome(record)
        audit_mod.log_record(record)

        if record["status"] == "recovered":
            break
        if record["action"] == "ESCALATE_HUMAN":
            break  # handed to a human, no further automated attempts

    return record


if __name__ == "__main__":
    run_pipeline()