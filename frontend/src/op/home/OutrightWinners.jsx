// Outright winners — desktop bar + mobile-card variants.
// Data is hardcoded in this PR (data.js). Live wiring is a separate workstream.

import { OUTRIGHTS, POLYMARKET_OUTRIGHT_URL } from "./data";

export default function OutrightWinners() {
  const ariaLabel = `Outright winner implied probability: ${OUTRIGHTS.map(
    (o) => `${o.team} ${o.pct}%`,
  ).join(", ")}`;

  return (
    <section className="outright" id="outrights" aria-labelledby="o-title">
      <div className="o-head">
        <div>
          <div className="o-eyebrow" id="o-title">
            Outright winner · Implied probability · Polymarket consensus, Kalshi best
          </div>
        </div>
        <a
          className="o-source"
          href={POLYMARKET_OUTRIGHT_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View the Outright Winner market source on Polymarket"
        >
          View source on Polymarket <span className="arr">↗</span>
        </a>
      </div>

      {/* Desktop: single horizontal bar */}
      <div className="o-bar-wrap">
        <div className="o-bar" role="img" aria-label={ariaLabel}>
          {OUTRIGHTS.map((o) => (
            <div
              key={o.team}
              className={o.segClass}
              style={{ width: `${o.pct}%` }}
            />
          ))}
        </div>
        <div className="o-legend">
          {OUTRIGHTS.map((o) => (
            <span key={o.team} className={`pill${o.lead ? " lead" : ""}`}>
              <span
                className="swatch"
                style={{
                  background: o.swatch,
                  border: o.swatchBorder ? "1px solid var(--rule)" : undefined,
                }}
              />
              {o.team} <span className="num">{o.pct}%</span>
            </span>
          ))}
        </div>
      </div>

      {/* Mobile: horizontal-scrolling cards */}
      <div className="o-cards" role="list" aria-label="Outright winner standings">
        {OUTRIGHTS.map((o) => (
          <a
            key={o.team}
            className={`o-card${o.lead ? " is-lead" : ""}`}
            role="listitem"
            href={POLYMARKET_OUTRIGHT_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="name">{o.team}</span>
            <span className="pct">{o.pct}%</span>
            <span className="src">{o.source}</span>
          </a>
        ))}
      </div>

      <p className="o-foot">
        Where the field stands. We don't verdict outright winners
        <span className="dag"> †</span> — this is the market consensus, not our call.
        The 28-team Field outweighs every individual contender; that's the read.
      </p>
    </section>
  );
}
