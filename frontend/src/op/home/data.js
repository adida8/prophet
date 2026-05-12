// Hardcoded sample data for the home page (PR scope: surface only).
// Wiring to live data is gated on later PRs (THE_DESK_OUTRIGHTS_SPEC.md
// for outrights, THE_DESK_SPEC.md PR 6 for fixtures).

export const OUTRIGHTS = [
  { team: "Brazil",    pct: 22, segClass: "seg-lead", swatch: "var(--flame)",         source: "Polymarket best", lead: true  },
  { team: "Argentina", pct: 18, segClass: "seg-2",    swatch: "var(--ink-soft)",      source: "Kalshi best",     lead: false },
  { team: "France",    pct: 16, segClass: "seg-3",    swatch: "var(--graphite)",      source: "Polymarket best", lead: false },
  { team: "England",   pct: 12, segClass: "seg-4",    swatch: "#B89968",              source: "Polymarket best", lead: false },
  { team: "Spain",     pct: 11, segClass: "seg-5",    swatch: "var(--paper-deep)",    source: "Kalshi best",     lead: false },
  { team: "Field",     pct: 21, segClass: "seg-6",    swatch: "var(--paper-warm)",    source: "28 other teams",  lead: false, swatchBorder: true },
];

export const FIXTURE_HREF = "/v2/market-v2-newspaper-deck.html";

export const FIXTURE_GROUPS = [
  {
    name: "Group F",
    fixtureCount: 4,
    summary: "2 picks · 1 pass · 1 avoid",
    fixtures: [
      {
        verdict: "pick",
        teamA: "France", teamB: "Mexico",
        meta: "MEX · Estadio Azteca · 21:00 local",
        thesisHtml: "<em>France look four points underpriced.</em> <span class=\"nm\">Polymarket</span> is the slower of the two markets — that's where to read the price.",
        venue: "Polymarket", price: "−180",
        when: "Sat · 21:00",
      },
      {
        verdict: "pass",
        teamA: "Cameroon", teamB: "Saudi Arabia",
        meta: "USA · MetLife · 18:00 local",
        thesisHtml: "Two markets within half a point — no edge. Skip the moneyline; total may have legs.",
        venue: "Kalshi", price: "+135",
        when: "Sat · 18:00",
      },
      {
        verdict: "pick",
        teamA: "Cameroon", teamB: "France",
        meta: "CAN · BMO Field · 15:00 local",
        thesisHtml: "<em>Total goals is mispriced.</em> Both teams need a result; over 2.5 has 6.5 points of room.",
        venue: "Kalshi", price: "+108",
        when: "Wed · 15:00",
      },
      {
        verdict: "avoid",
        teamA: "Mexico", teamB: "Saudi Arabia",
        meta: "MEX · Guadalajara · 18:00 local",
        thesisHtml: "Mexico overpriced as the home favourite; Saudi Arabia priced as if they can't draw. Both sides cost too much.",
        venue: "Polymarket", price: "−240",
        when: "Tue · 18:00",
      },
    ],
  },
  {
    name: "Group A",
    fixtureCount: 2,
    summary: "1 pick · 1 pass",
    fixtures: [
      {
        verdict: "pick",
        teamA: "Argentina", teamB: "Canada",
        meta: "USA · Levi's Stadium · 19:00 local",
        thesisHtml: "<em>Canada +1.5 has clean value.</em> The handicap line hasn't tracked Canada's improved second half of 2025.",
        venue: "Polymarket", price: "−108",
        when: "Sun · 19:00",
      },
      {
        verdict: "pass",
        teamA: "Iceland", teamB: "Tunisia",
        meta: "CAN · BC Place · 16:00 local",
        thesisHtml: "Pick'em with three-way uncertainty. The market is doing its job here — leave it.",
        venue: "Kalshi", price: "+220",
        when: "Sun · 16:00",
      },
    ],
  },
  {
    name: "Group B",
    fixtureCount: 2,
    summary: "2 passes",
    fixtures: [
      {
        verdict: "pass",
        teamA: "Brazil", teamB: "Norway",
        meta: "USA · SoFi Stadium · 20:00 local",
        thesisHtml: "Both markets within 0.4 points of consensus. The line is doing its job.",
        venue: "Polymarket", price: "−145",
        when: "Mon · 20:00",
      },
      {
        verdict: "pass",
        teamA: "Egypt", teamB: "Australia",
        meta: "USA · Hard Rock Stadium · 17:00 local",
        thesisHtml: "Tight three-way market; movement on draw odds is consistent across both venues. No edge to play.",
        venue: "Kalshi", price: "+155",
        when: "Tue · 17:00",
      },
    ],
  },
];

export const TODAYS_SUMMARY = {
  picks: 3,
  passes: 4,
  avoids: 1,
  total: 8,
  picksSub: "avg edge +3.4 points · highest conviction: France v Mexico",
  passesSub: "markets within tolerance · check back at kickoff",
  avoidsSub: "both sides overpriced · the rare two-way no",
  totalSub: "across three groups · matchday 2 of 3",
};

export const FEATURED_COLUMNS = [
  {
    href: "/columns/poly-kalshi-france",
    kicker: "Outright winner",
    title: "Why Polymarket and Kalshi don't agree on France",
    deck: "A two-cent gap on a binary contract is a two-percentage-point gap on the same outcome. Small in the abstract, large for a market this liquid.",
    meta: "6 min read · The Editors · 12 May",
  },
  {
    href: "/columns/what-plus-130-means",
    kicker: "Reading the numbers",
    title: "What +130 actually means",
    deck: "American odds, decimal odds, and \"cents\" on a contract — three notations for the same idea. A short conversion table, with examples.",
    meta: "4 min read · 10 May",
  },
  {
    href: "/columns/group-d-priced-closest",
    kicker: "Group stage",
    title: "Group D is priced as the closest in the tournament",
    deck: "France is favored, but four cents separates the field. We look at why the books and the markets disagree most where the football is closest.",
    meta: "5 min read · 09 May",
  },
];

export const POLYMARKET_OUTRIGHT_URL =
  "https://polymarket.com/event/2026-fifa-world-cup-winner-595";
