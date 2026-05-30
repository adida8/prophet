#!/usr/bin/env python3
"""Odds Primer — static site generator.

Reads:
  desk/data/output/football/*.json          (per-match verdicts)
  desk/data/output/football/index.json      (manifest)
  desk/data/output/outrights/*.json         (per-outright verdicts — optional)
  desk/data/output/outrights/index.json     (manifest — optional)

Writes:
  site/public/index.html                    (home — headline + upcoming + outrights)
  site/public/matches/index.html            (all matches, grouped by date)
  site/public/m/{match_id}.html             (per-match page)
  site/public/outrights/index.html          (outright winners or "coming soon")
  site/public/outrights/{outright_id}.html  (per-outright page)

Pure stdlib. No jinja. Templates inlined as f-strings.

Design source: Odds Primer Design System/mockups/home-cards-v5.html
CSS extracted verbatim from that mockup — lv-card pattern is locked.

Usage:
    python site/generate.py
    python site/generate.py --quiet
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK_OUT = ROOT / "desk" / "data" / "output"
FOOTBALL_DIR = DESK_OUT / "football"
OUTRIGHTS_DIR = DESK_OUT / "outrights"
SITE_OUT = ROOT / "site" / "public"

# Shared team-code → flag helpers live in the desk package. The module is
# pure stdlib (just a dict + parsing) so this import doesn't pull in the
# ingest stack the generator deliberately stays away from.
sys.path.insert(0, str(ROOT / "desk"))
from desk.sports.football.flags import (  # noqa: E402 — path tweak above
    flag_path,
    team_codes_from_match_id,
)
from desk.sports.football.teams import iso3_for_name  # noqa: E402

# Canonical host for the public site. www is the host that serves every
# page in production (the bare apex 404s on deep paths), so canonical tags,
# og:url, sitemap.xml and robots.txt all agree on it. Single source of truth.
BASE_URL = "https://www.oddsprimer.com"

# Newsletter signup → posts to the Prophet backend (/api/subscribe), which
# forwards the opt-in to SendX server-side. No form action or API key is
# exposed in the generated HTML; the only client-visible value is the
# same-origin endpoint path. SUBSCRIBE_ENDPOINT can be overridden if the
# backend is ever hosted on a different origin.
SUBSCRIBE_ENDPOINT = (os.environ.get("OP_SUBSCRIBE_ENDPOINT") or "/api/subscribe").strip()
# Off-screen anti-bot field name. Real users never see or fill it; a
# non-empty value makes the backend silently drop the submission.
NEWSLETTER_HONEYPOT_NAME = "op_company"
# The forms always render — config now lives on the backend, so there is
# no client-side credential to gate on.
NEWSLETTER_CONFIGURED = True
# Set True to suppress the pop-up modal for launch; footer signup is unaffected.
NEWSLETTER_POPUP_DISABLED = True

# Populated at the start of main() — see `_load_kalshi_event_index`.
# Maps (kickoff_date, frozenset({iso3_a, iso3_b})) → event_ticker (str).
KALSHI_EVENT_INDEX: dict[tuple, str] = {}


# ─── CSS (verbatim from Odds Primer Design System/mockups/home-cards-v5.html) ───
# Kept inline so every page is a self-contained HTML file — works opened
# from disk (file://) AND served from any path. ~12KB per page.

CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;0,8..60,700;1,8..60,400;1,8..60,500&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
  --paper:        #FAF7F0;
  --paper-pure:   #FFFFFF;
  --paper-warm:   #F0ECE2;
  --ink:          #0E2240;
  --ink-soft:     #2A3957;
  --graphite:     #3A3F47;
  --graphite-soft:#6B7079;
  --rule:         #D9D2C0;
  --rule-soft:    #EDE7D6;
  --flame:        #D9461C;
  --flame-deep:   #A8341A;
  --flame-tint:   #F7E4DA;
  --dim:          #A8A294;
  --hairline:        1px solid var(--rule);
  --hairline-soft:   1px solid var(--rule-soft);
  --hairline-strong: 1px solid var(--ink);
  --font-sans:    'Inter Tight', 'Söhne', 'Inter', system-ui, sans-serif;
  --font-serif:   'Source Serif 4', 'Charter', 'Georgia', serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', 'Menlo', monospace;
  --gutter: clamp(16px, 4vw, 56px);
  --dur-fast: 160ms;
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; background: var(--paper); color: var(--ink); -webkit-font-smoothing: antialiased; }
html, body { overflow-x: hidden; }
body { font-family: var(--font-sans); font-size: 15px; line-height: 1.5; }
.page { max-width: 1180px; margin: 0 auto; padding: 0 var(--gutter); width: 100%; }
a { color: inherit; }

/* MASTHEAD */
.site-masthead { border-bottom: var(--hairline); background: var(--paper); }
.site-masthead .inner {
  max-width: 1180px; margin: 0 auto;
  padding: 14px var(--gutter) 12px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  border-top: var(--hairline-strong);
}
.brand-lock { display: inline-flex; flex-direction: column; gap: 4px; text-decoration: none; }
.brand-lock svg { display: block; }
.brand-lock .wm-row { display: flex; align-items: baseline; gap: 12px; }
.brand-lock .wm { font-family: var(--font-serif); font-weight: 700; font-size: 24px; color: var(--ink); letter-spacing: -0.01em; line-height: 1; }
.brand-lock .tag { font-family: var(--font-serif); font-style: italic; font-weight: 400; font-size: 12px; line-height: 1.3; color: var(--graphite); }
.brand-lock .tag .flame { color: var(--flame-deep); font-style: normal; font-weight: 600; }

.site-nav { display: none; }
@media (min-width: 820px) { .site-nav { display: block; } }
.site-nav ul { list-style: none; padding: 0; margin: 0; display: flex; gap: 26px; }
.site-nav a {
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  letter-spacing: 0.04em; color: var(--ink); text-decoration: none;
  padding: 6px 0; border-bottom: 1.5px solid transparent;
}
.site-nav a[aria-current="page"] { border-bottom-color: var(--flame); }
.site-nav a:hover { color: var(--flame-deep); border-bottom-color: var(--flame); }

.nav-meta {
  display: none;
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--graphite-soft); font-variant-numeric: tabular-nums;
}
@media (min-width: 820px) { .nav-meta { display: inline; } }

/* Burger — native <details>/<summary> disclosure. No JS needed. */
.burger { position: relative; display: inline-block; }
.burger-btn {
  list-style: none; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 36px;
  border: var(--hairline); background: var(--paper-pure);
  color: var(--ink); border-radius: 2px;
}
.burger-btn::-webkit-details-marker { display: none; }
.burger-btn::marker { content: ""; }
.burger-btn:hover { color: var(--flame-deep); }
.burger[open] .burger-btn { background: var(--ink); color: var(--paper); }
.burger-menu {
  position: absolute; right: 0; top: calc(100% + 8px);
  min-width: 220px;
  background: var(--paper-pure); border: var(--hairline);
  list-style: none; margin: 0; padding: 6px 0;
  box-shadow: 0 8px 24px rgba(14, 34, 64, 0.08); z-index: 50;
}
.burger-menu li { padding: 0; margin: 0; list-style: none; }
.burger-menu a {
  display: block; padding: 10px 18px;
  font-family: var(--font-sans); font-size: 14px; font-weight: 600;
  letter-spacing: 0.02em; color: var(--ink); text-decoration: none;
}
.burger-menu a:hover { background: var(--paper-warm); color: var(--flame-deep); }
.burger-menu a[aria-current="page"] { color: var(--flame-deep); border-left: 3px solid var(--flame); padding-left: 15px; }
@media (min-width: 820px) { .burger { display: none; } }

/* Mobile pill-nav — visible primary links beneath the masthead on small
   screens. Hidden on desktop where the full .site-nav is shown. */
.pill-nav {
  display: flex; gap: 6px; align-items: center;
  padding: 12px var(--gutter);
  border-bottom: var(--hairline); background: var(--paper);
  overflow-x: auto; scrollbar-width: none;
}
.pill-nav::-webkit-scrollbar { display: none; }
.pill-nav a {
  font-family: var(--font-sans); font-size: 15px; font-weight: 600;
  letter-spacing: -0.005em; color: var(--ink); text-decoration: none;
  padding: 10px 18px; border-radius: 999px; white-space: nowrap;
  transition: background var(--dur-fast) var(--ease-standard),
              color var(--dur-fast) var(--ease-standard);
}
.pill-nav a[aria-current="page"] { background: var(--ink); color: var(--paper); }
.pill-nav a:not([aria-current="page"]):hover { color: var(--flame-deep); }
@media (min-width: 820px) { .pill-nav { display: none; } }

.edition-strip { border-top: var(--hairline-soft); background: var(--paper); }
.edition-strip .inner {
  max-width: 1180px; margin: 0 auto;
  padding: 8px var(--gutter);
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
}
.edition-strip .vol { color: var(--ink); }
.edition-strip .live::before {
  content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 999px;
  background: var(--flame); margin-right: 8px; vertical-align: 1px;
}

/* HERO */
.hero { padding: 40px 0 24px; }
.hero h1 {
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(2rem, 4.6vw, 3.5rem);
  line-height: 1.04; letter-spacing: -0.02em;
  margin: 0; color: var(--ink); text-wrap: balance; max-width: 18ch;
}
.hero .standfirst {
  font-family: var(--font-serif); font-style: italic;
  font-size: clamp(15px, 1.5vw, 18px);
  line-height: 1.5; color: var(--ink-soft);
  margin: 16px 0 0; max-width: 58ch;
}
.hero .standfirst em.vlead {
  font-style: italic; font-weight: 600; color: var(--ink);
  border-bottom: 1.5px solid var(--flame); padding-bottom: 1px;
}
@media (max-width: 720px) { .hero { padding: 28px 0 20px; } }

/* VERDICT KEY — legend strip below the hero. Colour, glyph, and label
   all carry the same meaning so the reader can scan a card at a glance. */
.verdict-key {
  margin: 8px 0 0;
  padding: 18px 0 20px;
  border-top: var(--hairline);
  border-bottom: var(--hairline);
  display: grid;
  grid-template-columns: max-content repeat(3, 1fr);
  column-gap: 36px; row-gap: 14px;
  align-items: center;
}
.verdict-key .vk-label {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
}
.verdict-key .vk-item { display: flex; align-items: center; gap: 14px; }
.verdict-key .vk-icon {
  position: relative;
  width: 44px; height: 30px;
  background: var(--paper-pure);
  border: var(--hairline);
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--font-sans); font-weight: 800;
  line-height: 1; flex-shrink: 0;
}
.verdict-key .vk-icon::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}
.verdict-key .vk-icon.is-pick::before { background: var(--flame); }
.verdict-key .vk-icon.is-pick { color: var(--flame); font-size: 16px; }
.verdict-key .vk-icon.is-pass::before { background: var(--graphite-soft); }
.verdict-key .vk-icon.is-pass { color: var(--graphite-soft); font-size: 18px; }
.verdict-key .vk-icon.is-avoid::before { background: var(--ink); }
.verdict-key .vk-icon.is-avoid { color: var(--flame-deep); font-size: 16px; }
.verdict-key .vk-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.verdict-key .vk-name {
  font-family: var(--font-sans); font-size: 12px; font-weight: 800;
  letter-spacing: 0.14em; text-transform: uppercase;
}
.verdict-key .vk-name.is-pick  { color: var(--flame); }
.verdict-key .vk-name.is-pass  { color: var(--ink); }
.verdict-key .vk-name.is-avoid { color: var(--ink); border-bottom: 1.5px solid var(--flame); padding-bottom: 1px; align-self: flex-start; }
.verdict-key .vk-desc {
  font-family: var(--font-serif); font-style: italic; font-size: 13.5px;
  color: var(--graphite); line-height: 1.4;
}
.verdict-key .vk-note {
  grid-column: 1 / -1;
  font-family: var(--font-sans); font-size: 11px; color: var(--graphite-soft);
  letter-spacing: 0.02em;
}
.verdict-key .vk-note em { color: var(--ink); font-style: normal; font-weight: 600; }
@media (max-width: 720px) {
  .verdict-key { grid-template-columns: 1fr; column-gap: 0; row-gap: 12px; padding: 16px 0 18px; }
  .verdict-key .vk-label { margin-bottom: 2px; }
}

/* SECTION label */
.section-label {
  margin-top: 32px; padding-bottom: 10px; border-bottom: var(--hairline);
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
}
.section-label .see-all {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink); text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 12px 4px; min-height: 44px;
  margin: -12px -4px;
}
.section-label .see-all .arr { color: var(--flame); }
.section-label .see-all:hover { color: var(--flame-deep); }

/* Date grouping on /matches/ */
.date-head {
  margin-top: 28px; padding-bottom: 8px; border-bottom: var(--hairline-soft);
  font-family: var(--font-serif); font-weight: 600; font-size: 16px;
  color: var(--ink); letter-spacing: -0.01em;
}
.date-head + .lv-card { margin-top: 14px; }

/* LV-CARD — canonical card. Same skeleton drives match / outright / headline. */
.lv-card {
  position: relative; display: grid;
  grid-template-columns: 6px minmax(0, 1fr);
  grid-template-rows: auto auto auto auto auto;
  column-gap: 22px; row-gap: 6px;
  padding: 22px 26px 22px 0;
  background: var(--paper-pure);
  border: var(--hairline);
  text-decoration: none; color: var(--ink);
  transition: background var(--dur-fast) var(--ease-standard);
  width: 100%; max-width: 100%; overflow: hidden;
}
.lv-card > * { min-width: 0; }
.lv-card .lv-teams, .lv-card .lv-thesis, .lv-card .lv-venue-meta { overflow-wrap: anywhere; }
.lv-card + .lv-card { margin-top: 14px; }
.lv-card:hover { background: var(--paper-warm); }
.lv-card .lv-bar { grid-column: 1; grid-row: 1 / -1; background: var(--rule); }

/* Overlay link — the entire card is clickable. Content sits visually on top
   (z-index 2) but has `pointer-events: none` so clicks anywhere fall through
   to the overlay link. The market CTAs explicitly re-enable pointer-events
   so they capture their own clicks. */
.lv-card .lv-card-link {
  position: absolute; inset: 0;
  z-index: 1;
  text-indent: -9999px; overflow: hidden;
  background: transparent;
}
.lv-card > *:not(.lv-card-link) { position: relative; z-index: 2; pointer-events: none; }
.lv-card .lv-action a.cta { pointer-events: auto; z-index: 3; }

.lv-card .lv-head { grid-column: 2; grid-row: 1; display: flex; align-items: baseline; gap: 12px; }
.lv-card .lv-glyph { font-family: var(--font-sans); font-weight: 700; font-size: 16px; line-height: 1; color: var(--graphite-soft); }
.lv-card .lv-lab {
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--graphite-soft);
}
.lv-card .lv-when {
  font-family: var(--font-sans); font-size: 11px; color: var(--graphite-soft);
  letter-spacing: 0.04em; font-variant-numeric: tabular-nums; margin-left: auto;
  display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
  line-height: 1.2;
}
.lv-card .lv-fresh {
  font-size: 10px; color: var(--graphite-soft); opacity: 0.72;
  letter-spacing: 0.02em;
}

.lv-card .lv-teams {
  grid-column: 2; grid-row: 2;
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(22px, 2.6vw, 28px);
  line-height: 1.08; letter-spacing: -0.015em;
  color: var(--ink); margin: 4px 0 0; text-wrap: balance;
}
.lv-card .lv-teams .vs { color: var(--graphite-soft); font-weight: 400; font-style: italic; margin: 0 6px; }
.lv-card .lv-teams .lv-team.is-dim { color: var(--dim); font-weight: 500; }
.lv-card .lv-pick-chip {
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.06em; color: var(--paper);
  background: var(--flame); padding: 3px 9px; border-radius: 2px;
  white-space: nowrap;
}
.lv-card .lv-stat-lead {
  font-family: var(--font-sans); font-size: 11px; font-weight: 600;
  color: var(--ink); margin: 0 0 5px;
}
.lv-card .lv-reads-stack { display: flex; flex-direction: column; gap: 0; min-width: 0; }
.lv-card .lv-flag {
  display: inline-block;
  width: 1.05em; height: 0.7em;       /* ≈3:2, scales with surrounding type */
  object-fit: cover;
  margin-right: 0.32em;
  vertical-align: -0.05em;
  border-radius: 2px;
  /* hairline keeps light flags (Japan, white fields) from bleeding into paper */
  box-shadow: 0 0 0 1px rgba(14, 34, 64, 0.12);
}
.lv-card .lv-venue-meta {
  grid-column: 2; grid-row: 3;
  font-family: var(--font-sans); font-size: 11.5px; color: var(--graphite);
  letter-spacing: 0.04em; margin: 0;
}

.lv-card .lv-thesis {
  grid-column: 2; grid-row: 4;
  font-family: var(--font-serif); font-size: 15px; line-height: 1.55;
  color: var(--graphite); margin: 8px 0 0; max-width: 60ch;
}
.lv-card .lv-thesis em { font-style: italic; color: var(--ink); font-weight: 600; }

.lv-card .lv-foot {
  grid-column: 2; grid-row: 5;
  display: flex; flex-wrap: wrap; gap: 14px 24px; align-items: baseline;
  margin-top: 10px; padding-top: 14px;
  border-top: var(--hairline-soft);
}
.lv-card .lv-reads { display: flex; gap: 14px; flex-wrap: wrap; align-items: baseline; }
.lv-card .rp { display: inline-flex; align-items: baseline; gap: 6px; }
.lv-card .rp .k {
  font-family: var(--font-sans); font-size: 10px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--graphite-soft);
}
.lv-card .rp .v {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-weight: 700; font-size: 14px; color: var(--ink);
}
.lv-card .edge {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-weight: 700; font-size: 13px; color: var(--flame-deep);
  border-bottom: 2px solid var(--flame); padding-bottom: 1px; line-height: 1;
}
.lv-card .edge.is-neg { color: var(--ink); border-bottom-color: var(--ink); }
.lv-card .edge.is-flat { color: var(--graphite-soft); border-bottom-color: var(--rule); }

.lv-card .lv-flat-msg {
  font-family: var(--font-sans); font-size: 11.5px; color: var(--graphite-soft);
  letter-spacing: 0.04em;
}

.lv-card .lv-action { margin-left: auto; display: inline-flex; align-items: center; gap: 12px; }
.lv-card .lv-action .venue {
  font-family: var(--font-sans); font-size: 10px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--graphite-soft);
}
.lv-card .lv-action .price {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-weight: 700; font-size: 16px; color: var(--ink);
  border-bottom: 2px solid var(--flame); padding-bottom: 1px;
}

/* CTA — small but bold + standout. Ink pill desktop. */
.lv-card .lv-action .cta {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px 6px;
  background: var(--ink); color: var(--paper);
  border-radius: 4px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  white-space: nowrap;
  text-decoration: none;
  transition: background var(--dur-fast) var(--ease-standard);
}
.lv-card .lv-action .cta .arr { color: var(--flame); transition: transform var(--dur-fast) var(--ease-standard); }
.lv-card:hover .lv-action .cta,
.lv-card .lv-action .cta:hover { background: var(--flame-deep); }
.lv-card:hover .lv-action .cta .arr,
.lv-card .lv-action .cta:hover .arr { color: var(--paper); transform: translate(2px, -2px); }
.lv-card .lv-action a.cta:focus-visible { outline: 2px solid var(--flame); outline-offset: 2px; }

/* Placeholder venue pill — Kalshi is wired as a search-fallback until
   the live Kalshi ingest lands. Visually differentiated so it doesn't
   read as the primary CTA. */
.lv-card .lv-action a.cta.is-placeholder {
  background: var(--paper-pure);
  color: var(--ink);
  border: 1.5px solid var(--ink);
}
.lv-card .lv-action a.cta.is-placeholder .arr { color: var(--ink); }
.lv-card:hover .lv-action a.cta.is-placeholder,
.lv-card .lv-action a.cta.is-placeholder:hover {
  background: var(--ink); color: var(--paper-pure);
}
.lv-card:hover .lv-action a.cta.is-placeholder .arr,
.lv-card .lv-action a.cta.is-placeholder:hover .arr { color: var(--flame); }

/* Allow CTAs to wrap onto a second row on narrow viewports. */
.lv-card .lv-action { flex-wrap: wrap; gap: 14px; align-items: flex-start; }
.lv-card .lv-foot   { flex-wrap: wrap; row-gap: 12px; }

/* Stacked CTA — the pill plus its small "best price / live / search"
   caption beneath. The caption is the editorial signal that tells the
   reader which venue to trade on. */
.lv-card .lv-action .cta-stack {
  display: inline-flex; flex-direction: column;
  align-items: stretch; gap: 4px;
  pointer-events: none;   /* the child <a> re-enables clicks */
}
.lv-card .lv-action .cta-stack .cta { pointer-events: auto; }
.lv-card .lv-action .cta-caption {
  font-family: var(--font-sans); font-size: 9.5px; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--graphite-soft);
  font-variant-numeric: tabular-nums;
  text-align: center;
  padding: 0 4px;
}
.lv-card .lv-action .cta-caption.is-best   { color: var(--flame-deep); }
.lv-card .lv-action .cta-caption.is-live   { color: var(--ink); }
.lv-card .lv-action .cta-caption.is-search { color: var(--graphite-soft); font-style: italic; letter-spacing: 0.04em; text-transform: none; font-size: 11px; font-weight: 500; }
.lv-card .lv-action .cta-caption.is-spacer { visibility: hidden; }

/* Secondary "Read the case" CTA — text link, no pill. Sits next to the
   two primary trade pills as a tertiary action. */
.lv-card .lv-action a.cta-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink); text-decoration: none;
  padding: 14px 8px; min-height: 44px;
  border-bottom: 1.5px solid transparent;
  pointer-events: auto;
  position: relative; z-index: 3;
  transition: color var(--dur-fast) var(--ease-standard),
              border-color var(--dur-fast) var(--ease-standard);
}
.lv-card .lv-action a.cta-secondary .arr { color: var(--flame); }
.lv-card .lv-action a.cta-secondary:hover { color: var(--flame-deep); border-bottom-color: var(--flame); }
.lv-card .lv-action a.cta-secondary:hover .arr { transform: translateX(2px); }

/* Pass-state cards now also carry the CTA — keep the flat-msg in the same
   row as the action button. */
.lv-card.is-pass .lv-foot { display: flex; align-items: center; gap: 16px; justify-content: space-between; flex-wrap: wrap; }
.lv-card.is-pass .lv-flat-msg { margin: 0; }

/* Verdict variants */
.lv-card.is-pick { background: var(--flame-tint); border-color: var(--flame); }
.lv-card.is-pick .lv-bar { background: var(--flame); }
.lv-card.is-pick .lv-glyph { color: var(--flame); }
.lv-card.is-pick .lv-lab { color: var(--flame-deep); }
.lv-card.is-pick:hover { filter: brightness(0.985); }

.lv-card.is-pass .lv-bar { background: var(--rule); }
.lv-card.is-pass .lv-glyph { color: var(--graphite-soft); }
.lv-card.is-pass .lv-lab { color: var(--graphite-soft); }
.lv-card.is-pass .lv-teams { font-size: clamp(20px, 2.2vw, 24px); }
.lv-card.is-pass .lv-thesis { font-size: 14.5px; }

.lv-card.is-avoid .lv-bar { background: var(--ink); }
.lv-card.is-avoid .lv-glyph { color: var(--flame); }
.lv-card.is-avoid .lv-lab { color: var(--ink); border-bottom: 1.5px solid var(--flame); padding-bottom: 1px; }
.lv-card.is-avoid .lv-action .price {
  text-decoration: line-through; text-decoration-color: var(--flame); text-decoration-thickness: 1.5px;
}

/* Lead headline (scale-up, same skeleton) */
.lv-card.is-lead { padding: 28px 32px 28px 0; }
.lv-card.is-lead .lv-teams { font-size: clamp(28px, 4.2vw, 42px); line-height: 1.04; }
.lv-card.is-lead .lv-thesis { font-size: 16.5px; }
.lv-card.is-lead .lv-action .price { font-size: 19px; }
.lv-card.is-lead .lv-action .cta { padding: 9px 14px 8px; font-size: 11.5px; }

/* Mobile (≤720px) */
@media (max-width: 720px) {
  .lv-card { padding: 18px 16px 18px 0; column-gap: 14px; row-gap: 4px; }
  .lv-card .lv-when { display: none; }
  .lv-card .lv-teams { font-size: 22px; }
  .lv-card.is-lead .lv-teams { font-size: 26px; }
  .lv-card .lv-thesis { font-size: 14.5px; }
  .lv-card .lv-foot { flex-direction: column; align-items: stretch; gap: 14px; }
  .lv-card .lv-action {
    margin-left: 0; width: 100%;
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  }
  .lv-card .lv-action .venue,
  .lv-card .lv-action .price { flex: 0 0 auto; }
  .lv-card .lv-action .cta {
    flex: 1 1 100%;
    display: inline-flex; align-items: center; justify-content: center;
    min-height: 44px; padding: 11px 14px;
    font-size: 12px; letter-spacing: 0.08em;
  }
}

/* PAGE-HEADER (per-match / per-outright pages) */
.page-header { padding: 32px 0 16px; }
.page-header .crumb {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  text-decoration: none;
}
.page-header .crumb:hover { color: var(--flame-deep); }
.page-header .crumb .arr { color: var(--flame); }
.page-header h1 {
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(1.7rem, 3.4vw, 2.6rem);
  line-height: 1.08; letter-spacing: -0.02em;
  margin: 14px 0 0; color: var(--ink); text-wrap: balance; max-width: 22ch;
}

/* Drivers list on per-match page */
.drivers { margin: 32px 0 0; }
.drivers h2 {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  margin: 0 0 12px; padding-bottom: 8px; border-bottom: var(--hairline);
}
.drivers ol { list-style: none; padding: 0; margin: 0; counter-reset: dr; }
.drivers li {
  counter-increment: dr;
  font-family: var(--font-serif); font-size: 15px; line-height: 1.55;
  color: var(--ink-soft); padding: 12px 0 12px 36px;
  border-bottom: var(--hairline-soft); position: relative; max-width: 64ch;
}
.drivers li:last-child { border-bottom: none; }
.drivers li::before {
  content: counter(dr, decimal-leading-zero);
  position: absolute; left: 0; top: 14px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  color: var(--flame-deep); letter-spacing: 0.06em;
}

.blurb {
  margin: 28px 0 0; max-width: 64ch;
  font-family: var(--font-serif); font-size: 17px; line-height: 1.6;
  color: var(--ink-soft);
}
.blurb p + p { margin-top: 14px; }

/* Ladder — per-team verdict grid on the per-outright page. Each
   <article class="lc-card"> is its own tile carrying team name,
   verdict pill, model/market/edge stats, a one-line editorial blurb,
   and a "See {team} on Polymarket" CTA. Sorted by model_p desc;
   Pick tiles get a flame tint so they jump out of the 48-tile grid. */
.ladder { margin: 32px 0 0; }
.ladder h2 {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  margin: 0 0 16px; padding-bottom: 8px; border-bottom: var(--hairline);
}
.lc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.lc-card {
  position: relative;
  border: 1px solid rgba(14, 34, 64, 0.12);
  border-radius: 4px;
  padding: 16px;
  background: var(--paper, #fff);
  display: flex; flex-direction: column; gap: 10px;
  transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
}
.lc-card:hover {
  border-color: rgba(14, 34, 64, 0.32);
  box-shadow: 0 2px 12px rgba(14, 34, 64, 0.08);
  transform: translateY(-1px);
}
.lc-card.is-pick {
  border-color: rgba(217, 70, 28, 0.35);
  background: rgba(217, 70, 28, 0.05);
}
.lc-card.is-pick:hover { border-color: rgba(217, 70, 28, 0.6); }
.lc-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px;
}
.lc-team {
  font-family: var(--font-serif); font-size: 17px; font-weight: 600;
  color: var(--ink); line-height: 1.15;
}
.lc-verdict { white-space: nowrap; }
.lc-glyph {
  display: inline-block; margin-right: 4px;
  font-family: var(--font-mono); font-size: 10.5px;
  color: var(--graphite-soft);
}
.lc-lab {
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--graphite-soft);
}
.lc-card.is-pick .lc-glyph,
.lc-card.is-pick .lc-lab { color: var(--flame-deep); }
.lc-card.is-avoid .lc-glyph,
.lc-card.is-avoid .lc-lab { color: var(--ink); }
.lc-stats {
  display: flex; gap: 16px; margin: 0; padding: 8px 0;
  border-top: var(--hairline-soft); border-bottom: var(--hairline-soft);
}
.lc-stats div { display: flex; flex-direction: column; gap: 2px; }
.lc-stats dt {
  font-family: var(--font-sans); font-size: 10px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--graphite-soft);
  margin: 0;
}
.lc-stats dd {
  margin: 0; font-family: var(--font-mono); font-size: 13px;
  font-variant-numeric: tabular-nums; color: var(--ink-soft);
}
.lc-stats dd.lc-edge { color: var(--ink); font-weight: 600; }
.lc-stats dd.lc-edge.is-neg { color: var(--graphite-soft); font-weight: 400; }
.lc-blurb {
  margin: 0; font-family: var(--font-serif); font-size: 14px;
  line-height: 1.5; color: var(--ink-soft);
}
.lc-link {
  display: inline-block; margin-top: 2px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--flame-deep); text-decoration: none;
}
.lc-link:hover { text-decoration: underline; }

/* Sources — verifiable links behind the press chorus in the blurb.
   One row per outlet; each row links to the article and shows the
   verbatim line we quoted. Editorial register, not a directory. */
.sources { margin: 32px 0 0; max-width: 64ch; }
.sources h2 {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  margin: 0 0 12px; padding-bottom: 8px; border-bottom: var(--hairline);
}
.sources ul { list-style: none; padding: 0; margin: 0; }
.sources li {
  padding: 14px 0;
  border-bottom: var(--hairline-soft);
}
.sources li:last-child { border-bottom: none; }
.sources li a {
  font-family: var(--font-sans); font-size: 13px; font-weight: 700;
  letter-spacing: 0.04em; color: var(--ink);
  text-decoration: none; border-bottom: 1px solid var(--ink);
}
.sources li a:hover { color: var(--flame-deep); border-bottom-color: var(--flame-deep); }
.sources .src-date {
  font-family: var(--font-mono); font-size: 11px; font-weight: 500;
  letter-spacing: 0.02em; color: var(--graphite-soft);
  margin-left: 4px;
}
.sources blockquote {
  margin: 6px 0 0; padding: 0;
  font-family: var(--font-serif); font-style: italic; font-size: 15px;
  line-height: 1.5; color: var(--ink-soft);
}

/* Model adjustments — per-signal Elo nudges applied before the model ran.
   Diagnostic block; lets a reader trace a verdict back to a specific
   news signal without opening the JSON. */
.model-adjustments { margin: 32px 0 0; max-width: 64ch; }
.model-adjustments h2 {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--graphite-soft);
  margin: 0 0 8px; padding-bottom: 8px; border-bottom: var(--hairline);
}
.model-adjustments .adj-lede {
  font-family: var(--font-serif); font-size: 14px; line-height: 1.5;
  color: var(--ink-soft); margin: 0 0 12px;
}
.model-adjustments ul { list-style: none; padding: 0; margin: 0; }
.model-adjustments li {
  padding: 10px 0; border-bottom: var(--hairline-soft);
  font-family: var(--font-sans); font-size: 13px; line-height: 1.5;
  color: var(--ink-soft);
}
.model-adjustments li:last-child { border-bottom: none; }
.model-adjustments .adj-delta {
  font-family: var(--font-mono); font-weight: 700; color: var(--ink);
}
.model-adjustments .adj-team { font-weight: 700; color: var(--ink); }
.model-adjustments .adj-reason { color: var(--ink-soft); }
.model-adjustments .adj-date {
  font-family: var(--font-mono); font-size: 11px; color: var(--graphite-soft);
}
.model-adjustments .adj-type {
  font-family: var(--font-sans); font-size: 10px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--graphite-soft); margin-left: 6px;
}
.model-adjustments a {
  color: var(--ink); text-decoration: none;
  border-bottom: 1px solid var(--ink);
}
.model-adjustments a:hover { color: var(--flame-deep); border-bottom-color: var(--flame-deep); }

.cta-row {
  margin: 28px 0 0; display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}
.cta-row .open-market {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 13px 18px; min-height: 44px;
  background: var(--ink); color: var(--paper);
  text-decoration: none; border-radius: 4px;
  font-family: var(--font-sans); font-size: 12.5px; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase;
  transition: background var(--dur-fast) var(--ease-standard);
}
.cta-row .open-market .venue-name { white-space: nowrap; }
.cta-row .open-market:hover { background: var(--flame-deep); }
.cta-row .open-market .arr { color: var(--flame); }
.cta-row .open-market:hover .arr { color: var(--paper); }
.cta-row .meta-note {
  font-family: var(--font-serif); font-style: italic; font-size: 13px; color: var(--graphite);
}

/* Affiliate note + voice block */
.affiliate-note {
  margin: 16px 0 0;
  font-family: var(--font-serif); font-style: italic; font-size: 13px;
  color: var(--graphite); max-width: 60ch;
}
.voice {
  margin: 40px 0 0;
  padding: 22px 22px;
  background: var(--paper-warm); border-left: 3px solid var(--flame);
  border-radius: 0 4px 4px 0;
}
.voice h3 {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--flame-deep);
  margin: 0 0 8px;
}
.voice p { font-family: var(--font-serif); font-size: 14.5px; line-height: 1.55; color: var(--ink); margin: 0; max-width: 60ch; }
.voice p em { font-weight: 600; font-style: italic; }

.empty-state {
  margin: 32px 0 0; padding: 36px 24px;
  background: var(--paper-pure); border: var(--hairline);
  text-align: center;
}
.empty-state h2 {
  font-family: var(--font-serif); font-weight: 600; font-size: 24px;
  letter-spacing: -0.01em; margin: 0; color: var(--ink);
}
.empty-state p {
  font-family: var(--font-serif); font-style: italic; font-size: 15px;
  color: var(--graphite); margin: 12px auto 0; max-width: 52ch;
}

/* OUTRIGHTS STANDINGS TABLE
   One component, reusable for league tables later. Column contract:
   Team · Verdict · P · W · D · L · GF · GA · GD · Pts · Model · Market · Edge.
   Team is the pinned identity column. Stat block is data-driven — empty (—)
   for winner markets pre-kickoff, populated from standings for league markets.
   Mobile collapses to Team · Verdict · P · Pts · Model. */
.standings-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px 20px;
  margin-top: 22px; padding-bottom: 13px; border-bottom: var(--hairline);
  font-family: var(--font-sans); font-size: 12.5px; color: var(--graphite-soft);
}
.standings-meta span b { color: var(--ink-soft); font-weight: 600; }
.tablewrap {
  margin-top: 18px; border: var(--hairline); border-radius: 8px;
  background: var(--paper-pure); overflow-x: auto; -webkit-overflow-scrolling: touch;
}
table.standings { border-collapse: collapse; width: 100%; font-size: 14px; }
.standings thead th {
  position: sticky; top: 0; background: var(--paper-warm); z-index: 2;
  font-family: var(--font-sans); font-weight: 600; font-size: 10.5px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--graphite-soft); text-align: right;
  padding: 11px 10px; border-bottom: var(--hairline); white-space: nowrap;
}
.standings thead th.grp {
  text-align: left; border-bottom: var(--hairline);
  font-size: 10px; color: var(--graphite); background: var(--rule); padding: 6px 10px;
}
.standings .col-verdict { width: 104px; text-align: center !important; }
.standings .col-team { text-align: left !important; min-width: 178px; }
.standings .col-stat { width: 46px; }
.standings .col-desk { width: 74px; }
.standings .c-team {
  position: sticky; left: 0; background: var(--paper-pure); z-index: 1;
  box-shadow: 1px 0 0 var(--rule);
}
.standings thead .c-team { z-index: 3; background: var(--paper-warm); }
.standings .c-verdict { text-align: center; }
.standings tbody tr { cursor: pointer; transition: background var(--dur-fast) var(--ease-standard); }
.standings tbody tr:hover { background: var(--flame-tint); }
.standings tbody tr:hover .c-team { background: var(--flame-tint); }
.standings tbody td {
  padding: 11px 10px; border-bottom: var(--hairline-soft);
  text-align: right; vertical-align: middle; white-space: nowrap;
}
.standings tbody tr:last-child td { border-bottom: 0; }
.standings .team { display: flex; align-items: center; gap: 10px; text-align: left; }
.standings .team .rank {
  font-family: var(--font-mono); font-size: 12px; color: var(--graphite-soft);
  width: 18px; text-align: right; flex: 0 0 auto;
}
.standings .team .flag {
  width: 22px; height: 16px; border-radius: 2px; flex: 0 0 auto;
  display: inline-block; object-fit: cover; background: var(--rule-soft);
}
.standings .team .name {
  font-family: var(--font-sans); font-weight: 600; font-size: 14.5px; color: var(--ink);
}
.standings .team a {
  display: flex; align-items: center; gap: 10px;
  text-decoration: none; color: inherit;
}
.standings .stat { font-family: var(--font-mono); font-size: 13px; color: var(--ink-soft); }
.standings .stat.muted { color: var(--rule); }
.standings .stat.pts { font-weight: 600; color: var(--ink); }
.standings .num { font-family: var(--font-mono); font-size: 13px; color: var(--ink-soft); }
.standings .num.model { color: var(--ink); font-weight: 600; }
.standings .edge { font-family: var(--font-mono); font-size: 13px; font-weight: 600; }
.standings .edge.pos { color: var(--flame-deep); }
.standings .edge.neg { color: var(--graphite-soft); }
.standings .chip {
  display: inline-block; font-family: var(--font-sans); font-weight: 600; font-size: 11px;
  letter-spacing: 0.04em; text-transform: uppercase; padding: 4px 11px; border-radius: 999px;
  border: 1px solid transparent;
}
.standings .chip.pick { background: var(--flame); color: #fff; }
.standings .chip.pass { background: transparent; color: var(--graphite-soft); border-color: var(--rule); }
.standings .chip.avoid { background: transparent; color: var(--ink); border-color: var(--ink); }
.standings .chip .side { opacity: 0.8; font-weight: 500; margin-left: 3px; }
.standings-legend {
  margin-top: 20px; display: flex; flex-wrap: wrap; gap: 8px 24px;
  font-family: var(--font-sans); font-size: 12px; color: var(--graphite-soft);
}
.standings-legend b { color: var(--ink-soft); font-weight: 600; }
.standings-legend .chip { padding: 2px 9px; }
.standings-note {
  margin-top: 14px; font-family: var(--font-serif); font-style: italic; font-size: 13.5px;
  color: var(--graphite); max-width: 64ch; line-height: 1.5;
}
.standings-note .dag { color: var(--flame); font-style: italic; }
@media (max-width: 640px) {
  .standings { table-layout: fixed; }
  .standings thead tr.groups { display: none; }
  .standings .hide-mobile { display: none !important; }
  .standings .col-team { min-width: 0; width: auto; }
  .standings .col-verdict { width: 60px; }
  .standings .col-stat { width: 28px; }
  .standings .col-desk { width: 48px; }
  .standings .team { gap: 7px; }
  .standings .team a { gap: 7px; }
  .standings .team .rank { display: none; }
  .standings .team .flag { width: 18px; height: 13px; }
  .standings .team .name {
    font-size: 12.5px; white-space: normal; line-height: 1.25;
    word-break: break-word;
  }
  .standings tbody td, .standings thead th { padding: 9px 4px; }
  .standings .num, .standings .stat { font-size: 11.5px; }
  .standings .edge { font-size: 11.5px; }
  .standings .chip { padding: 3px 6px; font-size: 9.5px; letter-spacing: 0.03em; }
  .standings .chip .side { margin-left: 2px; }
  .standings-meta { font-size: 11.5px; gap: 4px 14px; }
}

.site-foot {
  margin: 48px 0 28px; padding-top: 18px; border-top: var(--hairline);
  display: flex; flex-direction: column; gap: 14px;
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--graphite-soft);
}
.site-foot .foot-row {
  display: flex; flex-wrap: wrap; gap: 6px 16px; justify-content: space-between;
}
.site-foot .left { color: var(--ink); }
.site-foot .foot-nav {
  display: flex; flex-wrap: wrap; gap: 0 18px;
  padding-top: 8px; border-top: var(--hairline-soft);
}
.site-foot .foot-nav a {
  color: var(--graphite-soft); text-decoration: none;
  font-size: 11px; letter-spacing: 0.12em;
  border-bottom: 1px solid transparent;
  padding: 14px 0;
  min-height: 44px; display: inline-flex; align-items: center;
  transition: color var(--dur-fast) var(--ease-standard),
              border-color var(--dur-fast) var(--ease-standard);
}
.site-foot .foot-nav a:hover { color: var(--flame-deep); border-bottom-color: var(--flame); }

/* ─── FOOTER TRUST BLOCK ───────────────────────────────────────────── */
.site-foot .foot-trust {
  margin: 0 0 18px;
  padding: 16px 18px;
  background: var(--paper-warm);
  border-left: 3px solid var(--flame);
  font-family: var(--font-serif);
  color: var(--ink);
  font-size: 13.5px; line-height: 1.55;
}
.site-foot .foot-trust .ft-disclaimer {
  margin: 0 0 8px; font-weight: 500;
}
.site-foot .foot-trust .ft-data,
.site-foot .foot-trust .ft-contact {
  margin: 0; font-size: 13px; color: var(--graphite);
}
.site-foot .foot-trust .ft-lbl {
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--flame-deep);
  margin-right: 6px;
}
.site-foot .foot-trust a {
  color: var(--ink); text-decoration: underline;
  text-decoration-color: var(--rule); text-underline-offset: 3px;
}
.site-foot .foot-trust a:hover { color: var(--flame-deep); }

/* ─── TRUST STRIP ON EVENT PAGES ───────────────────────────────────── */
.trust-strip {
  display: flex; flex-wrap: wrap; gap: 6px 18px;
  margin: 0 0 14px;
  padding: 8px 0;
  border-top: var(--hairline-soft); border-bottom: var(--hairline-soft);
  font-family: var(--font-sans); font-size: 11px;
  color: var(--graphite-soft); letter-spacing: 0.04em;
}
.trust-strip .ts-item { white-space: nowrap; }
.trust-strip .ts-lbl {
  font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--flame-deep); margin-right: 5px;
}

/* ─── EDITORIAL DISCLAIMER UNDER VERDICT ───────────────────────────── */
.event-disclaimer {
  margin: 10px 0 18px;
  font-family: var(--font-sans); font-size: 11.5px;
  color: var(--graphite-soft);
  letter-spacing: 0.02em;
  border-left: 2px solid var(--rule);
  padding: 4px 0 4px 10px;
}

/* ─── WHY THE MODEL DISAGREES (wide-gap Picks) ─────────────────────── */
.why-disagrees {
  margin: 24px 0 18px;
  padding: 16px 20px;
  background: var(--paper-warm); border-left: 3px solid var(--flame);
}
.why-disagrees h2 {
  margin: 0 0 8px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--flame-deep);
}
.why-disagrees p {
  margin: 0; font-family: var(--font-serif); font-size: 16px; line-height: 1.55;
  color: var(--ink); max-width: 64ch;
}

/* ─── HOW THE DESK WORKS ───────────────────────────────────────────── */
.how-desk {
  margin: 24px 0 28px;
  padding: 22px 22px 18px;
  border-top: var(--hairline-strong); border-bottom: var(--hairline);
  background: var(--paper-pure);
}
.how-desk .hd-title {
  margin: 0 0 18px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--flame-deep);
}
.how-desk .hd-steps {
  list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: 1fr; gap: 14px;
}
@media (min-width: 720px) {
  .how-desk .hd-steps { grid-template-columns: repeat(4, 1fr); gap: 22px; }
}
.how-desk .hd-steps li {
  position: relative;
  padding: 8px 0 8px 38px;
  border-top: 2px solid var(--ink);
}
.how-desk .hd-num {
  position: absolute; left: 0; top: 8px;
  font-family: var(--font-sans); font-size: 22px; font-weight: 700;
  color: var(--flame-deep); line-height: 1;
}
.how-desk .hd-steps h3 {
  margin: 0 0 4px;
  font-family: var(--font-sans); font-size: 14.5px; font-weight: 700;
  letter-spacing: -0.005em; color: var(--ink);
}
.how-desk .hd-steps p {
  margin: 0;
  font-family: var(--font-serif); font-size: 14.5px; line-height: 1.45;
  color: var(--graphite);
}
.how-desk .hd-thesis {
  margin: 18px 0 0;
  font-family: var(--font-serif); font-style: italic;
  font-size: 16px; line-height: 1.5; color: var(--ink-soft);
  max-width: 60ch;
  padding-top: 14px; border-top: var(--hairline);
}

/* ─── THE DESK POSITIONING BLOCK ───────────────────────────────────── */
.the-desk-block {
  margin: 32px 0 12px;
  padding: 28px 0 28px;
  border-top: var(--hairline-strong);
}
.the-desk-block .td-eyebrow {
  margin: 0 0 8px;
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--flame-deep);
}
.the-desk-block .td-title {
  margin: 0 0 14px;
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(22px, 3.2vw, 30px); line-height: 1.15;
  letter-spacing: -0.012em; color: var(--ink);
  max-width: 28ch; text-wrap: balance;
}
.the-desk-block .td-lede {
  margin: 0 0 12px;
  font-family: var(--font-serif); font-size: 17px; line-height: 1.55;
  color: var(--ink); max-width: 60ch;
}
.the-desk-block .td-body {
  margin: 0;
  font-family: var(--font-serif); font-size: 15.5px; line-height: 1.55;
  color: var(--graphite); max-width: 60ch;
}

/* ─── HOMEPAGE HERO SECONDARY STANDFIRST ───────────────────────────── */
.hero .standfirst-secondary {
  font-family: var(--font-serif); font-style: italic;
  font-size: clamp(15px, 1.5vw, 17px); line-height: 1.5;
  color: var(--ink-soft);
  margin: 10px 0 0; max-width: 56ch;
}

/* ─── PILL-NAV: scrollability fade on narrow viewports ─────────────── */
.pill-nav {
  position: relative;
  mask-image: linear-gradient(to right, #000 0, #000 calc(100% - 28px), transparent 100%);
  -webkit-mask-image: linear-gradient(to right, #000 0, #000 calc(100% - 28px), transparent 100%);
}

/* ─── MOBILE WHITESPACE TIGHTENING ─────────────────────────────────── */
@media (max-width: 720px) {
  .hero { padding: 22px 0 14px; }
  .hero h1 { font-size: clamp(28px, 8vw, 38px); margin-bottom: 8px; }
  .hero .standfirst { font-size: 15.5px; margin-top: 8px; }
  .hero .standfirst-secondary { font-size: 14px; margin-top: 6px; }
  .how-desk { padding: 16px 14px 14px; margin: 16px 0 18px; }
  .how-desk .hd-steps { gap: 10px; }
  .how-desk .hd-steps li { padding: 6px 0 6px 32px; }
  .the-desk-block { padding: 20px 0 18px; margin: 20px 0 8px; }
  .the-desk-block .td-title { font-size: 22px; }
  /* Trust strip stacks vertically on narrow phones so each label/value
     pair reads as its own line. */
  .trust-strip {
    flex-direction: column; align-items: flex-start;
    gap: 4px; font-size: 11px; padding: 8px 0;
  }
  .trust-strip .ts-item { white-space: normal; }
  .event-disclaimer { font-size: 11px; margin: 8px 0 14px; }
  /* "Why the model disagrees" comfort on narrow screens */
  .why-disagrees { padding: 14px 16px; margin: 18px 0 14px; }
  .why-disagrees p { font-size: 15px; line-height: 1.55; }
  /* CTA button: ensure full-width-ish behaviour so taps are easy */
  .cta-row { margin-top: 18px; }
  .cta-row .open-market { padding: 14px 18px; font-size: 12px; }
  .cta-row .meta-note { font-size: 12.5px; }
  /* Footer trust card — fewer pixels of left padding, lighter rule */
  .site-foot .foot-trust { padding: 14px 14px; font-size: 13px; border-left-width: 2px; }
  .site-foot .foot-trust .ft-data,
  .site-foot .foot-trust .ft-contact { font-size: 12.5px; }
  /* Verdict-key gap tightening on narrow screens */
  .verdict-key .vk-item { gap: 10px; padding: 8px 0; }
  /* Popup: clamp to viewport on tiny phones (<420px gutter) */
  .op-popup { max-width: calc(100vw - 20px); }
  .op-popup__title { font-size: 22px; line-height: 1.15; }
  .op-popup__body { padding: 22px 18px 20px; }
}
@media (max-width: 380px) {
  .op-popup__title { font-size: 20px; }
  .hero h1 { font-size: clamp(26px, 9vw, 34px); }
}

/* ─── NEWSLETTER FOOTER SIGNUP ─────────────────────────────────────
   Sits above .site-foot. Dark navy block, on-ink text, single email
   field, stacks on mobile and goes inline at ≥600px. */
.op-news {
  background: var(--ink);
  color: var(--paper);
  border-top: var(--hairline-strong);
}
.op-news .op-news__inner {
  max-width: 1180px; margin: 0 auto;
  padding: 30px var(--gutter) 28px;
}
.op-news__eyebrow {
  margin: 0 0 6px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--flame);
}
.op-news__title {
  margin: 0 0 10px;
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(22px, 3.2vw, 28px); line-height: 1.18;
  letter-spacing: -0.01em;
}
.op-news__lede {
  margin: 0 0 16px;
  font-family: var(--font-serif); font-size: 15px; line-height: 1.5;
  color: rgba(250, 247, 240, 0.82);
  max-width: 60ch;
}
.op-news__form {
  display: flex; flex-direction: column; gap: 10px;
  max-width: 520px;
}
.op-news__form input[type="email"] {
  height: 48px; padding: 0 14px;
  border: 1px solid rgba(217, 210, 192, 0.32);
  border-radius: 4px;
  background: rgba(250, 247, 240, 0.06);
  color: var(--paper);
  font-family: var(--font-sans); font-size: 16px;
  outline: none;
}
.op-news__form input[type="email"]::placeholder { color: rgba(250, 247, 240, 0.48); }
.op-news__form input[type="email"]:focus-visible {
  border-color: var(--flame);
  box-shadow: 0 0 0 2px rgba(217, 70, 28, 0.32);
}
.op-news__form button {
  height: 46px; padding: 0 18px;
  border: 0; border-radius: 4px;
  background: var(--flame); color: #fff;
  font-family: var(--font-sans); font-size: 14px; font-weight: 600;
  letter-spacing: 0.01em;
  cursor: pointer;
}
.op-news__form button:hover { background: var(--flame-deep); }
.op-news__form button:disabled { opacity: 0.6; cursor: progress; }
.op-news__hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
.op-news__success {
  margin: 6px 0 0;
  font-family: var(--font-serif); font-size: 15px;
  color: var(--paper);
}
.op-news__error {
  margin: 4px 0 0;
  font-family: var(--font-sans); font-size: 13px;
  color: #F7C8B8;
}
.op-news__micro {
  margin: 10px 0 0;
  font-family: var(--font-sans); font-size: 12px;
  color: rgba(250, 247, 240, 0.62);
}
.op-news__alt {
  margin: 18px 0 0;
  font-family: var(--font-serif); font-size: 14px;
  color: rgba(250, 247, 240, 0.84);
}
.op-news__alt a {
  color: var(--paper);
  text-decoration: underline; text-decoration-color: var(--flame);
  text-underline-offset: 2px;
}
.op-news__alt a:hover { color: var(--flame); text-decoration-color: var(--flame); }
.op-news a:focus-visible,
.op-news button:focus-visible,
.op-news input:focus-visible {
  outline: 2px solid var(--flame); outline-offset: 2px;
}
@media (min-width: 600px) {
  .op-news__form { flex-direction: row; align-items: stretch; flex-wrap: wrap; }
  .op-news__form input[type="email"] { flex: 1 1 280px; min-width: 0; }
  .op-news__form button { flex: 0 0 auto; }
  .op-news__error, .op-news__success { flex-basis: 100%; }
}

/* ─── NEWSLETTER POP-UP ────────────────────────────────────────────
   Engagement-triggered modal — timer + scroll trigger, suppression
   on /learn, focus trap, scroll lock, ESC + backdrop close. */
body.op-noscroll { overflow: hidden; }
.op-popup-overlay {
  position: fixed; inset: 0;
  background: rgba(14, 34, 64, 0.55);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
  z-index: 1000;
}
.op-popup-overlay[hidden] { display: none; }
.op-popup {
  position: relative;
  width: 100%; max-width: 420px;
  max-height: calc(100vh - 32px); overflow: auto;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(14, 34, 64, 0.28);
  font-family: var(--font-sans);
  color: var(--ink);
}
.op-popup__accent { height: 3px; background: var(--flame); }
.op-popup__body { padding: 26px 24px 24px; position: relative; }
.op-popup__close {
  position: absolute; top: 10px; right: 10px;
  width: 44px; height: 44px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 0; background: transparent;
  color: var(--graphite-soft); font-size: 24px; line-height: 1;
  cursor: pointer; border-radius: 4px;
}
.op-popup__close:hover { color: var(--ink); background: var(--rule-soft); }
.op-popup__close:focus-visible,
.op-popup__btn:focus-visible,
.op-popup__decline:focus-visible {
  outline: 2px solid var(--flame); outline-offset: 2px;
}
.op-popup__eyebrow {
  margin: 0;
  font-size: 11px; font-weight: 700; letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--graphite-soft);
}
.op-popup__title {
  margin: 10px 0 0;
  font-family: var(--font-serif); font-weight: 600;
  font-size: 26px; line-height: 1.14; letter-spacing: -0.01em;
  color: var(--ink);
}
.op-popup__lede {
  margin: 12px 0 0;
  font-family: var(--font-serif); font-size: 16px; line-height: 1.5;
  color: var(--ink-soft);
}
.op-popup__field-label {
  display: block; margin: 20px 0 6px;
  font-size: 12px; font-weight: 500;
}
.op-popup__input {
  width: 100%; height: 48px;
  padding: 0 14px;
  border: 1px solid var(--rule); border-radius: 4px;
  background: var(--paper-pure);
  font-family: var(--font-sans); font-size: 15px;
  color: var(--ink); outline: none;
}
.op-popup__input:focus-visible {
  border-color: var(--flame);
  box-shadow: 0 0 0 2px rgba(217, 70, 28, 0.18);
}
.op-popup__hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
.op-popup__btn {
  margin-top: 14px;
  width: 100%; height: 50px;
  border: 0; border-radius: 4px;
  background: var(--flame); color: #fff;
  font-family: var(--font-sans); font-weight: 600; font-size: 15px;
  cursor: pointer;
}
.op-popup__btn:hover { background: var(--flame-deep); }
.op-popup__btn:disabled { opacity: 0.7; cursor: progress; }
.op-popup__success {
  margin: 18px 0 0;
  font-family: var(--font-serif); font-size: 16px;
  color: var(--ink);
}
.op-popup__error {
  margin: 10px 0 0;
  font-family: var(--font-sans); font-size: 13px;
  color: var(--flame-deep);
}
.op-popup__micro { margin: 12px 0 0; font-size: 12px; color: var(--graphite-soft); }
.op-popup__decline {
  margin-top: 14px;
  width: 100%; border: 0; background: transparent;
  font-family: var(--font-sans); font-size: 13px;
  color: var(--graphite-soft);
  text-decoration: underline; text-underline-offset: 2px;
  cursor: pointer;
}
.op-popup__decline:hover { color: var(--ink); }
.op-popup__form [hidden] { display: none; }
"""

# Standalone newsletter CSS — extracted from the inline CSS block above so
# the editorial-page patcher (which doesn't go through chrome_head) can
# inject the same styles without duplicating them. Kept as a runtime
# slice of CSS to preserve a single source of truth.
_NEWSLETTER_CSS_MARKER = "/* ─── NEWSLETTER FOOTER SIGNUP"
NEWSLETTER_CSS = _NEWSLETTER_CSS_MARKER + CSS.split(_NEWSLETTER_CSS_MARKER, 1)[1]


# ─── Page chrome (shared across all pages) ───

FAVICON_LINKS = """<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
<link rel="apple-touch-icon" sizes="192x192" href="/favicon-192.png">"""


GA_SNIPPET = """<!-- Google Analytics (gtag.js) — only loads on oddsprimer.com -->
<script>
(function(){
  var h = location.hostname;
  if (h !== 'oddsprimer.com' && h !== 'www.oddsprimer.com') return;
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=G-DH4D6X8YRN';
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function(){dataLayer.push(arguments);};
  gtag('js', new Date());
  gtag('config', 'G-DH4D6X8YRN');
})();
</script>"""


def chrome_head(title: str, description: str = "", *, path: str = "/", extra_head: str = "") -> str:
    """Return the <head> section for any page.

    `path` is the absolute URL path of the page being rendered (used for the
    canonical / og:url tag). Defaults to "/" — render_match_page etc. should
    pass their own path so shared links unfurl with the right URL.
    `extra_head` is injected verbatim before </head> (e.g. <meta name="robots">)."""
    desc = description or "Educational verdicts on Polymarket and Kalshi prices. Pick · Pass · Avoid."
    base = BASE_URL
    url = base + path
    og_image = f"{base}/favicon-192.png"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{escape(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Odds Primer">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:image" content="{escape(og_image)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(desc)}">
<meta name="twitter:image" content="{escape(og_image)}">
{FAVICON_LINKS}
{GA_SNIPPET}
<script src="/js/activity.js" defer></script>
{extra_head}
<style>{CSS}</style>
</head>
<body>
"""


def _relative_updated(iso: str | None) -> str:
    """Render 'Updated N mins/hours/days ago' from an ISO timestamp."""
    if not iso:
        return "moments ago"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(tz=timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 90:
            return "moments ago"
        mins = secs // 60
        if mins < 60:
            return f"{mins} min{'s' if mins != 1 else ''} ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours} hr{'s' if hours != 1 else ''} ago"
        days = hours // 24
        return f"{days} day{'s' if days != 1 else ''} ago"
    except (ValueError, AttributeError):
        return "moments ago"


def _fmt_short_utc(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        return "—"


def _desk_last_refresh_utc() -> datetime | None:
    """Most-recent timestamp the Desk pipeline published — read from the
    `updated_at` field of the football and outrights `index.json` files.
    Falls back to None if neither exists (fresh checkout)."""
    stamps: list[datetime] = []
    for idx in (FOOTBALL_DIR / "index.json", OUTRIGHTS_DIR / "index.json"):
        if not idx.exists():
            continue
        try:
            blob = json.loads(idx.read_text())
            iso  = blob.get("updated_at")
            if iso:
                stamps.append(datetime.fromisoformat(iso.replace("Z", "+00:00")))
        except (json.JSONDecodeError, ValueError):
            continue
    return max(stamps) if stamps else None


def chrome_masthead(active: str, edition_label: str = "World Cup 2026") -> str:
    """Masthead + edition strip. `active` is one of 'home' / 'matches' / 'outrights'."""
    def cur(name: str) -> str:
        return ' aria-current="page"' if active == name else ""
    last_run = _desk_last_refresh_utc()
    if last_run is not None:
        updated = last_run.strftime("Last refresh %H:%M UTC")
    else:
        updated = "Awaiting first refresh"
    return f"""<header class="site-masthead">
  <div class="inner">
    <a class="brand-lock" href="/" aria-label="Odds Primer home">
      <span class="wm-row">
        <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
          <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
          <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
          <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
          <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
        </svg>
        <span class="wm">Odds Primer</span>
      </span>
      <span class="tag">Independent football market analysis</span>
    </a>
    <nav class="site-nav" aria-label="Primary">
      <ul>
        <li><a href="/"{cur('home')}>Home</a></li>
        <li><a href="/matches/"{cur('matches')}>Upcoming matches</a></li>
        <li><a href="/outrights/"{cur('outrights')}>Outright winner</a></li>
        <li><a href="/methodology"{cur('methodology')}>How it works</a></li>
        <li><a href="/about"{cur('about')}>About</a></li>
      </ul>
    </nav>
    <span class="nav-meta">{updated}</span>
    <details class="burger">
      <summary class="burger-btn" aria-label="More links">
        <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
          <rect y="0"  width="16" height="1.5" fill="currentColor"/>
          <rect y="5"  width="16" height="1.5" fill="currentColor"/>
          <rect y="10" width="16" height="1.5" fill="currentColor"/>
        </svg>
      </summary>
      <ul class="burger-menu">
        <li><a href="/"{cur('home')}>Home</a></li>
        <li><a href="/matches/"{cur('matches')}>Upcoming matches</a></li>
        <li><a href="/outrights/"{cur('outrights')}>Outright winner</a></li>
        <li><a href="/methodology"{cur('methodology')}>How it works</a></li>
        <li><a href="/about"{cur('about')}>About</a></li>
        <li><a href="/responsible-use">Responsible use</a></li>
        <li><a href="/affiliate-disclosure">Affiliate disclosure</a></li>
        <li><a href="/corrections">Corrections</a></li>
      </ul>
    </details>
  </div>
  <div class="edition-strip">
    <div class="inner">
      <span class="vol">Vol. 1 · {escape(edition_label)}</span>
      <span class="live">Markets live</span>
    </div>
  </div>
  <nav class="pill-nav" aria-label="Primary (mobile)">
    <a href="/"{cur('home')}>Home</a>
    <a href="/matches/"{cur('matches')}>Matches</a>
    <a href="/outrights/"{cur('outrights')}>Outright</a>
    <a href="/methodology"{cur('methodology')}>How it works</a>
    <a href="/about"{cur('about')}>About</a>
  </nav>
</header>
"""


def newsletter_footer_block() -> str:
    """Footer signup block — rendered above the regular .site-foot bar.
    Returns "" when Mailchimp env vars aren't set, so dev builds without
    credentials skip the form entirely instead of showing a broken one."""
    if not NEWSLETTER_CONFIGURED:
        return ""
    hp = escape(NEWSLETTER_HONEYPOT_NAME)
    return f"""<section class="op-news" aria-labelledby="op-news-title">
  <div class="op-news__inner">
    <p class="op-news__eyebrow">New to prediction markets?</p>
    <h2 class="op-news__title" id="op-news-title">Start with the weekly primer.</h2>
    <p class="op-news__lede">Plain-English notes on prediction markets and World Cup prices before you read the verdicts.</p>
    <form class="op-news__form" id="op-news-form" novalidate>
      <label class="visually-hidden" for="op-news-email">Email address</label>
      <input type="email" name="EMAIL" id="op-news-email" placeholder="you@email.com" required autocomplete="email">
      <div class="op-news__hp" aria-hidden="true">
        <input type="text" name="{hp}" tabindex="-1" value="" autocomplete="off">
      </div>
      <button type="submit">Get the primer</button>
      <p class="op-news__error" id="op-news-error" role="alert" hidden></p>
      <p class="op-news__success" id="op-news-success" role="status" hidden>You&rsquo;re in &mdash; check your inbox.</p>
    </form>
    <p class="op-news__micro">Free. Weekly. Educational only. Unsubscribe anytime.</p>
    <p class="op-news__alt">Prefer to just read? Start here: <a href="/learn/read-a-price">How to read a price</a></p>
  </div>
</section>
"""


def newsletter_popup_block() -> str:
    """Modal pop-up + inline JS for trigger/focus-trap/Mailchimp JSON-P.
    Mirrors the React NewsletterPopup component verbatim in behaviour:
    50s timer (15s on high-intent paths), 50% scroll trigger, suppress on
    /learn, dismissals 10d / subscribers 365d in localStorage."""
    if not NEWSLETTER_CONFIGURED or NEWSLETTER_POPUP_DISABLED:
        return ""
    hp_attr     = escape(NEWSLETTER_HONEYPOT_NAME)
    endpoint_js = json.dumps(SUBSCRIBE_ENDPOINT)
    hp_js       = json.dumps(NEWSLETTER_HONEYPOT_NAME)
    return f"""<div class="op-popup-overlay" id="op-popup" hidden>
  <section class="op-popup" role="dialog" aria-modal="true" aria-labelledby="op-popup-title">
    <div class="op-popup__accent" aria-hidden="true"></div>
    <div class="op-popup__body">
      <button type="button" class="op-popup__close" id="op-popup-close" aria-label="Close newsletter sign-up">
        <span aria-hidden="true">&times;</span>
      </button>
      <p class="op-popup__eyebrow">The newsletter</p>
      <h2 class="op-popup__title" id="op-popup-title">Read World Cup odds before the verdicts arrive.</h2>
      <p class="op-popup__lede">One weekly primer on prediction markets and how to understand a price. No betting advice. No hype.</p>
      <form class="op-popup__form" id="op-popup-form" novalidate>
        <label class="op-popup__field-label" for="op-popup-email">Email address</label>
        <input class="op-popup__input" type="email" name="EMAIL" id="op-popup-email" placeholder="you@email.com" required autocomplete="email">
        <div class="op-popup__hp" aria-hidden="true">
          <input type="text" name="{hp_attr}" tabindex="-1" value="" autocomplete="off">
        </div>
        <button class="op-popup__btn" type="submit" id="op-popup-submit">Get the weekly primer</button>
        <p class="op-popup__error" id="op-popup-error" role="alert" hidden></p>
      </form>
      <p class="op-popup__success" id="op-popup-success" role="status" hidden>You&rsquo;re in &mdash; check your inbox.</p>
      <p class="op-popup__micro">Free. One email a week. Unsubscribe anytime.</p>
      <button type="button" class="op-popup__decline" id="op-popup-decline">Continue reading</button>
    </div>
  </section>
</div>
<script>
(function () {{
  var ENDPOINT = {endpoint_js};
  var HONEYPOT = {hp_js};

  var POPUP_DELAY_MS    = 50000;
  var HIGH_INTENT_MS    = 15000;
  var SCROLL_TRIGGER    = 0.5;
  var DISMISS_DAYS      = 10;
  var SUBSCRIBED_DAYS   = 365;
  var SUPPRESS_PATHS    = ['/learn'];
  var HIGH_INTENT_PATHS = ['/matches', '/match', '/outrights'];
  var STORAGE_KEY       = 'op_newsletter_popup';
  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])';

  var popup    = document.getElementById('op-popup');
  var form     = document.getElementById('op-popup-form');
  var emailEl  = document.getElementById('op-popup-email');
  var submitEl = document.getElementById('op-popup-submit');
  var errEl    = document.getElementById('op-popup-error');
  var okEl     = document.getElementById('op-popup-success');
  if (!popup || !form) return;

  var path = location.pathname;
  var lastFocus = null;
  var fired = false;

  function startsAny(list) {{
    for (var i = 0; i < list.length; i++) {{
      if (path === list[i] || path.indexOf(list[i] + '/') === 0) return true;
    }}
    return false;
  }}
  function readStored() {{
    try {{
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var v = JSON.parse(raw);
      if (v && v.exp && Date.now() > v.exp) {{ localStorage.removeItem(STORAGE_KEY); return null; }}
      return v ? v.status : null;
    }} catch (e) {{ return null; }}
  }}
  function writeStored(status, days) {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify({{ status: status, exp: Date.now() + days * 864e5 }})); }} catch (e) {{}}
  }}

  function trap(e) {{
    if (e.key === 'Escape') {{ e.preventDefault(); close('dismissed', DISMISS_DAYS); return; }}
    if (e.key !== 'Tab') return;
    var nodes = popup.querySelectorAll(FOCUSABLE);
    if (!nodes.length) return;
    var first = nodes[0], last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {{ e.preventDefault(); last.focus(); }}
    else if (!e.shiftKey && document.activeElement === last) {{ e.preventDefault(); first.focus(); }}
  }}
  function open() {{
    if (fired || readStored() || startsAny(SUPPRESS_PATHS)) return;
    fired = true;
    lastFocus = document.activeElement;
    popup.hidden = false;
    document.body.classList.add('op-noscroll');
    document.addEventListener('keydown', trap);
    if (emailEl) emailEl.focus();
  }}
  function close(status, days) {{
    popup.hidden = true;
    document.body.classList.remove('op-noscroll');
    document.removeEventListener('keydown', trap);
    if (status) writeStored(status, days || DISMISS_DAYS);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }}

  // ── trigger: timer + scroll, one-shot ──
  if (!readStored() && !startsAny(SUPPRESS_PATHS)) {{
    var delay = startsAny(HIGH_INTENT_PATHS) ? HIGH_INTENT_MS : POPUP_DELAY_MS;
    setTimeout(open, delay);
    window.addEventListener('scroll', function onScroll() {{
      if (fired) {{ window.removeEventListener('scroll', onScroll); return; }}
      var h = document.documentElement;
      var max = (h.scrollHeight - h.clientHeight) || 1;
      var depth = (h.scrollTop || document.body.scrollTop) / max;
      if (depth >= SCROLL_TRIGGER) {{ window.removeEventListener('scroll', onScroll); open(); }}
    }}, {{ passive: true }});
  }}

  document.getElementById('op-popup-close').addEventListener('click', function () {{ close('dismissed', DISMISS_DAYS); }});
  document.getElementById('op-popup-decline').addEventListener('click', function () {{ close('dismissed', DISMISS_DAYS); }});
  popup.addEventListener('click', function (e) {{ if (e.target === popup) close('dismissed', DISMISS_DAYS); }});

  // ── submit via backend → SendX ──
  form.addEventListener('submit', function (e) {{
    e.preventDefault();
    if (submitEl.disabled) return;
    var email = (emailEl.value || '').trim();
    if (!email) return;
    var hpEl = form.querySelector('input[name="' + HONEYPOT + '"]');
    var hp = hpEl ? (hpEl.value || '') : '';
    submitEl.disabled = true;
    submitEl.textContent = 'Sending';
    errEl.hidden = true;

    function fail(msg) {{
      submitEl.disabled = false;
      submitEl.textContent = 'Get the weekly primer';
      errEl.textContent = msg || 'Something went wrong. Please try again.';
      errEl.hidden = false;
    }}
    function ok() {{
      form.hidden = true;
      okEl.hidden = false;
      writeStored('subscribed', SUBSCRIBED_DAYS);
    }}

    var ctrl = new AbortController();
    var to = setTimeout(function () {{ ctrl.abort(); }}, 10000);

    fetch(ENDPOINT, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ email: email, hp: hp }}),
      signal: ctrl.signal
    }}).then(function (resp) {{
      clearTimeout(to);
      if (resp.ok) {{ ok(); return; }}
      return resp.json().catch(function () {{ return {{}}; }}).then(function (data) {{
        if (resp.status === 429) fail("You're going a little fast — try again in a moment.");
        else fail((data && data.detail) ? data.detail : 'Something went wrong. Please try again.');
      }});
    }}).catch(function (err) {{
      clearTimeout(to);
      fail(err && err.name === 'AbortError'
        ? 'That took longer than expected. Please try again.'
        : 'Could not reach the newsletter service. Please try again.');
    }});
  }});
}})();
</script>
"""


def newsletter_footer_form_js() -> str:
    """Footer-signup form handler — same JSON-P submit path as the popup,
    scoped to the #op-news-form element. Kept separate so the popup can be
    suppressed on /learn while the footer form still works there."""
    if not NEWSLETTER_CONFIGURED:
        return ""
    endpoint_js = json.dumps(SUBSCRIBE_ENDPOINT)
    hp_js       = json.dumps(NEWSLETTER_HONEYPOT_NAME)
    return f"""<script>
(function () {{
  var ENDPOINT = {endpoint_js};
  var HONEYPOT = {hp_js};
  var SUBSCRIBED_DAYS = 365;
  var STORAGE_KEY     = 'op_newsletter_popup';

  var form = document.getElementById('op-news-form');
  if (!form) return;
  var submitEl = form.querySelector('button[type="submit"]');
  var emailEl  = form.querySelector('input[type="email"]');
  var errEl    = document.getElementById('op-news-error');
  var okEl     = document.getElementById('op-news-success');

  function writeStored(status, days) {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify({{ status: status, exp: Date.now() + days * 864e5 }})); }} catch (e) {{}}
  }}

  form.addEventListener('submit', function (e) {{
    e.preventDefault();
    if (submitEl.disabled) return;
    var email = (emailEl.value || '').trim();
    if (!email) return;
    var hpEl = form.querySelector('input[name="' + HONEYPOT + '"]');
    var hp = hpEl ? (hpEl.value || '') : '';
    submitEl.disabled = true;
    var origLabel = submitEl.textContent;
    submitEl.textContent = 'Sending';
    errEl.hidden = true;

    function fail(msg) {{
      submitEl.disabled = false;
      submitEl.textContent = origLabel;
      errEl.textContent = msg || 'Something went wrong. Please try again.';
      errEl.hidden = false;
    }}
    function ok() {{
      form.hidden = true;
      okEl.hidden = false;
      writeStored('subscribed', SUBSCRIBED_DAYS);
    }}

    var ctrl = new AbortController();
    var to = setTimeout(function () {{ ctrl.abort(); }}, 10000);

    fetch(ENDPOINT, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ email: email, hp: hp }}),
      signal: ctrl.signal
    }}).then(function (resp) {{
      clearTimeout(to);
      if (resp.ok) {{ ok(); return; }}
      return resp.json().catch(function () {{ return {{}}; }}).then(function (data) {{
        if (resp.status === 429) fail("You're going a little fast — try again in a moment.");
        else fail((data && data.detail) ? data.detail : 'Something went wrong. Please try again.');
      }});
    }}).catch(function (err) {{
      clearTimeout(to);
      fail(err && err.name === 'AbortError'
        ? 'That took longer than expected. Please try again.'
        : 'Could not reach the newsletter service. Please try again.');
    }});
  }});
}})();
</script>
"""


EDITORIAL_PAGES = (
    "about", "learn",
    "method", "methodology",
    "responsible-use", "affiliate-disclosure", "corrections",
    "terms", "privacy", "cookies", "404",
)


def patch_editorial_pages(log=print) -> None:
    """Inject (or strip) the newsletter pop-up + footer signup in every
    hand-written editorial HTML file under site/public/, and rewrite the
    legacy inline nav (primary, burger, pill-nav) to match chrome_masthead.

    Idempotent: each injection is wrapped in HTML-comment markers so a
    re-run strips the previous insertion and rewrites it from the
    current env vars. When NEWSLETTER_CONFIGURED is false, the function
    runs anyway but only strips — useful for local generation that
    deliberately omits Mailchimp creds."""
    import re

    css_start  = "<!-- op-newsletter-css-start -->"
    css_end    = "<!-- op-newsletter-css-end -->"
    foot_start = "<!-- op-newsletter-footer-start -->"
    foot_end   = "<!-- op-newsletter-footer-end -->"
    pop_start  = "<!-- op-newsletter-popup-start -->"
    pop_end    = "<!-- op-newsletter-popup-end -->"

    foot_block = newsletter_footer_block()
    popup_block = newsletter_popup_block() + newsletter_footer_form_js()

    def strip_between(html: str, a: str, b: str) -> str:
        # Also consume newlines adjacent to the markers — the inject
        # always prefixes/suffixes its own `\n`, so without this each
        # re-run accumulated one blank line per injection point.
        return re.sub(
            r"\n*" + re.escape(a) + r".*?" + re.escape(b) + r"\n*",
            "", html, flags=re.DOTALL,
        )

    # Canonical nav contents (must match chrome_masthead order). We rewrite
    # the legacy editorial pages' inline nav blocks to these so the pill
    # nav + burger menu + primary nav all stay in sync with the live chrome.
    def _legacy_site_nav_ul_for(slug: str) -> str:
        def attr(s: str) -> str:
            return ' aria-current="page"' if s == slug else ""
        return (
            f'\n          <li><a href="/"{attr("home")}>Home</a></li>'
            f'\n          <li><a href="/matches/"{attr("matches")}>Upcoming matches</a></li>'
            f'\n          <li><a href="/outrights/"{attr("outrights")}>Outright winner</a></li>'
            f'\n          <li><a href="/methodology"{attr("methodology")}>How it works</a></li>'
            f'\n          <li><a href="/about"{attr("about")}>About</a></li>'
            f'\n        '
        )

    def _legacy_burger_ul_for(slug: str) -> str:
        def attr(s: str) -> str:
            return ' aria-current="page"' if s == slug else ""
        return (
            f'\n          <li><a href="/"{attr("home")}>Home</a></li>'
            f'\n          <li><a href="/matches/"{attr("matches")}>Upcoming matches</a></li>'
            f'\n          <li><a href="/outrights/"{attr("outrights")}>Outright winner</a></li>'
            f'\n          <li><a href="/methodology"{attr("methodology")}>How it works</a></li>'
            f'\n          <li><a href="/about"{attr("about")}>About</a></li>'
            f'\n          <li><a href="/responsible-use">Responsible use</a></li>'
            f'\n          <li><a href="/affiliate-disclosure">Affiliate disclosure</a></li>'
            f'\n          <li><a href="/corrections">Corrections</a></li>'
            f'\n        '
        )
    # Page-level pill-nav builder. Marks the current page as aria-current
    # so the active pill (Matches / The Desk / etc.) renders filled. The
    # legacy editorial pages map onto these slugs via _CURRENT_PILL_FOR.
    def _legacy_pill_inner_for(slug: str) -> str:
        def attr(s: str) -> str:
            return ' aria-current="page"' if s == slug else ""
        return (
            f'\n      <a href="/"{attr("home")}>Home</a>'
            f'\n      <a href="/matches/"{attr("matches")}>Matches</a>'
            f'\n      <a href="/outrights/"{attr("outrights")}>Outright</a>'
            f'\n      <a href="/methodology"{attr("methodology")}>How it works</a>'
            f'\n      <a href="/about"{attr("about")}>About</a>'
            f'\n    '
        )

    # Page-name → pill slug mapping. Pages not listed get no active pill
    # (e.g. /responsible-use, /404).
    _CURRENT_PILL_FOR = {
        "about":       "about",
        "learn":       "learn",
        "method":      "methodology",
        "methodology": "methodology",
    }

    _SITE_NAV_RE = re.compile(
        r'(<nav class="site-nav"[^>]*>\s*<ul>)(.*?)(</ul>\s*</nav>)',
        flags=re.DOTALL,
    )
    _BURGER_RE = re.compile(
        r'(<ul class="burger-menu">)(.*?)(</ul>)',
        flags=re.DOTALL,
    )
    _PILL_RE = re.compile(
        r'(<nav class="pill-nav"[^>]*>)(.*?)(</nav>)',
        flags=re.DOTALL,
    )

    # Replace the legacy hand-written edition-strip text ("World Cup 2026 ·
    # Matchday 2" / "Updated 13 May 2026") with the same dynamic shape the
    # new chrome_masthead emits ("Vol. 1 · World Cup 2026" / "Markets live").
    _EDITION_STRIP_RE = re.compile(
        r'(<div class="edition-strip">\s*<div class="inner">)(.*?)(</div>\s*</div>)',
        flags=re.DOTALL,
    )
    legacy_edition_strip_inner = (
        '\n        <span class="vol">Vol. 1 · World Cup 2026</span>'
        '\n        <span class="live">Markets live</span>'
        '\n      '
    )

    # Strip the "Outright winners" link from the hand-authored .foot-col
    # editorial column on legacy editorial pages.
    _FOOT_OUTRIGHT_RE = re.compile(
        r'\n\s*<li><a href="/outrights/?">Outright winners</a></li>',
    )

    # Normalise the brand-lock tagline + aria-label across every editorial
    # page. The legacy hand-written pages shipped with "The AI sports desk
    # for market edge"; the new locked lockup uses "Independent football
    # market analysis". Without this rewrite, /responsible-use, /privacy,
    # /terms etc. keep showing the old tagline while /, /matches and
    # /methodology show the new one — exactly the inconsistency the
    # operator flagged on 2026-05-26.
    _BRAND_TAGLINE_RE = re.compile(
        r'(<span class="tag">)(.*?)(</span>\s*</a>)',
        flags=re.DOTALL,
    )
    canonical_tagline_inner = "Independent football market analysis"
    _BRAND_ARIA_RE = re.compile(
        r'(<a class="brand-lock"[^>]*\baria-label=")[^"]*(")',
    )
    canonical_brand_aria = "Odds Primer home"

    # CSS override block — re-styles the legacy pill-nav + edition-strip
    # so they match the new chrome's pill outline + dot indicator. The
    # legacy inline CSS still defines the masthead/brand; this block only
    # overrides the diverging rules.
    chrome_override_start = "<!-- op-chrome-override-start -->"
    chrome_override_end   = "<!-- op-chrome-override-end -->"
    chrome_override_css = (
        "\n" + chrome_override_start + "\n"
        "<style>\n"
        "/* Legacy-page chrome override — pill-nav gets the same outlined\n"
        "   pill look as the canonical chrome on /, /matches, /m/*. */\n"
        ".pill-nav a {\n"
        "  border: 1px solid var(--rule, #d9d2c0);\n"
        "  padding: 11px 16px; min-height: 44px;\n"
        "  display: inline-flex; align-items: center;\n"
        "  font-size: 13px;\n"
        "}\n"
        ".pill-nav a[aria-current=\"page\"] {\n"
        "  background: var(--ink, #0e2240); color: var(--paper, #faf7f0);\n"
        "  border-color: var(--ink, #0e2240);\n"
        "}\n"
        ".pill-nav a:not([aria-current=\"page\"]):hover {\n"
        "  color: var(--flame-deep, #b8390f); border-color: var(--flame, #d9461c);\n"
        "}\n"
        "/* Edition strip — dot indicator on the right-hand label. */\n"
        ".edition-strip .vol { color: var(--ink, #0e2240); }\n"
        ".edition-strip .live::before {\n"
        "  content: \"\"; display: inline-block;\n"
        "  width: 6px; height: 6px; border-radius: 999px;\n"
        "  background: var(--flame, #d9461c);\n"
        "  margin-right: 8px; vertical-align: 1px;\n"
        "}\n"
        "/* Wordmark — switch from Inter Tight to Source Serif 4 to match the\n"
        "   new locked lockup (2026-05-26). Re-sized to keep optical parity. */\n"
        ".brand-lock .wm {\n"
        "  font-family: \"Source Serif 4\", Charter, Georgia, serif !important;\n"
        "  font-weight: 700 !important;\n"
        "  font-size: 24px !important;\n"
        "  letter-spacing: -0.01em !important;\n"
        "}\n"
        "/* Hide the desktop burger above 820px so legacy pages match the\n"
        "   canonical chrome (home/matches/m/*). Without this the legacy\n"
        "   inline CSS leaves the burger visible at desktop widths. */\n"
        "@media (min-width: 820px) { .burger { display: none !important; } }\n"
        "/* Drop the baseline rule under the glyph bars — the new locked\n"
        "   lockup (2026-05-26) ships without it. The legacy inline SVG\n"
        "   still renders the <line>; hide it visually. */\n"
        ".brand-lock svg line { display: none !important; }\n"
        "</style>\n"
        + chrome_override_end + "\n"
    )

    n_patched = 0
    for name in EDITORIAL_PAGES:
        path = SITE_OUT / f"{name}.html"
        if not path.is_file():
            continue
        html = path.read_text()
        before = html

        # Rewrite the legacy nav blocks to match chrome_masthead.
        active_slug = _CURRENT_PILL_FOR.get(name, "")
        pill_inner = _legacy_pill_inner_for(active_slug)
        site_nav_ul = _legacy_site_nav_ul_for(active_slug)
        burger_ul = _legacy_burger_ul_for(active_slug)
        html = _SITE_NAV_RE.sub(
            lambda m: m.group(1) + site_nav_ul + m.group(3),
            html, count=1,
        )
        html = _BURGER_RE.sub(
            lambda m: m.group(1) + burger_ul + m.group(3),
            html, count=1,
        )
        html = _PILL_RE.sub(
            lambda m: m.group(1) + pill_inner + m.group(3),
            html, count=1,
        )
        html = _EDITION_STRIP_RE.sub(
            lambda m: m.group(1) + legacy_edition_strip_inner + m.group(3),
            html, count=1,
        )
        html = _FOOT_OUTRIGHT_RE.sub("", html)
        # Normalise tagline + aria-label on the brand-lock.
        html = _BRAND_TAGLINE_RE.sub(
            lambda m: m.group(1) + canonical_tagline_inner + m.group(3),
            html, count=1,
        )
        html = _BRAND_ARIA_RE.sub(
            lambda m: m.group(1) + canonical_brand_aria + m.group(2),
            html, count=1,
        )

        # Always strip any previous injection so re-runs don't double up.
        html = strip_between(html, css_start,  css_end)
        html = strip_between(html, foot_start, foot_end)
        html = strip_between(html, pop_start,  pop_end)
        html = strip_between(html, chrome_override_start, chrome_override_end)

        # Inject the chrome override CSS into every editorial page,
        # regardless of NEWSLETTER_CONFIGURED — the override is required for
        # the legacy chrome to match the canonical chrome.
        if "</head>" in html:
            html = html.replace("</head>", chrome_override_css + "</head>", 1)

        if NEWSLETTER_CONFIGURED:
            # CSS goes in its own <style> block right before </head> —
            # avoids splicing into the existing hand-written inline CSS.
            css_inject = (
                f"\n{css_start}\n<style>{NEWSLETTER_CSS}</style>\n{css_end}\n"
            )
            if "</head>" in html:
                html = html.replace("</head>", css_inject + "</head>", 1)

            # Footer signup sits immediately above the existing
            # <footer class="site-footer"> markup.
            foot_inject = f"\n{foot_start}\n{foot_block}\n{foot_end}\n"
            html = html.replace(
                '<footer class="site-footer">',
                foot_inject + '<footer class="site-footer">',
                1,
            )

            # Popup + JS sits right before </body>.
            pop_inject = f"\n{pop_start}\n{popup_block}\n{pop_end}\n"
            html = html.replace("</body>", pop_inject + "</body>", 1)

        if html != before:
            path.write_text(html)
            n_patched += 1

    if n_patched:
        verb = "patched" if NEWSLETTER_CONFIGURED else "stripped"
        log(f"Editorial      : {verb} newsletter blocks in {n_patched} page(s)")


def chrome_footer() -> str:
    today = datetime.now(timezone.utc).strftime("%-d %b %Y")
    return f"""{newsletter_footer_block()}<footer class="site-foot page">
  <div class="foot-trust">
    <p class="ft-disclaimer">
      Editorial analysis only. Odds Primer does not provide betting, investment, or financial advice.
    </p>
    <p class="ft-data">
      <span class="ft-lbl">Data sources:</span>
      Polymarket, Kalshi, public football data, internal model estimates.
    </p>
    <p class="ft-contact">
      <span class="ft-lbl">Corrections &amp; contact:</span>
      <a href="mailto:editor@oddsprimer.com">editor@oddsprimer.com</a>
    </p>
  </div>
  <div class="foot-row">
    <span class="left">Odds Primer · Independent editorial</span>
    <span>The Desk · v1.1 · {today}</span>
  </div>
  <nav class="foot-nav" aria-label="Trust and editorial">
    <a href="/responsible-use">Responsible use</a>
    <a href="/affiliate-disclosure">Affiliate disclosure</a>
    <a href="/corrections">Corrections</a>
    <a href="/methodology">Methodology</a>
    <a href="/terms">Terms</a>
    <a href="/privacy">Privacy</a>
    <a href="/cookies">Cookies</a>
  </nav>
</footer>
{newsletter_popup_block()}{newsletter_footer_form_js()}</body>
</html>
"""


# ─── Formatting helpers ───

def fmt_pct(p):
    if p is None: return "—"
    return f"{round(p * 100)}%"

def fmt_edge(edge_pp):
    if edge_pp is None: return None
    sign = "+" if edge_pp >= 0 else "−"
    return f"{sign}{abs(edge_pp):.1f} pts"

def _sanitize_copy(text: str | None) -> str:
    """Replace internal jargon in editorial copy with plain English.
    Applied at render time so the source JSON files stay untouched."""
    if not text:
        return text or ""
    # "Our prior reads X%" → "Our model projects X%"
    text = re.sub(r"\bOur prior reads\b", "Our model projects", text)
    # "Our Elo prior" → "Our model"
    text = re.sub(r"\bOur Elo prior\b", "Our model", text)
    # "Elo prior" standalone → "model estimate"
    text = re.sub(r"\bElo prior\b", "model estimate", text)
    # ", a +Xpp upgrade that crosses the Pick threshold comfortably" → " — making this a Pick"
    text = re.sub(
        r",\s*a \+[\d.]+pp upgrade that crosses the Pick threshold comfortably",
        " — making this a Pick",
        text,
    )
    # "crosses the Pick threshold" (any remaining) → "makes this a Pick"
    text = re.sub(r"\bcrosses the Pick threshold\b", "makes this a Pick", text)
    # "The +Xpp gap calls a Pick" → "That gap makes this a Pick"
    text = re.sub(r"The \+[\d.]+ pts gap calls a Pick", "That gap makes this a Pick", text)
    text = re.sub(r"The \+([\d.]+)pp gap calls a Pick", r"That +\1 pts gap makes this a Pick", text)
    # "The +Xpp gap is the Pick" → "That gap is a Pick"
    text = re.sub(r"The \+([\d.]+)pp gap is the Pick", r"That +\1 pts gap is a Pick", text)
    # "A +Xpp gap across" → "A X pts gap across"
    text = re.sub(r"A \+([\d.]+)pp gap\b", r"A \1 pts gap", text)
    # all remaining "+Xpp" → "+X pts"
    text = re.sub(r"\+([\d.]+)pp\b", r"+\1 pts", text)
    # remaining "Xpp" → "X pts"
    text = re.sub(r"\b([\d.]+)pp\b", r"\1 pts", text)
    # "threshold comfortably" → trim trailing adverb
    text = re.sub(r"\s+comfortably\.", ".", text)
    return text


def fmt_kickoff_short(iso: str) -> str:
    """'Fri · 19:00 UTC'"""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%a · %H:%M UTC")

def fmt_kickoff_date(iso: str) -> str:
    """'Friday 12 June 2026'"""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%A %-d %B %Y")

def fmt_kickoff_full(iso: str) -> str:
    """'Fri 12 Jun · 19:00 UTC'"""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%a %-d %b · %H:%M UTC")

def kickoff_date_key(iso: str) -> str:
    """YYYY-MM-DD for grouping."""
    return iso[:10]

def venue_name_from_url(market_url: str | None) -> str | None:
    """Derive a display venue name from a market URL. Used as a fallback
    when verdict.market_venue isn't populated (e.g. Pass rows).
    """
    if not market_url:
        return None
    low = market_url.lower()
    if "polymarket.com" in low:
        return "Polymarket"
    if "kalshi.com" in low:
        return "Kalshi"
    return None


def venue_label_for(verdict: dict) -> str | None:
    """Best display string for the venue: explicit field first, then derived."""
    explicit = (verdict.get("market_venue") or "").strip()
    if explicit:
        return explicit.title()
    return venue_name_from_url(verdict.get("market_url"))


def _polymarket_url_for(verdict: dict, fallback_search: str | None = None) -> str:
    """Polymarket URL — use the explicit one when present, fall back to a
    search on the event slug. Never returns empty; the venue is always
    surfaceable.

    Safety net: Polymarket migrated WC 2026 match pages from
    `/event/{slug}` to `/sports/world-cup/{slug}` (the old paths
    404). We detect stale URLs and rewrite them at build-time so a
    `verdict.market_url` written by an older tick still resolves.
    """
    url = (verdict.get("market_url") or "").strip()
    if url and "polymarket.com" in url.lower():
        return _normalise_polymarket_url(url)
    # No explicit Polymarket URL → degrade to a search.
    if fallback_search:
        from urllib.parse import quote_plus
        return f"https://polymarket.com/markets?_q={quote_plus(fallback_search)}"
    return "https://polymarket.com/"


def _normalise_polymarket_url(url: str) -> str:
    """Rewrite Polymarket URLs that still point at retired paths.
    Safe to call on already-correct URLs.

    Three known rewrites today:
      - per-match: `/event/fifwc-...` → `/sports/world-cup/fifwc-...`
      - per-match (older shim): `/sports/fifa-world-cup/fifwc-...` →
        `/sports/world-cup/fifwc-...` (Polymarket dropped the "fifa-"
        prefix from the WC path)
      - outright winner: `/event/2026-fifa-world-cup-winner-595` →
        `/event/world-cup-winner` (the canonical short slug Polymarket
        now uses on its UI).
    """
    old_event = "polymarket.com/event/fifwc-"
    new_path = "polymarket.com/sports/world-cup/fifwc-"
    if old_event in url:
        url = url.replace(old_event, new_path, 1)
    legacy_sports = "polymarket.com/sports/fifa-world-cup/fifwc-"
    if legacy_sports in url:
        url = url.replace(legacy_sports, new_path, 1)
    outright_old = "polymarket.com/event/2026-fifa-world-cup-winner-595"
    outright_new = "polymarket.com/event/world-cup-winner"
    if outright_old in url:
        url = url.replace(outright_old, outright_new, 1)
    return url


KALSHI_WC_LANDING = "https://kalshi.com/category/sports/soccer/fifa-world-cup"

_KALSHI_MONTH_TO_NUM = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Kalshi tri-letter codes don't match the Polymarket ones we use in
# our match-ids 1:1 — Kalshi mixes ISO3 (DZA, HTI) and IOC (SUI, IRI)
# while we follow whatever Polymarket put in its event slug. Map both
# directions so the WC26 event index can be looked up by our codes
# and the picked-side market ticker can be built in Kalshi's codes.
_KALSHI_CODE_TO_OURS = {
    "sui": "che",   # Switzerland (Kalshi IOC → ISO3)
    "hti": "hai",   # Haiti (Kalshi ISO3 → IOC)
    "iri": "irn",   # Iran (Kalshi IOC → ISO3)
    "dza": "alg",   # Algeria (Kalshi ISO3 → IOC)
}
_OURS_TO_KALSHI_CODE = {v: k for k, v in _KALSHI_CODE_TO_OURS.items()}


def _kalshi_to_our_code(code: str) -> str:
    return _KALSHI_CODE_TO_OURS.get(code.lower(), code.lower())


def _our_to_kalshi_code(code: str) -> str:
    return _OURS_TO_KALSHI_CODE.get(code.lower(), code.lower())


def _load_kalshi_event_index() -> dict[tuple, str]:
    """Fetch Kalshi's WC 2026 game series, return a fixture-keyed event index.

    Key: (kickoff_date, frozenset({iso3_a_lower, iso3_b_lower})).
    Value: full event_ticker string, e.g. "KXWCGAME-26JUN11MEXRSA".

    Pure stdlib (urllib) so generate.py stays dependency-free. On any
    network failure, returns {} and CTAs fall back to the WC landing.
    """
    import urllib.request, urllib.error
    from datetime import date as _date

    events: list[dict] = []
    cursor: str | None = None
    base = "https://api.elections.kalshi.com/trade-api/v2/events"
    try:
        while True:
            qs = "series_ticker=KXWCGAME&limit=200"
            if cursor:
                from urllib.parse import quote
                qs += f"&cursor={quote(cursor)}"
            with urllib.request.urlopen(f"{base}?{qs}", timeout=10) as r:
                payload = json.loads(r.read().decode("utf-8")) or {}
            page = payload.get("events") or []
            events.extend(page)
            cursor = payload.get("cursor")
            if not cursor or not page:
                break
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  kalshi index: fetch failed ({e}) — Kalshi CTAs will fall back to WC landing", file=sys.stderr)
        return {}

    index: dict[tuple, str] = {}
    for ev in events:
        ticker = ev.get("event_ticker") or ""
        body = ticker.removeprefix("KXWCGAME-")
        if len(body) < 13:
            continue
        try:
            yy   = int(body[0:2])
            mmm  = body[2:5]
            dd   = int(body[5:7])
            iso3_a = _kalshi_to_our_code(body[7:10])
            iso3_b = _kalshi_to_our_code(body[10:13])
            month = _KALSHI_MONTH_TO_NUM.get(mmm)
            if not month:
                continue
            kickoff = _date(2000 + yy, month, dd)
        except (ValueError, KeyError):
            continue
        index[(kickoff, frozenset({iso3_a, iso3_b}))] = ticker
    return index


def _fixture_key_from_match_id(match_id: str) -> tuple | None:
    """Parse `fb-{competition}-{home}-{away}-{yyyymmdd}` → fixture key.
    Mirrors desk/desk/sports/football/priced.py:_fixture_key so the site
    generator can look up Kalshi events without importing from desk/."""
    from datetime import date as _date

    parts = (match_id or "").split("-")
    if len(parts) < 4:
        return None
    yyyymmdd = parts[-1]
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return None
    try:
        kickoff = _date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None
    return (kickoff, frozenset({parts[-3].lower(), parts[-2].lower()}))


# Kalshi UI URL pattern (event landing page — the reader picks the
# side on the page itself):
#
#   https://kalshi.com/markets/{series_lower}/{series_slug}/{event_ticker_lower}
#
# We used to append `?op_market_ticker=…&op_side=BUY&op_order_side=yes
# &op_order_type=dollars` to preselect the picked side, but Kalshi
# retired those query params (dropped 2026-05-30); the URL with them
# stops resolving. If a new preselect param appears later, slot it
# into `_kalshi_market_ticker_for_side` + `_kalshi_url_for`.
#
# `series_slug` is a separate hyphenated slug for the series (NOT the
# series ticker). For KXWCGAME it's "world-cup-game", derived from the
# series title ("World Cup Game" → "world-cup-game"). Hardcoded today;
# if/when we add more Kalshi series we'll pull it from the series API.
KALSHI_SERIES_SLUGS: dict[str, str] = {
    "KXWCGAME": "world-cup-game",
}


def _kalshi_market_ticker_for_side(
    event_ticker: str,
    *,
    pick_side_iso3: str | None,
) -> str | None:
    """Return the Kalshi market ticker for the picked side, or None when
    no side was picked (Pass/Avoid → land on the event page with no
    side preselected).

    `pick_side_iso3` arrives in our (Polymarket-derived) code system;
    the Kalshi event ticker carries Kalshi's codes. Translate before
    comparing so e.g. our "che" matches Kalshi's "SUI".
    """
    body = event_ticker.removeprefix("KXWCGAME-")
    iso3_a = body[7:10].upper()
    iso3_b = body[10:13].upper()
    if pick_side_iso3 is None:
        return None
    if pick_side_iso3 == "draw":
        return f"{event_ticker}-TIE"
    pick_kalshi = _our_to_kalshi_code(pick_side_iso3).upper()
    if pick_kalshi == iso3_a:
        return f"{event_ticker}-{iso3_a}"
    if pick_kalshi == iso3_b:
        return f"{event_ticker}-{iso3_b}"
    return None


def _kalshi_url_for(
    match_id: str | None = None,
    *,
    pick_side_iso3: str | None = None,
) -> tuple[str, bool]:
    """Return (url, is_live).

    is_live=True  → real Kalshi event URL — lands on the event page; the
                    reader picks the side. We used to append
                    `?op_market_ticker=…&op_side=BUY&…` to preselect the
                    picked side, but Kalshi retired those query params
                    and the URL stopped resolving. Dropped 2026-05-30.
    is_live=False → WC landing page fallback (Kalshi has no event for
                    this fixture, or series slug not yet mapped).

    `pick_side_iso3` is currently unused but kept on the signature so the
    site renderer's call sites don't churn — if Kalshi exposes a new
    side-preselect param later, it slots back in here.
    """
    _ = pick_side_iso3  # reserved; see docstring
    if match_id and KALSHI_EVENT_INDEX:
        key = _fixture_key_from_match_id(match_id)
        event_ticker = KALSHI_EVENT_INDEX.get(key) if key else None
        if event_ticker and "-" in event_ticker:
            series_upper = event_ticker.split("-", 1)[0]
            series_slug = KALSHI_SERIES_SLUGS.get(series_upper)
            if not series_slug:
                return (KALSHI_WC_LANDING, False)
            base = (
                f"https://kalshi.com/markets/{series_upper.lower()}/"
                f"{series_slug}/{event_ticker.lower()}"
            )
            return (base, True)
    return (KALSHI_WC_LANDING, False)


# ── Kalshi outright winner deep links ──
#
# Kalshi's WC 2026 outright is its own series (KXMENWORLDCUP), one
# event (KXMENWORLDCUP-26), and one binary market per team. Each market
# ticker carries an ISO 3166-1 alpha-2 country code, e.g.
# `KXMENWORLDCUP-26-ES` (Spain). UI URL shape (event landing — the
# reader picks the team on the page itself):
#
#   https://kalshi.com/markets/kxmenworldcup/mens-world-cup-winner/kxmenworldcup-26
#
# We used to append `?op_market_ticker={MARKET_TICKER_UPPER}` to land
# directly on a per-team market, but Kalshi retired that query param
# (dropped 2026-05-30); the URL stops resolving.
#
# Names from Polymarket don't always match Kalshi's display strings
# 1:1 ("USA" vs "United States", "IR Iran" vs "Iran", etc.), so we
# normalise both sides before matching.
KALSHI_OUTRIGHT_SERIES = "KXMENWORLDCUP"
KALSHI_OUTRIGHT_SERIES_SLUG = "mens-world-cup-winner"
KALSHI_OUTRIGHT_EVENT_TICKER = "KXMENWORLDCUP-26"
KALSHI_OUTRIGHT_LANDING = (
    f"https://kalshi.com/markets/{KALSHI_OUTRIGHT_SERIES.lower()}/"
    f"{KALSHI_OUTRIGHT_SERIES_SLUG}/{KALSHI_OUTRIGHT_EVENT_TICKER.lower()}"
)


def _normalise_team_for_kalshi(name: str) -> str:
    """Squash Polymarket / Kalshi naming variants down to a lookup key."""
    n = (name or "").strip().lower()
    aliases = {
        "usa": "united states",
        "united states of america": "united states",
        "ir iran": "iran",
        "korea republic": "south korea",
        "republic of korea": "south korea",
        "türkiye": "turkey",
        "turkiye": "turkey",
        "côte d'ivoire": "ivory coast",
        "cote d'ivoire": "ivory coast",
        "dr congo": "democratic republic of the congo",
        "congo dr": "democratic republic of the congo",
        "cabo verde": "cape verde",
        "bosnia and herzegovina": "bosnia-herzegovina",
        "curaçao": "curacao",
    }
    return aliases.get(n, n)


def _load_kalshi_outright_index() -> dict[str, str]:
    """Fetch every market under KXMENWORLDCUP-26, return team-name → market_ticker.

    Pure stdlib (urllib) so generate.py stays dependency-free. On any
    network failure, returns {} and the Kalshi outright CTA falls back
    to the event landing page (no preselected team).
    """
    import urllib.request, urllib.error

    markets: list[dict] = []
    cursor: str | None = None
    base = "https://api.elections.kalshi.com/trade-api/v2/markets"
    try:
        while True:
            qs = f"event_ticker={KALSHI_OUTRIGHT_EVENT_TICKER}&limit=200"
            if cursor:
                from urllib.parse import quote
                qs += f"&cursor={quote(cursor)}"
            with urllib.request.urlopen(f"{base}?{qs}", timeout=10) as r:
                payload = json.loads(r.read().decode("utf-8")) or {}
            page = payload.get("markets") or []
            markets.extend(page)
            cursor = payload.get("cursor")
            if not cursor or not page:
                break
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(
            f"  kalshi outright: fetch failed ({e}) — outright CTAs will fall back to event landing",
            file=sys.stderr,
        )
        return {}

    index: dict[str, str] = {}
    for m in markets:
        ticker = (m.get("ticker") or "").strip()
        if not ticker.startswith(f"{KALSHI_OUTRIGHT_EVENT_TICKER}-"):
            continue
        # Kalshi exposes the team display name in a few places. Try the
        # richest first and fall back so we tolerate response shape drift.
        name = (
            m.get("yes_sub_title")
            or m.get("subtitle")
            or m.get("title")
            or ""
        ).strip()
        if not name:
            continue
        key = _normalise_team_for_kalshi(name)
        # First-write-wins. Kalshi shouldn't repeat tickers per team but
        # keep the guard so a duplicate doesn't silently overwrite.
        index.setdefault(key, ticker)
    return index


KALSHI_OUTRIGHT_INDEX: dict[str, str] = {}


def _kalshi_outright_url_for(team: str | None) -> tuple[str, bool]:
    """Return (url, is_live) for an outright-winner CTA on Kalshi.

    is_live=True  → real Kalshi event URL (no team preselected). We used
                    to append `?op_market_ticker=…` to land directly on
                    the per-team market, but Kalshi retired that query
                    param and the URL stopped resolving. Dropped
                    2026-05-30; the reader picks the team on the event
                    page itself.
    is_live=False → the event landing page (no team preselected). Used
                    when we have no team (Pass row), when Kalshi's index
                    is empty (network failure), or when the team doesn't
                    map to any Kalshi market.
    """
    if not team or not KALSHI_OUTRIGHT_INDEX:
        return (KALSHI_OUTRIGHT_LANDING, False)
    ticker = KALSHI_OUTRIGHT_INDEX.get(_normalise_team_for_kalshi(team))
    if not ticker:
        return (KALSHI_OUTRIGHT_LANDING, False)
    return (KALSHI_OUTRIGHT_LANDING, True)


def _cta_pill(
    label: str,
    url: str,
    *,
    placeholder: bool = False,
    caption: str | None = None,
    caption_kind: str = "",
    match_id: str | None = None,
    venue: str | None = None,
) -> str:
    """Render a single trade CTA pill, optionally with a small caption
    underneath. `caption_kind`:
      - "best"  → highlighted "best price" caption (flame)
      - "live"  → priced-but-not-best caption (ink)
      - "search" → no live price detected (muted)

    When both `match_id` and `venue` are provided, stamps the pill with
    `data-match-id` + `data-cta-venue` so activity.js can fire the
    `/api/activity/cta` beacon on click. Venue is "polymarket" | "kalshi".
    """
    extra = " is-placeholder" if placeholder else ""
    data_attrs = ""
    if match_id and venue:
        data_attrs = (
            f' data-match-id="{escape(match_id)}"'
            f' data-cta-venue="{escape(venue)}"'
        )
    pill = (
        f'<a class="cta market-cta{extra}" href="{escape(url)}" '
        f'target="_blank" rel="nofollow noopener"{data_attrs}>'
        f'{escape(label)} <span class="arr">↗</span>'
        f'</a>'
    )
    # Always emit a `.cta-caption` line, even when empty, so the two side-by-side
    # CTA stacks share the same total height and their bottom edges line up. An
    # invisible non-breaking space holds the line; the visible caption sits in
    # the same place when present.
    kind_cls = f" is-{caption_kind}" if caption_kind else ""
    if not caption:
        caption_html = '<span class="cta-caption is-spacer" aria-hidden="true">&nbsp;</span>'
    else:
        caption_html = f'<span class="cta-caption{kind_cls}">{escape(caption)}</span>'
    return f'<span class="cta-stack">{pill}{caption_html}</span>'


def _read_case_link(detail_href: str) -> str:
    """Secondary CTA — text-only "Read the case" link to the match/outright
    detail page. Styled tertiary so the two trade pills are the visual
    primary CTAs.
    """
    return (
        f'<a class="cta-secondary read-case" href="{escape(detail_href)}">'
        f'Read the full case <span class="arr">→</span>'
        f'</a>'
    )


def _pick_side_iso3(
    side: str | None,
    *,
    match_id: str | None,
    team_a: str | None,
    team_b: str | None,
) -> str | None:
    """Map verdict.side (team name or 'draw') → ISO3 code from match_id."""
    if side is None or not match_id:
        return None
    if str(side).strip().lower() == "draw":
        return "draw"
    parts = match_id.split("-")
    if len(parts) < 4:
        return None
    iso_a, iso_b = parts[-3], parts[-2]
    if team_a and side == team_a:
        return iso_a
    if team_b and side == team_b:
        return iso_b
    return None


def market_cta(
    verdict: dict,
    *,
    price: str | None = None,
    search_key: str | None = None,
    detail_href: str | None = None,
    match_id: str | None = None,
    team_a: str | None = None,
    team_b: str | None = None,
    outright_team: str | None = None,
) -> str:
    """Render the CTAs for a card.

    Tells the reader explicitly *which venue is the right one to trade
    on*. Each trade pill carries a small caption: "Best price · <odds>"
    on the venue Desk's verdict was struck against. Kalshi gets a real
    deep-link when we resolved a live event for this fixture; falls
    back to the WC 2026 landing page when we didn't.

    For outright winner cards, callers pass `outright_team=` and the
    Kalshi URL resolves through the WC26-winner market index instead of
    the per-match `KXWCGAME` one.
    """
    poly_price   = (verdict.get("market_venue") or "").lower() == "polymarket" and price
    kalshi_price = verdict.get("kalshi_price")    # not produced yet; future hook

    poly_url = _polymarket_url_for(verdict, fallback_search=search_key)

    if outright_team is not None:
        kalshi_url, kalshi_is_live = _kalshi_outright_url_for(outright_team)
    else:
        pick_side_iso3 = _pick_side_iso3(
            verdict.get("side"), match_id=match_id, team_a=team_a, team_b=team_b,
        )
        kalshi_url, kalshi_is_live = _kalshi_url_for(match_id, pick_side_iso3=pick_side_iso3)

    # Captions — only show one when we have something specific to say.
    poly_caption: str | None = None
    poly_kind = ""
    kalshi_caption: str | None = None
    kalshi_kind = ""

    if poly_price and kalshi_price:
        poly_caption, poly_kind = f"Best price · {price}", "best"
        kalshi_caption, kalshi_kind = f"Live · {kalshi_price}", "live"
    elif poly_price:
        poly_caption, poly_kind = f"Best price · {price}", "best"
    elif kalshi_price:
        kalshi_caption, kalshi_kind = f"Best price · {kalshi_price}", "best"
    else:
        poly_caption, poly_kind = "See live market", "live"

    poly_pill = _cta_pill(
        "See price on Polymarket", poly_url,
        caption=poly_caption, caption_kind=poly_kind,
        match_id=match_id, venue="polymarket",
    )
    kalshi_pill = _cta_pill(
        "See price on Kalshi", kalshi_url, placeholder=not kalshi_is_live,
        caption=kalshi_caption, caption_kind=kalshi_kind,
        match_id=match_id, venue="kalshi",
    )
    secondary = _read_case_link(detail_href) if detail_href else ""
    return f'{poly_pill}{kalshi_pill}{secondary}'


def venue_meta(match: dict) -> str:
    """Stadium · City · Competition stage."""
    parts = []
    v = match.get("venue")
    if v:
        if v.get("stadium"): parts.append(v["stadium"])
        if v.get("city"): parts.append(v["city"])
        if v.get("country"): parts.append(v["country"])
    comp = match.get("competition", {})
    if comp.get("stage"):
        parts.append(escape(comp["stage"].replace("_", " ").title()))
    if not parts:
        parts.append(escape(comp.get("label", "")))
    return " · ".join(p for p in parts if p)


# ─── Card renderer ───

GLYPHS = {"pick": "▲", "pass": "—", "avoid": "✕"}
LABELS = {"pick": "Pick", "pass": "Pass", "avoid": "Avoid"}


def _team_flag_img(team_code: str | None) -> str:
    """Inline flag <img> for a team short-code. Empty string when there's
    no resolvable code — keeps the title clean rather than rendering an
    `_unknown` placeholder where we don't have a team."""
    if not team_code:
        return ""
    return (
        f'<img class="lv-flag" src="{flag_path(team_code)}" alt="" '
        f'aria-hidden="true" loading="lazy">'
    )


def render_card(match: dict, *, is_lead: bool = False, show_read_case: bool = True) -> str:
    """Render one lv-card from a match JSON. Works for both Pick and Pass.

    `show_read_case=False` drops the "Read the case" tertiary link AND the
    whole-card overlay link — used when the card is already on its own
    detail page so the reader doesn't have a redundant self-link.
    """
    v = match["verdict"]
    state = v["state"]
    state_class = f"is-{state}" + (" is-lead" if is_lead else "")

    href = f"/m/{match['match_id']}"
    when = fmt_kickoff_full(match["kickoff_utc"])
    fresh_rel = _relative_updated(match.get("updated_at"))
    code_a, code_b = team_codes_from_match_id(match.get("match_id"))

    # Pick-only: which side did the engine call, and what's the chip label?
    # `verdict.side` is the team display name or the string "draw"; null on
    # Pass/Avoid. Treat anything outside {team_a, team_b, "draw"} as null so
    # an unexpected string never silently dims the wrong team.
    pick_side = v.get("side") if state == "pick" else None
    side_a = pick_side is not None and pick_side == match["team_a"]
    side_b = pick_side is not None and pick_side == match["team_b"]
    side_draw = pick_side == "draw"
    if pick_side is not None and not (side_a or side_b or side_draw):
        pick_side = None

    chip_label = None
    if pick_side == "draw":
        chip_label = "Draw"
    elif pick_side is not None:
        chip_label = f"{pick_side} to win"

    def _team_span(name: str, code: str, is_picked: bool) -> str:
        cls = "lv-team"
        if pick_side and not side_draw and not is_picked:
            cls += " is-dim"
        return f'<span class="{cls}">{_team_flag_img(code)}{escape(name)}</span>'

    title = (
        f'{_team_span(match["team_a"], code_a, side_a)}'
        f' <span class="vs">v</span> '
        f'{_team_span(match["team_b"], code_b, side_b)}'
    )

    # Header
    chip_html = (
        f'<span class="lv-pick-chip">{escape(chip_label)}</span>'
        if chip_label else ""
    )
    head = (
        f'<span class="lv-glyph" aria-hidden="true">{GLYPHS[state]}</span>'
        f'<span class="lv-lab">{LABELS[state]}</span>'
        f'{chip_html}'
        f'<span class="lv-when">'
        f'<span class="lv-when-row">{escape(when)}</span>'
        f'<span class="lv-fresh">Last updated ·{escape(fresh_rel)}</span>'
        f'</span>'
    )

    vmeta = venue_meta(match)
    thesis = escape(_sanitize_copy(match["copy"]["summary"] or ""))

    # Search-fallback key for Kalshi (no live ingest yet) and for
    # Polymarket if market_url is missing.
    search_key = f"{match.get('team_a','')} {match.get('team_b','')}".strip()

    cta_kwargs = dict(
        search_key=search_key,
        detail_href=href if show_read_case else None,
        match_id=match.get("match_id"),
        team_a=match.get("team_a"),
        team_b=match.get("team_b"),
    )

    # Foot — different for pick/avoid vs pass
    if state == "pass":
        cta_html = market_cta(v, **cta_kwargs)
        foot = (
            '<div class="lv-foot">'
            f'<span class="lv-flat-msg">The market and our model agree — no clear edge.</span>'
            f'<div class="lv-action">{cta_html}</div>'
            '</div>'
        )
    else:
        edge_class = ""
        edge_str = fmt_edge(v.get("edge_pp"))
        if edge_str:
            if v["edge_pp"] < 0:
                edge_class = " is-neg"
            elif abs(v["edge_pp"]) < 0.5:
                edge_class = " is-flat"

        reads = (
            f'<span class="rp"><span class="k">Model</span><span class="v">{fmt_pct(v.get("model_p"))}</span></span>'
            f'<span class="rp"><span class="k">Market</span><span class="v">{fmt_pct(v.get("market_p"))}</span></span>'
        )
        if edge_str:
            reads += f'<span class="edge{edge_class}">{edge_str}</span>'

        action_bits = market_cta(v, price=v.get("price"), **cta_kwargs)

        stat_lead_html = (
            f'<div class="lv-stat-lead">{escape(chip_label)}</div>'
            if chip_label else ""
        )
        foot = (
            '<div class="lv-foot">'
            '<div class="lv-reads-stack">'
            f'{stat_lead_html}'
            f'<div class="lv-reads">{reads}</div>'
            '</div>'
            f'<div class="lv-action">{action_bits}</div>'
            '</div>'
        )

    # Card is a <div> so we can nest the venue CTA as a real <a>. The
    # whole card is still clickable via an absolute-positioned overlay
    # link that goes to the match detail page; the venue CTA sits above
    # it (z-index) so a click on the pill opens the market instead.
    overlay_link = (
        f'<a class="lv-card-link" href="{href}" aria-label="Read the full case"></a>'
        if show_read_case else ""
    )
    # Activity slot — emitted on every card (home, matches index, detail).
    # Lives INSIDE the .lv-card grid; CSS in activity.js places it at
    # grid-column: 1 / -1 with pointer-events: auto so it spans the
    # full card width and chip clicks don't fall through to the card
    # overlay link.
    activity_slot = (
        f'<div class="op-activity" '
        f'data-match-id="{escape(match.get("match_id") or "")}" '
        f'data-verdict-state="{escape(state)}" '
        f'data-pick-side="{escape(pick_side or "")}"></div>'
    )
    return (
        f'<div class="lv-card {state_class}">'
        f'{overlay_link}'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{title}</h3>'
        f'<p class="lv-venue-meta">{vmeta}</p>'
        f'<p class="lv-thesis">{thesis}</p>'
        f'{foot}'
        f'{activity_slot}'
        '</div>'
    )


# ─── Page renderers ───

def render_home(matches: list[dict], outrights: list[dict]) -> str:
    """Home: hero + headline (top Pick) + upcoming Picks + outrights teaser."""
    picks = [m for m in matches if m["verdict"]["state"] == "pick"]
    picks.sort(key=lambda m: -(m["verdict"].get("edge_pp") or 0))

    headline_html = ""
    if picks:
        lead = picks[0]
        headline_html = (
            '<div class="section-label">'
            '<span>Today\'s headline verdict</span>'
            '<a class="see-all" href="/matches/">All matches <span class="arr">→</span></a>'
            '</div>'
            f'{render_card(lead, is_lead=True)}'
            '<p class="affiliate-note">'
            'Odds Primer may earn a referral fee if you use a partner venue. '
            'Verdicts are editorial and independent.'
            '</p>'
        )
    else:
        headline_html = (
            '<div class="section-label"><span>Today\'s headline verdict</span></div>'
            '<div class="empty-state">'
            '<h2>No Picks today — markets are pricing it right.</h2>'
            '<p>The model and the market agree across every priced fixture. '
            'We don\'t publish a Pick unless the gap clears 3 percentage points.</p>'
            '</div>'
        )

    # Other Picks (excluding the headline)
    other_picks_html = ""
    if len(picks) > 1:
        cards = "\n".join(render_card(m) for m in picks[1:6])
        other_picks_html = (
            '<div class="section-label">'
            f'<span>More Picks · {len(picks) - 1} more</span>'
            '<a class="see-all" href="/matches/">See all matches <span class="arr">→</span></a>'
            '</div>'
            f'{cards}'
        )

    # Outrights teaser is intentionally suppressed from the home —
    # the only live outright (WC26 winner) is a Pass and there's no
    # editorial value in surfacing "the model agrees with the market"
    # to a phone visitor. The /outrights page itself still ships and
    # is reachable from the masthead + footer; revisit this when a
    # tournament-winner market produces an actual Pick.

    # Verdict-led home: headline verdict comes directly under the
    # masthead/edition strip. The verdict key sits *below* the first
    # card so the value (Pick / Pass / Avoid call) is what a phone
    # visitor sees first, not the explanatory legend.
    verdict_key_html = (
        '<section class="verdict-key" aria-label="Verdict key">'
            '<span class="vk-label">Verdict key</span>'
            '<div class="vk-item">'
              '<span class="vk-icon is-pick" aria-hidden="true">&#9650;</span>'
              '<span class="vk-text">'
                '<span class="vk-name is-pick">Pick</span>'
                '<span class="vk-desc">the line appears underpriced</span>'
              '</span>'
            '</div>'
            '<div class="vk-item">'
              '<span class="vk-icon is-pass" aria-hidden="true">&mdash;</span>'
              '<span class="vk-text">'
                '<span class="vk-name is-pass">Pass</span>'
                '<span class="vk-desc">the line is fair &mdash; no edge to play</span>'
              '</span>'
            '</div>'
            '<div class="vk-item">'
              '<span class="vk-icon is-avoid" aria-hidden="true">&times;</span>'
              '<span class="vk-text">'
                '<span class="vk-name is-avoid">Avoid</span>'
                '<span class="vk-desc">overpriced both ways &mdash; sit it out</span>'
              '</span>'
            '</div>'
            '<p class="vk-note">'
              'Colour, glyph, and label all carry the same meaning, so a card\'s call is readable at a glance.'
            '</p>'
          '</section>'
    )

    hero_html = (
        '<section class="hero">'
        '<h1>Every 2026 World Cup price, read by The Desk.</h1>'
        '<p class="standfirst">Odds Primer compares live Kalshi and Polymarket prices, runs its '
        'own model, and explains whether each price is a Pick, a Pass, or one to Avoid. '
        'Free. Editorial. No tips, no hype.</p>'
        '</section>'
    )

    how_the_desk_works = (
        '<section class="how-desk" aria-labelledby="how-desk-title">'
        '<h2 id="how-desk-title" class="hd-title">How The Desk works</h2>'
        '<ol class="hd-steps">'
          '<li><span class="hd-num">1</span>'
            '<h3>Market prices update</h3>'
            '<p>Live snapshots from Polymarket and Kalshi.</p></li>'
          '<li><span class="hd-num">2</span>'
            '<h3>The model recalculates probabilities</h3>'
            '<p>An independent football model rebuilds each side&rsquo;s number.</p></li>'
          '<li><span class="hd-num">3</span>'
            '<h3>The Desk compares market vs model</h3>'
            '<p>Two reads, one fixture — the gap is the editorial signal.</p></li>'
          '<li><span class="hd-num">4</span>'
            '<h3>Pick / Pass / Avoid is published</h3>'
            '<p>With the reasoning, the citations, and what would move it.</p></li>'
        '</ol>'
        '<p class="hd-thesis">The goal is not to predict everything. The goal is to identify '
        'where market pricing and model conviction meaningfully diverge.</p>'
        '</section>'
    )

    the_desk_block = (
        '<section class="the-desk-block" aria-labelledby="the-desk-title">'
        '<p class="td-eyebrow">The Desk</p>'
        '<h2 id="the-desk-title" class="td-title">'
        'Comparing prediction-market prices against an independent football model.'
        '</h2>'
        '<p class="td-lede">'
        'The Desk compares live prediction-market pricing against an independent football '
        'model and publishes a verdict on every priced market it covers.'
        '</p>'
        '<p class="td-body">'
        'The Desk does not chase every match. It looks for disagreement, overreaction, '
        'uncertainty, and mispricing — and stays quiet when the line is already doing its '
        'job.'
        '</p>'
        '</section>'
    )

    return (
        chrome_head(
            "Odds Primer · World Cup 2026 prices",
            description=(
                "Odds Primer compares live Kalshi and Polymarket prices against an independent "
                "football model and publishes Pick, Pass, or Avoid verdicts on every "
                "major World Cup market."
            ),
            path="/",
        )
        + chrome_masthead("home")
        + '<main class="page">'
        + hero_html
        + how_the_desk_works
        + headline_html
        + verdict_key_html
        + other_picks_html
        + the_desk_block
        + '</main>'
        + chrome_footer()
    )


def render_matches_index(matches: list[dict]) -> str:
    """All matches grouped by date."""
    # Group by kickoff date
    by_date = defaultdict(list)
    for m in matches:
        by_date[kickoff_date_key(m["kickoff_utc"])].append(m)

    sections = []
    for date_key in sorted(by_date):
        cards = "\n".join(render_card(m) for m in sorted(by_date[date_key], key=lambda x: x["kickoff_utc"]))
        # Convert date_key to a friendly label using first match's ISO
        label = fmt_kickoff_date(by_date[date_key][0]["kickoff_utc"])
        sections.append(f'<h2 class="date-head">{escape(label)}</h2>{cards}')

    body = "\n".join(sections) if sections else (
        '<div class="empty-state"><h2>No matches in the schedule yet.</h2>'
        '<p>Run <code>python -m desk run --once</code> to ingest the latest priced fixtures.</p></div>'
    )

    pick_count = sum(1 for m in matches if m["verdict"]["state"] == "pick")
    pass_count = sum(1 for m in matches if m["verdict"]["state"] == "pass")
    avoid_count = sum(1 for m in matches if m["verdict"]["state"] == "avoid")

    return (
        chrome_head(
            "Upcoming matches · Odds Primer",
            description=(
                f"{len(matches)} priced World Cup fixtures with a Pick, Pass, or Avoid "
                "verdict on each — Polymarket and Kalshi side-by-side."
            ),
            path="/matches/",
        )
        + chrome_masthead("matches")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/"><span class="arr">←</span> Home</a>'
          '<h1>Upcoming matches</h1>'
          f'<p class="standfirst" style="font-family:var(--font-serif);font-style:italic;color:var(--ink-soft);margin:14px 0 0;">'
          f'{len(matches)} priced fixtures · '
          f'<strong style="color:var(--flame-deep)">{pick_count} Pick{"s" if pick_count != 1 else ""}</strong> · '
          f'{pass_count} Pass · '
          f'{avoid_count} Avoid'
          '</p>'
          '</section>'
        + body
        + '</main>'
        + chrome_footer()
    )


def _render_model_adjustments_block(adjustments: list[dict]) -> str:
    """Render `hard_signal_adjustments` as a transparency block.

    One row per applied Elo nudge: signed delta · team · short reason ·
    outlet (linked to the signal). Lets a reader answer "did this signal
    change the verdict?" from the page alone. Empty list → empty string
    (the section is hidden when no adjustments fired)."""
    if not adjustments:
        return ""
    items: list[str] = []
    for a in adjustments:
        team = (a.get("team") or "").strip()
        reason = (a.get("reason") or "").strip()
        url = (a.get("signal_url") or "").strip()
        outlet = (a.get("source_name") or a.get("source_id") or "").strip()
        sig_type = (a.get("signal_type") or "").strip()
        try:
            delta = float(a.get("delta_elo") or 0.0)
        except (TypeError, ValueError):
            delta = 0.0
        if not (team and reason):
            continue
        delta_str = f"{delta:+.1f} Elo"
        capped = " · capped" if a.get("capped") else ""
        when = ""
        pub = a.get("published_at")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                when = f' <span class="adj-date">· {dt.strftime("%-d %b %Y")}</span>'
            except Exception:
                when = ""
        outlet_html = ""
        if outlet and url:
            outlet_html = (
                f' · <a href="{escape(url)}" rel="nofollow noopener" target="_blank">'
                f'{escape(outlet)}</a>'
            )
        elif outlet:
            outlet_html = f' · {escape(outlet)}'
        type_tag = f'<span class="adj-type">{escape(sig_type)}</span>' if sig_type else ""
        items.append(
            '<li>'
            f'<span class="adj-delta">{escape(delta_str)}</span>'
            f' · <span class="adj-team">{escape(team)}</span>'
            f' · <span class="adj-reason">{escape(reason)}</span>'
            f'{capped}'
            f'{outlet_html}'
            f'{when}'
            f'{type_tag}'
            '</li>'
        )
    if not items:
        return ""
    return (
        '<section class="model-adjustments">'
        '<h2>Model adjustments</h2>'
        '<p class="adj-lede">News-signal nudges applied to each team\'s Elo before the model ran. '
        'Negative values are penalties; the cap is −30 Elo per team.</p>'
        '<ul>' + "".join(items) + '</ul>'
        '</section>'
    )


def _render_sources_block(citations: list[dict]) -> str:
    """Render `editorial_citations` as a clickable Sources block.

    Each row: outlet name (link to the article) · published date (when
    present) · verbatim quote. Empty list → empty string (the section
    is hidden entirely rather than showing an empty header).

    Links carry `rel="nofollow noopener"` + `target="_blank"`, matching
    the existing market-CTA convention. Quotes are HTML-escaped; URLs
    are escaped for attribute safety.
    """
    if not citations:
        return ""
    items: list[str] = []
    for c in citations:
        outlet = (c.get("outlet") or "").strip()
        url    = (c.get("url") or "").strip()
        quote  = (c.get("quote") or "").strip()
        if not (outlet and url):
            continue
        when = ""
        pub = c.get("published_at")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                when = f' <span class="src-date">· {dt.strftime("%-d %b %Y")}</span>'
            except Exception:
                when = ""
        items.append(
            '<li>'
            f'<a href="{escape(url)}" rel="nofollow noopener" target="_blank">'
            f'{escape(outlet)}</a>'
            f'{when}'
            f'<blockquote>{escape(quote)}</blockquote>'
            '</li>'
        )
    if not items:
        return ""
    return (
        '<section class="sources">'
        '<h2>Sources</h2>'
        '<ul>' + "".join(items) + '</ul>'
        '</section>'
    )


def render_match_page(match: dict) -> str:
    """Per-match page: header + lead card + blurb + drivers + sources."""
    title = match["copy"].get("title") or f"{match['team_a']} v {match['team_b']}"
    summary = match["copy"].get("summary") or ""
    blurb = _sanitize_copy(match["copy"].get("blurb") or "")
    drivers = match["copy"].get("drivers") or []
    citations = match["copy"].get("editorial_citations") or []
    adjustments = match.get("hard_signal_adjustments") or []
    v = match["verdict"]

    blurb_paras = "\n".join(f"<p>{escape(p)}</p>" for p in blurb.split("\n\n") if p.strip())

    drivers_html = ""
    if drivers:
        items = "\n".join(f'<li>{escape(d)}</li>' for d in drivers)
        drivers_html = f'<section class="drivers"><h2>The drivers</h2><ol>{items}</ol></section>'

    sources_html = _render_sources_block(citations)
    adjustments_html = _render_model_adjustments_block(adjustments)

    # ── Trust strip: updated/model-refresh/market-snapshot timestamps ──
    updated_at = match.get("updated_at") or ""
    rel_updated = _relative_updated(updated_at)
    model_refresh = _fmt_short_utc(updated_at)
    trust_strip = (
        '<section class="trust-strip" aria-label="Data freshness">'
        f'<span class="ts-item"><span class="ts-lbl">Updated</span> {escape(rel_updated)}</span>'
        f'<span class="ts-item"><span class="ts-lbl">Model refresh</span> {escape(model_refresh)} UTC</span>'
        f'<span class="ts-item"><span class="ts-lbl">Market snapshot</span> live</span>'
        '</section>'
    )

    # ── Editorial disclaimer beneath the verdict ──
    disclaimer_html = (
        '<p class="event-disclaimer">'
        'Editorial analysis only. Odds Primer does not provide betting or financial advice.'
        '</p>'
    )

    # Determine if this is a thin / no-verdict page → noindex it.
    has_real_verdict = bool(
        v and v.get("state") in ("pick", "pass", "avoid")
        and (blurb or summary)
    )
    extra_head = "" if has_real_verdict else '<meta name="robots" content="noindex">'

    market_url = v.get("market_url")
    if market_url:
        market_url = _normalise_polymarket_url(market_url)
    venue_name = (v.get("market_venue") or "").title()
    cta_row = ""
    if market_url:
        # Derive the beacon venue from the URL host so the bottom cta-row
        # logs the same way the in-card pills do.
        beacon_venue = venue_name_from_url(market_url)
        match_id = match.get("match_id") or ""
        data_attrs = ""
        if match_id and beacon_venue:
            data_attrs = (
                f' data-match-id="{escape(match_id)}"'
                f' data-cta-venue="{escape(beacon_venue.lower())}"'
            )
        cta_row = (
            '<div class="cta-row">'
            f'<a class="open-market" href="{escape(market_url)}" rel="nofollow noopener" target="_blank"{data_attrs}>'
            f'See price on <span class="venue-name">{escape(venue_name) if venue_name else "the source"}</span> <span class="arr">↗</span></a>'
            '<span class="meta-note">Affiliate link. Odds Primer may earn a commission. Editorial verdicts are independent.</span>'
            '</div>'
        )

    # "Why the model disagrees" — mandatory on wide-gap Picks where the
    # gap from the market is unusually large (≥10pp or model > 3× market).
    why_disagrees_html = ""
    edge_pp = (v or {}).get("edge_pp")
    model_p = (v or {}).get("model_p")
    market_p = (v or {}).get("market_p")
    if v and v.get("state") == "pick" and edge_pp is not None and edge_pp >= 10:
        ratio_note = ""
        if model_p and market_p and market_p > 0 and (model_p / market_p) >= 2.5:
            ratio_note = (
                f" The model rates this side at roughly "
                f"{round(model_p / market_p, 1)}× the market's number."
            )
        why_disagrees_html = (
            '<section class="why-disagrees">'
            '<h2>Why the model disagrees</h2>'
            '<p>'
            f'A gap this wide ({fmt_edge(edge_pp)}) usually means one of the '
            'following: a reputation-led short price the model isn\'t pricing in, '
            'a stale line that hasn\'t absorbed recent fitness or lineup news, '
            'a tactical or defensive profile that doesn\'t match the headline form, '
            'or a market lag on travel, altitude, or weather. The drivers below show '
            'which of these the engine is weighing on this fixture.'
            f'{ratio_note}'
            '</p>'
            '</section>'
        )

    return (
        chrome_head(
            f"{title} · Odds Primer",
            description=summary or f"Verdict, model probability, market probability, and the read on {title}.",
            path=f"/m/{match['match_id']}",
            extra_head=extra_head,
        )
        + chrome_masthead("matches")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/matches/"><span class="arr">←</span> All matches</a>'
          f'<h1>{escape(title)}</h1>'
          '</section>'
        + trust_strip
        + render_card(match, is_lead=True, show_read_case=False)
        + disclaimer_html
        + (f'<div class="blurb">{blurb_paras}</div>' if blurb_paras else "")
        + cta_row
        + why_disagrees_html
        + drivers_html
        + adjustments_html
        + sources_html
        + '<aside class="voice">'
          '<h3>How to read this</h3>'
          '<p>The Desk compares its <em>model probability</em> against the <em>best available market probability</em>. '
          'A <em>Pick</em> means the model rates a side three or more percentage points higher than the market. '
          '<em>Pass</em> means the line is doing its job. <em>Avoid</em> means every side looks overpriced.</p>'
          '</aside>'
        + '</main>'
        + chrome_footer()
    )


# ─── Outrights ───


def _outright_cta_row(market_url: str | None, team: str | None) -> str:
    """Dual-venue CTA row for an outright page: Polymarket first (the
    canonical source for the WC26 winner market today), Kalshi second
    when the team maps to a Kalshi market ticker. Mirrors the per-match
    page's two-CTA pattern; falls back to the Kalshi event landing when
    no team is known (Pass) or the team isn't mapped.

    `market_url` is the Polymarket URL already passed through
    `_normalise_polymarket_url`. `team` is the team display name from
    the verdict / ladder row.
    """
    pills: list[str] = []
    if market_url:
        pills.append(
            '<a class="open-market" '
            f'href="{escape(market_url)}" rel="nofollow noopener" target="_blank">'
            'See price on <span class="venue-name">Polymarket</span> '
            '<span class="arr">↗</span></a>'
        )
    kalshi_url, _is_live = _kalshi_outright_url_for(team)
    if kalshi_url:
        pills.append(
            '<a class="open-market" '
            f'href="{escape(kalshi_url)}" rel="nofollow noopener" target="_blank">'
            'See price on <span class="venue-name">Kalshi</span> '
            '<span class="arr">↗</span></a>'
        )
    if not pills:
        return ""
    return (
        '<div class="cta-row">'
        + "".join(pills)
        + '<span class="meta-note">Affiliate link. Odds Primer may earn '
          'a commission. Editorial verdicts are independent.</span>'
        + '</div>'
    )


def render_outright_card(outright: dict) -> str:
    """Render an outright as an lv-card. Mirrors the match card shape."""
    v = outright.get("verdict", {})
    state = v.get("state", "pass")
    state_class = f"is-{state}"
    href = f"/outrights/{outright['outright_id']}"

    resolves_at = outright.get("resolves_at")
    when = ""
    if resolves_at:
        try:
            dt = datetime.fromisoformat(resolves_at.replace("Z", "+00:00"))
            when = "Resolves " + dt.strftime("%-d %b %Y")
        except Exception:
            when = ""

    label = outright.get("market_label", outright.get("label", "Outright"))
    candidate = v.get("candidate") or outright.get("candidate") or ""
    if candidate in ("", "—"):
        # Pass verdicts have no Pick candidate — surface the market name
        # as the headline so the card isn't just a dash. Strip the
        # trailing "— outright winner" since that already shows below.
        candidate = label.split(" — ")[0].strip() or "Outright"
    summary = outright.get("copy", {}).get("summary") or ""

    fresh_rel = _relative_updated(outright.get("updated_at"))
    head = (
        f'<span class="lv-glyph" aria-hidden="true">{GLYPHS.get(state, "—")}</span>'
        f'<span class="lv-lab">{LABELS.get(state, "Pass")}</span>'
        f'<span class="lv-when">'
        f'<span class="lv-when-row">{escape(when)}</span>'
        f'<span class="lv-fresh">Last updated ·{escape(fresh_rel)}</span>'
        f'</span>'
    )

    # The outright top-level carries market_url / market_venue; the
    # nested verdict only carries them on Pick state. Compose a single
    # dict the CTA helper can read from.
    cta_dict = {
        "market_url":   v.get("market_url")   or outright.get("market_url"),
        "market_venue": v.get("market_venue") or outright.get("market_venue"),
    }

    search_key = "World Cup 2026 winner"

    # On Pick state we know the candidate team and can deep-link Kalshi;
    # on Pass we have no team, so Kalshi falls back to the event landing.
    pick_team = v.get("team") or v.get("candidate") if state == "pick" else None
    if state == "pass":
        cta_html = market_cta(
            cta_dict, search_key=search_key, detail_href=href,
            outright_team=pick_team,
        )
        foot = (
            '<div class="lv-foot">'
            '<span class="lv-flat-msg">Markets agree on this field.</span>'
            f'<div class="lv-action">{cta_html}</div>'
            '</div>'
        )
    else:
        edge_str = fmt_edge(v.get("edge_pp"))
        edge_class = ""
        if v.get("edge_pp") is not None and v["edge_pp"] < 0:
            edge_class = " is-neg"
        reads = (
            f'<span class="rp"><span class="k">Model</span><span class="v">{fmt_pct(v.get("model_p"))}</span></span>'
            f'<span class="rp"><span class="k">Market</span><span class="v">{fmt_pct(v.get("market_p"))}</span></span>'
        )
        if edge_str:
            reads += f'<span class="edge{edge_class}">{edge_str}</span>'
        action = market_cta(
            cta_dict, price=v.get("price"), search_key=search_key, detail_href=href,
            outright_team=pick_team,
        )
        foot = f'<div class="lv-foot"><div class="lv-reads">{reads}</div><div class="lv-action">{action}</div></div>'

    return (
        f'<div class="lv-card {state_class}">'
        f'<a class="lv-card-link" href="{href}" aria-label="Read the full case"></a>'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{escape(candidate)}</h3>'
        f'<p class="lv-venue-meta">{escape(label)}</p>'
        f'<p class="lv-thesis">{escape(summary)}</p>'
        f'{foot}'
        '</div>'
    )


def _team_slug(name: str) -> str:
    """URL-safe slug from a team name. Strips diacritics, lowercases,
    collapses anything non-alphanumeric to hyphens.
    "Argentina" → "argentina"; "Côte d'Ivoire" → "cote-d-ivoire";
    "Bosnia and Herzegovina" → "bosnia-and-herzegovina"."""
    import unicodedata
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug or "team"


def _outright_activity_id(outright: dict, row: dict) -> str:
    """Stable per-team identifier for the activity widget. Format:
    `outright-{outright_id}-{team-slug}` so views/votes on Argentina
    in the WC26 winner market don't collide with anything else."""
    outright_id = (outright.get("outright_id") or "").strip()
    slug = _team_slug(row.get("team", ""))
    return f"outright-{outright_id}-{slug}"


def render_outright_team_card(outright: dict, row: dict, *, show_overlay: bool = True) -> str:
    """Card for a single team in an outright market. Mirrors the
    .lv-card shape used by per-match cards: state-coloured rule on the
    left, glyph + label in the head, country-flag + team name as the
    h3, market label as the venue meta, model/market/edge stats in
    the foot, activity strip + reaction chips beneath. Optional overlay
    link so the whole tile is clickable through to /outrights/{slug}."""
    team = row.get("team", "—")
    model_p = row.get("model_p")
    market_p = row.get("yes_market_p")
    edge_pp = row.get("yes_edge_pp")
    state = row.get("verdict", "pass")
    state_class = f"is-{state}"

    href = f"/outrights/{_team_slug(team)}"
    iso = iso3_for_name(team) or ""
    market_label = outright.get("market_label") or outright.get("competition", {}).get("label", "Outright")

    resolves_at = outright.get("resolves_at")
    when = ""
    if resolves_at:
        try:
            dt = datetime.fromisoformat(resolves_at.replace("Z", "+00:00"))
            when = "Resolves " + dt.strftime("%-d %b %Y")
        except Exception:
            when = ""

    fresh_rel = _relative_updated(outright.get("updated_at"))
    head = (
        f'<span class="lv-glyph" aria-hidden="true">{GLYPHS.get(state, "—")}</span>'
        f'<span class="lv-lab">{LABELS.get(state, "Pass")}</span>'
        f'<span class="lv-when">'
        f'<span class="lv-when-row">{escape(when)}</span>'
        f'<span class="lv-fresh">Last updated ·{escape(fresh_rel)}</span>'
        f'</span>'
    )

    # Foot: stats for the YES side (model wins prob vs market wins prob).
    edge_class = ""
    edge_str = fmt_edge(edge_pp)
    if edge_str:
        if isinstance(edge_pp, (int, float)):
            if edge_pp < 0:
                edge_class = " is-neg"
            elif abs(edge_pp) < 0.5:
                edge_class = " is-flat"
    reads = (
        f'<span class="rp"><span class="k">Model</span><span class="v">{fmt_pct(model_p)}</span></span>'
        f'<span class="rp"><span class="k">Market</span><span class="v">{fmt_pct(market_p)}</span></span>'
    )
    if edge_str:
        reads += f'<span class="edge{edge_class}">{edge_str}</span>'

    # Foot CTAs — Polymarket + Kalshi pills, plus an optional "Read the
    # case" tertiary link. On the team's own drill-down page
    # (`show_overlay=False`) the self-link is dropped so the foot only
    # carries the two market pills.
    top_verdict = outright.get("verdict") or {}
    cta_dict = {
        "market_url":   top_verdict.get("market_url")   or outright.get("market_url"),
        "market_venue": top_verdict.get("market_venue") or outright.get("market_venue"),
    }
    # Price only applies on the top-level Pick team (e.g. Argentina YES
    # on the WC26 winner market); other rows share the same Polymarket
    # event URL but no per-team price.
    row_price = top_verdict.get("price") if (
        state == "pick" and top_verdict.get("team") == team
    ) else None
    detail_href = href if show_overlay else None
    cta_html = market_cta(
        cta_dict,
        price=row_price,
        search_key="World Cup 2026 winner",
        detail_href=detail_href,
        outright_team=team,
    )
    foot = (
        '<div class="lv-foot">'
        f'<div class="lv-reads">{reads}</div>'
        f'<div class="lv-action">{cta_html}</div>'
        '</div>'
    )

    overlay = (
        f'<a class="lv-card-link" href="{href}" aria-label="Read the case for {escape(team)}"></a>'
        if show_overlay else ""
    )
    short_blurb = escape(_ladder_blurb_for(row))
    # Country flag inline before the team name — mirrors the per-match
    # card where the flag sits to the left of the team's display name.
    team_h3 = f'<h3 class="lv-teams"><span class="lv-team">{_team_flag_img(iso)}{escape(team)}</span></h3>'
    # Activity widget — anonymous views + reaction chips. Activity.js
    # picks up the data-* attributes at runtime; the slot lives inside
    # the lv-card grid so chip clicks don't fall through to the overlay.
    activity_slot = (
        f'<div class="op-activity" '
        f'data-match-id="{escape(_outright_activity_id(outright, row))}" '
        f'data-verdict-state="{escape(state)}" '
        f'data-pick-side="{escape(row.get("pick_side") or "")}"></div>'
    )
    return (
        f'<div class="lv-card {state_class}">'
        f'{overlay}'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'{team_h3}'
        f'<p class="lv-venue-meta">{escape(market_label)}</p>'
        f'<p class="lv-thesis">{short_blurb}</p>'
        f'{foot}'
        f'{activity_slot}'
        '</div>'
    )


def _outright_market_type(outright: dict) -> str:
    """Which market shape this outright is — drives the sort key + the
    stat-block data source. Winner markets sort by model probability
    and render an empty stat block (no games played yet). League-table
    markets (future) will sort by points and pull stats from a
    `standings` field on each ladder row."""
    label = (outright.get("market_label") or "").lower()
    if "league" in label or "table" in label:
        return "league_table"
    return "winner"


def _outright_sort_key(market_type: str):
    """Row sort key by market type. Winner markets descend on model
    probability (current behaviour). League tables descend on points."""
    if market_type == "league_table":
        def _key(row: dict) -> float:
            st = row.get("standings") or {}
            try:
                return -float(st.get("points") or 0)
            except (TypeError, ValueError):
                return 0.0
        return _key
    return lambda row: -(row.get("model_p") or 0)


def _outright_stat_cells(row: dict, market_type: str) -> str:
    """Stat block (P · W · D · L · GF · GA · GD · Pts) as 8 <td> cells.
    Winner markets render every cell as muted '—' until the tournament
    kicks off. League-table markets pull from row['standings']; the
    cells fill automatically without forking the row builder."""
    if market_type == "winner":
        muted = '<td class="stat muted">—</td>'
        muted_h = '<td class="stat muted hide-mobile">—</td>'
        return (
            f'{muted}'                # P (visible mobile)
            f'{muted_h}'              # W
            f'{muted_h}'              # D
            f'{muted_h}'              # L
            f'{muted_h}'              # GF
            f'{muted_h}'              # GA
            f'{muted_h}'              # GD
            f'<td class="stat muted pts">—</td>'  # Pts (visible mobile)
        )
    st = row.get("standings") or {}
    def _i(key: str) -> int:
        try:
            return int(st.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    P, W, D, L = _i("played"), _i("won"), _i("drawn"), _i("lost")
    GF, GA = _i("goals_for"), _i("goals_against")
    GD = GF - GA
    Pts = _i("points") if st.get("points") is not None else (W * 3 + D)
    gd_str = f"+{GD}" if GD > 0 else str(GD)
    return (
        f'<td class="stat">{P}</td>'
        f'<td class="stat hide-mobile">{W}</td>'
        f'<td class="stat hide-mobile">{D}</td>'
        f'<td class="stat hide-mobile">{L}</td>'
        f'<td class="stat hide-mobile">{GF}</td>'
        f'<td class="stat hide-mobile">{GA}</td>'
        f'<td class="stat hide-mobile">{gd_str}</td>'
        f'<td class="stat pts">{Pts}</td>'
    )


def _verdict_chip(verdict: str, side: str | None) -> str:
    """Verdict chip in the standings row — Pick (flame fill, shows YES/NO
    side), Pass (muted outline), Avoid (ink outline)."""
    if verdict == "pick":
        side_html = f'<span class="side">{escape(side)}</span>' if side else ""
        return f'<span class="chip pick">Pick{side_html}</span>'
    if verdict == "avoid":
        return '<span class="chip avoid">Avoid</span>'
    return '<span class="chip pass">Pass</span>'


def _standings_row(outright: dict, row: dict, rank: int, market_type: str) -> str:
    team = row.get("team", "—")
    href = f"/outrights/{_team_slug(team)}"
    iso = iso3_for_name(team) or ""
    flag_html = (
        f'<img class="flag" src="{flag_path(iso)}" alt="" aria-hidden="true" loading="lazy">'
        if iso else '<span class="flag" aria-hidden="true"></span>'
    )
    verdict = row.get("verdict", "pass")
    pick_side = row.get("pick_side")
    model_p = row.get("model_p")
    market_p = row.get("yes_market_p")
    edge_pp = row.get("yes_edge_pp")

    model_str = f"{(model_p or 0) * 100:.1f}%" if model_p is not None else "—"
    market_str = f"{(market_p or 0) * 100:.1f}%" if market_p is not None else "—"
    if isinstance(edge_pp, (int, float)):
        edge_class = "pos" if edge_pp >= 0 else "neg"
        edge_sign = "+" if edge_pp >= 0 else ""
        edge_str = f"{edge_sign}{edge_pp:.1f}"
    else:
        edge_class = "neg"
        edge_str = "—"

    team_cell = (
        '<td class="c-team">'
        f'<div class="team">'
        f'<a href="{href}">'
        f'<span class="rank">{rank}</span>'
        f'{flag_html}'
        f'<span class="name">{escape(team)}</span>'
        '</a>'
        '</div>'
        '</td>'
    )
    return (
        f'<tr data-href="{href}">'
        f'{team_cell}'
        f'<td class="c-verdict">{_verdict_chip(verdict, pick_side)}</td>'
        f'{_outright_stat_cells(row, market_type)}'
        f'<td class="num model">{model_str}</td>'
        f'<td class="num hide-mobile">{market_str}</td>'
        f'<td class="edge hide-mobile {edge_class}">{edge_str}</td>'
        '</tr>'
    )


def _standings_table(outright: dict) -> tuple[str, int, int, int]:
    """Render one <table.standings> for a single outright. Returns the
    HTML plus (total, picks, passes) for the standfirst counts."""
    market_type = _outright_market_type(outright)
    ladder = sorted(outright.get("ladder") or [], key=_outright_sort_key(market_type))
    total = len(ladder)
    picks = sum(1 for r in ladder if r.get("verdict") == "pick")
    passes = sum(1 for r in ladder if r.get("verdict") == "pass")
    grp_label = (
        "Group stage — pending kick-off" if market_type == "winner"
        else "Season form"
    )
    rows_html = "\n".join(
        _standings_row(outright, row, i + 1, market_type)
        for i, row in enumerate(ladder)
    )
    head = (
        '<thead>'
        '<tr class="groups">'
        '<th class="grp c-team">Team</th>'
        '<th class="grp"></th>'
        f'<th class="grp" colspan="8">{escape(grp_label)}</th>'
        '<th class="grp" colspan="3">The Desk</th>'
        '</tr>'
        '<tr>'
        '<th class="col-team c-team">Team</th>'
        '<th class="col-verdict c-verdict">Verdict</th>'
        '<th class="col-stat" title="Played">P</th>'
        '<th class="col-stat hide-mobile" title="Won">W</th>'
        '<th class="col-stat hide-mobile" title="Drawn">D</th>'
        '<th class="col-stat hide-mobile" title="Lost">L</th>'
        '<th class="col-stat hide-mobile" title="Goals for">GF</th>'
        '<th class="col-stat hide-mobile" title="Goals against">GA</th>'
        '<th class="col-stat hide-mobile" title="Goal difference">GD</th>'
        '<th class="col-stat" title="Points">Pts</th>'
        '<th class="col-desk" title="Model probability">Model</th>'
        '<th class="col-desk hide-mobile" title="Market-implied probability">Market</th>'
        '<th class="col-desk hide-mobile" title="Model minus market, points">Edge</th>'
        '</tr>'
        '</thead>'
    )
    table = (
        '<div class="tablewrap">'
        '<table class="standings">'
        f'{head}'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '</div>'
    )
    return table, total, picks, passes


def render_outrights_index(outrights: list[dict]) -> str:
    """Listing page at /outrights/ — every priced team rendered as one
    row of a league-style standings table. Column contract is the same
    component a league table will reuse later: Team · Verdict · P · W ·
    D · L · GF · GA · GD · Pts · Model · Market · Edge. The stat block
    is data-driven — empty (—) on winner markets pre-kick-off, populated
    from `row['standings']` on league markets. Sort key swaps too:
    winner markets sort by model probability, league tables by points.
    When no outright market has a Pick or Avoid verdict the page falls
    back to a coming-soon empty state."""
    decisive = [
        o for o in (outrights or [])
        if (o.get("verdict") or {}).get("state") in ("pick", "avoid")
    ]
    if not decisive:
        return (
            chrome_head(
                "Outright winners · Odds Primer",
                description="Outright (tournament-winner) verdicts — Polymarket and Kalshi side-by-side.",
                path="/outrights/",
            )
            + chrome_masthead("outrights")
            + '<main class="page">'
              '<section class="page-header">'
              '<a class="crumb" href="/"><span class="arr">←</span> Home</a>'
              '<h1>Outright winners</h1>'
              '</section>'
              '<div class="empty-state">'
              '<h2>Outright verdicts — coming with the next engine update.</h2>'
              '<p>The Desk publishes per-match verdicts today. Tournament-winner outrights '
              '(World Cup 2026 champion, group winners, golden boot) are the next thing we wire up. '
              'Check back, or follow the matches page for the current verdicts.</p>'
              '</div>'
              '</main>'
            + chrome_footer()
        )

    sections: list[str] = []
    pick_total = 0
    pass_total = 0
    total = 0
    primary_outright = decisive[0]
    for outright in decisive:
        table, n, picks, passes = _standings_table(outright)
        if not n:
            continue
        if len(decisive) > 1:
            heading = outright.get("market_label") or outright.get("competition", {}).get("label", "Outright")
            sections.append(f'<h2 class="date-head">{escape(heading)}</h2>{table}')
        else:
            sections.append(table)
        total += n
        pick_total += picks
        pass_total += passes

    market_label = escape(primary_outright.get("market_label") or "Tournament winner")
    standfirst_inner = (
        f'{market_label} · '
        f'<strong>{pick_total} Pick{"s" if pick_total != 1 else ""}</strong> · '
        f'{pass_total} Pass across {total} priced sides.'
    )
    standfirst = (
        '<p class="standfirst" style="font-family:var(--font-serif);font-style:italic;'
        'color:var(--ink-soft);margin:14px 0 0;max-width:60ch;">'
        f'{standfirst_inner}'
        '</p>'
    )

    # Meta strip: source venue · resolves-on · as-of stamp. Pulled from
    # the primary outright (today there's only one decisive outright).
    venue = (
        primary_outright.get("market_venue")
        or (primary_outright.get("verdict") or {}).get("market_venue")
        or "Polymarket"
    ).title()
    resolves_label = ""
    if primary_outright.get("resolves_at"):
        try:
            rdt = datetime.fromisoformat(primary_outright["resolves_at"].replace("Z", "+00:00"))
            resolves_label = rdt.strftime("%-d %b %Y")
        except (ValueError, AttributeError):
            resolves_label = ""
    asof_label = ""
    if primary_outright.get("asof") or primary_outright.get("updated_at"):
        try:
            adt = datetime.fromisoformat(
                (primary_outright.get("asof") or primary_outright["updated_at"]).replace("Z", "+00:00")
            )
            asof_label = adt.strftime("%-d %b, %H:%M UTC")
        except (ValueError, AttributeError):
            asof_label = ""
    meta_bits = [f'<span><b>Source</b> {escape(venue)}</span>']
    if resolves_label:
        meta_bits.append(f'<span><b>Resolves</b> {escape(resolves_label)}</span>')
    if asof_label:
        meta_bits.append(f'<span><b>As of</b> {escape(asof_label)}</span>')
    meta = f'<div class="standings-meta">{"".join(meta_bits)}</div>'

    legend = (
        '<div class="standings-legend">'
        '<span><b>Model</b> the Desk\'s simulated probability</span>'
        '<span><b>Market</b> price-implied probability</span>'
        '<span><b>Edge</b> model − market, in points</span>'
        '<span><span class="chip pick">Pick</span> edge clears +3.0pp</span>'
        '<span><span class="chip pass">Pass</span> no decisive gap</span>'
        '</div>'
    )
    note = (
        '<p class="standings-note">'
        '<span class="dag">†</span> Stat columns sit empty until the tournament kicks off — '
        'a winner market has no games played yet. The same cells fill automatically once group play begins.'
        '</p>'
    )

    # Whole-row click → drill-down. Inline so the page stays self-contained.
    row_click_js = (
        '<script>'
        'document.querySelectorAll("table.standings").forEach(t=>'
        't.addEventListener("click",e=>{'
        'const tr=e.target.closest("tr[data-href]");'
        'if(!tr)return;'
        'if(e.target.closest("a"))return;'
        'window.location.href=tr.dataset.href;}));'
        '</script>'
    )

    return (
        chrome_head(
            "Outright winners · Odds Primer",
            description="Tournament-winner verdicts — every priced team with the model's edge against the market.",
            path="/outrights/",
        )
        + chrome_masthead("outrights")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/"><span class="arr">←</span> Home</a>'
          '<h1>Outright winners</h1>'
          f'{standfirst}'
          f'{meta}'
          '</section>'
        + "\n".join(sections)
        + legend
        + note
        + '</main>'
        + row_click_js
        + chrome_footer()
    )


def _ladder_blurb_for(row: dict) -> str:
    """One-sentence editorial read for a single team in the ladder.
    The wording branches on verdict + edge sign so a reader can scan
    48 rows and instantly see which way the model leans on each side."""
    team = row.get("team", "this team")
    mp = row.get("model_p") or 0.0
    mkp = row.get("yes_market_p") or 0.0
    edge = row.get("yes_edge_pp")
    lower = row.get("yes_lower_edge_pp")
    state = row.get("verdict", "pass")
    mp_pct = f"{mp * 100:.1f}%"
    mkp_pct = f"{mkp * 100:.1f}%"
    if state == "pick":
        tail = ""
        if isinstance(lower, (int, float)):
            tail = (
                f" Bootstrap lower bound ({lower:+.1f}pp) clears the +3.0pp"
                f" Pick threshold."
            )
        return (
            f"Model rates {team} at {mp_pct}; market prices that side at"
            f" {mkp_pct}. The {edge:+.1f}pp gap is the basis for the Pick."
            f"{tail}"
        )
    if state == "avoid":
        return (
            f"Model rates {team} at {mp_pct}, well below market {mkp_pct}"
            f" ({edge:+.1f}pp). The market is paying a premium the model"
            f" does not back."
        )
    if not isinstance(edge, (int, float)):
        return f"Model {mp_pct} · market {mkp_pct}. No verdict computed."
    if edge >= 1.5:
        tail = ""
        if isinstance(lower, (int, float)):
            if lower > 0:
                tail = (
                    f" Bootstrap lower bound ({lower:+.1f}pp) is positive"
                    f" but doesn't clear the +3.0pp threshold."
                )
            else:
                tail = (
                    f" Bootstrap lower bound ({lower:+.1f}pp) crosses zero,"
                    f" so the edge isn't robust enough to act on."
                )
        return (
            f"Model leans yes — {mp_pct} vs market {mkp_pct} ({edge:+.1f}pp)."
            f"{tail}"
        )
    if edge <= -1.5:
        return (
            f"Model leans no — {mp_pct} vs market {mkp_pct} ({edge:+.1f}pp)."
            f" The market is paying more than the model thinks the side is"
            f" worth."
        )
    return (
        f"Priced close to fair: model {mp_pct} vs market {mkp_pct}"
        f" ({edge:+.1f}pp). No edge in either direction."
    )


def render_outright_ladder(outright: dict) -> str:
    """Per-team verdict ladder for an outright. Sorted by model_p desc;
    rendered as a grid of cards. Each card carries team, verdict pill,
    model/market/edge stats, a short editorial blurb, and a CTA to the
    outright market URL (Polymarket has no stable per-team deep-link,
    so every card lands on the same event page where the user can act)."""
    ladder = outright.get("ladder") or []
    if not ladder:
        return ""
    rows_sorted = sorted(ladder, key=lambda r: -(r.get("model_p") or 0))
    poly_url_raw = outright.get("market_url") or (outright.get("verdict") or {}).get("market_url") or ""
    poly_url = _normalise_polymarket_url(poly_url_raw) if poly_url_raw else ""
    cards = []
    for row in rows_sorted:
        team = row.get("team", "—")
        model_p = row.get("model_p")
        market_p = row.get("yes_market_p")
        edge_pp = row.get("yes_edge_pp")
        state = row.get("verdict", "pass")
        glyph = GLYPHS.get(state, "—")
        label = LABELS.get(state, "Pass")
        edge_class = ""
        if isinstance(edge_pp, (int, float)) and edge_pp < 0:
            edge_class = " is-neg"
        blurb = _ladder_blurb_for(row)
        links: list[str] = []
        if poly_url:
            poly_text = f"See {team} on Polymarket"
            links.append(
                f'<a class="lc-link" href="{escape(poly_url)}" rel="nofollow noopener" '
                f'target="_blank" aria-label="{escape(poly_text)}">'
                f'<span aria-hidden="true">{escape(poly_text)} ↗</span></a>'
            )
        kalshi_url, kalshi_is_live = _kalshi_outright_url_for(team)
        if kalshi_url and kalshi_is_live:
            kalshi_text = f"See {team} on Kalshi"
            links.append(
                f'<a class="lc-link" href="{escape(kalshi_url)}" rel="nofollow noopener" '
                f'target="_blank" aria-label="{escape(kalshi_text)}">'
                f'<span aria-hidden="true">{escape(kalshi_text)} ↗</span></a>'
            )
        cta = "".join(links)
        cards.append(
            f'<article class="lc-card is-{state}">'
            f'<header class="lc-head">'
            f'<span class="lc-team">{escape(team)}</span>'
            f'<span class="lc-verdict">'
            f'<span class="lc-glyph" aria-hidden="true">{glyph}</span>'
            f'<span class="lc-lab">{label}</span>'
            f'</span>'
            f'</header>'
            f'<dl class="lc-stats">'
            f'<div><dt>Model</dt><dd>{fmt_pct(model_p)}</dd></div>'
            f'<div><dt>Market</dt><dd>{fmt_pct(market_p)}</dd></div>'
            f'<div><dt>Edge</dt><dd class="lc-edge{edge_class}">{fmt_edge(edge_pp) or "—"}</dd></div>'
            f'</dl>'
            f'<p class="lc-blurb">{escape(blurb)}</p>'
            f'{cta}'
            f'</article>'
        )
    return (
        '<section class="ladder">'
        '<h2>Verdicts across the field</h2>'
        f'<div class="lc-grid">{"".join(cards)}</div>'
        '</section>'
    )


def _ordinal(n: int) -> str:
    """1 → '1st', 22 → '22nd'. Stays inside the function family because
    nothing else in this file uses ordinals."""
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _pick_threshold_p(market_p: float) -> float:
    """Model probability at which a YES Pick fires (market_p + 3pp)."""
    return market_p + 0.03


def _outright_team_blurb_paragraphs(outright: dict, row: dict) -> list[str]:
    """Multi-paragraph editorial read for a per-team outright page.
    Synthesised from the row's data + the surrounding ladder so every
    team gets a meaningful dedicated page even when the engine never
    wrote prose for it.

    Ranks the team by `model_p` against the rest of the ladder and
    cross-references the leader, the immediate neighbours, and the
    Pick threshold so a Pass team's page reads as editorial rather
    than as a footnote.
    """
    team = row.get("team", "this team")
    mp = row.get("model_p")
    mp_lower = row.get("model_p_lower")
    mp_upper = row.get("model_p_upper")
    mkp = row.get("yes_market_p")
    edge = row.get("yes_edge_pp")
    lower = row.get("yes_lower_edge_pp")
    state = row.get("verdict", "pass")
    pick_side = row.get("pick_side")

    market_label = outright.get("market_label") or outright.get("competition", {}).get("label", "the outright")
    market_label_lower = market_label.lower()
    mp_pct = f"{(mp or 0) * 100:.1f}%"
    mkp_pct = f"{(mkp or 0) * 100:.1f}%"

    # ── Rank the team against the rest of the ladder by model_p ────
    ladder = list(outright.get("ladder") or [])
    by_model = sorted(
        ladder, key=lambda r: r.get("model_p") or 0.0, reverse=True,
    )
    rank: int | None = None
    leader: dict | None = None
    field_size = len(by_model)
    for i, r in enumerate(by_model, 1):
        if r.get("team") == team:
            rank = i
            break
    if by_model and by_model[0].get("team") != team:
        leader = by_model[0]

    # Ranked-by-market context — useful when model + market disagree
    # on the leader (which is the whole reason this market exists).
    by_market = sorted(
        ladder, key=lambda r: r.get("yes_market_p") or 0.0, reverse=True,
    )
    market_rank: int | None = None
    for i, r in enumerate(by_market, 1):
        if r.get("team") == team:
            market_rank = i
            break

    paragraphs: list[str] = []

    if state == "pick":
        side_str = f"{pick_side} {team}" if pick_side else team
        paragraphs.append(
            f"The Desk's model rates {team} at {mp_pct} to win {market_label_lower}. "
            f"The market currently prices that side at {mkp_pct} — a {edge:+.1f}pp gap. "
            f"The position is {side_str}, and the verdict is Pick."
        )
        if rank is not None and field_size:
            ranking = (
                f"That's the {_ordinal(rank)}-highest probability the model "
                f"assigns in a field of {field_size}."
            )
            if market_rank is not None and market_rank != rank:
                ranking += (
                    f" The market has {team} {_ordinal(market_rank)} on its own ladder — "
                    f"the disagreement on where {team} sits is precisely what creates the edge."
                )
            paragraphs.append(ranking)
        if isinstance(lower, (int, float)) and isinstance(mp_lower, (int, float)) and isinstance(mp_upper, (int, float)):
            paragraphs.append(
                f"Across 100 bootstrap re-simulations of the tournament the model's "
                f"probability lands in the band [{mp_lower * 100:.1f}%, {mp_upper * 100:.1f}%]. "
                f"Even at the conservative floor the YES edge against the market is {lower:+.1f}pp — "
                f"which clears the +3.0pp Pick threshold."
            )
        paragraphs.append(
            "The Desk doesn't tip. We publish what the model thinks and what the market thinks; "
            "the gap is editorial. Take the position only if you've read the case and the price still stands."
        )
        return paragraphs

    if state == "avoid":
        paragraphs.append(
            f"The Desk's model rates {team} at {mp_pct} to win {market_label_lower} — well below "
            f"the market's {mkp_pct} ({edge:+.1f}pp). The verdict is Avoid."
        )
        if rank is not None and market_rank is not None and field_size:
            spread = market_rank - rank
            if spread <= -2:
                paragraphs.append(
                    f"The Desk has {team} {_ordinal(rank)} on the model ladder; "
                    f"the market has them {_ordinal(market_rank)}. The market is paying "
                    f"for an outcome the model thinks is meaningfully less likely than "
                    f"the betting public has priced in."
                )
            else:
                paragraphs.append(
                    f"The Desk has {team} {_ordinal(rank)} in a field of {field_size}; "
                    f"the market has them {_ordinal(market_rank)}. Even by the model's own "
                    f"ranking, the price is buying a contender — the Desk just doesn't think "
                    f"that contender is worth what the market is asking."
                )
        if isinstance(mp_upper, (int, float)) and mkp is not None:
            paragraphs.append(
                f"Across 100 bootstrap re-simulations the model's probability never gets "
                f"above {mp_upper * 100:.1f}% — still below the {mkp_pct} the market is asking. "
                f"In the simulations where {team} look best, the YES side is still overpriced."
            )
        paragraphs.append(
            "Avoid is structural — it doesn't tell you to take the NO side; it tells you the "
            "YES price isn't fair. If you do trade, the case has to come from somewhere else."
        )
        return paragraphs

    # ── Pass — the long tail ───────────────────────────────────────
    #
    # The thin two-sentence stub that shipped first read as a footnote
    # rather than an editorial — most of the ladder is Pass, so the
    # tail has to carry its own weight. The synthesised read does
    # four things: states the model + market split (1), places the
    # team in the ladder (2), quantifies what would have to change
    # for a Pick or Avoid to fire (3), and closes on what Pass means
    # for a reader (4).

    paragraphs.append(
        f"The Desk's model rates {team} at {mp_pct} to win {market_label_lower}; "
        f"the market prices that side at {mkp_pct}. The edge is {edge:+.1f}pp — "
        + ("inside the Pass band." if abs(edge or 0) < 1.5 else
           ("a lean toward YES that doesn't clear the bar." if (edge or 0) >= 1.5 else
            "a lean toward NO that doesn't clear the Avoid bar."))
    )

    if rank is not None and field_size:
        ladder_line = (
            f"That puts {team} {_ordinal(rank)} on the model ladder in a field of {field_size}."
        )
        if leader is not None:
            leader_pct = (leader.get("model_p") or 0) * 100
            leader_team = leader.get("team", "the leader")
            ladder_line += (
                f" The model's leader, {leader_team}, sits at {leader_pct:.1f}%."
            )
        if market_rank is not None and market_rank != rank:
            ladder_line += (
                f" The market has {team} {_ordinal(market_rank)} on its own ladder — "
                f"so reader and model disagree about where this side belongs, but not "
                f"by enough to publish a position."
            )
        paragraphs.append(ladder_line)

    # Quantify what would have to move for a Pick to trip — a useful
    # editorial hook: it tells the reader what to watch.
    if isinstance(mp, (int, float)) and isinstance(mkp, (int, float)):
        threshold_pct = (_pick_threshold_p(mkp)) * 100
        current_pct = mp * 100
        if threshold_pct > current_pct:
            band_hits = (
                isinstance(mp_upper, (int, float))
                and mp_upper * 100 >= threshold_pct
            )
            band_phrase = (
                f"the band runs [{(mp_lower or 0) * 100:.1f}%, {(mp_upper or 0) * 100:.1f}%], "
                + ("so even at the upper end the Pick bar is in reach."
                   if band_hits else
                   "and even at the upper end the Pick bar isn't reached.")
            )
            paragraphs.append(
                f"For the verdict to flip to Pick at today's market price, the model would "
                f"need to rate {team} at {threshold_pct:.1f}% or better — a "
                f"{threshold_pct - current_pct:.1f}pp move from where it sits now. "
                f"Across 100 bootstrap re-simulations of the tournament {band_phrase}"
            )

    paragraphs.append(
        "Pass isn't 'no opinion'. It's the Desk saying the price and the model agree closely "
        "enough that there's no edge to publish. A reader can still take a side on conviction; "
        "we just don't have an editorial reason to push them either way."
    )
    return paragraphs


def render_outright_team_page(outright: dict, row: dict) -> str:
    """Per-team dedicated page at /outrights/{team-slug}. Mirrors the
    per-match page skeleton: chrome, crumb back to /outrights/, h1
    team name, the team's lv-card (overlay disabled — already on the
    page), a multi-paragraph editorial blurb, and a CTA out to the
    outright market URL."""
    team = row.get("team", "Outright entry")
    state = row.get("verdict", "pass")
    market_label = outright.get("market_label") or outright.get("competition", {}).get("label", "Outright")
    verdict_word = LABELS.get(state, "Pass")

    title = f"{team} · {verdict_word} · {market_label}"
    paragraphs = _outright_team_blurb_paragraphs(outright, row)
    blurb_html = "\n".join(f"<p>{escape(p)}</p>" for p in paragraphs)

    market_url = outright.get("market_url") or (outright.get("verdict") or {}).get("market_url")
    if market_url:
        market_url = _normalise_polymarket_url(market_url)
    cta_row = _outright_cta_row(market_url, team)

    description = paragraphs[0] if paragraphs else f"Verdict for {team} in the {market_label} market."

    return (
        chrome_head(
            f"{team} · Odds Primer",
            description=description,
            path=f"/outrights/{_team_slug(team)}",
        )
        + chrome_masthead("outrights")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/outrights/"><span class="arr">←</span> All outright winners</a>'
          f'<h1>{escape(team)}</h1>'
          f'<p class="standfirst" style="font-family:var(--font-serif);font-style:italic;'
          f'color:var(--ink-soft);margin:14px 0 0;">{escape(market_label)} · '
          f'<strong style="color:var(--flame-deep)">{escape(verdict_word)}</strong></p>'
          '</section>'
        + render_outright_team_card(outright, row, show_overlay=False)
        + (f'<div class="blurb">{blurb_html}</div>' if blurb_html else "")
        + cta_row
        + '</main>'
        + chrome_footer()
    )


def render_outright_page(outright: dict) -> str:
    """Per-outright page. Same skeleton as per-match."""
    title = outright.get("copy", {}).get("title") or outright.get("candidate", "Outright")
    summary = outright.get("copy", {}).get("summary") or ""
    blurb = outright.get("copy", {}).get("blurb") or ""
    drivers = outright.get("copy", {}).get("drivers") or []

    blurb_paras = "\n".join(f"<p>{escape(p)}</p>" for p in blurb.split("\n\n") if p.strip())
    drivers_html = ""
    if drivers:
        items = "\n".join(f'<li>{escape(d)}</li>' for d in drivers)
        drivers_html = f'<section class="drivers"><h2>The drivers</h2><ol>{items}</ol></section>'

    v = outright.get("verdict", {})
    market_url = v.get("market_url") or outright.get("market_url")
    if market_url:
        market_url = _normalise_polymarket_url(market_url)
    candidate = v.get("team") or v.get("candidate") or outright.get("candidate")
    cta_row = _outright_cta_row(market_url, candidate)

    return (
        chrome_head(
            f"{title} · Odds Primer",
            description=summary or f"Verdict and per-team ladder for the {title} market.",
            path=f"/outrights/{outright.get('outright_id', '')}",
        )
        + chrome_masthead("outrights")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/outrights/"><span class="arr">←</span> All outrights</a>'
          f'<h1>{escape(title)}</h1>'
          '</section>'
        + render_outright_card(outright)
        + (f'<div class="blurb">{blurb_paras}</div>' if blurb_paras else "")
        + cta_row
        + drivers_html
        + render_outright_ladder(outright)
        + '</main>'
        + chrome_footer()
    )


# ─── Loaders ───

def load_matches() -> list[dict]:
    if not FOOTBALL_DIR.exists():
        return []
    matches = []
    for path in sorted(FOOTBALL_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            matches.append(json.loads(path.read_text()))
        except json.JSONDecodeError as e:
            print(f"  skip (bad json): {path.name} — {e}", file=sys.stderr)
    return matches


def load_outrights() -> list[dict]:
    if not OUTRIGHTS_DIR.exists():
        return []
    outrights = []
    for path in sorted(OUTRIGHTS_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            outrights.append(json.loads(path.read_text()))
        except json.JSONDecodeError as e:
            print(f"  skip (bad json): {path.name} — {e}", file=sys.stderr)
    return outrights


def filter_priced_upcoming(matches: list[dict], now_utc: datetime | None = None) -> list[dict]:
    """Drop matches with no Polymarket URL (unpriced) and matches in the past."""
    now = now_utc or datetime.now(timezone.utc)
    kept = []
    for m in matches:
        # Past matches
        try:
            ko = datetime.fromisoformat(m["kickoff_utc"].replace("Z", "+00:00"))
            if ko < now:
                continue
        except Exception:
            pass
        kept.append(m)
    return kept


# ─── Entry point ───

# ── sitemap.xml + robots.txt ──────────────────────────────────────────────
# Static, indexable pages that the server actually routes (see server.py's
# _EDITORIAL_PAGES + explicit routes). /the-desk is routed but stays out
# of the sitemap — it's a meta-refresh to /methodology, the canonical URL.
# Outrights are hidden until a real verdict lands, so they're excluded too.
_SITEMAP_STATIC = [
    # (url path, backing file under SITE_OUT, priority, changefreq)
    ("/",                     "index.html",          "1.0", "hourly"),
    ("/matches",              "matches/index.html",  "0.9", "hourly"),
    ("/about",                "about.html",          "0.4", "monthly"),
    ("/method",               "method.html",         "0.5", "monthly"),
    ("/methodology",          "methodology.html",    "0.5", "monthly"),
    ("/responsible-use",      "responsible-use.html","0.3", "yearly"),
    ("/affiliate-disclosure", "affiliate-disclosure.html", "0.3", "yearly"),
    ("/corrections",          "corrections.html",    "0.3", "yearly"),
    ("/terms",                "terms.html",          "0.2", "yearly"),
    ("/privacy",              "privacy.html",        "0.2", "yearly"),
    ("/cookies",              "cookies.html",        "0.2", "yearly"),
]

# SPA-owned, server-routed via SPA_PREFIXES (server.py). No backing static
# file — content lives in frontend/src/op/. Listed here so the sitemap
# advertises them; ranking still depends on the SPA being indexable
# (per-route titles + meta live in OpApp.jsx's META map).
_SITEMAP_SPA = [
    # (url path, priority, changefreq)
    ("/world-cup",                      "0.9", "hourly"),
    ("/learn",                          "0.6", "weekly"),
    ("/learn/what-is-a-prediction-market", "0.5", "monthly"),
    ("/learn/how-prices-are-set",          "0.5", "monthly"),
    ("/learn/is-it-legal",                 "0.5", "monthly"),
    ("/learn/is-kalshi-legit",             "0.5", "monthly"),
    ("/learn/prediction-market-fees",      "0.5", "monthly"),
    ("/learn/how-to-start",                "0.5", "monthly"),
]


def _match_is_indexable(m: dict) -> bool:
    """Mirror render_match_page's noindex gate: only matches with a real
    verdict + prose are indexable, so only those belong in the sitemap."""
    v = m.get("verdict") or {}
    copy = m.get("copy") or {}
    return bool(
        v.get("state") in ("pick", "pass", "avoid")
        and (copy.get("blurb") or copy.get("summary"))
    )


def render_sitemap(matches: list[dict]) -> str:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: list[str] = []

    def add(loc: str, lastmod: str, priority: str, changefreq: str) -> None:
        rows.append(
            "  <url>\n"
            f"    <loc>{escape(loc)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )

    for path, rel, priority, changefreq in _SITEMAP_STATIC:
        if (SITE_OUT / rel).is_file():
            add(BASE_URL + path, today, priority, changefreq)

    for path, priority, changefreq in _SITEMAP_SPA:
        add(BASE_URL + path, today, priority, changefreq)

    for m in matches:
        if not _match_is_indexable(m):
            continue
        updated = (m.get("updated_at") or "")[:10] or today
        add(f"{BASE_URL}/m/{m['match_id']}", updated, "0.7", "daily")

    body = "\n".join(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def render_robots() -> str:
    """Allow everything indexable; keep crawlers off app/API surfaces and
    point them at the sitemap."""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /dashboard\n"
        "Disallow: /backtest\n"
        "\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Odds Primer static site generator")
    parser.add_argument("--quiet", action="store_true", help="suppress per-file output")
    parser.add_argument("--include-past", action="store_true", help="include matches whose kickoff is in the past")
    args = parser.parse_args()

    log = (lambda *a, **k: None) if args.quiet else print

    log(f"Reading from   : {DESK_OUT}")
    log(f"Writing to     : {SITE_OUT}")
    SITE_OUT.mkdir(parents=True, exist_ok=True)
    (SITE_OUT / "m").mkdir(exist_ok=True)
    (SITE_OUT / "matches").mkdir(exist_ok=True)
    (SITE_OUT / "outrights").mkdir(exist_ok=True)

    matches = load_matches()
    log(f"Loaded matches : {len(matches)}")

    if not args.include_past:
        kept = filter_priced_upcoming(matches)
        log(f"  after filter : {len(kept)} upcoming (dropped {len(matches) - len(kept)} past)")
        matches = kept

    # Sort by kickoff
    matches.sort(key=lambda m: m["kickoff_utc"])

    outrights = load_outrights()
    log(f"Loaded outrights: {len(outrights)}")

    # Pull the Kalshi WC 2026 event index so every "Trade on Kalshi"
    # button can deep-link to the right market.
    global KALSHI_EVENT_INDEX, KALSHI_OUTRIGHT_INDEX
    KALSHI_EVENT_INDEX = _load_kalshi_event_index()
    log(f"Loaded kalshi  : {len(KALSHI_EVENT_INDEX)} WC26 events")
    KALSHI_OUTRIGHT_INDEX = _load_kalshi_outright_index()
    log(f"Loaded kalshi  : {len(KALSHI_OUTRIGHT_INDEX)} outright markets")

    # Home
    (SITE_OUT / "index.html").write_text(render_home(matches, outrights))
    log("Wrote          : index.html")

    # Matches index
    (SITE_OUT / "matches" / "index.html").write_text(render_matches_index(matches))
    log("Wrote          : matches/index.html")

    # Per-match pages
    for m in matches:
        (SITE_OUT / "m" / f"{m['match_id']}.html").write_text(render_match_page(m))
    log(f"Wrote          : {len(matches)} match page(s) in m/")

    # Outrights pages render only when at least one market produces a
    # Pick or Avoid verdict. /outrights/ becomes a team-card listing
    # that mirrors /matches/ — every team in every decisive market is
    # its own lv-card. Each card links to /outrights/{team-slug} for a
    # dedicated per-team page. Pass-state outright markets are left
    # out so search engines don't index empty placeholders.
    decisive = [
        o for o in outrights
        if (o.get("verdict") or {}).get("state") in ("pick", "avoid")
    ]
    out_dir = SITE_OUT / "outrights"
    out_idx = out_dir / "index.html"
    legacy_o_dir = SITE_OUT / "o"
    if decisive:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_idx.write_text(render_outrights_index(decisive))
        log(f"Wrote          : outrights/index.html ({len(decisive)} decisive market(s))")
        kept_slugs: set[str] = set()
        team_pages = 0
        for outright in decisive:
            for row in outright.get("ladder") or []:
                slug = _team_slug(row.get("team", ""))
                if not slug:
                    continue
                (out_dir / f"{slug}.html").write_text(
                    render_outright_team_page(outright, row)
                )
                kept_slugs.add(slug)
                team_pages += 1
        log(f"Wrote          : {team_pages} team page(s) in outrights/")
        # Sweep any orphans (retired team pages from a previous run, or
        # the old per-outright market pages that this scheme replaced).
        n_removed = 0
        for stale in out_dir.glob("*.html"):
            if stale.name == "index.html":
                continue
            if stale.stem in kept_slugs:
                continue
            stale.unlink()
            n_removed += 1
        if n_removed:
            log(f"Removed        : {n_removed} stale page(s) in outrights/")
    else:
        if out_idx.exists():
            out_idx.unlink()
            log("Removed        : outrights/index.html (no pick/avoid verdict)")
        for stale in out_dir.glob("*.html"):
            if stale.name == "index.html":
                continue
            stale.unlink()
    # Sweep the retired /o/ output dir on every build — the server now
    # 301s /o/{id} to /outrights/, so any leftover static HTML there
    # would be unreachable and confuse search engines if rediscovered.
    if legacy_o_dir.is_dir():
        n_legacy = 0
        for stale in legacy_o_dir.glob("*.html"):
            stale.unlink()
            n_legacy += 1
        if n_legacy:
            log(f"Removed        : {n_legacy} retired page(s) in legacy o/")

    # Hand-written editorial pages live under site/public/ as flat HTML;
    # the generator doesn't rewrite them, but it does inject (or strip)
    # the newsletter pop-up + footer signup so they stay in sync.
    patch_editorial_pages(log=log)

    # sitemap.xml + robots.txt (regenerated every run so they track the
    # current indexable match set)
    (SITE_OUT / "sitemap.xml").write_text(render_sitemap(matches))
    n_urls = render_sitemap(matches).count("<url>")
    log(f"Wrote          : sitemap.xml ({n_urls} URLs)")
    (SITE_OUT / "robots.txt").write_text(render_robots())
    log("Wrote          : robots.txt")

    log(f"\n✓ Site ready  : {SITE_OUT}")


if __name__ == "__main__":
    main()
