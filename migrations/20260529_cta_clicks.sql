-- CTA clicks — schema v1.0
-- Powers the "CTAs to Polymarket / Kalshi" rows in the Odds Primer Daily
-- Report. Append-only log of beacon hits fired from site/public/js/activity.js
-- when a reader clicks a market CTA tagged with data-cta-venue.
--
-- Apply once, by hand, against the Railway Postgres DATABASE_PUBLIC_URL
-- (same flow as migrations/20260527_activity_signals.sql). The BEGIN/COMMIT
-- wrapper + IF NOT EXISTS on every statement means a re-apply on a stale
-- partial state is safe.
--
-- The seeded column mirrors match_views / match_reactions so the daily
-- report's WHERE seeded = false filter is consistent across the activity
-- tables. Click traffic is never seeded today — the column reserves the
-- option without breaking the consistent filter pattern.

BEGIN;

CREATE TABLE IF NOT EXISTS cta_clicks (
  id          bigserial   PRIMARY KEY,
  match_id    text        NOT NULL,
  venue       text        NOT NULL CHECK (venue IN ('polymarket', 'kalshi')),
  anon_id     text        NOT NULL,
  ip_hash     text        NOT NULL,
  seeded      boolean     NOT NULL DEFAULT false,
  clicked_at  timestamptz NOT NULL DEFAULT now()
);

-- Daily report groups by venue inside a UTC-day window — index on
-- (clicked_at, venue) keeps the GROUP BY cheap as the table grows.
CREATE INDEX IF NOT EXISTS idx_cta_clicks_time_venue
  ON cta_clicks (clicked_at, venue);

-- Top-N CTA matches in the report joins by match_id inside the same
-- window — separate index on (match_id, clicked_at) keeps that sort
-- index-only when the working set is small.
CREATE INDEX IF NOT EXISTS idx_cta_clicks_match_time
  ON cta_clicks (match_id, clicked_at);

COMMIT;
