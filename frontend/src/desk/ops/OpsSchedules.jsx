// The Desk · Ops schedules — unified loop on/off control.
//
// One table, one row per background loop. Toggle persists to
// /api/desk/ops/schedules/{loop_id}/enabled which writes either
// schedules.json or control.json depending on the loop. Loops poll
// the registry on every tick so flips land within ~60s without a
// restart.
//
// Shows the cadence in human-readable form (every N min / every N h /
// hourly @ HH UTC / weekly weekday HH:MM UTC) and any env-flag
// prerequisites that still need to be set for the loop to actually
// do work even when the toggle is on.

import { useCallback, useEffect, useState } from "react";

import { fmtAgo, fetchJson } from "./util";

function fmtCadence(loop) {
  const { shape, state } = loop;
  if (shape === "cron_hourly") {
    const hours = state.hours || [];
    if (!hours.length) return "no hours scheduled";
    const labels = [...hours].sort((a, b) => a - b)
      .map((h) => `${String(h).padStart(2, "0")}:00`);
    return `daily @ ${labels.join(" / ")} UTC`;
  }
  if (shape === "interval") {
    const sec = Number(state.tick_sec) || 0;
    if (sec >= 86400) return `every ${Math.round(sec / 86400)} day${sec >= 172800 ? "s" : ""}`;
    if (sec >= 3600)  return `every ${Math.round(sec / 3600)}h`;
    if (sec >= 60)    return `every ${Math.round(sec / 60)} min`;
    return `every ${sec}s`;
  }
  if (shape === "cron_weekly") {
    const wd = (state.weekday || "sun").slice(0, 3);
    const at = state.hh_mm || "09:00";
    return `weekly ${wd} ${at} UTC`;
  }
  return "—";
}

export default function OpsSchedules() {
  const [doc, setDoc]     = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy]   = useState(null);   // loop_id currently mutating

  const load = useCallback(async () => {
    try {
      const r = await fetchJson("/api/desk/ops/schedules");
      setDoc(r);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  const toggle = useCallback(async (loopId, nextEnabled) => {
    setBusy(loopId);
    setError(null);
    try {
      const updated = await fetchJson(
        `/api/desk/ops/schedules/${encodeURIComponent(loopId)}/enabled`,
        {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ enabled: nextEnabled }),
        },
      );
      setDoc(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }, []);

  if (!doc) {
    return (
      <header className="ops__header">
        <div>
          <div className="ops__title">The Desk · Schedules</div>
          <div className="ops__subtitle">{error || "loading…"}</div>
        </div>
      </header>
    );
  }

  const loops = doc.loops || [];
  const onCount  = loops.filter((l) => l.state?.enabled).length;
  const offCount = loops.length - onCount;

  return (
    <>
      <header className="ops__header">
        <div>
          <div className="ops__title">The Desk · Schedules</div>
          <div className="ops__subtitle">
            {onCount} loop{onCount === 1 ? "" : "s"} on · {offCount} off
            {doc.updated_at && <> · last changed {fmtAgo(doc.updated_at)}</>}
          </div>
        </div>
        <div className="ops__header-right">
          <button className="ops__reload" onClick={load}>Reload</button>
        </div>
      </header>

      {error && <div className="ops__error">{error}</div>}

      <section className="ops__section">
        <h2 className="ops__section-title">Background loops</h2>
        <table className="ops__history">
          <thead>
            <tr>
              <th>Loop</th>
              <th>Cadence</th>
              <th>Status</th>
              <th>Requires</th>
              <th style={{ textAlign: "right" }}>Control</th>
            </tr>
          </thead>
          <tbody>
            {loops.map((l) => {
              const enabled = !!l.state?.enabled;
              const isBusy  = busy === l.id;
              return (
                <tr key={l.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{l.label}</div>
                    <div className="small" style={{ color: "var(--graphite-soft)" }}>
                      {l.description}
                    </div>
                  </td>
                  <td className="mono">{fmtCadence(l)}</td>
                  <td>
                    <span className={`ops__pill ${enabled ? "ops__pill--ok" : "ops__pill--source-static"}`}>
                      {enabled ? "on" : "off"}
                    </span>
                  </td>
                  <td className="mono small">
                    {(l.requires || []).length === 0
                      ? <span style={{ color: "var(--graphite-soft)" }}>—</span>
                      : (l.requires || []).join(" · ")}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className={`ops__reload ${enabled ? "ops__reload--off" : ""}`}
                      onClick={() => toggle(l.id, !enabled)}
                      disabled={isBusy}
                      title={enabled ? "Turn this loop off" : "Turn this loop on"}
                    >
                      {isBusy ? "…" : (enabled ? "Turn off" : "Turn on")}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <p className="ops__note">
          Toggles persist immediately; loops re-check on their next iteration
          (typically within 60s). Loops listed under <strong>Requires</strong>
          will stay idle until those env vars are also set on Railway — the
          on/off toggle is an additional gate, not an override.
          <br />
          Desk refresh's hour schedule is edited on the <strong>Desk admin</strong> tab;
          the on/off here is the same flag.
        </p>
      </section>
    </>
  );
}
