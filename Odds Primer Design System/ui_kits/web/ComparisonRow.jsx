// ComparisonRow.jsx — the atomic unit. Shows the same outcome priced across
// venues, with the best price highlighted (bold ink + flame chip, never green).
const VENUE_DOT = {
  Polymarket: "var(--venue-polymarket)",
  Kalshi:     "var(--venue-kalshi)",
  DraftKings: "var(--venue-sportsbook)",
  FanDuel:    "var(--venue-sportsbook)",
  BetMGM:     "var(--venue-sportsbook)",
};

const fmtDelta = (d) => {
  if (d == null) return "—";
  const s = d > 0 ? "+" : d < 0 ? "−" : "";
  return `${s}${Math.abs(d).toFixed(1)}`;
};

const ComparisonRow = ({ venue, price, implied, delta7d, isBest, native }) => (
  <div style={{
    display: "grid",
    gridTemplateColumns: "1fr 100px 100px 90px 80px",
    padding: "14px 18px",
    borderBottom: "1px solid var(--rule-soft)",
    background: isBest ? "var(--flame-tint)" : "transparent",
    alignItems: "center",
    transition: "background 200ms cubic-bezier(0.2,0,0,1)",
  }}>
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: VENUE_DOT[venue] || "var(--graphite)", flex: "none" }} />
        <span style={{
          fontFamily: "var(--font-sans)",
          fontWeight: isBest ? 600 : 500, fontSize: 14,
          color: "var(--ink)",
        }}>{venue}</span>
        {isBest && <span style={{
          fontFamily: "var(--font-sans)",
          fontSize: 10, fontWeight: 600, letterSpacing: "0.06em",
          textTransform: "uppercase",
          padding: "2px 8px", borderRadius: 999,
          background: "var(--flame)", color: "var(--paper)",
        }}>Best</span>}
      </div>
      {native && <span style={{
        fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
        fontSize: 11, color: "var(--graphite-soft)", marginLeft: 18,
      }}>{native}</span>}
    </div>
    <div style={{
      fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
      textAlign: "right", fontWeight: isBest ? 600 : 500,
      color: "var(--ink)",
    }}>{price}</div>
    <div style={{
      fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
      textAlign: "right", color: "var(--ink)",
    }}>{implied}</div>
    <div style={{
      fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
      textAlign: "right", fontSize: 13,
      color: delta7d > 0 ? "var(--ink-soft)" : delta7d < 0 ? "var(--graphite)" : "var(--graphite-soft)",
    }}>{fmtDelta(delta7d)}</div>
    <div style={{ textAlign: "right" }}>
      <a href="#" onClick={(e) => e.preventDefault()} style={{
        fontFamily: "var(--font-sans)", fontSize: 12,
        color: "var(--ink)",
        textDecoration: "underline",
        textDecorationColor: "var(--rule)",
        textUnderlineOffset: 3,
        whiteSpace: "nowrap",
      }}>Open ↗</a>
    </div>
  </div>
);

const ComparisonTable = ({ rows = [] }) => {
  // determine best by highest implied probability (assumes "yes" semantics)
  const bestImp = Math.max(...rows.map(r => r.impliedNum ?? 0));
  return (
    <div style={{
      background: "var(--paper-pure)",
      border: "1px solid var(--rule)",
      borderRadius: 6,
      overflow: "hidden",
    }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 100px 100px 90px 80px",
        padding: "10px 18px",
        borderBottom: "1px solid var(--rule)",
        fontFamily: "var(--font-sans)",
        fontSize: 11, fontWeight: 600, letterSpacing: "0.08em",
        textTransform: "uppercase", color: "var(--graphite-soft)",
      }}>
        <div>Venue</div>
        <div style={{ textAlign: "right" }}>Price</div>
        <div style={{ textAlign: "right" }}>Implied</div>
        <div style={{ textAlign: "right" }}>7d Δ</div>
        <div></div>
      </div>
      {rows.map((r, i) => (
        <ComparisonRow key={i} {...r} isBest={r.impliedNum === bestImp} />
      ))}
    </div>
  );
};

window.ComparisonRow = ComparisonRow;
window.ComparisonTable = ComparisonTable;
