# AI Revenue Recovery Agent

**Razorpay AI Buildathon — Track 03: AI Revenue Recovery**

An agent that detects revenue at risk from failed payments, diagnoses the root
cause, decides on a bounded recovery action, executes it against Razorpay's
test-mode APIs, and logs a full audit trail — with measured money recovered
across a 65-record batch.

## What it does

Every failed or at-risk transaction goes through four stages:

```
Diagnose  →  Decide  →  Execute  →  Log
```

1. **Diagnose** (`02_diagnose.py`) — classifies the failure into a root cause
   (card issue, insufficient funds, transient gateway error, mandate issue,
   or checkout abandonment). Rule-based first pass on known error codes;
   Gemini API fallback for anything the rules can't classify.

2. **Decide** (`03_decide.py`) — maps root cause to exactly one bounded
   action (send a recovery link, retry payment, retry mandate, send a nudge,
   or escalate to a human). Enforces a hard stop after 3 retries per case and
   a cooldown window before the next attempt, so the agent never loops
   indefinitely on a case that isn't recovering.

3. **Execute** (`04_execute.py`) — carries out the action. Recovery
   links/nudges call the real Razorpay Payment Links API. Payment/mandate
   retries are logged as attempted (no live card/mandate exists in a batch
   job to actually retry against — see **Design decisions** below).

4. **Log** (`05_audit_db.py`) — every decision and outcome is written to a
   SQLite audit trail: root cause, action, execution result, retry count,
   money recovered, timestamp.

The orchestrator (`06_pipeline.py`) runs all four stages across the batch and
reports aggregate metrics. A FastAPI layer (`07_api.py`) exposes it over HTTP,
and a Next.js dashboard (`frontend/`) visualizes it.

## Results (sample run, 65-record batch)

| Metric | Value |
|---|---|
| Cases processed | 65 |
| Money recovered | ₹1,18,466 |
| Sent (recovery link / nudge) | 44 |
| Retry attempted | 21 |
| Exceptions | 0 |

Outcomes are simulated with a fixed random seed for reproducibility — see
below for why, and what "simulated" actually means here.

## Architecture

```
data/transactions.json   — synthetic batch (65 records, 5 failure types)
        │
        ▼
02_diagnose.py  → root_cause (rule-based, Gemini fallback)
        │
        ▼
03_decide.py    → action + stopping rules (max 3 retries, cooldown)
        │
        ▼
04_execute.py   → real Razorpay API call OR simulated (see below)
        │
        ▼
05_audit_db.py  → SQLite audit_log table
        │
        ▼
06_pipeline.py  → orchestrates all of the above, reports metrics
        │
        ▼
07_api.py       → FastAPI: /run-batch, /metrics, /audit
        │
        ▼
frontend/       → Next.js dashboard (ledger-style audit trail UI)
```

## Design decisions (and what broke)

**Test-mode's 30-link cap, not a rate limit.** Razorpay's test mode allows
only 30 Payment Links per business, total — not per minute. Early runs threw
`"Too many requests"` on batch calls, which I first misdiagnosed as a
standard rate limit and tried to fix with exponential backoff. That didn't
help, because it isn't a throttle — it's a hard account ceiling. Once
diagnosed correctly, the fix was architectural: prove the real integration
works via a small number of live calls, then simulate the rest of the batch
with an honestly labeled `[simulated]` tag in the execution detail. Real
capability is proven in `00_test_connection.py` and a standalone
`04_execute.py` run, both of which created genuine Razorpay payment links.

**Retry actions are simulated, transparently.** `RETRY_PAYMENT` and
`RETRY_MANDATE` can't be real in a batch job — there's no live card or
mandate session to retry against outside an actual checkout flow. These are
logged identically to how a real retry attempt would be logged, clearly
flagged, so the audit trail never claims something happened that didn't.

**Recovery outcomes are simulated, with a fixed seed.** Whether a sent
recovery link actually gets paid would come from a Razorpay webhook
(`payment_link.paid`) in production — not knowable synchronously in a batch
script. `simulate_outcome()` draws a probability per action type, seeded
(`random.seed(42)`, reset at the start of every run) so the ₹ recovered
figure is reproducible across runs and demos, not a different number every
time.

**Audit log resets per run, not cumulative.** Originally, calling
`/run-batch` twice appended a second full pass onto the first, doubling
`total_events` and inflating recovered-money metrics — a real bug that would
have looked bad in front of judges re-running the API. Fixed by clearing the
audit table at the start of every `run_pipeline()` call, so each run reports
one clean, self-contained batch result.

**Phone number validation.** Razorpay's fraud check rejects customer contact
numbers with 5+ repeating digits (e.g. `9999999999`). The synthetic data
generator (`01_generate_data.py`) explicitly avoids generating these.

## Setup

### Backend

```bash
pip install razorpay fastapi uvicorn google-genai python-dotenv
```

Set environment variables (get keys from
[Razorpay Dashboard → Test Mode → API Keys](https://dashboard.razorpay.com)
and [Google AI Studio](https://aistudio.google.com/apikey)):

```bash
export RAZORPAY_KEY_ID="rzp_test_..."
export RAZORPAY_KEY_SECRET="..."
export GEMINI_API_KEY="..."
```

Run the pipeline stages in order:

```bash
python 01_generate_data.py   # generates data/transactions.json
python 06_pipeline.py        # runs the full pipeline, prints metrics
uvicorn 07_api:app --reload --port 8000   # serves the API
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Requires the backend running on port 8000.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Health check |
| `/run-batch` | POST | Runs the full pipeline over `data/transactions.json` |
| `/metrics` | GET | Aggregate recovery metrics |
| `/audit?limit=N` | GET | Raw audit log rows |

## Stack

Python, FastAPI, SQLite, Razorpay Python SDK, Google Gemini API (`gemini-2.5-flash`),
Next.js, TypeScript, Tailwind CSS, Recharts.
