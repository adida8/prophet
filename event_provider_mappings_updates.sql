-- =====================================================================
-- Event Provider Mappings — NULL slug fills for WC 2026 fixtures
-- Generated 2026-05-18 from live Polymarket Gamma API + Kalshi API
-- =====================================================================
--
-- Polymarket source: https://gamma-api.polymarket.com/events?series_slug=soccer-fifwc
-- Kalshi source:    https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME
--
-- ASSUMED SCHEMA: per CLAUDE.md, slugs live on event_provider_configs
-- (one row per event × provider). If the table you exported from is a
-- single flat row per event with polymarket_slug / kalshi_slug columns,
-- the alternative single-UPDATE form is in the second section below.
--
-- Summary
--   Polymarket NULLs filled: 12 / 12  (all verified against live catalogue)
--   Kalshi NULLs filled:     18 / 36  (remaining 18 not yet listed on Kalshi)
--
-- The 18 Kalshi-missing fixtures involve teams Kalshi has not yet posted
-- WC26 markets for: Sweden, Czech Republic, Turkey/Türkiye, Iraq, DR Congo,
-- Bosnia and Herzegovina. Kalshi's catalogue covers group-stage matches
-- through Jun 27 only — knockouts and these laggard fixtures should
-- appear closer to kickoff. Leaving them NULL per agreed plan.
-- =====================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────
-- Section 1 — event_provider_configs (canonical schema)
-- One UPDATE per (event_id, provider). Adjust column names if needed.
-- ─────────────────────────────────────────────────────────────────────

-- ── Polymarket fills (12) ─────────────────────────────────────────────
UPDATE event_provider_configs SET slug = 'fifwc-arg-alg-2026-06-16'
  WHERE event_id = 'ac0524c7-a556-4778-a3cf-5aaafdb8dafb' AND provider = 'polymarket';  -- Argentina vs Algeria
UPDATE event_provider_configs SET slug = 'fifwc-hrv-gha-2026-06-27'
  WHERE event_id = '908046d0-f324-4cc4-b34d-b284e033b578' AND provider = 'polymarket';  -- Croatia vs Ghana
UPDATE event_provider_configs SET slug = 'fifwc-kor-civ-2026-06-25'
  WHERE event_id = 'd7cdbacd-c0c4-4008-8adc-2f06a7d96be4' AND provider = 'polymarket';  -- Curaçao vs Ivory Coast (Polymarket: Curaçao = `kor`, Côte d'Ivoire = `civ`)
UPDATE event_provider_configs SET slug = 'fifwc-ecu-kor-2026-06-20'
  WHERE event_id = 'ba08a07c-430c-4986-90bc-5463fa84335b' AND provider = 'polymarket';  -- Ecuador vs Curaçao (Polymarket: Curaçao = `kor`)
UPDATE event_provider_configs SET slug = 'fifwc-eng-hrv-2026-06-17'
  WHERE event_id = '46ec619f-768f-445a-b543-5169395d1c6a' AND provider = 'polymarket';  -- England vs Croatia
UPDATE event_provider_configs SET slug = 'fifwc-irn-nzl-2026-06-15'
  WHERE event_id = 'b1f3a710-2a63-42fc-9f81-fe2d155ba7f1' AND provider = 'polymarket';  -- Iran vs New Zealand
UPDATE event_provider_configs SET slug = 'fifwc-nzl-egy-2026-06-21'
  WHERE event_id = 'dda90afa-0e40-4daa-9733-e32104b8518f' AND provider = 'polymarket';  -- New Zealand vs Egypt
UPDATE event_provider_configs SET slug = 'fifwc-pan-hrv-2026-06-23'
  WHERE event_id = '15bc1a28-87ae-4f04-9b9e-e09d07985f13' AND provider = 'polymarket';  -- Panama vs Croatia
UPDATE event_provider_configs SET slug = 'fifwc-par-aus-2026-06-25'
  WHERE event_id = '9ebf894a-07ba-4958-8f70-18fcd43011bd' AND provider = 'polymarket';  -- Paraguay vs Australia
UPDATE event_provider_configs SET slug = 'fifwc-tun-jpn-2026-06-21'
  WHERE event_id = 'edda5fd8-050f-4454-a8fb-f403d9b9b2c9' AND provider = 'polymarket';  -- Tunisia vs Japan
UPDATE event_provider_configs SET slug = 'fifwc-tun-nld-2026-06-25'
  WHERE event_id = 'b1f3a319-7590-4c01-821c-dee5b5450022' AND provider = 'polymarket';  -- Tunisia vs Netherlands
UPDATE event_provider_configs SET slug = 'fifwc-tur-usa-2026-06-25'
  WHERE event_id = '55dd03f9-1ba9-4ac6-92f1-2b4718c9a0d5' AND provider = 'polymarket';  -- Turkey vs United States

-- ── Kalshi fills (18) ────────────────────────────────────────────────
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun16argdza'
  WHERE event_id = 'ac0524c7-a556-4778-a3cf-5aaafdb8dafb' AND provider = 'kalshi';  -- Argentina vs Algeria
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun21beliri'
  WHERE event_id = '91ff4efa-0117-40c7-95fb-857939deb273' AND provider = 'kalshi';  -- Belgium vs Iran
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun19brahti'
  WHERE event_id = 'e3db5ff8-4b56-42d0-8032-9ad43c200713' AND provider = 'kalshi';  -- Brazil vs Haiti
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun26cpvksa'
  WHERE event_id = '694ba486-7250-412a-b1c7-23feea4445d4' AND provider = 'kalshi';  -- Cape Verde vs Saudi Arabia
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun27crogha'
  WHERE event_id = '908046d0-f324-4cc4-b34d-b284e033b578' AND provider = 'kalshi';  -- Croatia vs Ghana
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun25cuwciv'
  WHERE event_id = 'd7cdbacd-c0c4-4008-8adc-2f06a7d96be4' AND provider = 'kalshi';  -- Curaçao vs Ivory Coast
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun26egyiri'
  WHERE event_id = '3933edab-f1e4-4c44-a672-87c0dfb03eaf' AND provider = 'kalshi';  -- Egypt vs Iran
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun13htisco'
  WHERE event_id = 'c1e0d4c8-03d9-4d97-b443-5c21653f2cc9' AND provider = 'kalshi';  -- Haiti vs Scotland
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun15irinzl'
  WHERE event_id = 'b1f3a710-2a63-42fc-9f81-fe2d155ba7f1' AND provider = 'kalshi';  -- Iran vs New Zealand
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun14civecu'
  WHERE event_id = 'da3a4433-82a1-4d87-8392-789e91a7a0e5' AND provider = 'kalshi';  -- Ivory Coast vs Ecuador
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun22jordza'
  WHERE event_id = '573f22c7-822a-4e7f-8ee1-d5ac6b491bcf' AND provider = 'kalshi';  -- Jordan vs Algeria
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun24marhti'
  WHERE event_id = 'd9837a28-02de-4c11-a652-6cd46c776fb4' AND provider = 'kalshi';  -- Morocco vs Haiti
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun21nzlegy'
  WHERE event_id = 'dda90afa-0e40-4daa-9733-e32104b8518f' AND provider = 'kalshi';  -- New Zealand vs Egypt
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun25paraus'
  WHERE event_id = '9ebf894a-07ba-4958-8f70-18fcd43011bd' AND provider = 'kalshi';  -- Paraguay vs Australia
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun15ksauru'
  WHERE event_id = '6d2331d5-f11d-4562-b40e-0462ea90d3d9' AND provider = 'kalshi';  -- Saudi Arabia vs Uruguay
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun21espksa'
  WHERE event_id = '3c1c2dc6-dc0e-48fa-90ce-0577c525f737' AND provider = 'kalshi';  -- Spain vs Saudi Arabia
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun21tunjpn'
  WHERE event_id = 'edda5fd8-050f-4454-a8fb-f403d9b9b2c9' AND provider = 'kalshi';  -- Tunisia vs Japan
UPDATE event_provider_configs SET slug = 'kxwcgame-26jun25tunned'
  WHERE event_id = 'b1f3a319-7590-4c01-821c-dee5b5450022' AND provider = 'kalshi';  -- Tunisia vs Netherlands

COMMIT;

-- =====================================================================
-- Section 2 — ALTERNATIVE: single-table flat schema
-- Use this instead of Section 1 if slugs are columns on `events`
-- (or whatever the table in the original snippet is). One UPDATE per row.
-- =====================================================================
--
-- BEGIN;
--
-- UPDATE events SET
--     polymarket_slug = 'fifwc-arg-alg-2026-06-16',
--     kalshi_slug     = 'kxwcgame-26jun16argdza'
--   WHERE id = 'ac0524c7-a556-4778-a3cf-5aaafdb8dafb';  -- Argentina vs Algeria
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun21beliri'
--   WHERE id = '91ff4efa-0117-40c7-95fb-857939deb273';  -- Belgium vs Iran
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun19brahti'
--   WHERE id = 'e3db5ff8-4b56-42d0-8032-9ad43c200713';  -- Brazil vs Haiti
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun26cpvksa'
--   WHERE id = '694ba486-7250-412a-b1c7-23feea4445d4';  -- Cape Verde vs Saudi Arabia
-- UPDATE events SET
--     polymarket_slug = 'fifwc-hrv-gha-2026-06-27',
--     kalshi_slug     = 'kxwcgame-26jun27crogha'
--   WHERE id = '908046d0-f324-4cc4-b34d-b284e033b578';  -- Croatia vs Ghana
-- UPDATE events SET
--     polymarket_slug = 'fifwc-kor-civ-2026-06-25',
--     kalshi_slug     = 'kxwcgame-26jun25cuwciv'
--   WHERE id = 'd7cdbacd-c0c4-4008-8adc-2f06a7d96be4';  -- Curaçao vs Ivory Coast
-- UPDATE events SET polymarket_slug = 'fifwc-ecu-kor-2026-06-20'
--   WHERE id = 'ba08a07c-430c-4986-90bc-5463fa84335b';  -- Ecuador vs Curaçao
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun26egyiri'
--   WHERE id = '3933edab-f1e4-4c44-a672-87c0dfb03eaf';  -- Egypt vs Iran
-- UPDATE events SET polymarket_slug = 'fifwc-eng-hrv-2026-06-17'
--   WHERE id = '46ec619f-768f-445a-b543-5169395d1c6a';  -- England vs Croatia
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun13htisco'
--   WHERE id = 'c1e0d4c8-03d9-4d97-b443-5c21653f2cc9';  -- Haiti vs Scotland
-- UPDATE events SET
--     polymarket_slug = 'fifwc-irn-nzl-2026-06-15',
--     kalshi_slug     = 'kxwcgame-26jun15irinzl'
--   WHERE id = 'b1f3a710-2a63-42fc-9f81-fe2d155ba7f1';  -- Iran vs New Zealand
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun14civecu'
--   WHERE id = 'da3a4433-82a1-4d87-8392-789e91a7a0e5';  -- Ivory Coast vs Ecuador
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun22jordza'
--   WHERE id = '573f22c7-822a-4e7f-8ee1-d5ac6b491bcf';  -- Jordan vs Algeria
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun24marhti'
--   WHERE id = 'd9837a28-02de-4c11-a652-6cd46c776fb4';  -- Morocco vs Haiti
-- UPDATE events SET
--     polymarket_slug = 'fifwc-nzl-egy-2026-06-21',
--     kalshi_slug     = 'kxwcgame-26jun21nzlegy'
--   WHERE id = 'dda90afa-0e40-4daa-9733-e32104b8518f';  -- New Zealand vs Egypt
-- UPDATE events SET polymarket_slug = 'fifwc-pan-hrv-2026-06-23'
--   WHERE id = '15bc1a28-87ae-4f04-9b9e-e09d07985f13';  -- Panama vs Croatia
-- UPDATE events SET
--     polymarket_slug = 'fifwc-par-aus-2026-06-25',
--     kalshi_slug     = 'kxwcgame-26jun25paraus'
--   WHERE id = '9ebf894a-07ba-4958-8f70-18fcd43011bd';  -- Paraguay vs Australia
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun15ksauru'
--   WHERE id = '6d2331d5-f11d-4562-b40e-0462ea90d3d9';  -- Saudi Arabia vs Uruguay
-- UPDATE events SET kalshi_slug = 'kxwcgame-26jun21espksa'
--   WHERE id = '3c1c2dc6-dc0e-48fa-90ce-0577c525f737';  -- Spain vs Saudi Arabia
-- UPDATE events SET
--     polymarket_slug = 'fifwc-tun-jpn-2026-06-21',
--     kalshi_slug     = 'kxwcgame-26jun21tunjpn'
--   WHERE id = 'edda5fd8-050f-4454-a8fb-f403d9b9b2c9';  -- Tunisia vs Japan
-- UPDATE events SET
--     polymarket_slug = 'fifwc-tun-nld-2026-06-25',
--     kalshi_slug     = 'kxwcgame-26jun25tunned'
--   WHERE id = 'b1f3a319-7590-4c01-821c-dee5b5450022';  -- Tunisia vs Netherlands
-- UPDATE events SET polymarket_slug = 'fifwc-tur-usa-2026-06-25'
--   WHERE id = '55dd03f9-1ba9-4ac6-92f1-2b4718c9a0d5';  -- Turkey vs United States
--
-- COMMIT;

-- =====================================================================
-- Kalshi STILL-NULL fixtures (18) — no market listed yet on 2026-05-18
-- Re-poll Kalshi closer to kickoff; all should appear before the group
-- stage starts (Jun 11).
-- =====================================================================
--   Australia vs Turkey                            (2026-06-14)
--   Bosnia and Herzegovina vs Qatar                (2026-06-24)
--   Canada vs Bosnia and Herzegovina               (2026-06-12)
--   Colombia vs DR Congo                           (2026-06-23)
--   Czech Republic vs Mexico                       (2026-06-24)
--   Czech Republic vs South Africa                 (2026-06-18)
--   DR Congo vs Uzbekistan                         (2026-06-27)
--   France vs Iraq                                 (2026-06-22)
--   Iraq vs Norway                                 (2026-06-16)
--   Japan vs Sweden                                (2026-06-25)
--   Netherlands vs Sweden                          (2026-06-20)
--   Portugal vs DR Congo                           (2026-06-17)
--   Senegal vs Iraq                                (2026-06-26)
--   South Korea vs Czech Republic                  (2026-06-11)
--   Sweden vs Tunisia                              (2026-06-14)
--   Switzerland vs Bosnia and Herzegovina          (2026-06-18)
--   Turkey vs Paraguay                             (2026-06-19)
--   Turkey vs United States                        (2026-06-25)
