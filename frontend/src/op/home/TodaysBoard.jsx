// Today's board — ported from home-v2.
// Each fixture row links to /v2/market-v2-newspaper-deck.html (Vite serves
// public/ at the root). The React newspaper-deck port is a separate
// workstream — for this PR we keep the static-asset href verbatim.

import { FIXTURE_GROUPS, FIXTURE_HREF, TODAYS_SUMMARY } from "./data";

const VERDICT_GLYPH = { pick: "▲", pass: "—", avoid: "✕" };
const VERDICT_LABEL = { pick: "Pick", pass: "Pass", avoid: "Avoid" };

const totalFixtures = FIXTURE_GROUPS.reduce(
  (n, g) => n + g.fixtures.length,
  0,
);

export default function TodaysBoard() {
  return (
    <section className="board-header" id="today" aria-labelledby="board-title">
      <div className="title-block">
        <div>
          <div className="h-eyebrow">Today's board · {totalFixtures} fixtures</div>
          <h2 id="board-title" className="board-title">
            Where the prices look wrong, and where they don't.
          </h2>
        </div>
        <p className="deck">
          Three calls per fixture. <em>Pick</em> when the line is slow;{" "}
          <em>Pass</em> when it's right; <em>Avoid</em> when the favourite is
          overpriced and the contrarian is unattractive too. Tap any row to
          read the case.
        </p>
      </div>

      <Legend />

      {FIXTURE_GROUPS.map((g) => (
        <GroupBlock key={g.name} group={g} />
      ))}

      <SummaryStrip />
    </section>
  );
}

function Legend() {
  return (
    <div className="legend">
      <span className="lbl">Verdict key</span>
      <div className="items">
        <div className="item pick">
          <div className="demo demo--pick"><div className="bar" /><div className="glyph">▲</div></div>
          <div className="text">
            <span className="name">Pick</span>
            <span className="what">the line is underpriced — back it</span>
          </div>
        </div>
        <div className="item pass">
          <div className="demo demo--pass"><div className="bar" /><div className="glyph">—</div></div>
          <div className="text">
            <span className="name">Pass</span>
            <span className="what">the line is fair — no edge to play</span>
          </div>
        </div>
        <div className="item avoid">
          <div className="demo demo--avoid"><div className="bar" /><div className="glyph">✕</div></div>
          <div className="text">
            <span className="name">Avoid</span>
            <span className="what">overpriced both ways — sit it out</span>
          </div>
        </div>
      </div>
      <div className="by">Color, glyph, and label all carry the call — any one is enough.</div>
    </div>
  );
}

function GroupBlock({ group }) {
  return (
    <>
      <div className="group-banner">
        <div className="gname">
          {group.name}<em>{group.fixtureCount} fixtures</em>
        </div>
        <div className="grule" />
        <div className="gcount">{group.summary}</div>
      </div>

      <div className="fixtures">
        {group.fixtures.map((fx, i) => (
          <FixtureRow key={`${group.name}-${i}`} fx={fx} />
        ))}
      </div>
    </>
  );
}

function FixtureRow({ fx }) {
  const cls = `fx is-${fx.verdict}`;
  return (
    <a className={cls} href={FIXTURE_HREF}>
      <span className="bar" />
      <div className="verdict-cell">
        <span className="gly">{VERDICT_GLYPH[fx.verdict]}</span>
        <span className="lab">{VERDICT_LABEL[fx.verdict]}</span>
      </div>
      <div className="match">
        <div className="teams">
          {fx.teamA} <span className="vs">v</span> {fx.teamB}
        </div>
        <div className="meta">{fx.meta}</div>
      </div>
      <div className="thesis" dangerouslySetInnerHTML={{ __html: fx.thesisHtml }} />
      <div className="line">
        <span className="venue">{fx.venue}</span>
        <span className="price">{fx.price}</span>
      </div>
      <div className="action">
        <span className="when">{fx.when}</span>
        <span className="open">Read <span className="arr">↗</span></span>
      </div>
    </a>
  );
}

function SummaryStrip() {
  return (
    <div className="summary">
      <div className="v-pick">
        <div className="lbl">Picks today</div>
        <div className="val">{TODAYS_SUMMARY.picks}</div>
        <div className="sub">{TODAYS_SUMMARY.picksSub}</div>
      </div>
      <div>
        <div className="lbl">Passes</div>
        <div className="val">{TODAYS_SUMMARY.passes}</div>
        <div className="sub">{TODAYS_SUMMARY.passesSub}</div>
      </div>
      <div>
        <div className="lbl">Avoids</div>
        <div className="val">{TODAYS_SUMMARY.avoids}</div>
        <div className="sub">{TODAYS_SUMMARY.avoidsSub}</div>
      </div>
      <div>
        <div className="lbl">Total fixtures</div>
        <div className="val">{TODAYS_SUMMARY.total}</div>
        <div className="sub">{TODAYS_SUMMARY.totalSub}</div>
      </div>
    </div>
  );
}
