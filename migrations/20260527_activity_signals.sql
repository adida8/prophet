-- Activity signals — schema v1.0
-- Spec: ACTIVITY_SIGNALS_SPEC.md (v1.0.1, 2026-05-27)
--
-- Creates three tables on the Railway Postgres add-on:
--   match_views       — append-only log of unique reads (pruned to 7 days)
--   match_reactions   — one row per (match_id, anon_id) vote
--   match_aggregates  — denormalised counts maintained by the 60s aggregator
--
-- Apply once, by hand, against the Railway Postgres `DATABASE_PUBLIC_URL`
-- (TablePlus / Postico / psql / DBeaver). The transaction wrapper means a
-- failure partway through leaves the database untouched, so it is safe to
-- re-run on a stale partial apply (everything is IF NOT EXISTS).
--
-- No bootstrap rows are inserted here. The aggregator job (PR 4) UPSERTs
-- match_aggregates lazily on the first real or seeded row; the GET endpoint
-- (PR 3) returns zeros when the row is absent. Keeps the SQL decoupled from
-- the desk output directory.

BEGIN;

CREATE TABLE IF NOT EXISTS match_views (
  id          bigserial   PRIMARY KEY,
  match_id    text        NOT NULL,
  anon_id     text        NOT NULL,
  ip_hash     text        NOT NULL,
  seeded      boolean     NOT NULL DEFAULT false,
  viewed_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_match_views_match_time
  ON match_views (match_id, viewed_at);

-- Daily prune scans by viewed_at alone (DELETE WHERE viewed_at < now() - 7d).
CREATE INDEX IF NOT EXISTS idx_match_views_time
  ON match_views (viewed_at);

-- Auto-decay threshold check counts non-seeded views per match. Partial index
-- stays small until seeding turns off; planner uses it for the count query.
CREATE INDEX IF NOT EXISTS idx_match_views_real_by_match
  ON match_views (match_id) WHERE seeded = false;


CREATE TABLE IF NOT EXISTS match_reactions (
  match_id    text        NOT NULL,
  anon_id     text        NOT NULL,
  reaction    text        NOT NULL CHECK (reaction IN (
                            'sharp_call', 'fair_call', 'off_mark', 'wait_see'
                          )),
  seeded      boolean     NOT NULL DEFAULT false,
  voted_at    timestamptz NOT NULL DEFAULT now(),
  locked_at   timestamptz,
  PRIMARY KEY (match_id, anon_id)
);

-- Same rationale as the views partial index: cheap, scoped to live data.
CREATE INDEX IF NOT EXISTS idx_match_reactions_real_by_match
  ON match_reactions (match_id) WHERE seeded = false;


CREATE TABLE IF NOT EXISTS match_aggregates (
  match_id        text          PRIMARY KEY,
  views_24h       int           NOT NULL DEFAULT 0,
  votes_total     int           NOT NULL DEFAULT 0,
  sharp_call      int           NOT NULL DEFAULT 0,
  fair_call       int           NOT NULL DEFAULT 0,
  off_mark        int           NOT NULL DEFAULT 0,
  wait_see        int           NOT NULL DEFAULT 0,
  aligned_pct     int,
  seeded_share    numeric(4,3),
  seed_disabled   boolean       NOT NULL DEFAULT false,
  refreshed_at    timestamptz   NOT NULL
);

COMMIT;
