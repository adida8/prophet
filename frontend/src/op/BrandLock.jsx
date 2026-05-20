// BrandLock — the canonical lockup (glyph + Inter Tight 700 wordmark).
//
// Two variants per the brief's brand spec (updated 2026-05-12):
//   - "canonical": glyph + wordmark stacked over the tagline.
//     The tagline sits at padding-left: 0 so it stretches under
//     the whole lockup (glyph + wordmark). Used on the home
//     masthead only. Hidden under 520px viewport (footer carries
//     it on small screens).
//   - "minimal": glyph + wordmark side by side, no tagline.
//     Used on About + Learn mastheads, and inside the footer
//     alongside a sibling-rendered tagline.
//
// Glyph geometry is locked: viewBox 0 0 38 34, bars at x={2,11,20,29},
// width 6, heights {10,16,28,14}, flame (#D9461C) on the third bar,
// baseline rule at y=34 stroke-width 1. Do NOT use the older 56x50
// geometry from branding/locked/ — that folder is archived.

export default function BrandLock({
  variant = "minimal",
  href = "/",
  onNavigate,
  glyphSize = 38,
  wordmarkSize = 22,
  ariaLabel,
}) {
  const handleClick = (e) => {
    if (!onNavigate) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; // let new-tab / shift-click through
    e.preventDefault();
    onNavigate(href);
  };

  const className = `brand-lock brand-lock--${variant}`;
  const label = ariaLabel || (variant === "canonical"
    ? "Odds Primer — the AI sports desk for market edge"
    : "Odds Primer");

  return (
    <a className={className} href={href} onClick={handleClick} aria-label={label}>
      {variant === "canonical" ? (
        <>
          <span className="wm-row">
            <BarsGlyph size={glyphSize} />
            <span className="wm" style={{ fontSize: `${wordmarkSize}px` }}>Odds Primer</span>
          </span>
          <span className="tag">
            The <span className="flame">AI</span> sports desk for <span className="flame">market edge</span>
          </span>
        </>
      ) : (
        <>
          <BarsGlyph size={glyphSize} />
          <span className="wm" style={{ fontSize: `${wordmarkSize}px` }}>Odds Primer</span>
        </>
      )}
    </a>
  );
}

export function BarsGlyph({ size = 38, ink = "#0E2240", flame = "#D9461C" }) {
  // Aspect 38 × 34 — preserve it via the SVG's intrinsic ratio.
  const h = Math.round((size * 34) / 38);
  return (
    <svg viewBox="0 0 38 34" width={size} height={h} aria-hidden="true">
      <line x1="0"  y1="34" x2="38" y2="34" stroke={ink} strokeWidth="1" />
      <rect x="2"  y="24" width="6" height="10" fill={ink}   />
      <rect x="11" y="18" width="6" height="16" fill={ink}   />
      <rect x="20" y="6"  width="6" height="28" fill={flame} />
      <rect x="29" y="20" width="6" height="14" fill={ink}   />
    </svg>
  );
}
