"""
Step 7: FastAPI backend for the dashboard.
Run: uvicorn 07_api:app --reload --port 8000
(NOTE: uvicorn needs a valid module name — rename this file's import target
 to `api.py` when you wire it into your final repo, or run via:
 python -c "import importlib,uvicorn; m=importlib.import_module('07_api'); uvicorn.run(m.app)")
"""
import importlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

pipeline_mod = importlib.import_module("06_pipeline")
audit_mod = importlib.import_module("05_audit_db")

app = FastAPI(title="Revenue Recovery Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before submission
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "revenue-recovery-agent"}


@app.post("/run-batch")
def run_batch():
    """Runs the full pipeline over data/transactions.json"""
    metrics = pipeline_mod.run_pipeline()
    return metrics


@app.get("/metrics")
def metrics():
    return audit_mod.get_metrics()


@app.get("/audit")
def audit_log(limit: int = 100):
    import sqlite3
    conn = sqlite3.connect(audit_mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"count": len(rows), "rows": rows}
