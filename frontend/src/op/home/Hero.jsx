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
    if (navigate) navigate("/learn");
  };

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="h-eyebrow">Vol. 1 · World Cup 2026 edition</div>
      <h1 id="hero-title">The 2026 World Cup, priced.</h1>
      <p className="standfirst">
        The Desk, our verdict engine, reads every World Cup market against its own model —
        Polymarket, Kalshi, and the sportsbooks — and calls each one Pick, Pass, or Avoid,
        with the reasoning. We don't tip.
      </p>
      <div className="ctas">
        <a className="btn-primary" href="#today" onClick={handleBoard}>
          See today's board <span className="arr">↘</span>
        </a>
        <a className="link-secondary" href="/learn" onClick={handleLearn}>
          What is a prediction market? →
        </a>
      </div>
    </section>
  );
}
