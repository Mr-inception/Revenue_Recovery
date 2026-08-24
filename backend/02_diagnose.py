"""
Step 2: Diagnose root cause for each transaction.
Rule-based first pass; Gemini API fallback for anything ambiguous.
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = "data/diagnosis_cache.json"
try:
    with open(CACHE_FILE, "r") as f:
        _diagnosis_cache = json.load(f)
except FileNotFoundError:
    _diagnosis_cache = {}

def _save_cache():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(_diagnosis_cache, f)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set. "
        "Get a key from https://aistudio.google.com/apikey and set it before running."
    )
_client = genai.Client(api_key=GEMINI_API_KEY)
_MODEL = "gemini-2.5-flash"

# Codes the rules engine deliberately does NOT cover — these force the
# Gemini fallback path to actually run, instead of every case resolving
# via rules alone. See 01_generate_data.py for where these get generated.
RULE_MAP = {
    "BAD_REQUEST_ERROR": "CARD_ISSUE",
    "CARD_DECLINED_BY_ISSUER": "CARD_ISSUE",
    "INSUFFICIENT_FUNDS": "FUNDS_ISSUE",
    "GATEWAY_ERROR": "TRANSIENT_ERROR",
    "TIMEOUT": "TRANSIENT_ERROR",
    "MANDATE_REJECTED": "MANDATE_ISSUE",
    "MANDATE_EXPIRED": "MANDATE_ISSUE",
    "USER_DROPPED_OFF": "ABANDONMENT",
    # Intentionally unmapped: "PROCESSOR_ERROR", "UNCATEGORIZED_DECLINE"
}


def diagnose_rule_based(record):
    code = record.get("failure_code")
    return RULE_MAP.get(code)


def diagnose_with_gemini(record):
    # Gemini free-tier quota is 5 requests/minute, so this throttle keeps calls safely under that limit 
    # and avoids unnecessary escalations to ESCALATE_HUMAN when the real diagnosis could have succeeded.
    time.sleep(13)

    prompt = f"""You are classifying a failed payment for root-cause analysis.
Transaction failure_type: {record['failure_type']}
failure_code: {record['failure_code']}
is_subscription: {record['is_subscription']}

Classify into exactly one of: CARD_ISSUE, FUNDS_ISSUE, TRANSIENT_ERROR, MANDATE_ISSUE, ABANDONMENT, UNKNOWN.
Reply with only the label, nothing else."""
    try:
        resp = _client.models.generate_content(model=_MODEL, contents=prompt)
        label = resp.text.strip().upper()
        valid = {"CARD_ISSUE", "FUNDS_ISSUE", "TRANSIENT_ERROR", "MANDATE_ISSUE", "ABANDONMENT"}
        return label if label in valid else "UNKNOWN"
    except Exception as e:
        print(f"⚠️ Gemini fallback failed for {record['transaction_id']}: {e}")
        return "UNKNOWN"


def diagnose(record):
    """Returns root_cause string. Rules first, Gemini only if rules can't classify."""
    cache_key = f"{record.get('failure_type')}|{record.get('failure_code')}|{record.get('is_subscription')}"
    if cache_key in _diagnosis_cache:
        record["root_cause"] = _diagnosis_cache[cache_key]
        record["diagnosis_method"] = "cached"
        return record

    root_cause = diagnose_rule_based(record)
    if root_cause is None:
        root_cause = diagnose_with_gemini(record)
        record["diagnosis_method"] = "gemini_fallback"
        _diagnosis_cache[cache_key] = root_cause
        _save_cache()
    else:
        record["diagnosis_method"] = "rule_based"
    record["root_cause"] = root_cause
    return record


if __name__ == "__main__":
    import json
    with open("data/transactions.json") as f:
        batch = json.load(f)
    for r in batch[:5]:
        diagnose(r)
        print(r["transaction_id"], "->", r["root_cause"], f"({r['diagnosis_method']})")