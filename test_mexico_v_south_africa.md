# Engine test — Mexico v South Africa, WC 2026 opener

**Run date:** 2026-05-03 (38 days before kickoff)
**Match:** Group A · Thu 11 Jun 2026, 15:00 ET / 12:00 PT · Estadio Azteca, Mexico City (alt. 2,240 m)
**Status:** end-to-end dry run with current public data. Numbers are illustrative — productionising requires headless render for Elo and a market-search call for live odds.

## What the engine ingested

| Source | Used for | Status this run |
|---|---|---|
| Polymarket Gamma API | Market existence + live prices | Slug lookup returned empty; markets exist but require search-by-keyword endpoint. Live prices below from Polymarket UI. |
| Kalshi sports/soccer/fifa-world-cup | Comparison venue | Confirmed live; prices not pulled this run. |
| FIFA official site (canadamexicousa2026) | Fixture metadata, venue, kickoff | Confirmed match #1, Estadio Azteca, 11 Jun. |
| World Football Elo (eloratings.net) | Pre-tournament strength prior | **Blocker** — JS-rendered. Used estimated Elo from FIFA-rank proxy; production needs Playwright or the Wikipedia data module. |
| Recent results (form proxy) | Last 5 matches | Mexico 3W in last 5, +6 GD. South Africa AFCON R16 exit, lost 1–2 to Panama in friendly. |
| Public injury news | Availability adjustment | Mexico has a real injury crisis (see Drivers). |
| OpenWeatherMap | Match-day conditions | Out of forecast window (38 days); annotated as TBD. |

## Feature vector

| Feature | Mexico | South Africa | Note |
|---|---|---|---|
| FIFA rank (Apr 2026) | 15 | 60 | 45-place gap |
| Estimated Elo | ~1750 | ~1525 | Δ ≈ +225 to Mexico (proxy from rank) |
| Last-5 form (W-D-L) | 3-?-? (+6 GD) | losses to Cameroon (R16), Panama (friendly) | Mexico trending up, RSA trending down |
| Home advantage | Yes | — | International HA worth ~+75 Elo |
| Altitude effect | +15 Elo over non-altitude opponent | RSA bases at Johannesburg (1,750 m), partial adaptation | Smaller than typical Azteca altitude bonus |
| Key absences | GK Malagón (Achilles), Romo, Chávez (ACL), Huerta, Huescas; Giménez doubtful | None publicly reported | -3 to -4 pp swing on Mexico |
| Coach | Aguirre (3rd WC) | Broos | — |
| Kickoff pressure | Hosting opener at Azteca, ceremonial weight | Underdog, low expectations | Asymmetric — pressure cuts vs Mexico |

## Model output

**Rule observed:** weather and injuries are late-binding features and **not** factored at T-38. They will enter on a second run inside the final ~5 days before kickoff.

**Probabilities at T-38 (fundamentals only):**

| Outcome | Model (T-38) | Polymarket (raw) | Polymarket (devigged) | Gap |
|---|---|---|---|---|
| Mexico win | **66%** | 65¢ | 62% | +4 pp |
| Draw | **22%** | 24¢ | 23% | -1 pp |
| South Africa win | **12%** | 16¢ | 15% | -3 pp |

(Polymarket vig ≈ 5%; devig is proportional.)

**Expected goals:** Mexico 1.7 · South Africa 0.8 · total 2.5
**Confidence band:** mid — international-form samples are thin and the late-binding inputs aren't in yet.

**The gap is the educational story.** The market is at 62% Mexico; our pure-fundamentals model is at 66%. That 4-point gap is roughly the haircut traders are already applying for Mexico's known injury list (Malagón, Romo, Chávez, Huerta, Huescas, Giménez doubt). When we re-run at T-5 and inject the injury feature, we expect our number to drop into the market's range. If at T-5 the gap is *still* there, that's signal — either the market is over-discounting the injuries, or our model is missing something the market sees.

## Drivers at T-38 (ordered by contribution)

1. **Class gap.** 45 places of FIFA ranking and ~225 Elo points. The bulk of the model's lean is structural.
2. **Home + altitude at Azteca.** Worth roughly +90 Elo combined. South Africa's Joburg base muffles the altitude piece but doesn't erase it.
3. **Form delta.** Mexico won 3 of last 5 with strong defensive numbers. South Africa lost a friendly to Panama in March — a team the model would rate well below them.
4. **Opening-match pressure on host.** Documented effect — host nations underperform Elo by ~3 pp in opening matches. Already absorbed into the calibrated number.

**Held back until T-5:** Mexico's injury list (Malagón, Romo, Chávez, Huerta, Huescas, Giménez doubt) and venue weather. We can see them now but the rule says don't move the model on inputs that won't survive 38 days.

## Blurb (Prophet voice, T-38 version, 80 words)

> Mexico and South Africa open the World Cup in Mexico City on 11 June, sixteen years after they drew the same opening fixture in Johannesburg. The class gap is wide — Mexico sits 45 places higher in the FIFA ranking, and Azteca's altitude is a real edge. On fundamentals alone our model lands at 66% Mexico, 22% draw, 12% South Africa. The market is closer to 62% Mexico — that gap is the discount traders are already taking for Mexico's injuries. We'll know more closer to kickoff.

## What this test reveals

**Where the model and market agree** is itself the story. The educational move here is *not* "the market is wrong, here's a trade" — it's "here is the mental model the market is also running, broken into its parts." That framing keeps us inside the design system's anti-promo voice.

**Operational findings for the build:**

- **eloratings.net needs headless render** or a switch to Wikipedia's data module. Add ~half a day to the ingest layer.
- **Polymarket slug lookup is unreliable.** We need to use the Gamma `markets?question=...` search endpoint, or pull the full WC event tree once and cache the slug map.
- **Injury data is the hardest piece** — none of the free APIs cover this well 38 days out. Likely a manual ops job for the WC beta: a daily Faktor + Adi 5-minute pass over Sky/ESPN team-news pages.
- **Weather is out of forecast range** until ~5 days before kickoff. The pipeline should treat weather as a late-binding feature, not a launch-day input.

## Open questions before building

1. **Confidence-band display.** Do we show "mid confidence" to the user, or only at the page footer? The design system needs a component for this.
2. **When the model agrees with the market**, what does the comparison view actually show? A flat "model and market agree at 62%" is honest but visually quiet. Worth a mockup.
3. **Injury data sourcing.** Manual ops for WC (acceptable) vs scraping team news (fragile) vs a paid feed like SportMonks for the tournament only. Decide before the beta.
4. **Wikipedia Module as Elo source.** It's plain-text, version-controlled, and updated within hours of matches. May be a better production choice than eloratings.net.
