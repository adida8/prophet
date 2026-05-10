// /desk — list view. WC 2026 fixtures with verdict badges.
//
// Sort: upcoming first; within the same day, Picks → Avoid → Pass.
// Filter chips: All / Picks / Pass / Avoid (default All — the credibility
// of the desk depends on showing every state).
//
// Per the conversion design: list cards do NOT show the full blurb.
// They show the editorial title, a one-line summary, and verdict
// data. The blurb lives on the match page so the click has somewhere
// to take the reader.

import { useEffect, useMemo, useState } from "react";

const FILTERS = [
  { id: "all",   label: "All" },
  { id: "pick",  label: "Picks" },
  { id: "pass",  label: "Pass" },
  { id: "avoid", label: "Avoid" },
];

const STATE_RANK = { pick: 0, avoid: 1, pass: 2 };

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit",
  });
}

function venueLabel(venue) {
  if (!venue) return "";
  return venue === "polymarket" ? "Polymarket" : venue === "kalshi" ? "Kalshi" : venue;
}

export default function DeskList({ onSelect }) {
  const [matches, setMatches] = useState(null);
  const [error,   setError]   = useState(null);
  const [filter,  setFilter]  = useState("all");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/desk/matches?competition=wc26")
      .then((r) => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return r.json();
      })
      .then((data) => { if (!cancelled) setMatches(data.matches || []); })
      .catch((err)  => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  const sorted = useMemo(() => {
    if (!matches) return [];
    const filtered = filter === "all" ? matches : matches.filter((m) => m.verdict?.state === filter);
    return [...filtered].sort((a, b) => {
      const da = (a.kickoff_utc || "").slice(0, 10);
      const db = (b.kickoff_utc || "").slice(0, 10);
      if (da !== db) return da < db ? -1 : 1;
      // same day → state rank, then kickoff time
      const ra = STATE_RANK[a.verdict?.state] ?? 9;
      const rb = STATE_RANK[b.verdict?.state] ?? 9;
      if (ra !== rb) return ra - rb;
      return (a.kickoff_utc || "") < (b.kickoff_utc || "") ? -1 : 1;
    });
  }, [matches, filter]);

  // Group by calendar date — mimics a desk's matchday rundown.
  const grouped = useMemo(() => {
    const out = [];
    let last = null;
    for (const m of sorted) {
      const day = (m.kickoff_utc || "").slice(0, 10);
      if (day !== last) {
        out.push({ day, items: [] });
        last = day;
      }
      out[out.length - 1].items.push(m);
    }
    return out;
  }, [sorted]);

  const counts = useMemo(() => {
    const c = { all: 0, pick: 0, pass: 0, avoid: 0 };
    for (const m of matches || []) {
      c.all++;
      const s = m.verdict?.state;
      if (s in c) c[s]++;
    }
    return c;
  }, [matches]);

  return (
    <main className="op-desk__list">
      <section className="op-desk__hero">
        <span className="op-eyebrow">Vol. 1 · The Desk</span>
        <h1 className="op-display">The World Cup 2026 desk</h1>
        <p className="op-desk__hero-lede">
          Every priced fixture rated against the market. Pick where we disagree by
          three points or more, Pass where the market and our model agree,
          Avoid where every side looks too expensive. Live prices are checked
          at the venue, never quoted from us.
        </p>
      </section>

      <div className="op-desk__filters" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            className={`op-desk__filter${filter === f.id ? " is-active" : ""}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
            <span className="op-desk__filter-count">{counts[f.id] ?? 0}</span>
          </button>
        ))}
      </div>

      {error ? (
        <p className="op-desk__error">Couldn't load the desk — {error}</p>
      ) : matches === null ? (
        <p className="op-desk__loading">Loading the desk…</p>
      ) : sorted.length === 0 ? (
        <p className="op-desk__loading">No fixtures match this filter.</p>
      ) : (
        grouped.map(({ day, items }) => (
          <section key={day} className="op-desk__day">
            <h2 className="op-desk__day-header">{fmtDate(items[0].kickoff_utc)}</h2>
            <div className="op-desk__cards">
              {items.map((m) => (
                <MatchCard key={m.match_id} match={m} onSelect={onSelect} />
              ))}
            </div>
          </section>
        ))
      )}
    </main>
  );
}

function MatchCard({ match, onSelect }) {
  const v = match.verdict || {};
  const state = v.state || "pass";
  const klass = `op-desk__card op-desk__card--${state}`;
  const edge  = typeof v.edge_pp === "number" ? v.edge_pp : null;

  return (
    <a
      className={klass}
      href={`/desk/${match.match_id}`}
      onClick={(e) => { e.preventDefault(); onSelect(match.match_id); }}
    >
      <div className="op-desk__card-head">
        <VerdictBadge state={state} />
        <span className="op-desk__card-time">{fmtTime(match.kickoff_utc)}</span>
      </div>

      <h3 className="op-desk__card-fixture">
        {match.team_a} <span className="op-desk__vs">vs</span> {match.team_b}
      </h3>

      {match.copy?.title ? (
        <p className="op-desk__card-headline">{match.copy.title}</p>
      ) : null}
      {match.copy?.summary ? (
        <p className="op-desk__card-summary">{match.copy.summary}</p>
      ) : null}

      {state === "pick" ? (
        <div className="op-desk__card-pickline">
          <span className="op-desk__card-pickside">{v.side}</span>
          {v.price ? <span className="op-desk__card-price">{v.price}</span> : null}
          {v.market_venue ? <span className="op-desk__card-venue">on {venueLabel(v.market_venue)}</span> : null}
          {edge !== null ? <span className="op-desk__card-edge">+{edge.toFixed(1)}pp</span> : null}
        </div>
      ) : state === "avoid" && edge !== null ? (
        <div className="op-desk__card-pickline">
          <span className="op-desk__card-edge op-desk__card-edge--neg">
            {edge.toFixed(1)}pp on the worst side
          </span>
        </div>
      ) : null}

      <span className="op-desk__card-cta">Read verdict →</span>
    </a>
  );
}

function VerdictBadge({ state, size = "sm" }) {
  const labels = { pick: "PICK", pass: "PASS", avoid: "AVOID" };
  return (
    <span className={`op-desk__badge op-desk__badge--${state} op-desk__badge--${size}`}>
      {labels[state] || state.toUpperCase()}
    </span>
  );
}
