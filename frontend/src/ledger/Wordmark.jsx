// Locked logo + wordmark. Glyph spec from branding/bars-locked-v2.html:
// viewBox 0 0 56 50, bars at heights 14·24·38·18, flame on bar 3, 11px gap.

export function BarsGlyph({ height = 38, inverted = false }) {
  const ink   = inverted ? "#FAF7F0" : "#0E2240";
  const flame = "#D9461C";
  const w = (height * 56) / 50;
  return (
    <svg
      viewBox="0 0 56 50"
      width={w}
      height={height}
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <line x1="2" y1="46" x2="54" y2="46" stroke={ink} strokeWidth="1.5" />
      <rect x="6"  y="32" width="6" height="14" fill={ink} />
      <rect x="16" y="22" width="6" height="24" fill={ink} />
      <rect x="26" y="8"  width="6" height="38" fill={flame} />
      <rect x="36" y="28" width="6" height="18" fill={ink} />
    </svg>
  );
}

export function Wordmark({
  glyphHeight = 42,
  fontSize = 18,
  fontWeight = 700,
  inverted = false,
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "11px",
      }}
    >
      <BarsGlyph height={glyphHeight} inverted={inverted} />
      <span
        style={{
          fontFamily: "var(--font-serif)",
          fontWeight,
          fontSize,
          letterSpacing: "-0.012em",
          color: inverted ? "var(--paper)" : "var(--ink)",
          fontFeatureSettings: '"ss01" on',
          lineHeight: 1,
        }}
      >
        Odds Primer
      </span>
    </span>
  );
}
