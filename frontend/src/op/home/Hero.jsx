// Hero — the issue headline. Carries the page-level <h1>.

export default function Hero({ navigate }) {
  const handleBoard = (e) => {
    e.preventDefault();
    const t = document.getElementById("today");
    if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const handleLearn = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn/how-prices-are-set");
  };

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="h-eyebrow">Vol. 1 · World Cup 2026 edition</div>
      <h1 id="hero-title">Every 2026 World Cup price, read by The Desk.</h1>
      <p className="standfirst">
        Odds Primer compares live Kalshi and Polymarket prices, runs its own model, and explains
        whether each price is a Pick, a Pass, or one to Avoid. Free. Editorial. No tips, no hype.
      </p>
      <p className="standfirst-secondary">
        Built for readers who want to understand the price — not just follow it.
      </p>
      <div className="ctas">
        <a className="btn-primary" href="#today" onClick={handleBoard}>
          See today's Picks <span className="arr">→</span>
        </a>
        <a className="link-secondary" href="/learn/how-prices-are-set" onClick={handleLearn}>
          New here? How to read a price
        </a>
      </div>
    </section>
  );
}
