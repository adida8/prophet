// /world-cup — SEO cornerstone hub for the verdict cluster.
//
// This is the front door for "world cup 2026 prediction market", "world cup
// odds", and value-pick queries. It explains the market, then funnels into
// the live board (/#today) and outright winners (/#outrights) plus the /learn
// primers. Copy is editorial + evergreen; the live numbers live on the board,
// not hardcoded here, so this page doesn't go stale during the tournament.

import Footer from "../Footer";
import Masthead from "../Masthead";

const FAQS = [
  {
    q: "What is a prediction market for the World Cup?",
    a: "A market where you trade contracts on tournament outcomes — who wins the trophy, who tops a group, the result of a single match. The price of each contract is the market's implied probability: a contract at 18¢ means the market thinks there's an 18% chance. Unlike a sportsbook, you're trading with other people, not against the house.",
  },
  {
    q: "Where can I see World Cup 2026 odds as probabilities?",
    a: "Our board standardises every venue to implied probability, so a Polymarket cent quote and a sportsbook line sit on the same row. That lets you compare like with like — and see where two venues disagree about the same outcome.",
  },
  {
    q: "What does Odds Primer add on top of the odds?",
    a: "A verdict. For each market we run our own model and compare it to the market price, then publish a Pick, Pass, or Avoid with the reasoning. The odds tell you what the market thinks; the verdict tells you where we think the market might be wrong, and why.",
  },
  {
    q: "Is betting on the World Cup through a prediction market legal?",
    a: "It depends on where you live and which venue you use. Kalshi is federally regulated and available in most US states; Polymarket is restricted in several. Our legality primer has the state-by-state read.",
  },
];

export default function WorldCup({ navigate, currentPath }) {
  const goHash = (id) => (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (!navigate) return;
    navigate("/");
    setTimeout(() => {
      const t = document.getElementById(id);
      if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const goTo = (href) => (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate(href);
  };

  return (
    <div className="op-site">
      <Masthead
        variant="minimal"
        currentPath={currentPath}
        navigate={navigate}
        navMeta="The World Cup edition"
        editionLeft="World Cup 2026 · USA · Canada · Mexico"
        editionRight="Updated for live markets"
      />

      <main className="page">
        <section className="learn-hero">
          <div className="learn-eyebrow">The issue · World Cup 2026</div>
          <h1>World Cup 2026 odds, prediction markets, and where the price looks wrong.</h1>
          <p className="standfirst">
            Forty-eight teams, one expanded tournament, and a prediction market
            that reprices every time the team news drops. We track the winner
            market and every priced match across Polymarket, Kalshi, and the
            sportsbooks — standardise them to one probability — and publish a
            verdict on each: <strong>Pick</strong>, <strong>Pass</strong>, or{" "}
            <strong>Avoid</strong>.
          </p>
        </section>

        <section className="wc-actions" aria-label="Live markets">
          <a className="btn-primary" href="/#today" onClick={goHash("today")}>
            Today's board <span className="arr">↘</span>
          </a>
          <a className="btn-secondary" href="/#outrights" onClick={goHash("outrights")}>
            Who wins the trophy? <span className="arr">↘</span>
          </a>
        </section>

        <article className="learn-article">
          <div className="article-body">
            <h2>How to read the World Cup as a market</h2>
            <p>
              A sportsbook gives you a line. A prediction market gives you a
              probability — the price <em>is</em> the market's best guess at the
              chance. When France trades at 18¢ to win the trophy, the market is
              saying roughly 18%. When two venues quote the same outcome at
              different prices, one of them is wrong about something, and the gap
              is the interesting part.{" "}
              <a href="/learn/what-is-a-prediction-market" onClick={goTo("/learn/what-is-a-prediction-market")}>
                Start with the basics primer
              </a>{" "}
              if any of that is new.
            </p>

            <h2>The winner market</h2>
            <p>
              The outright "who wins the World Cup" market is the headline.
              Spain, France, England, Argentina, and Brazil sit at the top of
              the board, but the expanded 48-team field and host-nation effects
              make this one of the most fluid futures markets in years — which
              means more moments where the price drifts away from the true
              chance.{" "}
              <a href="/#outrights" onClick={goHash("outrights")}>
                See the live winner ladder
              </a>{" "}
              for our model probability against the market on every contender.
            </p>

            <h2>Match by match</h2>
            <p>
              Beyond the trophy, every priced match gets the same treatment: our
              model probability, the market price, and a verdict with the
              reasoning. Group-stage mismatches, knockout coin-flips, host
              advantage — each is a market, and each is a place the price can be
              off.{" "}
              <a href="/#today" onClick={goHash("today")}>
                The board groups today's matches by tournament group.
              </a>
            </p>

            <h2>What a verdict means</h2>
            <p>
              <strong>Pick</strong> — our model rates a side meaningfully higher
              than the market price; the gap is the basis for the call.{" "}
              <strong>Pass</strong> — model and market agree closely enough that
              there's no edge worth acting on. <strong>Avoid</strong> — the
              market looks distorted in a way that makes the visible price
              misleading. Every verdict ships with the case behind it, so you're
              never asked to take the call on trust.
            </p>

            <h2>Questions people ask</h2>
            {FAQS.map((f) => (
              <div key={f.q} style={{ marginBottom: 18 }}>
                <h3 style={{ marginBottom: 6 }}>{f.q}</h3>
                <p style={{ marginTop: 0 }}>{f.a}</p>
              </div>
            ))}

            <div className="notice">
              <p>
                <strong>Read the market, then read us, then decide.</strong>{" "}
                Nothing here is betting advice — only stake what you can afford
                to lose, and check each venue's own rules before you trade.
              </p>
            </div>
          </div>

          <div className="nextup">
            <span className="nlbl">New to this?</span>
            <a href="/learn" onClick={goTo("/learn")}>
              Read the primers first <span className="arr">→</span>
            </a>
          </div>
        </article>
      </main>

      <Footer navigate={navigate} currentPath={currentPath} />
    </div>
  );
}
