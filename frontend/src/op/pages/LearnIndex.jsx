// /learn — primer index.

import Footer from "../Footer";
import Masthead from "../Masthead";

const PRIMERS = [
  {
    num:    "01",
    meta:   "3 min read · The basics",
    title:  "What is a prediction market?",
    deck:   "A market where you trade contracts that pay out on real-world events. Different from sports betting in one important way — the price is the probability.",
    href:   "/learn/what-is-a-prediction-market",
  },
  {
    num:    "02",
    meta:   "5 min read · Reading the numbers",
    title:  "How are prices set?",
    deck:   "Order books, implied probability, and the reason two venues can quote the same outcome at different prices. With one worked example you can replay in your head.",
    href:   "/learn/how-prices-are-set",
  },
  {
    num:    "03",
    meta:   "4 min read · Geo + age",
    title:  "Is it legal?",
    deck:   "It depends on where you live and which venue you use. A state-by-state read on Kalshi, Polymarket, and the sportsbook-run prediction products — without the lawyer-pretending tone.",
    href:   "/learn/is-it-legal",
  },
];

export default function LearnIndex({ navigate, currentPath }) {
  const goBoard = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (!navigate) return;
    navigate("/");
    setTimeout(() => {
      const t = document.getElementById("today");
      if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const goPrimer = (href) => (e) => {
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
        navMeta="Three primers · 12 min total"
        editionLeft="Learn · The basics"
        editionRight="Updated 12 May 2026"
      />

      <main className="page">
        <section className="learn-hero">
          <div className="learn-eyebrow">Learn · Volume 1</div>
          <h1>Three short reads, and you'll know how to read the rest of the site.</h1>
          <p className="standfirst">
            You don't need a finance background to read a prediction market — you need
            about twelve minutes and a willingness to think in percentages instead of
            slogans. Start with the first; the others are stand-alone.
          </p>
        </section>

        <section className="primers" aria-label="Primers">
          {PRIMERS.map((p) => (
            <a key={p.num} className="primer" href={p.href} onClick={goPrimer(p.href)}>
              <span className="num">{p.num}</span>
              <div>
                <div className="meta">{p.meta}</div>
                <h2>{p.title}</h2>
                <p>{p.deck}</p>
              </div>
              <span className="read">Read <span className="arr">↗</span></span>
            </a>
          ))}
        </section>

        <section className="outro">
          <h3>Ready to read a market?</h3>
          <p>The board is grouped by tournament group. Tap any row to read the case behind the call.</p>
          <a className="btn-primary" href="/#today" onClick={goBoard}>
            See today's board <span className="arr">↘</span>
          </a>
        </section>
      </main>

      <Footer navigate={navigate} currentPath={currentPath} />
    </div>
  );
}
