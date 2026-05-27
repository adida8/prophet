# Activity signals — implementation spec v1.0

**Date:** 2026-05-27 · **Status:** locked for Claude Code handoff. All decisions made.

> **v1.0.1 (2026-05-27)** — clarifications after first review:
> 1. Activity package lives at top-level `activity/`, not under `desk/` (it's a site-wide concern, not a verdict-engine concern; mirrors `ledger/`).
> 2. Engine jobs run in a new project-root `activity_refresh_loop.py`, sibling to `desk_refresh_loop.py` / `desk_distribute_loop.py`. Cadences are unrelated to the Desk's hourly tick.
> 3. Frontend ships as a vanilla-JS island injected into the static match page by `site/generate.py` — the consumer surface at `/m/{id}` is static HTML (`render_match_page`), not the React app under `frontend/src/op/`.
> 4. Vote-lock rule stays lazy. No daily lock-sweep job; `locked_at` is only set when a returning voter touches the row past 24h. The 409 on further updates is the real enforcement.

## Goal

Add on-brand community signals to every match card — view count, reader sentiment, four-way reaction, one-click voting. Cards feel alive from day one via a modest, popularity-weighted seed engine; real reader engagement layers on top and dominates within weeks.

Brand voice is anti-hype. **No emoji. No "Bullish / Trap line / Lock". No fake comments, no fabricated user names, no inflated viral numbers.**

## Non-goals

User accounts, comments, fabricated personas, real-time websockets at v1, "N users viewing now" toasts, club-football tier table (national teams only — WC26 wedge).

## Surface

**Readers strip** (rendered below the existing stats row on every match page):

- `Read today` — anonymized count of unique reads in the last 24h.
- `Aligned with the Pick` — % of voters whose reaction is *Sharp call* or *Fair call*. **Shown on Pick verdicts only**; hidden on Pass/Avoid.
- Horizontal sentiment bar (0–100%) with midpoint marker. **Pick-only.**

**Reactions row** — four chip buttons.
- Pick verdicts: *Sharp call · Fair call · Off the mark · Wait and see*.
- Pass/Avoid: *Agree · Lean disagree · Disagree · Wait and see*.
- One click = one vote. Vote is changeable within 24h, then locked.
- Voter's chosen chip is marked "on" via cookie.

## Display rules

- Views rendered once total reads ≥ 10.
- Sentiment bar + chip counts rendered once votes_total ≥ 5.
- Aggregate refresh **60s server-side**; frontend polls **every 90s**.
- "Just now / 2 min ago" timestamp on the readers strip.

## Data model (Supabase / Postgres)

```sql
CREATE TABLE match_views (
  id bigserial PRIMARY KEY,
  match_id text NOT NULL,
  anon_id text NOT NULL,
  ip_hash text NOT NULL,
  seeded boolean NOT NULL DEFAULT false,
  viewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_match_views_match_time ON match_views (match_id, viewed_at);

CREATE TABLE match_reactions (
  match_id text NOT NULL,
  anon_id text NOT NULL,
  reaction text NOT NULL CHECK (reaction IN ('sharp_call','fair_call','off_mark','wait_see')),
  seeded boolean NOT NULL DEFAULT false,
  voted_at timestamptz NOT NULL DEFAULT now(),
  locked_at timestamptz,
  PRIMARY KEY (match_id, anon_id)
);

CREATE TABLE match_aggregates (
  match_id text PRIMARY KEY,
  views_24h int NOT NULL DEFAULT 0,
  votes_total int NOT NULL DEFAULT 0,
  sharp_call int NOT NULL DEFAULT 0,
  fair_call int NOT NULL DEFAULT 0,
  off_mark int NOT NULL DEFAULT 0,
  wait_see int NOT NULL DEFAULT 0,
  aligned_pct int,
  seeded_share numeric(4,3),
  seed_disabled boolean NOT NULL DEFAULT false,
  refreshed_at timestamptz NOT NULL
);
```

## API — FastAPI under `/api/activity/`

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/view` | `{match_id}` | 204 |
| POST | `/vote` | `{match_id, reaction}` | `{your_vote, locked_at}` |
| GET  | `/:match_id` | — | `{views_24h, votes_total, by_reaction, aligned_pct, your_vote, refreshed_at}` |

**Edge cache:** GET responses cached 30s. **Rate limits** (enforced server-side, 429 on breach): 1 vote change per anon_id per 30s; 10 votes/min per ip_hash; 500 votes/day per anon_id.

**Lock rule (decision 2):** on each vote, if `voted_at` is more than 24h before now and `locked_at` is null, set `locked_at = now()`. Further updates return 409.

## Engine — three jobs in `activity_refresh_loop.py`

New project-root async loop, sibling to `desk_refresh_loop.py` / `desk_distribute_loop.py`. Job bodies live in `activity/jobs.py`; the loop just schedules them.

| Job | Cadence | Purpose |
|---|---|---|
| `aggregate_match_activity` | 60s | UPSERT `match_aggregates` for matches with new rows since `refreshed_at`. O(changed). |
| `seed_match_activity` | 8 min | Insert popularity-weighted seed rows for matches where `seed_disabled = false`. |
| `prune_old_views` | daily | DELETE from `match_views` where `viewed_at < now() - interval '7 days'`. Aggregate counts preserved. |

Activity is fetched at runtime via the API — **never** baked into the per-match published JSON. The ETag/content-hash invariant of `desk/publish/writer.py` stays intact.

## Seed engine — conservative ranges (locked)

**Baseline target ranges (Tier 3, 1× multiplier). Per match, per 24h:**

| Stage | View target/day | Vote target (lifetime) |
|---|---|---|
| Kickoff > 14d away | 12–30 | 2–5 |
| Kickoff 14d → 5d | 25–60 | 4–10 |
| Kickoff 5d → 1d | 50–130 | 8–20 |
| Match day | 100–260 | 15–40 |

**Reaction distribution by verdict (mean ±15% noise per match):**

| State | Sharp call | Fair call | Off the mark | Wait and see |
|---|---|---|---|---|
| Pick | 45% | 30% | 12% | 13% |
| Pass | 20% | 25% | 18% | 37% |
| Avoid | 10% | 15% | 50% | 25% |

Tier 1–2 matches lean slightly sharper on dissent (+10% to *Off the mark*); Tier 4 matches lean more *Wait and see* (+10%).

**Time-of-day weighting (Madrid local):** peak 19:00–23:00, active 09:00–01:00, quiet 02:00–07:00. Insertion times jittered with normal noise — never uniform, never overnight bursts.

**Auto-decay:** set `seed_disabled = true` for a match once **real** views_24h ≥ 60 **and** real votes_total ≥ 25. Use `seeded = false` rows for the threshold check.

**Audit:** every seeded row carries `seeded = true`. Fully queryable. `seeded_share` in the aggregate is private (never displayed). Target ≤ 25% mix by week 8 across the catalog.

**Hard caps (v1):** no match exceeds **450 views/day** or **70 votes lifetime** in seeded counts. Editorial frame.

## Popularity weighting — `desk/sports/football/data/team_popularity.py`

```python
POPULARITY_TIER = {
    # Tier 1 — Global icons (4×)
    "Argentina": 1, "Brazil": 1, "France": 1, "Germany": 1, "Spain": 1,
    "Italy": 1, "England": 1, "Netherlands": 1, "Portugal": 1,
    # Tier 2 — Major draws (2×)
    "USA": 2, "Mexico": 2, "Croatia": 2, "Belgium": 2, "Uruguay": 2,
    "Japan": 2, "Korea Republic": 2, "Senegal": 2, "Morocco": 2,
    "Côte d'Ivoire": 2, "Colombia": 2, "Chile": 2, "Switzerland": 2,
    "Poland": 2, "Denmark": 2, "Austria": 2, "Sweden": 2,
    # Tier 4 — Niche (0.4×)
    "Saudi Arabia": 4, "Iran": 4, "Curaçao": 4, "Haiti": 4, "Cape Verde": 4,
    "Jordan": 4, "New Zealand": 4, "Iraq": 4, "Qatar": 4, "Panama": 4,
    "Honduras": 4, "El Salvador": 4, "Trinidad and Tobago": 4,
    "Bolivia": 4, "Venezuela": 4,
    # Default for any unmapped team = Tier 3 (1×)
}
TIER_MULTIPLIER = {1: 4.0, 2: 2.0, 3: 1.0, 4: 0.4}
WC26_HOSTS = {"USA", "Canada", "Mexico"}
BLOCKBUSTER_TIERS = {1, 2}

def tier_for_team(name: str) -> int:
    return POPULARITY_TIER.get(name, 3)

def match_popularity_multiplier(team_a: str, team_b: str) -> float:
    mult = max(TIER_MULTIPLIER[tier_for_team(team_a)],
               TIER_MULTIPLIER[tier_for_team(team_b)])
    if tier_for_team(team_a) in BLOCKBUSTER_TIERS and tier_for_team(team_b) in BLOCKBUSTER_TIERS:
        mult *= 1.25
    if team_a in WC26_HOSTS or team_b in WC26_HOSTS:
        mult *= 1.5
    return mult
```

Name lookups use `desk.sports.football.teams.iso3_for_name` for normalization (handles Côte d'Ivoire / Ivory Coast, Korea Republic / South Korea, etc.). The lookup must round-trip via the existing teams module — do not duplicate name normalization.

**Worked checks for the implementer:**
- Argentina v Austria → max(T1, T2) × 1.25 blockbuster = 5×. Pre-kickoff: 60–150 views/day. Match day: capped at 450.
- Haiti v Iran → max(T4, T4) = 0.4×. Pre-kickoff: 5–12 views/day.
- Curaçao v Côte d'Ivoire → max(T4, T2) = 2×. Pre-kickoff: 50–120 views/day.
- USA v Argentina → max(T2, T1) × 1.25 blockbuster × 1.5 host = 7.5×. Hits the cap on match day.

## Identity & privacy

- First load sets `op_anon` cookie (1y, UUIDv4, SameSite=Lax, HttpOnly=false).
- Client IP hashed with daily-rotated salt — same-day rate-limiting, unlinkable across days.
- No fingerprinting, no third-party tracking.
- Disclosed in existing `/privacy` page (one-line addition).

## Anti-abuse (v1)

One vote per anon_id per match. Per-IP and per-anon rate limits as above. Public proxy/VPN range block list (cheap, not bulletproof). No CAPTCHA; revisit if spam patterns emerge in week 3+.

## Trust guardrails

**Public `/methodology` disclosure (must ship with the engine):** *"During launch, view and reaction counts include a modest seed reflecting expected interest, decaying as real readers join. Comments and citations are never seeded."*

**Never:** seeded comments, fabricated names/handles, "N viewing now" toasts, vote totals exceeding the editorial frame, seeding that doesn't decay.

## Rollout

| Week | Stage |
|---|---|
| 1 | Schema migrations + API + `team_popularity.py` on staging. Seed engine in dry-run (logs only — no DB writes). |
| 2 | Seed engine live on staging. Frontend chips and readers strip wired. Internal review. |
| 3 | Public on staging URL. Monitor `seeded_share` and abuse patterns. |
| 4+ | Merge to `init/project-setup` (prod). Continue monitoring; tune ranges if curves drift. |

## Implementation breakdown for Claude Code

Suggested PR sequence — each PR ships tests + a brief README note.

1. **Schema migration** (Supabase). Three tables + indexes + seed bootstrap rows for every currently-priced fixture (zero counts). File: `migrations/2026XXXX_activity_signals.sql`.
2. **`team_popularity.py`** + helper functions. Unit tests in `desk/tests/sports/football/test_team_popularity.py` covering: tier lookup, default fallback, blockbuster bonus, host bonus, max-of-two rule. Round-trip names through `iso3_for_name`.
3. **API router** at `activity/router.py` (FastAPI), top-level package alongside `ledger/`. Mounted by `server.py` under `/api/activity/`. Three endpoints, rate limiting (use existing `slowapi` if present, else add). Cookie middleware for `op_anon`. Daily-salt IP hash helper. Tests in `tests/activity/test_api.py`.
4. **`aggregate_match_activity` job**. Job body in `activity/jobs.py`, scheduled by new `activity_refresh_loop.py` at the project root. Single SQL view + UPSERT. Cadence 60s. Test against frozen fixture data.
5. **`seed_match_activity` job**. Same loop. Cadence 8 min. Reads upcoming fixtures from the existing priced-fixtures iterator. Applies popularity + time-of-day + verdict-state distributions. Marks rows `seeded=true`. Auto-decay check before inserting. Conservative ranges per spec.
6. **`prune_old_views` job**. Same loop. Cadence daily. Single DELETE.
7. **Frontend — readers strip + reaction chips, vanilla-JS island.** The consumer match page is static HTML rendered by `site/generate.py` (`render_match_page`), not the React app — so this ships as a vanilla-JS file at `site/public/js/activity.js` referenced from a `<div id="activity-root">` placeholder that `render_match_page` writes under the existing stats row. Script fires `POST /view` once on load, polls `/api/activity/{match_id}` every 90s, wires the four reaction chips to `POST /vote`. Renders only when thresholds crossed. Pick-only sentiment bar. Cookie-aware "on" state on the voter's own chip via the `op_anon` cookie. No emoji, anti-hype copy. The static HTML stays CDN-cacheable; all dynamic counts come from the API.
8. **`/methodology` disclosure**. One-paragraph addition with the disclosure line above.

Each PR onto `staging` branch per repo convention. Acceptance for each PR: green tests + a manual smoke check + README update under `desk/README.md` or `docs/`.

## Acceptance for the full feature

- All three tables populated for every priced WC26 fixture.
- `seed_match_activity` running every 8 min, marking `seeded=true` on every insert.
- `seeded_share` for sample matches shows expected ratios (Haiti-Iran low absolute counts; Argentina-Austria higher with blockbuster bonus active).
- API endpoints return correct counts; rate limits enforced.
- Frontend renders readers strip + chips on match pages, polls every 90s, hides UI below thresholds.
- `/methodology` disclosure live.
- Tests green across all PRs.
- One end-to-end manual: open a staging match page, see live counts; click a chip → count updates within the next poll cycle.
