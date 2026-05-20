// How we work — three-column explanation block.

export default function HowWeWork({ navigate }) {
  const handle = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn");
  };

  return (
    <section className="how" aria-labelledby="how-title">
      <h2 id="how-title">How we work</h2>
      <p className="lede">
        Three things every page on this site shows: a price, a comparison, and an explanation.
      </p>
      <div className="how-cols">
        <div className="how-col">
          <h3>We compare</h3>
          <p>
            Prices on Polymarket, Kalshi, and the major US sportsbooks, refreshed every minute.
            {" "}<span className="em">Best price</span> is bold ink, not a green badge — it isn't a buy signal.
          </p>
        </div>
        <div className="how-col">
          <h3>We explain</h3>
          <p>
            Plain English on what the market resolves to, how implied probability works, and why two
            venues might disagree on the same outcome.
          </p>
        </div>
        <div className="how-col">
          <h3>We don't tip</h3>
          <p>
            No "bet now". No lock-of-the-day. The Desk flags fixtures where the line looks slow, fair,
            or both-sides expensive — a structural read on the prices, not a pick against the outcome.
          </p>
        </div>
      </div>
      <div className="how-foot">
        <a className="link-secondary" href="/learn" onClick={handle}>
          Read the methodology →
        </a>
      </div>
    </section>
  );
}
