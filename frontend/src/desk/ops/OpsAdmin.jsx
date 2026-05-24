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
  const [picker, setPicker] = useState(6);

  const load = useCallback(async () => {
    try {
      const c = await fetchJson("/api/desk/ops/control");
      setState(c);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

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
  const canAdd = !hours.includes(picker) && hours.length < 24;

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
            value={picker}
            onChange={(e) => setPicker(parseInt(e.target.value, 10))}
            disabled={busy}
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
    </>
  );
}
