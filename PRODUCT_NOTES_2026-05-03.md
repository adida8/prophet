# Product notes — 2026-05-03

Captured from a chat brain-dump. Living notes, not a spec.

## Homepage

- Reference: Kalshi.
- Default view = list of games. Allow user to add more.
- One row per game. Show date and time.
- Per row, show 1 / X / 2 prices from **both Kalshi and Polymarket**, side by side.
- Add an "Odds Primer suggests" indicator on each row (graph / chart / badge — TBD). This is our pick, not a venue's price.

## Single-game view (click a row)

- Trend graph of the prices over time. **Nice-to-have** — only if the API exposes history.
- An editorial blurb we write: our prediction for the game, in plain English.
- The blurb is the product. We collect data from multiple sources and turn it into a solid recommendation.
- Recommendation must cite its inputs: "based on X tips" — where X is the count of tip data sources that fed the call.
- Tone example: *"The price for the France–Mexico game on Kalshi is overpriced right now…"*

## Open workstream

- **Scoring algorithm** that produces the recommendation. Not designed yet. Inputs (tip sources, market prices, anything else) and weighting still to define.
