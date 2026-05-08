// MarketBlock.jsx — a single market on a match page (winner / total goals / first scorer).
// Title + standfirst + ProbabilityBar + ComparisonTable. Compact variant of EventHero+ComparisonTable.
const MarketBlock = ({ kicker, title, standfirst, outcomes, highlight, rows, footnote }) => (
  <section style={{
    padding: "28px 0",
    borderTop: "1px solid var(--rule)",
  }}>
    <div className="op-eyebrow" style={{
      fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
      letterSpacing: "0.08em", textTransform: "uppercase",
      color: "var(--graphite-soft)", marginBottom: 10,
    }}>{kicker}</div>
    <h2 style={{
      fontFamily: "var(--font-serif)", fontWeight: 600,
      fontSize: 28, letterSpacing: "-0.005em",
      lineHeight: 1.18, margin: 0, color: "var(--ink)", textWrap: "balance",
    }}>{title}</h2>
    {standfirst && (
      <p style={{
        fontFamily: "var(--font-serif)", fontSize: 16, fontStyle: "italic",
        lineHeight: 1.5, color: "var(--ink-soft)",
        margin: "10px 0 0", maxWidth: "58ch",
      }}>{standfirst}</p>
    )}
    {outcomes && (
      <div style={{ marginTop: 18 }}>
        <ProbabilityBar items={outcomes} highlight={highlight} />
      </div>
    )}
    <div style={{ marginTop: 18 }}>
      <ComparisonTable rows={rows} />
    </div>
    {footnote && (
      <div style={{
        marginTop: 10, fontFamily: "var(--font-serif)", fontStyle: "italic",
        fontSize: 13, color: "var(--graphite)",
      }}>{footnote}</div>
    )}
  </section>
);

window.MarketBlock = MarketBlock;
