// The Desk · Ops admin — controls the refresh-loop schedule.
//
// Reads/writes /api/desk/ops/control. The refresh loop polls the same
// file on every scheduling decision, so changes here land within a
// minute or two without a server restart.
//
// Mental model the UI maps to:
//   - Master enable/disable toggle.
//   - A list of "daily runs" — each entry is a UTC hour (0..23). The
//     loop fires the tick at the top of each listed hour, once per day.
//   - Add Run picks an hour, validates it doesn't duplicate an existing
//     entry, and persists.
//   - Remove drops the hour from the list and persists.

import { useCallback, useEffect, useMemo, useState } from "react";

import { fmtAgo, fetchJson } from "./util";

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, h) => h);

function fmtHour(h) {
  return `${String(h).padStart(2, "0")}:00 UTC`;
}

function nextHourFromList(hours, now = new Date()) {
  if (!hours || hours.length === 0) return null;
  const sorted = [...hours].sort((a, b) => a - b);
  const curH = now.getUTCHours();
  const curM = now.getUTCMinutes();
  for (const h of sorted) {
    if (h > curH || (h === curH && curM === 0)) {
      // Today at h:00 if it's still in the future (we treat exact match
      // at minute 0 as "now").
      const target = new Date(now);
      target.setUTCHours(h, 0, 0, 0);
      if (target > now) return target;
    }
  }
  // Tomorrow at the earliest scheduled hour.
  const target = new Date(now);
  target.setUTCDate(target.getUTCDate() + 1);
  target.setUTCHours(sorted[0], 0, 0, 0);
  return target;
}

function fmtCountdown(targetDate, now = new Date()) {
  if (!targetDate) return "—";
  const ms = targetDate - now;
  if (ms < 0) return "now";
  const totalMin = Math.round(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `in ${m}m`;
  if (h < 24)  return `in ${h}h ${m}m`;
  return `in ${Math.round(h / 24)}d`;
}

export default function OpsAdmin() {
  const [state, setState]   = useState(null);
  const [error, setError]   = useState(null);
  const [busy, setBusy]     = useState(false);
  // `picker` is the hour the dropdown currently shows. We default it to
  // the first unscheduled hour so the Add button is enabled on load; if
  // the operator manually picks an unscheduled hour, that choice sticks
  // (the useEffect below only re-snaps when the current pick collides
  // with an already-scheduled hour).
  const [picker, setPicker] = useState(null);

  // Distribute (MTA push wire) state, polled independently so a slow
  // control-state read doesn't block the dead-letter panel.
  const [dist, setDist] = useState(null);

  const load = useCallback(async () => {
    try {
      const c = await fetchJson("/api/desk/ops/control");
      setState(c);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const loadDistribute = useCallback(async () => {
    try {
      const d = await fetchJson("/api/desk/ops/distribute");
      setDist(d);
    } catch (e) {
      // Surface in the panel, not the page-level error — the schedule
      // is still operable even if the outbox read fails.
      setDist({ error: e.message });
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    loadDistribute();
    // Drain ticks every 30s on the backend; mirror that here.
    const t = setInterval(loadDistribute, 30_000);
    return () => clearInterval(t);
  }, [loadDistribute]);

  useEffect(() => {
    if (!state) return;
    const taken = new Set(state.hours || []);
    if (picker == null || taken.has(picker)) {
      const next = HOUR_OPTIONS.find((h) => !taken.has(h));
      if (next != null) setPicker(next);
    }
  }, [state, picker]);

  // Save-on-change: any mutation immediately persists. Simpler than a
  // Save button + dirty tracking and matches the "feels like a settings
  // panel" expectation.
  const save = useCallback(async (patch) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await fetchJson("/api/desk/ops/control", {
        method:  "PUT",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(patch),
      });
      setState(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }, []);

  const nextRun = useMemo(
    () => state && state.enabled ? nextHourFromList(state.hours) : null,
    [state],
  );

  if (!state) {
    return (
      <>
        <header className="ops__header">
          <div>
            <div className="ops__title">The Desk · Admin</div>
            <div className="ops__subtitle">{error || "loading…"}</div>
          </div>
        </header>
      </>
    );
  }

  const hours = state.hours || [];
  const canAdd = picker != null && !hours.includes(picker) && hours.length < 24;

  async function addHour() {
    if (!canAdd) return;
    await save({ hours: [...hours, picker] });
  }

  async function removeHour(h) {
    await save({ hours: hours.filter((x) => x !== h) });
  }

  async function toggleEnabled() {
    await save({ enabled: !state.enabled });
  }

  return (
    <>
      <header className="ops__header">
        <div>
          <div className="ops__title">The Desk · Admin</div>
          <div className="ops__subtitle">
            {state.enabled
              ? <>Loop enabled · next run <strong>{fmtCountdown(nextRun)}</strong>{nextRun && <> ({String(nextRun.getUTCHours()).padStart(2, "0")}:00 UTC)</>}</>
              : <>Loop paused</>}
            {state.updated_at && <> · last changed {fmtAgo(state.updated_at)}</>}
          </div>
        </div>
        <div className="ops__header-right">
          <button
            className={`ops__reload ${state.enabled ? "" : "ops__reload--off"}`}
            onClick={toggleEnabled}
            disabled={busy}
          >
            {state.enabled ? "Pause loop" : "Enable loop"}
          </button>
        </div>
      </header>

      {error && <div className="ops__error">{error}</div>}

      <section className="ops__section">
        <h2 className="ops__section-title">Daily runs · {hours.length}</h2>

        {hours.length === 0 ? (
          <div className="ops__empty">
            No runs scheduled — add one below to start the loop.
          </div>
        ) : (
          <ul className="ops__hourlist">
            {hours.map((h) => (
              <li key={h} className="ops__hourchip">
                <span className="mono">{fmtHour(h)}</span>
                <button
                  className="ops__hourchip-x"
                  onClick={() => removeHour(h)}
                  disabled={busy}
                  aria-label={`Remove ${fmtHour(h)}`}
                  title="Remove"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="ops__hour-add">
          <label htmlFor="hour-picker">Add run at</label>
          <select
            id="hour-picker"
            value={picker ?? ""}
            onChange={(e) => setPicker(parseInt(e.target.value, 10))}
            disabled={busy || hours.length >= 24}
          >
            {HOUR_OPTIONS.map((h) => (
              <option
                key={h}
                value={h}
                disabled={hours.includes(h)}
              >
                {fmtHour(h)}{hours.includes(h) ? " — already scheduled" : ""}
              </option>
            ))}
          </select>
          <button
            className="ops__reload"
            onClick={addHour}
            disabled={busy || !canAdd}
          >
            Add run
          </button>
        </div>

        <p className="ops__note">
          All times in UTC. The loop fires once at the top of each listed
          hour. Empty list = no scheduled runs (loop idles).
        </p>
      </section>

      <DistributePanel dist={dist} onReload={loadDistribute} />
    </>
  );
}


// ── Distribute panel ───────────────────────────────────────────────
// MTA push wire visibility. Shows whether push is enabled, the
// pending/dead counts, and the most recent dead-lettered rows with
// their last error so the operator can read WHY a push died without
// shelling into the SQLite volume.

function DistributePanel({ dist, onReload }) {
  if (!dist) {
    return (
      <section className="ops__section">
        <h2 className="ops__section-title">Distribute · MTA push wire</h2>
        <div className="ops__empty">loading…</div>
      </section>
    );
  }

  if (dist.error) {
    return (
      <section className="ops__section">
        <h2 className="ops__section-title">Distribute · MTA push wire</h2>
        <div className="ops__error">distribute read failed: {dist.error}</div>
      </section>
    );
  }

  const {
    push_enabled, db_exists, pending_count, dead_count, recent_dead, db_path,
  } = dist;

  // Status pill rules:
  //   off       → push_enabled=false
  //   has-dead  → dead_count > 0 (most actionable, wins over backlog)
  //   backlog   → pending_count > 0 (between sweeps or worker stalled)
  //   healthy   → push on, no backlog, no dead
  let pillClass = "ops__pill--source-static";
  let pillLabel = "off";
  if (push_enabled) {
    if (dead_count > 0) {
      pillClass = "ops__pill--fail";
      pillLabel = "has dead-letters";
    } else if (pending_count > 0) {
      pillClass = "ops__pill--partial";
      pillLabel = "backlog";
    } else {
      pillClass = "ops__pill--ok";
      pillLabel = "healthy";
    }
  }

  return (
    <section className="ops__section">
      <h2 className="ops__section-title">Distribute · MTA push wire</h2>

      <div className="ops__distribute-row">
        <span className={`ops__pill ${pillClass}`}>{pillLabel}</span>
        <span className="ops__distribute-stat">
          <span className="ops__distribute-stat-label">pending</span>
          <span className="mono">{pending_count}</span>
        </span>
        <span className="ops__distribute-stat">
          <span className="ops__distribute-stat-label">dead</span>
          <span className={`mono ${dead_count > 0 ? "ops__distribute-stat--dead" : ""}`}>
            {dead_count}
          </span>
        </span>
        <button className="ops__reload" onClick={onReload}>Reload</button>
      </div>

      {!db_exists && (
        <p className="ops__note">
          No outbox DB yet at <code className="mono">{db_path}</code> —
          will appear on the first match enqueue.
        </p>
      )}

      {dead_count > 0 && (
        <>
          <h3 className="ops__distribute-deads-title">Recent dead-letters</h3>
          <ul className="ops__distribute-deads">
            {recent_dead.map((r) => (
              <li key={r.id} className="ops__distribute-dead">
                <div className="ops__distribute-dead-head">
                  <span className="mono">{r.match_id}</span>
                  <span className="ops__distribute-dead-meta">
                    {r.attempts} attempt{r.attempts === 1 ? "" : "s"}
                    {" · "}
                    enqueued {fmtAgo(new Date(r.created_at * 1000).toISOString())}
                  </span>
                </div>
                <div className="ops__distribute-dead-err mono">
                  {r.last_error || "(no error recorded)"}
                </div>
              </li>
            ))}
          </ul>
          <p className="ops__note">
            Dead rows are preserved for inspection — never auto-retried.
            Clear them with SQL on the volume once acknowledged.
          </p>
        </>
      )}

      {push_enabled && dead_count === 0 && pending_count === 0 && db_exists && (
        <p className="ops__note">
          All caught up — every enqueued match has been delivered to MTA
          and 200'd.
        </p>
      )}

      {!push_enabled && (
        <p className="ops__note">
          Push is off (<code className="mono">DESK_DISTRIBUTE_PUSH=0</code>).
          Set to <code className="mono">1</code> on Railway to activate the
          wire — runner already enqueues, drain loop will catch up.
        </p>
      )}
    </section>
  );
}
