"""
Step 5: SQLite audit trail. Every decision + action + outcome gets logged here.
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import json
from datetime import datetime

DB_PATH = "data/audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    customer_email TEXT,
    amount INTEGER,
    failure_type TEXT,
    root_cause TEXT,
    diagnosis_method TEXT,
    action TEXT,
    action_reason TEXT,
    execution_status TEXT,
    execution_detail TEXT,
    retry_count INTEGER,
    money_recovered INTEGER DEFAULT 0,
    logged_at TEXT
);
"""


def init_db():
    import os
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def log_record(record):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO audit_log (
            transaction_id, customer_email, amount, failure_type, root_cause,
            diagnosis_method, action, action_reason, execution_status,
            execution_detail, retry_count, money_recovered, logged_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("transaction_id"),
        record.get("customer_email"),
        record.get("amount"),
        record.get("failure_type"),
        record.get("root_cause"),
        record.get("diagnosis_method"),
        record.get("action"),
        record.get("action_reason"),
        record.get("execution_status"),
        record.get("execution_detail"),
        record.get("retry_count"),
        record.get("money_recovered", 0),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()

def clear_audit_log():
    """Clears all rows so a fresh batch run reports clean, non-cumulative metrics."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM audit_log")
    conn.commit()
    conn.close()


def get_metrics():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*), COUNT(DISTINCT transaction_id) FROM audit_log")
    total_events, total_cases = cur.fetchone()

    cur.execute("SELECT SUM(money_recovered) FROM audit_log")
    recovered = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT execution_status, COUNT(*) FROM audit_log GROUP BY execution_status
    """)
    status_breakdown = dict(cur.fetchall())

    cur.execute("""
        SELECT transaction_id, execution_status, execution_detail
        FROM audit_log WHERE execution_status IN ('failed', 'escalated', 'unknown_action')
    """)
    exceptions = [
        {"transaction_id": r[0], "status": r[1], "detail": r[2]}
        for r in cur.fetchall()
    ]

    conn.close()
    return {
        "total_events": total_events,
        "total_cases": total_cases,
        "money_recovered_paise": recovered,
        "money_recovered_inr": recovered / 100,
        "status_breakdown": status_breakdown,
        "exceptions": exceptions,
    }


if __name__ == "__main__":
    init_db()
    print("✅ audit.db initialized at", DB_PATH)
    print(json.dumps(get_metrics(), indent=2))
