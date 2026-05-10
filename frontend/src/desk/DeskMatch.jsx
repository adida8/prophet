// /desk/{match_id} — single-match verdict page.
//
// Hierarchy (iteration brief, conversion-focused):
//   1. Match context strip (teams, kickoff, competition stage, venue)
//   2. Verdict hero — verdict-first, then evidence, then verification:
//        - "Pick: {side}"  (or Pass / Avoid framing line)
//        - Data row "Model: 34% · Market: 22% · Edge: +11.1pp"
//        - Plain-English interpretation (copy.summary)
//        - "Why this call?" bullets (copy.drivers)
//        - "Best current source: {Venue}"  block with price
//        - Trust line ("Prices move…")
//        - PRIMARY CTA, copy varies by state:
//             Pick   → "View live price on Polymarket"
//             Pass   → "See live market price"
//             Avoid  → "Check market before acting"
//   3. Longer-form prose (copy.blurb) below the fold
//   4. Pick/Pass/Avoid ladder explainer
//   5. Back to desk
//
// Voice rules: no betting language. No "trade", no "bet", no "back",
// no "wager", no "value". The CTA is a verification step, not a call
// to action on a wager.

import { useEffect, useState } from "react";

const VENUE_LABEL = { polymarket: "Polymarket", kalshi: "Kalshi" };

function fmtKickoff(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${date} · ${time}`;
}

function pct(p) {
  if (typeof p !== "number") return "—";
  return `${Math.round(p * 100)}%`;
}

function venueFromUrl(url) {
  if (!url) return null;
  if (url.includes("polymarket.com")) return "Polymarket";
  if (url.includes("kalshi.com"))     return "Kalshi";
  return null;
}

export default function DeskMatch({ matchId, onBack }) {
  const [match, setMatch] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setMatch(null); setError(null);
    fetch(`/api/desk/match/${encodeURIComponent(matchId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "fixture not found" : `status ${r.status}`);
        return r.json();
      })
      .then((data) => { if (!cancelled) setMatch(data); })
      .catch((err)  => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [matchId]);

  if (error) {
    return (
      <main className="op-desk__match">
        <p className="op-desk__error">Couldn't load this fixture — {error}.</p>
        <BackLink onBack={onBack} />
      </main>
    );
  }
  if (!match) {
    return (
      <main className="op-desk__match">
        <p className="op-desk__loading">Loading verdict…</p>
      </main>
    );
  }

  return (
    <main className="op-desk__match">
      <ContextStrip match={match} />
      <VerdictHero match={match} />
      <Blurb copy={match.copy || {}} />
      <LadderExplainer />
      <BackLink onBack={onBack} />
    </main>
  );
}

function ContextStrip({ match }) {
  const comp  = match.competition || {};
  const venue = match.venue;
  const stageLabel = comp.stage ? comp.stage.replace(/_/g, " ") : null;
  return (
    <header className="op-desk__match-context">
      <span className="op-eyebrow">{comp.label || "Match"}{stageLabel ? ` · ${stageLabel}` : ""}</span>
      <h1 className="op-h1 op-desk__match-title">
        {match.team_a} <span className="op-desk__vs">vs</span> {match.team_b}
      </h1>
      <p className="op-desk__match-meta">
        {fmtKickoff(match.kickoff_utc)}
        {venue ? ` · ${venue.stadium}, ${venue.city}` : ""}
      </p>
    </header>
  );
}

function VerdictHero({ match }) {
  const v = match.verdict || {};
  const c = match.copy || {};
  const state = v.state || "pass";

  // Lead line — verdict first.
  const leadLine =
    state === "pick"  ? `Pick: ${v.side}` :
    state === "avoid" ? "Avoid — every side priced inside the model" :
                        "Pass — model and market aligned";

  // Data row. Pick gets full Model/Market/Edge. Pass/Avoid get edge
  // only (no single side to talk about), and only when present.
  const dataRow = renderDataRow(state, v);

  // CTA copy + venue context.
  const venueLabel = v.market_venue
    ? VENUE_LABEL[v.market_venue]
    : venueFromUrl(v.market_url);

  const ctaText =
    state === "pick"  ? `View live price on ${venueLabel || "Polymarket"}` :
    state === "avoid" ? "Check market before acting" :
                        "See live market price";

  return (
    <section className={`op-desk__hero-card op-desk__hero-card--${state}`}>
      <div className="op-desk__hero-badge-row">
        <span className={`op-desk__badge op-desk__badge--${state} op-desk__badge--lg`}>
          {state.toUpperCase()}
        </span>
        <span className="op-desk__hero-lead">{leadLine}</span>
      </div>

      {dataRow ? <p className="op-desk__hero-dataline">{dataRow}</p> : null}

      {c.summary ? (
        <p className="op-desk__hero-summary">{c.summary}</p>
      ) : null}

      {Array.isArray(c.drivers) && c.drivers.length > 0 ? (
        <WhyThisCall drivers={c.drivers} />
      ) : null}

      <SourceBlock state={state} verdict={v} venueLabel={venueLabel} />

      <p className="op-desk__cta-trust">
        Prices move. We show the model-vs-market gap; the live source has the final price.
      </p>

      {v.market_url ? (
        <a
          className={`op-desk__cta op-desk__cta--${state}`}
          href={v.market_url}
          target="_blank"
          rel="noopener nofollow sponsored"
          data-match-id={match.match_id}
          data-verdict-state={state}
          data-venue={v.market_venue || venueLabel?.toLowerCase() || ""}
        >
          {ctaText}
          <span aria-hidden="true" className="op-desk__cta-arrow">↗</span>
        </a>
      ) : null}
    </section>
  );
}

function renderDataRow(state, v) {
  if (state === "pick") {
    const parts = [];
    if (typeof v.model_p  === "number") parts.push(`Model: ${pct(v.model_p)}`);
    if (typeof v.market_p === "number") parts.push(`Market: ${pct(v.market_p)}`);
    if (typeof v.edge_pp  === "number") parts.push(`Edge: ${v.edge_pp >= 0 ? "+" : ""}${v.edge_pp.toFixed(1)}pp`);
    return parts.length ? parts.join("  ·  ") : null;
  }
  if (state === "avoid" && typeof v.edge_pp === "number") {
    return `Worst-side gap: ${v.edge_pp.toFixed(1)}pp against the model`;
  }
  return null;
}

function WhyThisCall({ drivers }) {
  return (
    <div className="op-desk__why">
      <h3 className="op-desk__why-heading">Why this call?</h3>
      <ul className="op-desk__why-list">
        {drivers.map((d, i) => <li key={i}>{d}</li>)}
      </ul>
    </div>
  );
}

function SourceBlock({ state, verdict, venueLabel }) {
  if (!venueLabel) return null;
  // Verification framing — the venue is where the live price lives,
  // not where Odds Primer pushes the user to act.
  return (
    <div className="op-desk__source">
      <span className="op-desk__source-label">Best current source</span>
      <span className="op-desk__source-venue">{venueLabel}</span>
      {state === "pick" && verdict.price ? (
        <span className="op-desk__source-price">{verdict.price}</span>
      ) : null}
    </div>
  );
}

function Blurb({ copy }) {
  if (!copy.blurb) return null;
  return (
    <section className="op-desk__blurb">
      <h3 className="op-desk__blurb-heading">The fuller picture</h3>
      <p className="op-desk__blurb-text">{copy.blurb}</p>
      {Array.isArray(copy.citations) && copy.citations.length > 0 ? (
        <p className="op-desk__blurb-citations">
          Sources:{" "}
          {copy.citations.map((url, i) => (
            <span key={url}>
              {i > 0 ? ", " : ""}
              <a href={url} target="_blank" rel="noopener nofollow">{hostname(url)}</a>
            </span>
          ))}
        </p>
      ) : null}
    </section>
  );
}

function LadderExplainer() {
  return (
    <section className="op-desk__ladder">
      <h3 className="op-desk__ladder-heading">How to read this verdict</h3>
      <dl>
        <div><dt>Pick</dt><dd>Our model and the market disagree by at least 3 percentage points on a side.</dd></div>
        <div><dt>Pass</dt><dd>Within 1 percentage point of the market on every side. Nothing to add.</dd></div>
        <div><dt>Avoid</dt><dd>Every side looks too expensive against our model.</dd></div>
      </dl>
    </section>
  );
}

function BackLink({ onBack }) {
  return (
    <p className="op-desk__back">
      <a href="/desk" onClick={(e) => { e.preventDefault(); onBack(); }}>
        ← Back to The Desk
      </a>
    </p>
  );
}

function hostname(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch { return url; }
}
