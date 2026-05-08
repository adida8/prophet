# Odds Primer — Web UI kit

The anchor product surface. One full page (`index.html`) plus reusable components.

## Files
- `index.html` — the **event explainer**: "Will France win the 2026 World Cup?" Renders the masthead, hero, prose explainer with inline footnotes, sticky glossary aside, comparison table, and footer. This is the page that proves all three jobs at once: explain, compare, teach.
- `Wordmark.jsx` — brand wordmark with the bars-glyph as flag.
- `Masthead.jsx` — sticky top nav with edition strip and live indicator.
- `Footnote.jsx` — inline `FootnoteMark` (popover on hover) + `FootnoteList` for the footer column.
- `ProbabilityBar.jsx` — the system's chart primitive. Charts ARE the imagery.
- `ComparisonRow.jsx` — the atomic unit. Plus `ComparisonTable` which auto-highlights the best implied probability.
- `EventHero.jsx` — page-top: kicker, headline, standfirst, byline, probability bar.
- `Glossary.jsx` — `GlossaryEntry` card.

## Conventions
- All components read CSS vars from `../../colors_and_type.css`.
- All number-bearing UI uses `font-family: var(--font-mono)` + `tabular-nums`.
- "Best" is **never green**. Best is bold ink + flame chip + flame-tint background.
- Venue handoff is always: "View source on [venue] ↗" — venue as citation, not destination.
