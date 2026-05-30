// The Desk · Ops main view — run history + sources + news signals.
//
// Schedule / enable-disable lives on the sibling Desk admin view; this
// surface stays read-only so the operator can scan it without worrying
// about clicking the wrong control. Mounted by OpsApp's shell at
// /desk/ops.

import { useCallback, useEffect, useState } from "react";

import { fmtAgo, fmtClockUTC, fmtDateUTC, fmtUSD, fetchJson } from "./util";

const SOURCE_LABELS = {
  polymarket_gamma: "Polymarket · gamma",
  kalshi_kxwcgame:  "Kalshi · KXWCGAME",
  elo_seed:         "Elo · seed",
  wc26_venues:      "WC26 · venues",
};

export default function OpsMain() {
  const [report, setReport] = useState(null);
  const [manifest, setManifest] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [dataSources, setDataSources] = useState(null);
  const [dailyReport, setDailyReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async (runId = null) => {
    setLoading(true);
    setError(null);
    try {
      const m = await fetchJson("/api/desk/ops/runs?limit=5");
      const runs = m.runs || [];
      setManifest(runs);

      // Data-sources panel — loads independently of run history so a
      // fresh-deploy with no runs yet still surfaces external provider
      // health.
      fetchJson("/api/desk/ops/data-sources")
        .then(setDataSources)
        .catch(() => setDataSources(null));

      // Daily report status — same loose-coupling rationale.
      fetchJson("/api/desk/ops/daily-report")
        .then(setDailyReport)
        .catch(() => setDailyReport(null));

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
    <>
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

      <Section title={`Run history · last ${manifest.length}`}>
        <RunHistory
          manifest={manifest}
          selectedRunId={selectedRunId}
          onSelect={load}
        />
      </Section>

      {dailyReport && (
        <Section title="Daily report">
          <DailyReportStatus state={dailyReport} />
        </Section>
      )}

      {dataSources && (
        <Section title="External providers">
          <ExternalProviders data={dataSources} />
        </Section>
      )}

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
    </>
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

function DailyReportStatus({ state }) {
  if (!state || !state.last_sent_date) {
    return <div className="ops__empty">No daily report sent yet.</div>;
  }
  return (
    <div className="ops__daily-report">
      <div>
        Covering <span className="mono">{state.last_sent_date}</span>
        {" · "}
        sent <span className="mono">{fmtClockUTC(state.sent_at)}</span>
        {" "}({fmtAgo(state.sent_at)})
      </div>
    </div>
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
          <th>Date</th>
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
            <td className="mono small">{fmtDateUTC(row.started_at)}</td>
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

// ── External providers ───────────────────────────────────────────────

function ExternalProviders({ data }) {
  const { api_football: af, elo, openweathermap: ow } = data || {};
  return (
    <div className="ops__providers">
      {af && (
        <ProviderCard
          label="api-football"
          configured={af.key_configured}
          enabled={af.fetch_enabled}
          dbExists={af.db_exists}
          counts={[
            ["teams resolved",        af.team_count],
            ["form_delta rows",       af.form_delta_count],
            ["injury penalties",      af.injury_penalty_count],
            ["fixtures cached",       af.fixture_count],
          ]}
          fetches={af.fetches}
          extras={[
            af.injuries_enabled ? "DESK_INJURY_FETCH=1" : null,
          ].filter(Boolean)}
        />
      )}
      {elo && (
        <ProviderCard
          label="live Elo (eloratings + clubelo)"
          configured={true}
          enabled={elo.fetch_enabled}
          dbExists={elo.db_exists}
          counts={[
            ["national Elo rows", elo.national_count],
            ["club Elo rows",     elo.club_count],
          ]}
          fetches={elo.fetches.map((f) => ({
            endpoint:    f.source_id,
            last_fetched: f.last_fetched,
            last_status: f.last_status,
          }))}
        />
      )}
      {ow && (
        <ProviderCard
          label="openweathermap"
          configured={ow.key_configured}
          enabled={false}
          dbExists={false}
          counts={[]}
          fetches={[]}
          status={ow.data_flow_status}
          note={ow.note}
        />
      )}
    </div>
  );
}

function ProviderCard({
  label, configured, enabled, dbExists, counts, fetches,
  status, note, extras = [],
}) {
  return (
    <div className="ops__provider">
      <div className="ops__provider-head">
        <h3 className="ops__provider-name">{label}</h3>
        <ProviderStatus
          configured={configured}
          enabled={enabled}
          dbExists={dbExists}
          override={status}
        />
      </div>
      {extras.length > 0 && (
        <div className="ops__provider-extras small">
          {extras.join(" · ")}
        </div>
      )}
      {note && <div className="ops__provider-note small">{note}</div>}
      {counts.length > 0 && (
        <table className="ops__provider-counts">
          <tbody>
            {counts.map(([k, v]) => (
              <tr key={k}>
                <td className="small">{k}</td>
                <td className="mono small num">{v ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {fetches.length > 0 && (
        <div className="ops__provider-fetches">
          <div className="small ops__provider-fetches-title">Recent fetches</div>
          <table>
            <tbody>
              {fetches.slice(0, 8).map((f, i) => (
                <tr key={`${f.endpoint}-${i}`}>
                  <td className="mono small">{f.endpoint}</td>
                  <td>
                    <span className={`ops__pill ops__pill--source-${normaliseStatus(f.last_status)}`}>
                      {f.last_status}
                    </span>
                  </td>
                  <td className="mono small">{fmtAgo(f.last_fetched)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProviderStatus({ configured, enabled, dbExists, override }) {
  if (override === "not_wired") {
    return <span className="ops__pill ops__pill--source-stale">probe-only</span>;
  }
  if (!configured) {
    return <span className="ops__pill ops__pill--source-failed">no key</span>;
  }
  if (!enabled) {
    return <span className="ops__pill ops__pill--source-stale">fetch off</span>;
  }
  if (!dbExists) {
    return <span className="ops__pill ops__pill--source-stale">no cache yet</span>;
  }
  return <span className="ops__pill ops__pill--source-fresh">live</span>;
}

function normaliseStatus(s) {
  if (!s) return "stale";
  const v = String(s).toLowerCase();
  if (v === "ok") return "fresh";
  if (v.startsWith("http_") || v === "transient" || v === "parser_mismatch") {
    return "failed";
  }
  return "stale";
}
