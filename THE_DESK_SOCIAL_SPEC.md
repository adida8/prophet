# The Desk · Social Automation Spec

**Status:** v0.1 draft · 2026-05-28
**Owner (build):** Claude Code agent in `prophet/`
**Owner (approval):** operator (@techdadio)
**Deadline:** Phase 1 live before WC 2026 kickoff (2026-06-12)

**Companion docs**
- `THE_DESK_SOCIAL_RENDERER_SPEC.md` — slide image rendering (separate; not in scope here)
- `desk/VOICE.md` — editorial voice (binding on captions too)
- `Odds Primer Design System/` — token + lockup source of truth

---

## 1. Intent

Take every verdict The Desk publishes and turn the highest-conviction one of the day into an on-brand 4-slide Instagram carousel + an X post, plus a weekly roundup on Sundays. Operator approves each post on a gated page on oddsprimer.com before it goes live. Ship the queue and assets before WC kickoff; auto-posting layers on once Meta verification clears.

## 2. Decisions already locked

| Decision | Value |
|---|---|
| Primary platform | Instagram |
| Secondary | X (cross-post) |
| Deferred | TikTok |
| Format | 4-slide carousel (1080×1350 portrait) |
| Cadence | Daily Pick + Sunday roundup |
| Handle | `@oddsprimer` (both platforms) |
| Approval surface | `/desk/ops/social`, same Basic auth as `/desk/ops` |
| Compliance posture | Educational framing only — no "bet now" / "guaranteed" / "lock" language |
| Publish phase 1 | Manual — operator downloads bundle, posts themselves |
| Publish phase 2 | Auto-post via IG Graph API + X API v2 (when verification clears) |

Slide rendering is **out of scope here**. This spec assumes a `Renderer` contract; the implementation lives in `THE_DESK_SOCIAL_RENDERER_SPEC.md`.

## 3. Pipeline

```
TRIGGER          GENERATE                REVIEW              PUBLISH
─────────────────────────────────────────────────────────────────────────
Desk daily ─┐
            ├─→ Selector ──┐
Sun cron ───┘             │
                          ├─→ Renderer ─→ social_drafts ─→ /desk/ops/social
            ┌─→ Roundup ──┘    (4 PNGs)     (sqlite)         │
            │   builder        Captioner                     │
                              (IG + X)                       ▼
                                                      ┌─ Phase 1 ─┐
                                                      │ download  │
                                                      │ bundle    │
                                                      └─────┬─────┘
                                                            │
                                                      ┌─ Phase 2 ─┐
                                                      │ IG Graph  │
                                                      │ X API v2  │
                                                      └─────┬─────┘
                                                            ▼
                                                       Posted +
                                                       audit row
```

Lives under `desk/desk/social/`. Sport-agnostic (consumes the `MatchOutput` contract — no football imports).

## 4. PR ladder

| PR | Title | Lands |
|---|---|---|
| **S1** | Data model + queue + renderer stub | sqlite `social_drafts` table, `Renderer` protocol, stub returns 4 solid-colour PNGs at 1080×1350 |
| **S2** | Selector (daily + weekly) | `select_daily_pick()` + `build_weekly_roundup()`; pure functions, full unit coverage |
| **S3** | Caption generator + voice-check | IG + X caption templates, citation lockstep, `desk.explainer.voice` enforcement |
| **S4** | `/desk/ops/social` approval page | List + detail UI, caption editor, Approve / Reject / Skip; mounted under existing Basic-auth gate |
| **S5** | Phase 1 publish | Bundle download (`bundle.zip`: 4 PNGs + `caption-ig.txt` + `caption-x.txt`) + "Mark as posted" |
| **S6** | Scheduler integration | Hook into `desk_refresh_loop.py` (daily) + new `social_weekly_cron.py` (Sunday 09:00 UTC) |
| **S7** | Phase 2 — IG Graph API | Auto-post on Approve once `IG_ACCESS_TOKEN` + `IG_BUSINESS_ACCOUNT_ID` set |
| **S8** | Phase 2 — X API v2 | Auto-post on Approve once X Basic subscription active |

S1–S6 is the **Phase 1 ship**. S7 + S8 layer in when the platforms cooperate. No UX change to the approval page between phases.

## 5. Data model

One sqlite table — `social_drafts`. Lives at `DESK_SOCIAL_DB_PATH` (Railway: mounted volume).

```sql
CREATE TABLE social_drafts (
    draft_id          TEXT PRIMARY KEY,                  -- "soc-{kind}-{yyyymmdd}-{slug}"
    kind              TEXT NOT NULL,                     -- 'daily' | 'weekly_roundup'
    match_id          TEXT,                              -- nullable; set when kind='daily'
    week_starting     DATE,                              -- nullable; set when kind='weekly_roundup'

    source_json       TEXT NOT NULL,                     -- frozen MatchOutput (daily) or roundup payload (weekly)

    slides_json       TEXT NOT NULL,                     -- [{slide_no, png_path, png_sha256}] × 4
    caption_ig        TEXT NOT NULL,
    caption_x         TEXT NOT NULL,

    status            TEXT NOT NULL,                     -- 'pending' | 'approved' | 'rejected' | 'skipped' | 'published' | 'publish_failed'
    created_at        TIMESTAMP NOT NULL,
    decided_at        TIMESTAMP,
    decided_by        TEXT,                              -- ops user from Basic auth
    edit_history_json TEXT,                              -- [{at, by, field, before, after}]

    ig_permalink      TEXT,
    x_tweet_id        TEXT,
    published_at      TIMESTAMP,
    publish_error     TEXT
);

CREATE UNIQUE INDEX uq_daily   ON social_drafts(match_id)      WHERE kind = 'daily';
CREATE UNIQUE INDEX uq_weekly  ON social_drafts(week_starting) WHERE kind = 'weekly_roundup';
CREATE INDEX        ix_status  ON social_drafts(status, created_at DESC);
```

State machine: `pending → {approved, rejected, skipped}` → `approved → {published, publish_failed}`. Terminal: `published`, `rejected`, `skipped`, `publish_failed`. Idempotency: the two partial-unique indexes prevent double-drafts for the same match on the same day or the same week twice.

PNG bytes live on disk at `DESK_SOCIAL_ASSETS_DIR/{draft_id}/slide-{n}.png` — SHA-256 stored in `slides_json` for integrity check on publish.

## 6. Selector

`desk/desk/social/selector.py`

### Daily

Inputs: today's `MatchOutput[]` from `desk/data/output/football/`.

Rules, in order:

1. Filter to `verdict.state == "pick"`.
2. Filter to `verdict.lower_edge_pp >= DESK_SOCIAL_MIN_EDGE_PP` (default `2.0`).
3. Filter out matches with kickoff in the past.
4. Filter out matches that already have a `social_drafts` row with `kind='daily'`.
5. Sort by `verdict.lower_edge_pp` desc.
6. Return the top one. If empty → return `None`. Do not draft for the sake of drafting.

### Weekly roundup

Inputs: every `MatchOutput` published in the last 7 days (UTC, Mon 00:00 → Sun 23:59 of the trailing week).

Payload built into `source_json`:

- `top_picks`: top 5 by `lower_edge_pp` from the week
- `hit_rate`: of last week's published Picks that have now resolved (`verdict.state == "pick"` AND `result.resolved_at IS NOT NULL`), share that resolved in our favour
- `what_we_got_wrong`: the highest-conviction Pick that resolved against us (if any)

All three are computable from existing JSON. No new data sources.

## 7. Caption generator

`desk/desk/social/caption.py` — pure function: `MatchOutput → (caption_ig: str, caption_x: str)`.

### IG (max 2200 chars; first 125 visible on feed)

```
{copy.title}

{copy.summary}

{copy.blurb}

— The Desk
oddsprimer.com/m/{match_id}

#oddsprimer #worldcup2026 #wc2026 #{team_a_hashtag} #{team_b_hashtag} #predictionmarkets
```

### X (max 280 chars)

```
{copy.title}

We rate {pick_side} at {model_p}%. Market prices it at {market_p}%. +{edge_pp}pp.

oddsprimer.com/m/{match_id}
```

If `copy.title + body + URL` exceeds 280, drop the third line (model/market) and keep the title + URL.

### Safety gates (all enforced in unit tests)

1. **Voice check.** Both captions pass through `desk.explainer.voice.check()`. Any violation → fall back to a minimal caption: `"{team_a} vs {team_b} — oddsprimer.com/m/{match_id}"`. Log the violation.
2. **Citation lockstep.** If the caption mentions an outlet by name, that outlet **must** appear in `copy.editorial_citations[]`. Asserted by test.
3. **Banned phrases.** Extend `voice.py`'s banned list with: `bet now`, `guaranteed`, `lock`, `easy money`, `sure thing`, `can't lose`, `free pick`, `tip`.
4. **No emoji.** Existing voice rule, applied here too.
5. **No exclamation marks.** Same.

## 8. Approval surface

### Page: `GET /desk/ops/social`

Already-gated under `/desk/ops/*` via existing Basic auth (`DESK_OPS_USER` / `DESK_OPS_PASS`). Frontend is a small island matching the rest of the ops dashboard (vanilla JS or the existing React shell — match whatever PR 6 used).

**List view (top to bottom):**
- Pending drafts (most recent first) — each row: thumbnail of slide 1, kind, match label, edge, created, status badge, primary action button
- Approved-but-not-posted (Phase 1 only) — same row layout, primary button = "Download bundle"
- Last 14 days of history — read-only

**Detail panel (click a row):**
- 4 slide thumbnails (click → full size)
- "Why this draft" — small block citing the selector reason (`"Highest lower_edge_pp today: +X.Xpp"`)
- Caption editor: IG textarea + X textarea, character counters, live-validation against voice rules
- Buttons: `Approve` · `Reject` · `Skip`
- Editing a caption writes to `edit_history_json` with timestamp + ops user

### Routes (all gated, all audit-logged)

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET`  | `/desk/ops/social` | — | HTML list page |
| `GET`  | `/desk/ops/social/{draft_id}` | — | HTML detail page |
| `GET`  | `/api/social/drafts` | `?status=&kind=&limit=` | JSON list |
| `GET`  | `/api/social/drafts/{draft_id}` | — | JSON detail |
| `POST` | `/api/social/drafts/{draft_id}/edit-caption` | `{platform: "ig"\|"x", text}` | 200 + new draft |
| `POST` | `/api/social/drafts/{draft_id}/approve` | — | 200 + new draft |
| `POST` | `/api/social/drafts/{draft_id}/reject` | `{reason?}` | 200 |
| `POST` | `/api/social/drafts/{draft_id}/skip` | — | 200 |
| `GET`  | `/api/social/drafts/{draft_id}/bundle.zip` | — | zip: `slide-1..4.png` + `caption-ig.txt` + `caption-x.txt` + `meta.json` |
| `POST` | `/api/social/drafts/{draft_id}/mark-posted` | `{ig_permalink?, x_tweet_id?}` | 200 (Phase 1 only) |
| `POST` | `/api/social/drafts/{draft_id}/publish` | — | 202 (Phase 2 only) |

State-transition errors return `409` with a typed reason: `{error: "invalid_state", from: "rejected", to: "approve"}`.

## 9. Publish

### Phase 1 (S5) — manual

`Approve` flips state to `approved`. The UI shows a **Download bundle** button + **Mark as posted** with two optional fields (IG permalink, X tweet id). The operator posts manually from their phone or laptop, comes back, pastes the links, hits Mark as posted → state goes to `published`. No platform API calls.

### Phase 2 (S7 + S8) — auto

`Approve` enqueues a publish job. Worker hits IG Graph API:

1. `POST /{ig_user_id}/media` × 4 — one per slide (image_url pointing at a presigned URL we serve from `DESK_SOCIAL_ASSETS_DIR`), `is_carousel_item=true`
2. `POST /{ig_user_id}/media` with `media_type=CAROUSEL`, `children=[...4 container ids]`, `caption={caption_ig}`
3. `POST /{ig_user_id}/media_publish` with `creation_id`
4. Store `ig_permalink`, set state to `published`

X path:

1. `POST /2/media/upload` × 4
2. `POST /2/tweets` with `text={caption_x}` and `media.media_ids=[...4]`
3. Store `x_tweet_id`

Either platform fails → state `publish_failed`, error stored in `publish_error`, draft re-appears in the queue for retry/edit.

## 10. Scheduler hooks

### Daily — hook into existing `desk_refresh_loop.py`

After every tick that produces fresh `MatchOutput` JSON, call `desk social draft-daily` (subprocess, matching the existing pattern for `desk fetch-signals` etc.). Gated on `DESK_SOCIAL_ENABLED=1`. Runs after matches + outrights + site/generate so it sees today's published verdicts.

### Weekly — new `social_weekly_cron.py`

Project-root async loop, sibling to `desk_refresh_loop.py` + `activity_refresh_loop.py`. Sleeps until next Sunday 09:00 UTC (configurable via `DESK_SOCIAL_WEEKLY_DAY` + `DESK_SOCIAL_WEEKLY_AT`), calls `desk social draft-weekly`, sleeps a week.

Both subprocesses honour `DESK_AUTORUN` for the global kill switch.

## 11. Env vars

| Variable | Default | Purpose |
|---|---|---|
| `DESK_SOCIAL_ENABLED` | `0` | Master switch. `1` to enable selector + scheduler hooks. Approval surface is mounted regardless (404s on empty queue) so it's safe to inspect. |
| `DESK_SOCIAL_DB_PATH` | unset → `desk/data/social.db` | Override on Railway to a mounted volume so the queue survives deploys. |
| `DESK_SOCIAL_ASSETS_DIR` | unset → `desk/data/social_assets` | Same — mount on Railway so PNGs aren't lost on redeploy. |
| `DESK_SOCIAL_MIN_EDGE_PP` | `2.0` | Selector skip threshold. |
| `DESK_SOCIAL_WEEKLY_DAY` | `sunday` | Day of week for the roundup. |
| `DESK_SOCIAL_WEEKLY_AT` | `09:00` | UTC time-of-day for the roundup. |
| `DESK_SOCIAL_PUBLISH_MODE` | `manual` | `manual` (Phase 1) or `api` (Phase 2). |
| `IG_ACCESS_TOKEN` | unset | Phase 2 only. Long-lived Meta Graph access token. |
| `IG_BUSINESS_ACCOUNT_ID` | unset | Phase 2 only. The `@oddsprimer` IG Business account id. |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | unset | Phase 2 only. X API v2 OAuth 1.0a. |

All Phase 2 vars must be present together or `publish` fails fast at boot — never half-configured.

## 12. Tests

| Layer | What |
|---|---|
| Selector unit | empty day, single Pick, multiple Picks, all below threshold, kickoff-in-past filter, idempotency (already-drafted match), weekly window boundaries |
| Caption unit | template substitution, IG length cap, X length cap (with + without model/market line), hashtag formatting, citation lockstep enforcement, banned-phrase rejection + fallback path, no-emoji, no-exclamation |
| Voice check | every caption sample passes `desk.explainer.voice.check()`; a deliberately-violating sample triggers fallback |
| Queue | full state machine: every legal transition + every illegal one returns `409 invalid_state` |
| Router | unauthenticated → 401, wrong creds → 401, valid creds → 200, unknown draft → 404 |
| Integration | frozen `MatchOutput` fixture → selector → renderer (stub) → caption → queue → approval → bundle.zip round-trip |
| Snapshot | Phase 1: `bundle.zip` contains exactly `slide-1.png` … `slide-4.png` + `caption-ig.txt` + `caption-x.txt` + `meta.json` |

CI must pass before any PR merges to `staging`. Same convention as the rest of the repo.

## 13. Rollout

| Date | Milestone |
|---|---|
| 2026-05-28 | Spec locked (this doc) |
| 2026-05-28 → 2026-06-01 | S1 + S2 + S3 land on `staging` |
| 2026-06-01 → 2026-06-05 | S4 + S5 land on `staging`; operator click-tests end-to-end |
| 2026-06-05 → 2026-06-08 | S6 wires schedulers; first dry-run drafts in production-shape |
| 2026-06-09 → 2026-06-11 | Operator runs through one full daily approval per day; iterate captions |
| **2026-06-12** | **WC kickoff. Phase 1 live. First public post.** |
| Post-launch | S7 + S8 layer in once Meta verification + X Basic clear |

## 14. Operator-side prep (parallel to build)

These cannot be done by the agent — operator must run them in parallel:

1. Register `@oddsprimer` on Instagram (Business account) and X.
2. Create the Odds Primer Facebook Page; connect IG to it.
3. Submit Meta Business verification (`business.facebook.com` → Settings → Business Info).
4. Decide X tier: Basic ($200/mo) for auto-post, or stay manual on X indefinitely.
5. Set `DESK_OPS_USER` / `DESK_OPS_PASS` on Railway if not already (re-used here).
6. Provision mounted volume paths for `DESK_SOCIAL_DB_PATH` + `DESK_SOCIAL_ASSETS_DIR` on Railway.

## 15. Open questions

1. **Caption character count for hashtags** — keep them in IG caption body or move to first comment (IG-standard for engagement)? Defaulting to body for v0.1; revisit after first week.
2. **Rejected drafts — auto-retry next day?** Defaulting to no (operator skip = "not this one, ever"). Revisit if useful.
3. **Pass / Avoid verdicts** — daily skips them entirely; weekly roundup includes a single "we passed on these" block? v0.1 says no, weekly is Picks-only.
4. **Time zone for "today"** — defaulting to UTC across the board to match the Desk loop. Operator can shift via env var if needed.

---

*Renderer contract (placeholder in S1, replaced when the renderer spec lands):*

```python
# desk/desk/social/renderer.py
from typing import Protocol
from pathlib import Path

class SlideAsset(NamedTuple):
    slide_no: int          # 1..4
    png_path: Path
    png_sha256: str

class Renderer(Protocol):
    async def render_carousel(
        self,
        payload: SocialPayload,    # DailyMatchPayload | WeeklyRoundupPayload
        *,
        output_dir: Path,
    ) -> list[SlideAsset]: ...

class RendererError(Exception): ...
```

S1 ships `StubRenderer` (4 solid-colour PNGs at 1080×1350 with slide number burned in). Replaced byte-for-byte by the real renderer when `THE_DESK_SOCIAL_RENDERER_SPEC.md` lands.
