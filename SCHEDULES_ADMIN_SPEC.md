# Schedules admin — unified loop control

**Status:** spec v0.1 — 2026-05-31
**Author:** Adi
**Problem:** background loops are scattered across env vars + one hardcoded value. No single place to see what runs when, what it costs, or to pause it. Yesterday's $20 Anthropic burn happened because `DESK_LINEUP_LOOP_PUBLISH=1` (the default) silently re-fired Haiku across 72 matches × 2 envs on every successful lineup fetch — invisible from the admin.

## Goal

One page at `/desk/ops/schedules` that lists every background loop in the app, shows when it runs and what it costs, and lets the operator toggle or reschedule it without a redeploy. Same Basic-auth gate as the rest of `/desk/ops`.

## Inventory (what exists today)

| Loop | File | Current cadence | Cost driver | Current control |
|---|---|---|---|---|
| Desk refresh | `desk_refresh_loop.py` | Cron-style (hours in `control.json`) | **High** — Haiku blurb × ~72 matches, signals extract | `/desk/ops/admin` (master toggle + UTC hours) |
| Lineups refresh | `desk_lineups_refresh_loop.py` | Every 15 min | **High** if `DESK_LINEUP_LOOP_PUBLISH=1` (re-fires Haiku across all matches on any successful lineup fetch) | Env vars only |
| Distribute drain | `desk_distribute_loop.py` | Every 30 sec | $0 (HTTP only) | Env vars only |
| Activity aggregate | `activity_refresh_loop.py` | Every 60 sec | $0 (Postgres) | Env vars only |
| Activity seed | `activity_refresh_loop.py` | Every 8 min | $0 (Postgres) | Env vars only |
| Activity prune | `activity_refresh_loop.py` | Daily | $0 (Postgres) | Env vars only |
| Daily report | `daily_report_loop.py` | Hourly tick, fires at `DAILY_REPORT_HOUR` UTC | $0 (Postgres + SMTP) | Env vars only |
| Site QA | `site_qa_loop.py` | Hourly tick, fires at `SITE_QA_HOUR` UTC | $0 (HTTP + SMTP) | Env vars only |
| Ledger refresh | `ledger/refresh_loop.py` | **Every 15 min — hardcoded** | $0 (Polymarket HTTP) | None |
| Social weekly | `social_weekly_cron.py` | Weekly at `DESK_SOCIAL_WEEKLY_DAY`/`AT` | $0 in Phase 1 (renderer is stub) | Env vars only |

**Two findings to act on before any code:**
1. `ledger/refresh_loop.py` is hardcoded. Make it env-configurable as a prerequisite — the schedules admin can't control what isn't controllable.
2. Rename `DESK_LINEUP_LOOP_PUBLISH` default `1` → `0`. The default should be "fetch only"; auto-republish is the expensive opt-in, not the safe baseline. Yesterday's burn is the proof.

## What the page shows

A single table, one row per loop. Updates every 30s via `GET /api/desk/ops/schedules`.

| Column | Source |
|---|---|
| Loop name | Static (e.g. "Desk refresh", "Lineups refresh") |
| What it does | Static one-liner |
| Status | Live: `running` / `paused` / `disabled` |
| Schedule | Live (e.g. "06:00 UTC daily" / "every 15 min" / "Sun 09:00 UTC") |
| Last tick | Live: timestamp + `ok` / `error` / `skipped` |
| Next tick | Computed from schedule |
| Cost (24h) | Sum of `costs.jsonl` rows tagged with this `loop_id`, last 24h |
| Cost (7d) | Same, last 7d |
| Controls | Pause/resume button, "Edit schedule" link |

Above the table: total Haiku spend over the last 24h / 7d, broken out by env (staging vs prod). Pulls from `costs.jsonl` aggregated.

## Schedule shapes (three are enough)

Don't try to be cron. Three shapes cover everything in the inventory:

1. **`cron_hourly`** — fires at the top of N UTC hours per day. Config: `{ hours: [int] }`. Used by: Desk refresh, Daily report, Site QA.
2. **`interval`** — fires every N seconds. Config: `{ tick_sec: int }`. Used by: Lineups, Distribute, Activity aggregate/seed/prune, Ledger.
3. **`cron_weekly`** — fires once a week at `{ weekday: str, hh_mm: str }`. Used by: Social weekly.

Each loop registers itself with its shape; the admin only shows the controls that shape supports.

## Data model

Replace today's `{ops_root}/control.json` (which only carries the desk loop's state) with `{ops_root}/schedules.json`:

```json
{
  "version": 1,
  "loops": {
    "desk_refresh": {
      "shape": "cron_hourly",
      "enabled": true,
      "schedule": { "hours": [6] }
    },
    "lineups_refresh": {
      "shape": "interval",
      "enabled": false,
      "schedule": { "tick_sec": 900 }
    },
    "ledger_refresh": {
      "shape": "interval",
      "enabled": true,
      "schedule": { "tick_sec": 1800 }
    }
    // ... one entry per loop
  }
}
```

A `loop_runs.jsonl` event log (one row per tick) feeds the "last tick" / "status" columns. Each row: `{ loop_id, started_at, finished_at, status, error?, run_id? }`. Keep last N=500 rows; rotate the file by line count, not by date.

Backwards compat: on first read, if `schedules.json` is absent but `control.json` exists, migrate the desk-refresh row in-place and write the new file. One-shot, never again.

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/desk/ops/schedules` | All loops + status + last tick + 24h/7d cost |
| `POST` | `/api/desk/ops/schedules/{loop_id}/pause` | Sets `enabled=false`. Loop honours on next poll. |
| `POST` | `/api/desk/ops/schedules/{loop_id}/resume` | Sets `enabled=true`. |
| `PUT` | `/api/desk/ops/schedules/{loop_id}/schedule` | Body validated against the loop's `shape`; rejects mismatches. |

All four sit under the same `DESK_OPS_USER` / `DESK_OPS_PASS` Basic-auth gate as the rest of `/api/desk/ops/*`.

## Loop-side change (one helper, shared)

Every loop polls `schedules.json` instead of reading its env vars directly. One helper:

```python
# desk/desk/ops/schedules.py
def loop_should_run(loop_id: str, *, now_utc: datetime) -> tuple[bool, str]:
    """Return (should_fire_this_tick, reason). reason is logged for the admin."""
```

The helper handles all three shapes, plus the master `DESK_AUTORUN=0` kill-switch (kept as a deploy-time emergency brake — outside the admin). Each loop body becomes:

```python
while True:
    fire, reason = loop_should_run(LOOP_ID, now_utc=datetime.utcnow())
    if fire:
        await record_tick(LOOP_ID, _do_work)
    else:
        log.debug("skip: %s", reason)
    await asyncio.sleep(POLL_SEC)  # short fixed poll, e.g. 30s
```

`record_tick` wraps the work in a `try/except` + appends to `loop_runs.jsonl`.

## Cost attribution

Every Haiku call already appends to `{ops_root}/costs.jsonl` tagged with the current `DESK_TICK_ID`. Add one more tag: `loop_id`. The runner sets both env vars before spawning each subprocess. The schedules API joins `costs.jsonl` on `loop_id` for the 24h / 7d sums.

Non-Haiku loops report $0 — the page shows "—" in the cost column so it's obvious there's no spend, not just no data.

## Phases

**Phase 1 — read-only inventory + ledger fix** (small, no behaviour change for desk refresh)
- Make `ledger/refresh_loop.py` env-configurable; default `1800` (30 min, halving today's load).
- Flip `DESK_LINEUP_LOOP_PUBLISH` default to `0`.
- Write `desk/desk/ops/schedules.py` registry + helper.
- Migrate `control.json` → `schedules.json` on first boot.
- `GET /api/desk/ops/schedules` reads-only.
- New page at `/desk/ops/schedules` (table view, no controls yet). The existing `/desk/ops/admin` keeps working unchanged.

**Phase 2 — write controls**
- Pause / resume / edit-schedule buttons in the table.
- `PUT`/`POST` endpoints wired.
- Every loop reads `schedules.json` instead of its env vars. Env vars become legacy fallbacks (read only when the loop is missing from `schedules.json`).
- Retire `/desk/ops/admin` once parity is confirmed.

**Phase 3 — cost rollup**
- Tag `costs.jsonl` rows with `loop_id`.
- 24h / 7d sums in the table header + per-row.
- Add a "spend cap" per loop (optional): if 24h cost > cap, auto-pause + log a warning. Useful guardrail against another lineup-loop-style runaway.

## What this doesn't try to do

- Not replacing Railway env vars wholesale. Feature flags (`DESK_BLURB_HAIKU`, `DESK_INJURY_FETCH`, etc.) stay env-driven — they're per-deploy configuration, not per-schedule. The admin controls **when** a loop runs, not what it does inside the tick.
- Not adding cron-syntax support. Three shapes are enough; complexity isn't worth it for ~10 loops.
- Not building an event timeline / "what fired in the last hour" view in Phase 1. The 24h cost number + last-tick timestamp is enough until a real need surfaces.

## Open questions

- **Per-env schedules?** Staging and prod likely want different cadences (cheap on staging). The current control.json is already per-env (lives on each Railway service's volume), so this comes for free — but worth confirming both envs get their own `schedules.json` and the migration runs independently on each.
- **History retention.** Default 500 rows in `loop_runs.jsonl`; revisit if the page wants a real chart later.
- **Should `desk_refresh_loop`'s sub-steps be individually toggleable?** (e.g. "run blurb writer but skip signals extract"). The current spec keeps the loop as one atomic unit — sub-step gating stays env-var-driven. Revisit if cost data shows a single sub-step dominating.
