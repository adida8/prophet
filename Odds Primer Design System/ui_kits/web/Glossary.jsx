// Glossary.jsx — a single glossary entry, used inline on event pages and
// as the building block of the /glossary route.
const GlossaryEntry = ({ term, mark, def, example }) => (
  <div style={{
    padding: "20px 22px",
    background: "var(--paper-pure)",
    border: "1px solid var(--rule)",
    borderRadius: 6,
  }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
      <span style={{
        fontFamily: "var(--font-serif)", fontStyle: "italic",
        color: "var(--flame)", fontWeight: 500, fontSize: 18,
      }}>§</span>
      <span className="op-eyebrow" style={{
        fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
        letterSpacing: "0.08em", textTransform: "uppercase",
        color: "var(--graphite-soft)",
      }}>Reading the numbers</span>
    </div>
    <h3 style={{
      fontFamily: "var(--font-serif)", fontWeight: 600,
      fontSize: 22, margin: 0, color: "var(--ink)", letterSpacing: "-0.005em",
    }}>{term} <span style={{ fontFamily: "var(--font-mono)", fontWeight: 500, color: "var(--graphite)", fontSize: 18 }}>{mark}</span></h3>
    <p style={{
      fontFamily: "var(--font-serif)", fontSize: 15, lineHeight: 1.55,
      color: "var(--ink)", marginTop: 10, marginBottom: 0, maxWidth: "58ch",
    }}>{def}</p>
    {example && (
      <div style={{
        marginTop: 14, padding: "10px 12px",
        background: "var(--paper-warm)",
        borderRadius: 4,
        fontFamily: "var(--font-mono)", fontSize: 13,
        fontVariantNumeric: "tabular-nums",
        color: "var(--graphite)",
      }}>{example}</div>
    )}
  </div>
);

window.GlossaryEntry = GlossaryEntry;
