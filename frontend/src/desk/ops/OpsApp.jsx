// The Desk · Ops Dashboard — internal-only view of the engine's run log.
//
// Reads from /api/desk/ops/*. Auth is HTTP Basic and handled by the
// browser; if the user hits /desk/ops without creds, server.py prompts
// before the page even loads. Routed at /desk/ops by DeskApp.jsx.
//
// Spec: THE_DESK_OPS_DASHBOARD_SPEC.md §8. Utilitarian + dense by
// intent — this is an operator tool, not editorial.

import { useCallback, useEffect, useState } from "react";

import "../../ledger/op-tokens.css";
import "./ops.css";

const SOURCE_LABELS = {
  polymarket_gamma: "Polymarket · gamma",
  kalshi_kxwcgame:  "Kalshi · KXWCGAME",
  elo_seed:         "Elo · seed",
  wc26_venues:      "WC26 · venues",
};

function fmtAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60)    return `${sec}s ago`;
  if (sec < 3600)  return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

function fmtClockUTC(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  const ss = String(d.getUTCSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}Z`;
}

function fmtUSD(n) {
  if (n === null || n === undefined) return "—";
  if (n === 0) return "$0";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  if (n < 1)    return `$${n.toFixed(3)}`;
  return `$${n.toFixed(2)}`;
}

// Frequency presets — readable labels for the cadences operators actually want.
const FREQ_PRESETS = [
  { label: "Hourly",        minutes: 60 },
  { label: "Every 6 hours", minutes: 360 },
  { label: "Every 12 hours", minutes: 720 },
  { label: "Daily",         minutes: 1440 },
  { label: "Every 3 days",  minutes: 4320 },
  { label: "Weekly",        minutes: 10080 },
];

async function fetchJson(path, options = {}) {
  const r = await fetch(path, { credentials: "same-origin", ...options });
  if (!r.ok) {
    throw Object.assign(new Error(`${r.status} ${r.statusText}`), { status: r.status });
  }
  return r.json();
}

export default function OpsApp() {
  const [report, setReport] = useState(null);
  const [manifest, setManifest] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async (runId = null) => {
    setLoading(true);
    setError(null);
    try {
      const m = await fetchJson("/api/desk/ops/runs?limit=5");
      const runs = m.runs || [];
      setManifest(runs);

      const target = runId || (runs[0] && runs[0].run_id);
      if (!target) {
        setReport(null);
        setSelectedRunId(null);
        setError("No runs recorded yet.");
        return;
      }
      const r = await fetchJson(`/api/desk/ops/runs/${target}`);
      setReport(r);
      setSelectedRunId(target);
    } catch (e) {
      setError(e.status === 404 ? "No runs recorded yet." : e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="op-page ops">
      <header className="ops__header">
        <div>
          <div className="ops__title">The Desk · Ops</div>
          <div className="ops__subtitle">
            {report
              ? <>Run <span className="mono">{report.run_id}</span> · {report.trigger} · finished {fmtAgo(report.finished_at)}</>
              : (loading ? "loading…" : "no run loaded")}
          </div>
        </div>
        <div className="ops__header-right">
          {report && <StatusPill status={report.status} />}
          <button className="ops__reload" onClick={() => load(selectedRunId)} disabled={loading}>
            ↻ Reload
          </button>
        </div>
      </header>

      {error && <div className="ops__error">{error}</div>}

      <Section title="Refresh control">
        <Control />
      </Section>

      <Section title={`Run history · last ${manifest.length}`}>
        <RunHistory
          manifest={manifest}
          selectedRunId={selectedRunId}
          onSelect={load}
        />
      </Section>

      {report && (
        <>
          <Section title="Sources read">
            <Sources sources={report.sources} />
          </Section>
          <Section title={`News signals · ${(report.signal_impact || []).length} outlets`}>
            <SignalImpact rows={report.signal_impact || []} />
          </Section>
        </>
      )}
    </div>
  );
}

// ── pieces ──────────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <section className="ops__section">
      <h2 className="ops__section-title">{title}</h2>
      {children}
    </section>
  );
}

function StatusPill({ status }) {
  return <span className={`ops__pill ops__pill--${status}`}>{status}</span>;
}

function Sources({ sources }) {
  if (!sources || sources.length === 0) {
    return <div className="ops__empty">no sources read</div>;
  }
  return (
    <table className="ops__sources">
      <tbody>
        {sources.map((s, i) => (
          <tr key={`${s.id}-${i}`}>
            <td className="ops__source-id">{SOURCE_LABELS[s.id] || s.id}</td>
            <td>
              <span className={`ops__pill ops__pill--source-${s.status}`}>
                {s.status}
              </span>
            </td>
            <td className="ops__source-detail">{s.detail || ""}</td>
            <td className="ops__source-time mono small">{fmtAgo(s.last_ok)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SignalImpact({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="ops__empty">no news outlets registered (or signals cache empty)</div>;
  }
  // Order: failed first (surface problems), then by this-run contribution
  // desc, then by name. Lets the operator scan top-down for "what acted
  // up" and "what mattered".
  const STATUS_ORDER = { failed: 0, stale: 1, fresh: 2, frozen: 3, static: 4 };
  const sorted = [...rows].sort((a, b) => {
    const sa = STATUS_ORDER[a.status] ?? 9;
    const sb = STATUS_ORDER[b.status] ?? 9;
    if (sa !== sb) return sa - sb;
    const ca = (a.citations || 0) + (a.hard_adjustments || 0);
    const cb = (b.citations || 0) + (b.hard_adjustments || 0);
    if (cb !== ca) return cb - ca;
    return a.name.localeCompare(b.name);
  });
  return (
    <table className="ops__signals">
      <thead>
        <tr>
          <th>Outlet</th>
          <th>Status</th>
          <th>Cached</th>
          <th>Signals</th>
          <th>Cites</th>
          <th>Hard adj.</th>
          <th>Fixtures</th>
          <th>Last fetch</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.source_id}>
            <td className="ops__signal-name">
              <span className="ops__signal-name-text">{r.name}</span>
              <span className="ops__signal-id mono small">{r.source_id}</span>
            </td>
            <td><span className={`ops__pill ops__pill--source-${r.status}`}>{r.status}</span></td>
            <td className="mono small num">{r.cached_items}</td>
            <td className="mono small num">{r.extracted_signals}</td>
            <td className="mono small num">{r.citations}</td>
            <td className="mono small num">{r.hard_adjustments}</td>
            <td className="mono small num">{r.fixtures_touched}</td>
            <td className="mono small">{fmtAgo(r.last_ok)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RunHistory({ manifest, selectedRunId, onSelect }) {
  if (!manifest || manifest.length === 0) {
    return <div className="ops__empty">no runs in manifest</div>;
  }
  return (
    <table className="ops__history">
      <thead>
        <tr>
          <th>Run</th>
          <th>Start</th>
          <th>End</th>
          <th>Finished</th>
          <th>Trigger</th>
          <th>Status</th>
          <th>Pub.</th>
          <th>Picks</th>
          <th>Δ</th>
          <th>Cost</th>
        </tr>
      </thead>
      <tbody>
        {manifest.map((row) => (
          <tr
            key={row.run_id}
            className={row.run_id === selectedRunId ? "is-selected" : ""}
            onClick={() => onSelect(row.run_id)}
          >
            <td className="mono small">{row.run_id}</td>
            <td className="mono small">{fmtClockUTC(row.started_at)}</td>
            <td className="mono small">{fmtClockUTC(row.finished_at)}</td>
            <td className="small">{fmtAgo(row.finished_at)}</td>
            <td className="small">{row.trigger}</td>
            <td><StatusPill status={row.status} /></td>
            <td className="mono small">{row.published}</td>
            <td className="mono small">{row.picks}</td>
            <td className="mono small">{row.change_count}</td>
            <td
              className="mono small ops__cost"
              title={row.cost_calls != null ? `${row.cost_calls} Haiku calls` : ""}
            >
              {fmtUSD(row.cost_usd)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Control panel ──────────────────────────────────────────────────
// Reads/writes /api/desk/ops/control. The refresh loop polls the same
// file every iteration, so changes land on the next scheduling
// decision — no server restart needed.

function Control() {
  const [state, setState]     = useState(null);
  const [draft, setDraft]     = useState(null);
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  const load = useCallback(async () => {
    try {
      const c = await fetchJson("/api/desk/ops/control");
      setState(c);
      setDraft({ enabled: c.enabled, interval_minutes: c.interval_minutes });
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!draft) {
    return <div className="ops__empty">{error || "loading control…"}</div>;
  }

  const dirty =
    state &&
    (draft.enabled !== state.enabled ||
     draft.interval_minutes !== state.interval_minutes);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const updated = await fetchJson("/api/desk/ops/control", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: draft.enabled,
          interval_minutes: draft.interval_minutes,
        }),
      });
      setState(updated);
      setDraft({ enabled: updated.enabled, interval_minutes: updated.interval_minutes });
      setSavedAt(updated.updated_at);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ops__control">
      <div className="ops__control-row">
        <label className="ops__control-toggle">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
            disabled={busy}
          />
          <span>{draft.enabled ? "Loop enabled" : "Loop disabled"}</span>
        </label>

        <div className="ops__control-freq">
          <label htmlFor="freq-select">Run every</label>
          <select
            id="freq-select"
            value={
              FREQ_PRESETS.find((p) => p.minutes === draft.interval_minutes)
                ? String(draft.interval_minutes)
                : "custom"
            }
            disabled={busy}
            onChange={(e) => {
              const v = e.target.value;
              if (v !== "custom") {
                setDraft({ ...draft, interval_minutes: parseInt(v, 10) });
              }
            }}
          >
            {FREQ_PRESETS.map((p) => (
              <option key={p.minutes} value={p.minutes}>{p.label}</option>
            ))}
            <option value="custom">Custom…</option>
          </select>
          <input
            type="number"
            min="5"
            max="10080"
            step="1"
            value={draft.interval_minutes}
            disabled={busy}
            onChange={(e) =>
              setDraft({ ...draft, interval_minutes: Math.max(5, Math.min(10080, parseInt(e.target.value || "0", 10))) })
            }
            className="ops__control-num"
          />
          <span className="small">minutes</span>
        </div>

        <button
          className="ops__reload"
          onClick={save}
          disabled={busy || !dirty}
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>

      <div className="ops__control-meta small">
        {state && (
          <>
            Current: <strong>{state.enabled ? "enabled" : "paused"}</strong>
            {" · "}every <strong>{state.interval_minutes}m</strong>
            {state.updated_at && <> · last changed {fmtAgo(state.updated_at)}</>}
          </>
        )}
        {savedAt && <span className="ops__control-saved"> · saved ✓</span>}
        {error && <span className="ops__control-error"> · {error}</span>}
      </div>
    </div>
  );
}
