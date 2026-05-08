// ProbabilityBar.jsx — the system's chart primitive. Horizontal stack of
// outcomes; the highlighted segment uses flame.
const ProbabilityBar = ({ items = [], highlight }) => {
  const total = items.reduce((s, it) => s + it.value, 0);
  return (
    <div>
      <div style={{
        display: "flex", height: 18, width: "100%",
        border: "1px solid var(--rule)", borderRadius: 2, overflow: "hidden",
      }}>
        {items.map((it, i) => {
          const isHi = it.label === highlight;
          return (
            <div key={i} title={`${it.label}: ${((it.value/total)*100).toFixed(1)}%`} style={{
              width: `${(it.value/total)*100}%`,
              background: isHi ? "var(--flame)"
                        : i === 0 ? "var(--ink)"
                        : i === 1 ? "var(--ink-soft)"
                        : i === 2 ? "var(--graphite)"
                        : i === 3 ? "#B89968"
                        : "var(--paper-deep)",
            }} />
          );
        })}
      </div>
      <div style={{
        marginTop: 8, display: "flex", flexWrap: "wrap",
        gap: "4px 14px",
        fontFamily: "var(--font-sans)", fontSize: 11,
        color: "var(--graphite)",
      }}>
        {items.map((it, i) => {
          const isHi = it.label === highlight;
          const pct = ((it.value/total)*100).toFixed(0);
          return (
            <span key={i} style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              color: isHi ? "var(--flame-deep)" : "var(--graphite)",
              fontWeight: isHi ? 600 : 400,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: 2,
                background: isHi ? "var(--flame)"
                          : i === 0 ? "var(--ink)"
                          : i === 1 ? "var(--ink-soft)"
                          : i === 2 ? "var(--graphite)"
                          : i === 3 ? "#B89968"
                          : "var(--paper-deep)",
              }} />
              {it.label} <span className="op-num" style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{pct}%</span>
            </span>
          );
        })}
      </div>
    </div>
  );
};

window.ProbabilityBar = ProbabilityBar;
