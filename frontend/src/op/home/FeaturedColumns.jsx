// Featured columns — three editorial cards.
// Hardcoded sample data; cards link to /columns/* which are placeholder
// routes not implemented in this PR.

import { FEATURED_COLUMNS } from "./data";

export default function FeaturedColumns() {
  return (
    <section className="features" aria-labelledby="features-title">
      <div className="f-head">
        <h2 id="features-title">Featured columns</h2>
        <a href="/columns">
          All columns <span className="arr">→</span>
        </a>
      </div>
      <div className="f-grid">
        {FEATURED_COLUMNS.map((c) => (
          <a key={c.href} className="f-card" href={c.href}>
            <span className="kicker">{c.kicker}</span>
            <span className="title">{c.title}</span>
            <p className="deck">{c.deck}</p>
            <span className="meta">{c.meta}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
