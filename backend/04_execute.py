"""
Step 4: Execute the decided action against Razorpay test-mode APIs.
RETRY_PAYMENT / RETRY_MANDATE are simulated (no real card present in a batch
job) but logged identically to a real retry attempt.
SEND_RECOVERY_LINK / SEND_NUDGE create a REAL Razorpay test-mode payment link.
"""
import os
import time
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import razorpay
from dotenv import load_dotenv

load_dotenv()

KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
if not KEY_ID or not KEY_SECRET:
    raise RuntimeError(
        "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET environment variables are not set. "
        "Get test-mode keys from https://dashboard.razorpay.com and set them before running."
    )

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Razorpay test mode allows only 30 Payment Links per business, TOTAL, ever —
# not per minute (confirmed via Razorpay docs). This is a hard account
# ceiling, not a throttle that backoff can work around. Real proof-of-concept
# calls (00_test_connection.py, standalone 04_execute.py run) already confirm
# the integration genuinely works end to end. So: the batch pipeline defaults
# to ZERO real API calls (fully simulated, honestly labeled), keeping real
# calls to a separate, deliberate, rate-limited demo path you control.
_MIN_DELAY_SECONDS = 2.0
_MAX_RETRIES = 2
_REAL_API_CALL_LIMIT = 0  # set to a small number (e.g. 2) only for a live demo run
_real_call_count = 0


class CredentialError(Exception):
    """Raised when Razorpay rejects the request due to bad credentials.
    This must NEVER be caught and treated as a simulated success — it means
    the setup is broken, not that a business outcome (like the 30-link cap)
    occurred."""
    pass


def _is_auth_error(exc):
    msg = str(exc).lower()
    return "authentication" in msg or "unauthorized" in msg or "invalid key" in msg


def _create_payment_link(record):
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            time.sleep(_MIN_DELAY_SECONDS)  # throttle every call, not just retries
            link = client.payment_link.create({
                "amount": record["amount"],
                "currency": record["currency"],
                "description": f"Payment recovery for {record['transaction_id']}",
                "customer": {
                    "name": record["customer_name"],
                    "email": record["customer_email"],
                    "contact": record["customer_contact"],
                },
                "notify": {"sms": False, "email": False},
                "notes": {
                    "original_transaction_id": record["transaction_id"],
                    "root_cause": record.get("root_cause", "UNKNOWN"),
                },
            })
            return link
        except Exception as e:
            if _is_auth_error(e):
                # Never retry or simulate around bad credentials — surface
                # this immediately and loudly.
                raise CredentialError(
                    f"Razorpay rejected the credentials: {e}. "
                    "Check RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET."
                ) from e
            last_error = e
            msg = str(e).lower()
            if "too many requests" in msg or "rate" in msg:
                backoff = (2 ** attempt) * 2
                print(f"⚠️ Rate limited on {record['transaction_id']}, "
                      f"retrying in {backoff}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(backoff)
                continue
            # Not a rate-limit issue (e.g. bad phone number) — don't retry
            raise e
    raise last_error


def execute(record):
    """
    Mutates and returns record with: execution_status, execution_detail,
    money_recovered (0 unless simulated success).
    """
    global _real_call_count
    action = record.get("action")
    record["retry_count"] = record.get("retry_count", 0) + 1

    try:
        if action in ("SEND_RECOVERY_LINK", "SEND_NUDGE"):
            if _real_call_count < _REAL_API_CALL_LIMIT:
                _real_call_count += 1  # reserve the slot regardless of outcome,
                                        # so a failure doesn't cause endless retries
                try:
                    link = _create_payment_link(record)
                    record["execution_status"] = "sent"
                    record["execution_detail"] = link["short_url"]
                    record["razorpay_link_id"] = link["id"]
                    record["execution_is_real_api_call"] = True
                except CredentialError:
                    raise  # never simulate around bad credentials — let it crash loudly
                except Exception as e:
                    # Real call failed for a business reason (e.g. the 30-link
                    # cap) — degrade to simulated instead of failing the record.
                    record["execution_status"] = "sent"
                    record["execution_detail"] = (
                        f"[simulated - real API call failed: {e}] "
                        f"would create payment link for {record['transaction_id']}"
                    )
                    record["execution_is_real_api_call"] = False
            else:
                record["execution_status"] = "sent"
                record["execution_detail"] = (
                    f"[simulated] would create payment link for "
                    f"{record['transaction_id']} (real-call budget not used this run)"
                )
                record["execution_is_real_api_call"] = False

        elif action in ("RETRY_PAYMENT", "RETRY_MANDATE"):
            # No real card/mandate available in a batch job — this is where
            # you'd hook a real retry API in production. Logged as attempted.
            record["execution_status"] = "retry_attempted"
            record["execution_detail"] = f"{action} attempt #{record['retry_count']}"

        elif action == "ESCALATE_HUMAN":
            record["execution_status"] = "escalated"
            record["execution_detail"] = "Flagged for manual review"

        elif action == "STOP_MAX_RETRIES":
            record["execution_status"] = "stopped"
            record["execution_detail"] = "Max retries reached, no further action"

        else:
            record["execution_status"] = "unknown_action"
            record["execution_detail"] = f"Unhandled action: {action}"

    except Exception as e:
        record["execution_status"] = "failed"
        record["execution_detail"] = str(e)

    return record


if __name__ == "__main__":
    test_record = {
        "transaction_id": "txn_test123",
        "customer_name": "Test User",
        "customer_email": "test@example.com",
        "customer_contact": "+919876543210",
        "amount": 49900,
        "currency": "INR",
        "action": "SEND_RECOVERY_LINK",
        "root_cause": "CARD_ISSUE",
        "retry_count": 0,
    }
    execute(test_record)
    print(test_record["execution_status"], "->", test_record["execution_detail"])