"use client";

import { useState, useEffect, useCallback } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const API_BASE = "http://127.0.0.1:8000";

type Metrics = {
  total_events: number;
  total_cases: number;
  money_recovered_paise: number;
  money_recovered_inr: number;
  status_breakdown: Record<string, number>;
  exceptions: { transaction_id: string; status: string; detail: string }[];
};

type AuditRow = {
  id: number;
  transaction_id: string;
  customer_email: string;
  amount: number;
  failure_type: string;
  root_cause: string;
  diagnosis_method: string;
  action: string;
  action_reason: string;
  execution_status: string;
  execution_detail: string;
  retry_count: number;
  money_recovered: number;
  logged_at: string;
};

const STATUS_COLORS: Record<string, string> = {
  sent: "var(--green)",
  retry_attempted: "var(--amber)",
  escalated: "var(--red)",
  stopped: "var(--muted)",
  failed: "var(--red)",
};

function formatINR(paise: number) {
  return (paise / 100).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [m, a] = await Promise.all([
        fetch(`${API_BASE}/metrics`).then((r) => r.json()),
        fetch(`${API_BASE}/audit?limit=65`).then((r) => r.json()),
      ]);
      setMetrics(m);
      setAudit(a.rows ?? []);
    } catch {
      setError(
        "Can't reach the backend at " +
          API_BASE +
          ". Is uvicorn running on port 8000?"
      );
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function runBatch() {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_BASE}/run-batch`, { method: "POST" });
      await loadData();
    } catch {
      setError("Batch run failed — check the backend terminal for details.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = metrics
    ? Object.entries(metrics.status_breakdown).map(([status, count]) => ({
        status,
        count,
      }))
    : [];

  return (
    <main className="min-h-screen px-6 py-10 md:px-12 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
        <div>
          <p
            className="text-xs uppercase tracking-[0.2em] mb-2"
            style={{ color: "var(--muted)" }}
          >
            AI Revenue Recovery — Audit Console
          </p>
          <h1 className="font-display text-3xl md:text-4xl font-bold">
            Recovery batch ledger
          </h1>
        </div>
        <button
          onClick={runBatch}
          disabled={loading}
          className="font-mono text-sm px-5 py-3 rounded-md border transition-colors disabled:opacity-50"
          style={{
            borderColor: "var(--green)",
            color: "var(--green)",
            background: "transparent",
          }}
        >
          {loading ? "Running batch…" : "Run batch"}
        </button>
      </div>

      {error && (
        <div
          className="mb-8 px-4 py-3 rounded-md text-sm"
          style={{
            background: "rgba(229,72,77,0.1)",
            border: "1px solid var(--red)",
            color: "var(--red)",
          }}
        >
          {error}
        </div>
      )}

      {metrics && (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px mb-10 rounded-lg overflow-hidden border" style={{ borderColor: "var(--panel-border)" }}>
            <SummaryCell
              label="Recovered"
              value={formatINR(metrics.money_recovered_paise)}
              accent="var(--green)"
            />
            <SummaryCell
              label="Cases processed"
              value={String(metrics.total_cases)}
            />
            <SummaryCell
              label="Sent"
              value={String(metrics.status_breakdown.sent ?? 0)}
              accent="var(--green)"
            />
            <SummaryCell
              label="Exceptions"
              value={String(metrics.exceptions.length)}
              accent={metrics.exceptions.length ? "var(--red)" : undefined}
            />
          </div>

          {/* Status breakdown chart */}
          <section className="mb-10">
            <h2 className="font-display text-lg font-medium mb-4">
              Action breakdown
            </h2>
            <div
              className="rounded-lg border p-4"
              style={{ borderColor: "var(--panel-border)", background: "var(--panel)" }}
            >
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--panel-border)" horizontal={false} />
                  <XAxis type="number" stroke="var(--muted)" fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="status"
                    stroke="var(--muted)"
                    fontSize={12}
                    width={140}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--bg)",
                      border: "1px solid var(--panel-border)",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={STATUS_COLORS[entry.status] ?? "var(--muted)"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Exceptions */}
          {metrics.exceptions.length > 0 && (
            <section className="mb-10">
              <h2 className="font-display text-lg font-medium mb-4" style={{ color: "var(--red)" }}>
                Exceptions ({metrics.exceptions.length})
              </h2>
              <div
                className="rounded-lg border divide-y"
                style={{ borderColor: "var(--panel-border)" }}
              >
                {metrics.exceptions.map((exc) => (
                  <div
                    key={exc.transaction_id}
                    className="px-4 py-3 text-sm flex justify-between gap-4"
                    style={{ borderColor: "var(--panel-border)" }}
                  >
                    <span style={{ color: "var(--muted)" }}>
                      {exc.transaction_id}
                    </span>
                    <span className="text-right">{exc.detail}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Audit trail — ledger tape */}
          <section>
            <h2 className="font-display text-lg font-medium mb-4">
              Audit trail
            </h2>
            <div className="relative pl-6">
              <div
                className="absolute left-[7px] top-2 bottom-2 w-px"
                style={{ background: "var(--panel-border)" }}
              />
              <div className="space-y-3">
                {audit.map((row) => (
                  <div key={row.id} className="relative">
                    <div
                      className="absolute -left-6 top-2 w-[9px] h-[9px] rounded-full border-2"
                      style={{
                        borderColor: STATUS_COLORS[row.execution_status] ?? "var(--muted)",
                        background: "var(--bg)",
                      }}
                    />
                    <div
                      className="rounded-lg border px-4 py-3 text-sm"
                      style={{ borderColor: "var(--panel-border)", background: "var(--panel)" }}
                    >
                      <div className="flex flex-wrap justify-between gap-2 mb-1">
                        <span className="font-medium">{row.transaction_id}</span>
                        <span style={{ color: "var(--muted)" }}>
                          {new Date(row.logged_at).toLocaleString("en-IN")}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
                        <span>root_cause: <span style={{ color: "var(--text)" }}>{row.root_cause}</span></span>
                        <span>action: <span style={{ color: "var(--text)" }}>{row.action}</span></span>
                        <span>status: <span style={{ color: STATUS_COLORS[row.execution_status] ?? "var(--text)" }}>{row.execution_status}</span></span>
                        {row.money_recovered > 0 && (
                          <span style={{ color: "var(--green)" }}>
                            +{formatINR(row.money_recovered)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function SummaryCell({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="p-5" style={{ background: "var(--panel)" }}>
      <p className="text-xs uppercase tracking-wide mb-1" style={{ color: "var(--muted)" }}>
        {label}
      </p>
      <p
        className="font-display text-2xl font-bold"
        style={{ color: accent ?? "var(--text)" }}
      >
        {value}
      </p>
    </div>
  );
}
