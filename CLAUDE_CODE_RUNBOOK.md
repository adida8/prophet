# Claude Code Runbook — Daily Site Publish

**Purpose.** Refresh The Desk's match verdicts, regenerate the static Odds Primer site, commit, push. Whole thing is one Claude Code session, ≤2 minutes of work. Built as a manual bridge while the Faktor↔Desk integration is unblocked.

**Owner.** Adi.
**First version:** 2026-05-19. Authored in Cowork; everything from here lives in Claude Code.

---

## What this package does

1. Runs The Desk against live Polymarket / Kalshi prices → writes `desk/data/output/football/*.json`.
2. Runs `site/generate.py` → reads those JSONs → writes static HTML to `site/public/`.
3. Commits the changes on the working branch and pushes; Railway redeploys on merge to `init/project-setup`.

The website is **self-hosted on the existing FastAPI server**. New routes in `server.py` (`/`, `/matches/`, `/m/{id}`, `/outrights/`, `/o/{id}`) serve the static HTML when `site/public/index.html` exists, otherwise the React app keeps owning `/`. No new infra, no new deploy target.

Outright winners (WC champion etc.) render as a "coming soon" empty state until the engine produces `desk/data/output/outrights/*.json`. Authoritative spec for that engine work is **`THE_DESK_OUTRIGHTS_SPEC.md`** (v0.2) — Monte Carlo bracket sim, position-list waist integration, supersedes prior drafts.

---

## Pre-flight (do this once per machine)

```bash
cd /Users/adi/Documents/Claude/Projects/prophet

# Python deps (only if not already installed)
pip install -r requirements.txt
cd desk && python -m pip install -e ".[dev]" && cd ..

# Confirm working tree is clean and we know the branch
git status
git branch --show-current
```

Expected: clean working tree, branch is either `init/project-setup` (direct deploy) or a feature branch you'll PR into it.

If `git status` shows surprise staged files from the VS Code git/PR extension, run `git reset` first (touches no files).

---

## The daily run (4 commands)

```bash
cd /Users/adi/Documents/Claude/Projects/prophet

# 1. Refresh Desk verdicts (Polymarket + Kalshi → per-match JSON)
cd desk && python -m desk run --once && cd ..

# 2. Regenerate static site (reads desk/data/output/, writes site/public/)
python site/generate.py

# 3. Preview locally (optional QA — Ctrl+C when done)
python -m http.server 8765 --directory site/public
# Then open http://localhost:8765/

# 4. Commit + push
git add desk/data/output/ site/public/
git commit -m "site: refresh $(date -u +%Y-%m-%d)"
git push
```

### Expected output

Step 1 (`python -m desk run --once`):
```
wrote N files across 1 sport(s)
  football: N file(s)
```

Step 2 (`python site/generate.py`):
```
Reading from   : .../prophet/desk/data/output
Writing to     : .../prophet/site/public
Loaded matches : 78
  after filter : 47 upcoming (dropped 31 past)
Loaded outrights: 0
Wrote          : index.html
Wrote          : matches/index.html
Wrote          : 47 match page(s) in m/
Wrote          : outrights/index.html

✓ Site ready  : .../prophet/site/public
```

### Deploy

- **On `init/project-setup`:** push → Railway auto-deploys → live at https://web-production-9e0f9.up.railway.app/ within ~90s.
- **On a feature branch:** `gh pr create --base init/project-setup --title "site: refresh $(date -u +%Y-%m-%d)" --body "Daily verdict refresh."` Operator (Adi) merges. Railway deploys on merge.

---

## QA before push

Open these URLs in `localhost:8765` and eyeball:

| Page | Must show |
|---|---|
| `/` | Hero · headline Pick card · list of other Picks · "Outrights coming soon" empty state |
| `/matches/` | Every upcoming match grouped by date; Pick cards in flame-tint, Pass in paper-pure, Avoid in ink-bar |
| `/m/<any match_id>` | Page header → lead card → blurb prose → drivers list → "Open on Polymarket" CTA → voice block |
| `/outrights/` | Empty state until JSON lands |

Check the headline Pick's `edge_pp` is genuinely the largest on the day — that's the home page's anchor. If it's a thin Pick (sub-3pp shouldn't exist post-PR-4.5 but verify), the headline reads weak.

---

## Failure modes & fixes

**`python -m desk run --once` errors.**
- `ConnectionError` against Polymarket / Kalshi → transient; retry once. If persistent, check Polymarket gamma is up: `curl https://gamma-api.polymarket.com/markets?limit=1`.
- `ImportError` on first run → `cd desk && python -m pip install -e ".[dev]"` then retry.
- Test green check before publishing — `cd desk && pytest -q` should be all green (146 tests). If a test fails, do NOT publish; root-cause first.

**`python site/generate.py` errors.**
- `KeyError` on a match JSON → a per-match file from The Desk is missing a required field (probably `copy.summary` or `verdict.state`). Identify which file with `python -c "import json,glob; [print(f) for f in sorted(glob.glob('desk/data/output/football/*.json')) if json.load(open(f)).get('copy',{}).get('summary') is None]"`. Either re-run The Desk, or delete the offending JSON and re-run the generator (it'll render the remaining files).
- "0 matches" → either The Desk didn't produce JSONs (step 1 failed silently — re-check), or `--include-past` is needed because all kickoffs are historic.

**Empty home page (no Picks).**
This is correct behaviour when model and market agree. Home page renders an "No Picks today — markets are pricing it right" empty state. Don't fake a Pick to fill space.

**Site routes 404 on Railway.**
- Check `git ls-files site/public/` includes the HTML files. `.gitignore` rules might exclude them — verify with `git check-ignore -v site/public/index.html`.
- Check the FastAPI server boots cleanly post-deploy: Railway logs should show `Uvicorn running on http://0.0.0.0:$PORT`.
- The site routes in `server.py` are conditional on `site/public/index.html` existing on disk at boot. If the build dropped the file, routes silently disable and `/` falls through to the React app.

---

## Files this package touches

| File | Purpose |
|---|---|
| `site/generate.py` | The generator. Pure stdlib Python. Read this end-to-end before modifying. |
| `site/public/` | Generated output. Checked into git so Railway serves it without a build step. |
| `server.py` | FastAPI mounts at `/`, `/matches/`, `/m/{id}`, `/outrights/`, `/o/{id}` — search for `SITE_PUBLIC` to see the block. |
| `THE_DESK_OUTRIGHTS_SPEC.md` | v0.2 build spec for outrights engine work — Monte Carlo bracket sim + position-list waist. Engine work, not website work. |
| `CLAUDE_CODE_RUNBOOK.md` | This file. |

---

## When the package becomes obsolete

This is a manual bridge. It retires when **either** of these lands:

1. Faktor's site integration with The Desk is unblocked, and the website rebuilds itself from JSON without this generator.
2. PR 6 (scheduler) ships — The Desk runs continuously and writes JSONs automatically; `site/generate.py` becomes a cron'd post-step.

Until then: run this daily, more often during high-news periods (lineup news, injuries, weather), and once-per-event during the WC group stage.

---

## What you can change without breaking things

- **Headline policy.** `render_home` picks the highest-edge Pick. Swap to "most recent kickoff with a Pick" or "highest-edge in the next 24h" if you want a different anchor.
- **Past-match filter.** `--include-past` flag renders historic fixtures too (useful for a "track record" page later).
- **Voice block copy.** `render_match_page` ends with a fixed "How to read this" aside — edit the string directly.
- **Empty-state copy.** All empty states are inline strings in the renderers — easy to tune.

## What NOT to change

- **CSS.** The `CSS` constant in `site/generate.py` is the locked design system verbatim from `Odds Primer Design System/mockups/home-cards-v5.html`. If the design system updates, re-extract the CSS — do not hand-edit. Hand-editing breaks parity with the canonical mockup.
- **lv-card markup structure.** The card grid layout (6px bar + 1fr content, 5 rows: head / teams / venue-meta / thesis / foot) is part of the design contract. Adding rows or changing column widths breaks the locked aesthetic.
- **The Desk engine.** Per the spec-only rule: agents do not write engine code in `desk/`. The outrights contract above is the right shape for engine work — but the implementation goes via Faktor or a separate engineering session.
