// /about — five anchored sections + sticky side-rail.
// Role cards are anonymous per the brief: no founder names anywhere.

import { BarsGlyph } from "../BrandLock";
import Footer from "../Footer";
import Masthead from "../Masthead";

const RAIL_ITEMS = [
  { href: "#who",          label: "Who runs this" },
  { href: "#how",          label: "How we work" },
  { href: "#dont",         label: "What we don't do" },
  { href: "#money",        label: "Where the money comes from" },
  { href: "#corrections",  label: "Corrections" },
];

export default function About({ navigate, currentPath }) {
  return (
    <div className="op-site">
      <Masthead
        variant="minimal"
        currentPath={currentPath}
        navigate={navigate}
        navMeta="Vol. 1 · matchday 2"
        editionLeft="About the publication"
        editionRight="Last updated 12 May 2026"
      />

      <main className="page">
        <article className="about">
          <div className="about-eyebrow">About</div>
          <h1 className="about-title">A publication, not a sportsbook.</h1>
          <p className="about-standfirst">
            We compare prices on prediction markets for one sport at a time and explain
            what the numbers mean. The first edition is the 2026 FIFA World Cup. The next
            will be club football for the 2026–27 season.
          </p>

          <div className="about-body">
            <aside className="about-rail" aria-label="On this page">
              <span className="rail-lbl">On this page</span>
              {RAIL_ITEMS.map((item) => (
                <a key={item.href} href={item.href}>{item.label}</a>
              ))}
            </aside>

            <div className="about-prose">
              <section id="who">
                <h2>Who runs this</h2>
                <p>
                  Odds Primer is a small, independent publication. Two roles do the
                  work: an <strong>engineer</strong> builds <em className="em">The Desk</em>{" "}
                  — our verdict engine — and an{" "}
                  <strong>editor</strong> writes the columns. Neither role takes wagers,
                  holds your money, or recommends a play. When you act on what you read
                  here, you do so on a venue under that venue's terms.
                </p>
                <div className="bios">
                  <RoleCard
                    role="The engineer"
                    body="Builds The Desk — the ingest, the model, the verdict step. Reads prices for a living. Writes nothing for the front of the site; argues with the model in test files."
                  />
                  <RoleCard
                    role="The editor"
                    body="Writes the columns. Argues with the engineer in the margins. Believes the most useful sentence on any market page is the one that explains why two venues disagree."
                  />
                </div>
              </section>

              <section id="how">
                <h2>How we work</h2>
                <p className="lede">
                  Three things every page on this site shows: a price, a comparison, and an explanation.
                </p>
                <p>
                  <strong>Prices</strong> are pulled from Polymarket, Kalshi, and US sportsbooks
                  every minute. <strong>Comparison</strong> highlights the best price for a given
                  outcome — without a green badge, because best price isn't a buy signal.
                  <strong> The explanation</strong> is plain English about what the market
                  resolves to, how implied probability works, and why two venues might disagree
                  on the same outcome.
                </p>
                <p>
                  The Desk verdict engine flags fixtures where the line looks slow{" "}
                  (<span className="em">Pick</span>), fair (<span className="em">Pass</span>),
                  or both-sides overpriced (<span className="em">Avoid</span>). Those are structural
                  reads on the prices — not predictions of who will win.
                </p>
                <p>
                  We standardise prices to implied probability so a Polymarket cent quote
                  and a sportsbook moneyline can be compared directly on the same row.
                  Full methodology lives at{" "}
                  <LearnLink navigate={navigate}>Learn the basics</LearnLink>.
                </p>
              </section>

              <section id="dont">
                <h2>What we don't do</h2>
                <p className="lede">A short list, because it's load-bearing.</p>
                <ul className="nope">
                  <li>
                    We don't <span className="em">tip</span>. The verdict engine names where
                    the market looks mispriced — not what to back.
                  </li>
                  <li>
                    We don't write <span className="em">"bet now"</span>. Every venue handoff
                    is a citation — "View source on Polymarket ↗" — not a call to action.
                  </li>
                  <li>We don't use flame icons, shield icons, or any other dopamine furniture.</li>
                  <li>We don't promote sign-up bonuses, even when the venues we cite offer them.</li>
                  <li>
                    We don't score ourselves by hit rate. The Brier score on our calibration page
                    is the receipt; a Twitter screenshot is not.
                  </li>
                  <li>We don't take your money, hold a position, or earn a spread.</li>
                </ul>
              </section>

              <section id="money">
                <h2>Where the money comes from</h2>
                <p>
                  When a reader uses a "View source on Polymarket ↗" link and trades there,
                  Polymarket shares a portion of the trading fee with us. That's our only
                  revenue stream today. We disclose every affiliate relationship in the
                  footer of every page and in full on the{" "}
                  <a href="/affiliate-disclosure">Affiliate disclosure</a> page.
                </p>
                <p>
                  The Desk verdict engine is run blind to that revenue.{" "}
                  <strong>The model never sees a venue's trading volume or our payout</strong>{" "}
                  — the only inputs it reads are prices and the football-feature builders
                  (form, FIFA rank, host effect, altitude). How The Desk works in full is in{" "}
                  <a href="/methodology">our methodology page</a>.
                </p>
              </section>

              <section id="corrections">
                <h2>Corrections</h2>
                <p>
                  Email <a href="mailto:corrections@oddsprimer.com">corrections@oddsprimer.com</a>{" "}
                  with the URL and the issue. We post a correction on the page itself and date it.
                  We don't silently rewrite. If a column moves the market and we got it wrong,
                  the correction sits at the top of the column, not the bottom.
                </p>
                <div className="contact-box">
                  <span className="lbl">Editorial</span>
                  <a href="mailto:hello@oddsprimer.com">hello@oddsprimer.com</a>
                  <span className="lbl" style={{ marginTop: 8 }}>Corrections</span>
                  <a href="mailto:corrections@oddsprimer.com">corrections@oddsprimer.com</a>
                  <span className="lbl" style={{ marginTop: 8 }}>Press</span>
                  <a href="mailto:press@oddsprimer.com">press@oddsprimer.com</a>
                </div>
              </section>
            </div>
          </div>
        </article>
      </main>

      <Footer navigate={navigate} currentPath={currentPath} />
    </div>
  );
}

function RoleCard({ role, body }) {
  return (
    <div className="bio">
      <BarsGlyph size={36} />
      <div>
        <div className="who">Role</div>
        <div className="name">{role}</div>
        <p className="role">{body}</p>
      </div>
    </div>
  );
}

function LearnLink({ navigate, children }) {
  const handle = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn");
  };
  return (
    <a href="/learn" onClick={handle}>{children}</a>
  );
}
