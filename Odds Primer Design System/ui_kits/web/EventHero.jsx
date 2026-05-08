// EventHero.jsx — the page-top unit on an event page. Eyebrow, headline,
// standfirst, and a probability bar showing all outcomes side-by-side.
const EventHero = ({ kicker, title, standfirst, byline, outcomes, highlight }) => (
  <section style={{ padding: "48px var(--gutter-page) 32px" }}>
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div className="op-eyebrow" style={{
        fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
        letterSpacing: "0.08em", textTransform: "uppercase",
        color: "var(--graphite-soft)", marginBottom: 14,
      }}>{kicker}</div>
      <h1 style={{
        fontFamily: "var(--font-serif)", fontWeight: 600,
        fontSize: "clamp(2.25rem, 4.2vw, 3.5rem)",
        lineHeight: 1.06, letterSpacing: "-0.01em",
        margin: 0, color: "var(--ink)", textWrap: "balance",
      }}>{title}</h1>
      {standfirst && (
        <p style={{
          fontFamily: "var(--font-serif)", fontSize: 20,
          lineHeight: 1.45, color: "var(--ink-soft)",
          marginTop: 18, maxWidth: "62ch",
        }}>{standfirst}</p>
      )}
      {byline && (
        <div style={{
          marginTop: 20, fontFamily: "var(--font-sans)", fontSize: 12,
          color: "var(--graphite)", display: "flex", gap: 12, alignItems: "center",
        }}>
          <span style={{ fontWeight: 500 }}>{byline.author}</span>
          <span style={{ color: "var(--rule)" }}>·</span>
          <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic" }}>{byline.date}</span>
          <span style={{ color: "var(--rule)" }}>·</span>
          <span>{byline.read}</span>
        </div>
      )}
      {outcomes && (
        <div style={{ marginTop: 36 }}>
          <div className="op-eyebrow" style={{
            fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
            letterSpacing: "0.08em", textTransform: "uppercase",
            color: "var(--graphite-soft)", marginBottom: 10,
          }}>Implied probability across the field · Polymarket consensus</div>
          <ProbabilityBar items={outcomes} highlight={highlight} />
        </div>
      )}
    </div>
  </section>
);

window.EventHero = EventHero;
