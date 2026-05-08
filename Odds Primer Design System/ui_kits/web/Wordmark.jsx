// Wordmark.jsx — brand wordmark with probability-bars glyph as flag.
// Locked v2: Source Serif 4 800 wordmark, glyph-led proportions, heights 22·38·65·30.
// `size` is the wordmark font size. By default the glyph renders at ~1.95× that.
// For the masthead, pass `glyphSize` explicitly to break the ratio (glyph-led at small sizes).
const Wordmark = ({
  size = 36,
  glyphSize = null,
  weight = 800,
  color = "var(--ink)",
  flame = "var(--flame)",
  showGlyph = true,
}) => {
  const glyphH = glyphSize ?? size * 1.95;
  const barW   = glyphH * 0.12;
  const barGap = glyphH * 0.08;
  const stroke = Math.max(1, glyphH * 0.025);
  const baseY  = glyphH;
  // Heights mapped from real probabilities 22 · 38 · 65 · 30 (third bar wins, in flame).
  const heights = [0.28, 0.48, 0.76, 0.36];
  const colors  = [color, color, flame, color];
  const glyphW  = barW * 4 + barGap * 3;
  // Gap between glyph and wordmark — 11px at the production lockup (size 36 → ~11px).
  const gap = size * 0.30;
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap,
      lineHeight: 1,
      whiteSpace: "nowrap",
    }}>
      {showGlyph && (
        <svg
          width={glyphW}
          height={glyphH}
          viewBox={`0 0 ${glyphW} ${glyphH}`}
          style={{ display: "block" }}
          aria-hidden="true"
        >
          <line
            x1="0" y1={baseY - stroke / 2}
            x2={glyphW} y2={baseY - stroke / 2}
            stroke={color} strokeWidth={stroke}
          />
          {heights.map((h, i) => (
            <rect
              key={i}
              x={i * (barW + barGap)}
              y={baseY - glyphH * h}
              width={barW}
              height={glyphH * h - stroke}
              fill={colors[i]}
            />
          ))}
        </svg>
      )}
      <span style={{
        fontFamily: "var(--font-serif)",
        fontWeight: weight,
        fontSize: size,
        letterSpacing: "-0.012em",
        fontFeatureSettings: '"ss01" on',
        color: color,
      }}>Odds Primer</span>
    </span>
  );
};

window.Wordmark = Wordmark;
