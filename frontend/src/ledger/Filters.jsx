// Stub filter row — wired UI controls, no-ops in Phase 0 per the brief.
// Keeps the layout honest about what's coming in Phase 1+.

export default function Filters() {
  return (
    <section className="op-filters" aria-label="filters">
      <div className="op-filters__group">
        <span className="op-eyebrow">Venue</span>
        <span className="op-pill op-pill--on">Polymarket</span>
        <span className="op-pill op-pill--off" title="Phase 1">Kalshi</span>
      </div>
      <div className="op-filters__group">
        <span className="op-eyebrow">Category</span>
        <span className="op-pill op-pill--on">All</span>
        <span className="op-pill op-pill--off" title="Phase 1">Sports</span>
        <span className="op-pill op-pill--off" title="Phase 1">Politics</span>
        <span className="op-pill op-pill--off" title="Phase 1">Crypto</span>
      </div>
      <div className="op-filters__group">
        <span className="op-eyebrow">Market type</span>
        <span className="op-pill op-pill--on">All</span>
        <span className="op-pill op-pill--off" title="Phase 1">Binary</span>
        <span className="op-pill op-pill--off" title="Phase 1">Multi-outcome</span>
      </div>
    </section>
  );
}
