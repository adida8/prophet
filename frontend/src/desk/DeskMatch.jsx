// /desk/{match_id} — single-match verdict page.
//
// Layout per the conversion design:
//   1. Match context strip (teams, kickoff, competition stage, venue)
//   2. Verdict hero ABOVE THE FOLD:
//        - badge + side
//        - editorial title
//        - one-sentence summary
//        - verdict card (call · model-vs-market · venue · price)
//        - microcopy ("live price may have moved")
//        - PRIMARY CTA  →  market_url
//        - microcopy ("you'll leave Odds Primer…")
//   3. "Why this is the call" — the 60-90 word blurb
//   4. "How to read this verdict" — compact ladder explainer
//   5. Back to desk link

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

  const v = match.verdict || {};
  const c = match.copy || {};
  const state = v.state || "pass";
  const venueLabel = v.market_venue ? VENUE_LABEL[v.market_venue] : null;

  return (
    <main className="op-desk__match">
      <ContextStrip match={match} />
      <VerdictHero match={match} state={state} verdict={v} copy={c} venueLabel={venueLabel} />
      {c.blurb ? <Blurb text={c.blurb} citations={c.citations || []} /> : null}
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

function VerdictHero({ match, state, verdict, copy, venueLabel }) {
  const edge = typeof verdict.edge_pp === "number" ? verdict.edge_pp : null;
  const url  = verdict.market_url;

  // CTA copy varies by venue and state. Pick gets the directed CTA;
  // Pass/Avoid get a neutral "see the live market" so curiosity has
  // somewhere to go without being framed as a recommendation.
  const ctaText = state === "pick" && venueLabel
    ? `Check the current price on ${venueLabel}`
    : venueLabel
      ? `See the live market on ${venueLabel}`
      : "See the live market";

  return (
    <section className={`op-desk__hero-card op-desk__hero-card--${state}`}>
      <div className="op-desk__hero-badge-row">
        <span className={`op-desk__badge op-desk__badge--${state} op-desk__badge--lg`}>
          {state.toUpperCase()}
        </span>
        {state === "pick" && verdict.side ? (
          <span className="op-desk__hero-side">{verdict.side}</span>
        ) : null}
      </div>

      {copy.title ? <h2 className="op-h2 op-desk__hero-title">{copy.title}</h2> : null}
      {copy.summary ? <p className="op-desk__hero-summary">{copy.summary}</p> : null}

      <dl className="op-desk__verdict-card">
        <div>
          <dt>Call</dt>
          <dd>
            {state === "pick" && verdict.side ? `Pick — ${verdict.side}` :
             state === "pass" ? "Pass — model and market agree" :
             state === "avoid" ? "Avoid — every side looks too expensive" :
             state.toUpperCase()}
          </dd>
        </div>
        {edge !== null ? (
          <div>
            <dt>Model vs market</dt>
            <dd>
              {edge >= 0 ? "+" : ""}{edge.toFixed(1)} percentage points
              {state === "avoid" ? " on the worst side" : ""}
            </dd>
          </div>
        ) : null}
        {state === "pick" && venueLabel ? (
          <div>
            <dt>Available at</dt>
            <dd>{venueLabel}</dd>
          </div>
        ) : null}
        {state === "pick" && verdict.price ? (
          <div>
            <dt>Captured price</dt>
            <dd className="op-desk__verdict-price">{verdict.price}</dd>
          </div>
        ) : null}
      </dl>

      {url ? (
        <>
          <p className="op-desk__cta-prep">
            This call is based on the latest price we captured. The live market may have moved.
          </p>
          <a
            className={`op-desk__cta op-desk__cta--${state}`}
            href={url}
            target="_blank"
            rel="noopener nofollow sponsored"
            data-match-id={match.match_id}
            data-verdict-state={state}
            data-venue={verdict.market_venue || ""}
          >
            {ctaText}
            <span aria-hidden="true" className="op-desk__cta-arrow">↗</span>
          </a>
          <p className="op-desk__cta-trail">
            You'll leave Odds Primer and open {venueLabel || "the venue"}'s event page.
            Review the market terms and live price there.
          </p>
        </>
      ) : null}
    </section>
  );
}

function Blurb({ text, citations }) {
  return (
    <section className="op-desk__blurb">
      <h3 className="op-desk__blurb-heading">Why this is the call</h3>
      <p className="op-desk__blurb-text">{text}</p>
      {citations.length > 0 ? (
        <p className="op-desk__blurb-citations">
          Sources:{" "}
          {citations.map((url, i) => (
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
