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

const STAGE_LABELS = {
  polymarket_events:        "Polymarket events fetched",
  after_competition_filter: "After competition filter",
  priced_fixtures:          "Priced fixtures",
  verdict_eligible:         "Verdict-eligible",
  published:                "Published",
};

const SOURCE_LABELS = {
  polymarket_gamma: "Polymarket · gamma",
  kalshi_kxwcgame:  "Kalshi · KXWCGAME",
  elo_seed:         "Elo · seed",
  wc26_venues:      "WC26 · venues",
};

const CHANGE_LABEL = {
  new:     "new fixture",
  dropped: "dropped fixture",
  flip:    "verdict flipped",
  side:    "pick side rotated",
  edge:    "edge moved",
  venue:   "venue set changed",
  copy:    "copy changed",
};

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toUTCString().replace("GMT", "UTC");
}

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

function fmtDuration(s) {
  if (s == null) return "—";
  if (s < 1)   return `${Math.round(s * 1000)}ms`;
  if (s < 60)  return `${s.toFixed(1)}s`;
  return `${Math.round(s / 60)}m ${Math.round(s % 60)}s`;
}

async function fetchJson(path) {
  const r = await fetch(path, { credentials: "same-origin" });
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
      const [r, m] = await Promise.all([
        fetchJson(runId ? `/api/desk/ops/runs/${runId}` : "/api/desk/ops/latest"),
        fetchJson("/api/desk/ops/runs?limit=50"),
      ]);
      setReport(r);
      setManifest(m.runs || []);
      setSelectedRunId(runId || (r && r.run_id) || null);
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

      {report && (
        <>
          <MetricStrip report={report} />
          <div className="ops__grid">
            <Section title="Pipeline funnel">
              <Funnel funnel={report.funnel} forcedPass={report.forced_pass} />
            </Section>
            <Section title="Sources read">
              <Sources sources={report.sources} />
            </Section>
            <Section title="Verdict split">
              <VerdictSplit v={report.verdicts} published={publishedCount(report)} />
            </Section>
            <Section title={`Match changes since last run · ${report.changes.length}`}>
              <Changes changes={report.changes} />
            </Section>
            <Section title={`Errors & filters · ${report.errors.length}`}>
              <ErrorsList errors={report.errors} />
            </Section>
            <Section title={`Run history · ${manifest.length}`}>
              <RunHistory
                manifest={manifest}
                selectedRunId={selectedRunId}
                onSelect={load}
              />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

// ── helpers ─────────────────────────────────────────────────────────

function publishedCount(report) {
  const row = (report.funnel || []).find((s) => s.stage === "published");
  return row ? row.n : 0;
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

function MetricStrip({ report }) {
  const published = publishedCount(report);
  const items = [
    ["Run",        <span className="mono small">{report.run_id}</span>],
    ["Status",     <StatusPill status={report.status} />],
    ["Duration",   fmtDuration(report.duration_s)],
    ["Published",  published],
    ["Picks",      report.verdicts.pick],
    ["Changes",    report.changes.length],
  ];
  return (
    <div className="ops__metrics">
      {items.map(([label, value]) => (
        <div key={label} className="ops__metric">
          <div className="ops__metric-label">{label}</div>
          <div className="ops__metric-value">{value}</div>
        </div>
      ))}
    </div>
  );
}

function Funnel({ funnel, forcedPass }) {
  if (!funnel || funnel.length === 0) {
    return <div className="ops__empty">no funnel data</div>;
  }
  const max = Math.max(...funnel.map((s) => s.n), 1);
  return (
    <table className="ops__funnel">
      <tbody>
        {funnel.map((row) => (
          <tr key={row.stage}>
            <td className="ops__funnel-label">{STAGE_LABELS[row.stage] || row.stage}</td>
            <td className="ops__funnel-bar">
              <div className="ops__bar">
                <div
                  className="ops__bar-fill"
                  style={{ width: `${(row.n / max) * 100}%` }}
                />
              </div>
            </td>
            <td className="ops__funnel-n mono">{row.n}</td>
            <td className="ops__funnel-note">{row.note || ""}</td>
          </tr>
        ))}
        {forcedPass && (forcedPass.illiquid || forcedPass.stub_elo) ? (
          <tr className="ops__funnel-forced">
            <td className="ops__funnel-label">↳ forced Pass</td>
            <td colSpan="3" className="ops__funnel-note">
              {forcedPass.stub_elo ? `${forcedPass.stub_elo} stub_elo` : null}
              {forcedPass.stub_elo && forcedPass.illiquid ? " · " : null}
              {forcedPass.illiquid ? `${forcedPass.illiquid} illiquid` : null}
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
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

function VerdictSplit({ v, published }) {
  const total = Math.max(1, (v.pick || 0) + (v.pass || 0) + (v.avoid || 0));
  const seg = (n, kind) => ({
    width: `${(n / total) * 100}%`,
    background: kind === "pick"  ? "var(--flame)"
              : kind === "avoid" ? "var(--ink-soft)"
              :                    "var(--paper-deep)",
  });
  return (
    <div>
      <div className="ops__split-bar">
        <div style={seg(v.pick,  "pick")} title={`pick ${v.pick}`} />
        <div style={seg(v.pass,  "pass")} title={`pass ${v.pass}`} />
        <div style={seg(v.avoid, "avoid")} title={`avoid ${v.avoid}`} />
      </div>
      <div className="ops__split-legend mono small">
        <span>pick {v.pick}</span>
        <span>pass {v.pass}</span>
        <span>avoid {v.avoid}</span>
        <span className="ops__split-total">{published} published</span>
      </div>
      {(v.avoid === 0) && (
        <div className="ops__note">
          Avoid is structurally ~0 on single-venue normalized odds — see
          Phase A.4 in <span className="mono">THE_DESK_OPTIMIZATION_SPEC.md</span>.
        </div>
      )}
    </div>
  );
}

function Changes({ changes }) {
  if (!changes || changes.length === 0) {
    return <div className="ops__empty">no changes from previous run</div>;
  }
  return (
    <table className="ops__changes">
      <tbody>
        {changes.map((c, i) => (
          <tr key={i}>
            <td className={`ops__change-type ops__change-type--${c.type}`}>
              {CHANGE_LABEL[c.type] || c.type}
            </td>
            <td className="ops__change-id mono small">{c.match_id}</td>
            <td className="ops__change-detail">
              {c.from != null && c.to != null
                ? <><span className="mono">{c.from}</span> → <span className="mono">{c.to}</span></>
                : (c.detail || "")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ErrorsList({ errors }) {
  if (!errors || errors.length === 0) {
    return <div className="ops__empty">no errors</div>;
  }
  return (
    <table className="ops__errors">
      <tbody>
        {errors.map((e, i) => (
          <tr key={i}>
            <td className={`ops__err-level ops__err-level--${e.level}`}>{e.level}</td>
            <td className="mono small">{e.stage}</td>
            <td className="ops__err-msg">{e.message}</td>
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
          <th>Finished</th>
          <th>Trigger</th>
          <th>Status</th>
          <th>Pub.</th>
          <th>Picks</th>
          <th>Δ</th>
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
            <td className="small">{fmtAgo(row.finished_at)}</td>
            <td className="small">{row.trigger}</td>
            <td><StatusPill status={row.status} /></td>
            <td className="mono small">{row.published}</td>
            <td className="mono small">{row.picks}</td>
            <td className="mono small">{row.change_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
