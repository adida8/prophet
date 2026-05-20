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
  site/public/o/{outright_id}.html          (per-outright page)

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
  --hairline:        1px solid var(--rule);
  --hairline-soft:   1px solid var(--rule-soft);
  --hairline-strong: 2px solid var(--ink);
  --font-sans:    'Inter Tight', 'Söhne', 'Inter', system-ui, sans-serif;
  --font-serif:   'Source Serif 4', 'Charter', 'Georgia', serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', 'Menlo', monospace;
  --gutter: clamp(16px, 4vw, 56px);
  --dur-fast: 160ms;
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; background: var(--paper); color: var(--ink); -webkit-font-smoothing: antialiased; }
body { font-family: var(--font-sans); font-size: 15px; line-height: 1.5; }
.page { max-width: 1180px; margin: 0 auto; padding: 0 var(--gutter); }
a { color: inherit; }

/* MASTHEAD */
.masthead { border-top: var(--hairline-strong); background: var(--paper); }
.masthead .inner {
  max-width: 1180px; margin: 0 auto;
  padding: 14px var(--gutter) 12px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
}
.brand { display: inline-flex; flex-direction: column; gap: 4px; text-decoration: none; color: var(--ink); }
.brand .wm-row { display: flex; align-items: baseline; gap: 10px; }
.brand .glyph { display: inline-flex; align-items: flex-end; gap: 2px; height: 22px; }
.brand .glyph span { display: block; width: 4px; background: var(--ink); border-radius: 0.5px; }
.brand .glyph span:nth-child(1) { height: 22%; }
.brand .glyph span:nth-child(2) { height: 38%; }
.brand .glyph span:nth-child(3) { height: 65%; background: var(--flame); }
.brand .glyph span:nth-child(4) { height: 30%; }
.brand .wm { font-family: var(--font-serif); font-weight: 800; font-size: 22px; letter-spacing: -0.02em; line-height: 1; }
.brand .tag { font-family: var(--font-serif); font-style: italic; font-weight: 400; font-size: 12px; line-height: 1.3; color: var(--graphite); }
.brand .tag .flame { color: var(--flame-deep); font-style: normal; font-weight: 600; }

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
  min-width: 240px; background: var(--paper-pure); border: var(--hairline);
  list-style: none; margin: 0; padding: 6px 0;
  box-shadow: 0 8px 24px rgba(14, 34, 64, 0.08); z-index: 50;
}
.burger-menu li { padding: 0; margin: 0; list-style: none; }
.burger-menu a {
  display: block; padding: 10px 18px;
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  letter-spacing: 0.02em; color: var(--ink); text-decoration: none;
}
.burger-menu a:hover { background: var(--paper-warm); color: var(--flame-deep); }
.burger-menu a[aria-current="page"] { color: var(--flame-deep); border-left: 3px solid var(--flame); padding-left: 15px; }
@media (min-width: 820px) { .burger { display: none; } }

/* Mobile pill-nav — visible primary links beneath the masthead on small
   screens. Hidden on desktop where the full .site-nav is shown. */
.pill-nav {
  display: flex; gap: 6px; align-items: center;
  padding: 10px var(--gutter) 12px;
  border-bottom: var(--hairline); background: var(--paper);
  overflow-x: auto; scrollbar-width: none;
}
.pill-nav::-webkit-scrollbar { display: none; }
.pill-nav a {
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  letter-spacing: -0.005em; color: var(--ink); text-decoration: none;
  padding: 8px 14px; border-radius: 999px; white-space: nowrap;
  border: var(--hairline);
  transition: background var(--dur-fast) var(--ease-standard),
              color var(--dur-fast) var(--ease-standard);
}
.pill-nav a[aria-current="page"] { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.pill-nav a:not([aria-current="page"]):hover { color: var(--flame-deep); border-color: var(--flame); }
@media (min-width: 820px) { .pill-nav { display: none; } }

.edition-strip { border-top: var(--hairline-soft); border-bottom: var(--hairline); background: var(--paper); }
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
  grid-template-columns: 6px 1fr;
  grid-template-rows: auto auto auto auto auto;
  column-gap: 22px; row-gap: 6px;
  padding: 22px 26px 22px 0;
  background: var(--paper-pure);
  border: var(--hairline);
  text-decoration: none; color: var(--ink);
  transition: background var(--dur-fast) var(--ease-standard);
}
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
}

.lv-card .lv-teams {
  grid-column: 2; grid-row: 2;
  font-family: var(--font-serif); font-weight: 600;
  font-size: clamp(22px, 2.6vw, 28px);
  line-height: 1.08; letter-spacing: -0.015em;
  color: var(--ink); margin: 4px 0 0; text-wrap: balance;
}
.lv-card .lv-teams .vs { color: var(--graphite-soft); font-weight: 400; font-style: italic; margin: 0 6px; }
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

/* Secondary "Read the case" CTA — text link, no pill. Sits next to the
   two primary trade pills as a tertiary action. */
.lv-card .lv-action a.cta-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-sans); font-size: 11px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink); text-decoration: none;
  padding: 7px 6px 6px;
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

.cta-row {
  margin: 28px 0 0; display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}
.cta-row .open-market {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 11px 16px;
  background: var(--ink); color: var(--paper);
  text-decoration: none; border-radius: 4px;
  font-family: var(--font-sans); font-size: 12px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  transition: background var(--dur-fast) var(--ease-standard);
}
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
  display: flex; flex-wrap: wrap; gap: 8px 22px;
  padding-top: 12px; border-top: var(--hairline-soft);
}
.site-foot .foot-nav a {
  color: var(--graphite-soft); text-decoration: none;
  font-size: 10.5px; letter-spacing: 0.12em;
  border-bottom: 1px solid transparent;
  padding-bottom: 1px;
  transition: color var(--dur-fast) var(--ease-standard),
              border-color var(--dur-fast) var(--ease-standard);
}
.site-foot .foot-nav a:hover { color: var(--flame-deep); border-bottom-color: var(--flame); }
"""

# ─── Page chrome (shared across all pages) ───

def chrome_head(title: str, description: str = "") -> str:
    """Return the <head> section for any page."""
    desc = description or "Educational verdicts on Polymarket and Kalshi prices. Pick · Pass · Avoid."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<style>{CSS}</style>
</head>
<body>
"""


def chrome_masthead(active: str, edition_label: str = "World Cup 2026") -> str:
    """Masthead + edition strip. `active` is one of 'home' / 'matches' / 'outrights'."""
    def cur(name: str) -> str:
        return ' aria-current="page"' if active == name else ""
    updated = datetime.now(timezone.utc).strftime("Updated %H:%M UTC")
    return f"""<header class="masthead">
  <div class="inner">
    <a class="brand" href="/" aria-label="Odds Primer home">
      <span class="wm-row">
        <span class="glyph" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
        <span class="wm">Odds Primer</span>
      </span>
      <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
    </a>
    <nav class="site-nav" aria-label="Primary">
      <ul>
        <li><a href="/"{cur('home')}>Home</a></li>
        <li><a href="/matches/"{cur('matches')}>Upcoming matches</a></li>
        <li><a href="/outrights/"{cur('outrights')}>Outright winners</a></li>
        <li><a href="/methodology"{cur('methodology')}>How it works</a></li>
        <li><a href="/learn"{cur('learn')}>Learn</a></li>
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
        <li><a href="/outrights/"{cur('outrights')}>Outright winners</a></li>
        <li><a href="/methodology"{cur('methodology')}>How it works</a></li>
        <li><a href="/learn"{cur('learn')}>Learn</a></li>
        <li><a href="/about"{cur('about')}>About</a></li>
        <li><a href="/responsible-use">Responsible use</a></li>
        <li><a href="/affiliate-disclosure">Affiliate disclosure</a></li>
        <li><a href="/corrections">Corrections</a></li>
      </ul>
    </details>
  </div>
</header>
<div class="edition-strip">
  <div class="inner">
    <span class="vol">Vol. 1 · {escape(edition_label)}</span>
    <span class="live">Markets live</span>
  </div>
</div>
<nav class="pill-nav" aria-label="Primary (mobile)">
  <a href="/"{cur('home')}>Home</a>
  <a href="/matches/"{cur('matches')}>Matches</a>
  <a href="/outrights/"{cur('outrights')}>Winners</a>
  <a href="/methodology"{cur('methodology')}>How it works</a>
  <a href="/learn"{cur('learn')}>Learn</a>
  <a href="/about"{cur('about')}>About</a>
</nav>
"""


def chrome_footer() -> str:
    today = datetime.now(timezone.utc).strftime("%-d %b %Y")
    return f"""<footer class="site-foot page">
  <div class="foot-row">
    <span class="left">Odds Primer · educational, not advice</span>
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
</body>
</html>
"""


# ─── Formatting helpers ───

def fmt_pct(p):
    if p is None: return "—"
    return f"{round(p * 100)}%"

def fmt_edge(edge_pp):
    if edge_pp is None: return None
    sign = "+" if edge_pp >= 0 else "−"
    return f"{sign}{abs(edge_pp):.1f}pp"

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
    """
    url = (verdict.get("market_url") or "").strip()
    if url and "polymarket.com" in url.lower():
        return url
    # No explicit Polymarket URL → degrade to a search.
    if fallback_search:
        from urllib.parse import quote_plus
        return f"https://polymarket.com/markets?_q={quote_plus(fallback_search)}"
    return "https://polymarket.com/"


KALSHI_WC_LANDING = "https://kalshi.com/category/sports/soccer/fifa-world-cup"

_KALSHI_MONTH_TO_NUM = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


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
            iso3_a = body[7:10].lower()
            iso3_b = body[10:13].lower()
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


# Kalshi UI URL pattern (confirmed via address-bar inspection on a
# real WC 2026 event page):
#
#   https://kalshi.com/markets/{series_lower}/{series_slug}/{event_ticker_lower}
#       ?op_market_ticker={MARKET_TICKER_UPPER}
#       &op_side=BUY&op_order_side=yes&op_order_type=dollars
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
    side preselected)."""
    body = event_ticker.removeprefix("KXWCGAME-")
    iso3_a = body[7:10].upper()
    iso3_b = body[10:13].upper()
    if pick_side_iso3 is None:
        return None
    if pick_side_iso3 == "draw":
        return f"{event_ticker}-TIE"
    if pick_side_iso3.upper() == iso3_a:
        return f"{event_ticker}-{iso3_a}"
    if pick_side_iso3.upper() == iso3_b:
        return f"{event_ticker}-{iso3_b}"
    return None


def _kalshi_url_for(
    match_id: str | None = None,
    *,
    pick_side_iso3: str | None = None,
) -> tuple[str, bool]:
    """Return (url, is_live).

    is_live=True  → real Kalshi event URL. The picked side is preselected
                    via `op_market_ticker=` when a side is known; for
                    Pass/Avoid we just land on the event page.
    is_live=False → WC landing page fallback (Kalshi has no event for
                    this fixture, or series slug not yet mapped).
    """
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
            market_ticker = _kalshi_market_ticker_for_side(
                event_ticker, pick_side_iso3=pick_side_iso3,
            )
            if market_ticker:
                from urllib.parse import quote
                return (
                    f"{base}?op_market_ticker={quote(market_ticker)}"
                    f"&op_side=BUY&op_order_side=yes&op_order_type=dollars",
                    True,
                )
            return (base, True)
    return (KALSHI_WC_LANDING, False)


def _cta_pill(
    label: str,
    url: str,
    *,
    placeholder: bool = False,
    caption: str | None = None,
    caption_kind: str = "",
) -> str:
    """Render a single trade CTA pill, optionally with a small caption
    underneath. `caption_kind`:
      - "best"  → highlighted "best price" caption (flame)
      - "live"  → priced-but-not-best caption (ink)
      - "search" → no live price detected (muted)
    """
    extra = " is-placeholder" if placeholder else ""
    pill = (
        f'<a class="cta market-cta{extra}" href="{escape(url)}" '
        f'target="_blank" rel="nofollow noopener">'
        f'{escape(label)} <span class="arr">↗</span>'
        f'</a>'
    )
    if not caption:
        return f'<span class="cta-stack">{pill}</span>'
    kind_cls = f" is-{caption_kind}" if caption_kind else ""
    return (
        f'<span class="cta-stack">'
        f'{pill}'
        f'<span class="cta-caption{kind_cls}">{escape(caption)}</span>'
        f'</span>'
    )


def _read_case_link(detail_href: str) -> str:
    """Secondary CTA — text-only "Read the case" link to the match/outright
    detail page. Styled tertiary so the two trade pills are the visual
    primary CTAs.
    """
    return (
        f'<a class="cta-secondary read-case" href="{escape(detail_href)}">'
        f'Read the case <span class="arr">→</span>'
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
) -> str:
    """Render the CTAs for a card.

    Tells the reader explicitly *which venue is the right one to trade
    on*. Each trade pill carries a small caption: "Best price · <odds>"
    on the venue Desk's verdict was struck against. Kalshi gets a real
    deep-link when we resolved a live event for this fixture; falls
    back to the WC 2026 landing page when we didn't.
    """
    poly_price   = (verdict.get("market_venue") or "").lower() == "polymarket" and price
    kalshi_price = verdict.get("kalshi_price")    # not produced yet; future hook

    poly_url = _polymarket_url_for(verdict, fallback_search=search_key)

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
        poly_caption, poly_kind = "Open the market", "live"

    poly_pill = _cta_pill(
        "Trade on Polymarket", poly_url,
        caption=poly_caption, caption_kind=poly_kind,
    )
    kalshi_pill = _cta_pill(
        "Trade on Kalshi", kalshi_url, placeholder=not kalshi_is_live,
        caption=kalshi_caption, caption_kind=kalshi_kind,
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


def render_card(match: dict, *, is_lead: bool = False) -> str:
    """Render one lv-card from a match JSON. Works for both Pick and Pass."""
    v = match["verdict"]
    state = v["state"]
    state_class = f"is-{state}" + (" is-lead" if is_lead else "")

    href = f"/m/{match['match_id']}"
    when = fmt_kickoff_full(match["kickoff_utc"])
    title = f"{escape(match['team_a'])} <span class=\"vs\">v</span> {escape(match['team_b'])}"

    # Header
    head = (
        f'<span class="lv-glyph" aria-hidden="true">{GLYPHS[state]}</span>'
        f'<span class="lv-lab">{LABELS[state]}</span>'
        f'<span class="lv-when">{escape(when)}</span>'
    )

    vmeta = venue_meta(match)
    thesis = escape(match["copy"]["summary"] or "")

    # Search-fallback key for Kalshi (no live ingest yet) and for
    # Polymarket if market_url is missing.
    search_key = f"{match.get('team_a','')} {match.get('team_b','')}".strip()

    cta_kwargs = dict(
        search_key=search_key,
        detail_href=href,
        match_id=match.get("match_id"),
        team_a=match.get("team_a"),
        team_b=match.get("team_b"),
    )

    # Foot — different for pick/avoid vs pass
    if state == "pass":
        cta_html = market_cta(v, **cta_kwargs)
        foot = (
            '<div class="lv-foot">'
            f'<span class="lv-flat-msg">Markets agree — within 1pp on every side.</span>'
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

        foot = (
            '<div class="lv-foot">'
            f'<div class="lv-reads">{reads}</div>'
            f'<div class="lv-action">{action_bits}</div>'
            '</div>'
        )

    # Card is a <div> so we can nest the venue CTA as a real <a>. The
    # whole card is still clickable via an absolute-positioned overlay
    # link that goes to the match detail page; the venue CTA sits above
    # it (z-index) so a click on the pill opens the market instead.
    return (
        f'<div class="lv-card {state_class}">'
        f'<a class="lv-card-link" href="{href}" aria-label="Read the case"></a>'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{title}</h3>'
        f'<p class="lv-venue-meta">{vmeta}</p>'
        f'<p class="lv-thesis">{thesis}</p>'
        f'{foot}'
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

    # Outrights teaser
    if outrights:
        outright_cards = "\n".join(render_outright_card(o) for o in outrights[:3])
        outrights_html = (
            '<div class="section-label">'
            '<span>Outright winners</span>'
            '<a class="see-all" href="/outrights/">See all outrights <span class="arr">→</span></a>'
            '</div>'
            f'{outright_cards}'
        )
    else:
        outrights_html = (
            '<div class="section-label"><span>Outright winners</span></div>'
            '<div class="empty-state">'
            '<h2>Outright verdicts — coming with the next engine update.</h2>'
            '<p>The Desk publishes per-match verdicts today. Tournament-winner outrights '
            '(World Cup 2026 champion) are queued for the next engine release.</p>'
            '</div>'
        )

    return (
        chrome_head("Odds Primer · The 2026 World Cup, priced.")
        + chrome_masthead("home")
        + '<main class="page">'
        + '<section class="hero">'
          '<h1>The 2026 World Cup, priced.</h1>'
          '<p class="standfirst">Our AI model compares Polymarket and Kalshi prices against its own '
          'read of every match. Every market gets one verdict: '
          '<em class="vlead">Pick</em>, <em class="vlead">Pass</em>, or <em class="vlead">Avoid</em>. '
          'We show the price, the edge, and the reasoning. We don\'t tip.</p>'
          '</section>'
        + '<section class="verdict-key" aria-label="Verdict key">'
            '<span class="vk-label">Verdict key</span>'
            '<div class="vk-item">'
              '<span class="vk-icon is-pick" aria-hidden="true">&#9650;</span>'
              '<span class="vk-text">'
                '<span class="vk-name is-pick">Pick</span>'
                '<span class="vk-desc">the line is underpriced &mdash; back it</span>'
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
        + headline_html
        + other_picks_html
        + outrights_html
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
        chrome_head("Upcoming matches · Odds Primer")
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


def render_match_page(match: dict) -> str:
    """Per-match page: header + lead card + blurb + drivers."""
    title = match["copy"].get("title") or f"{match['team_a']} v {match['team_b']}"
    summary = match["copy"].get("summary") or ""
    blurb = match["copy"].get("blurb") or ""
    drivers = match["copy"].get("drivers") or []
    v = match["verdict"]

    # Build the blurb paragraphs (single string for now; split on \n\n if multi-para)
    blurb_paras = "\n".join(f"<p>{escape(p)}</p>" for p in blurb.split("\n\n") if p.strip())

    drivers_html = ""
    if drivers:
        items = "\n".join(f'<li>{escape(d)}</li>' for d in drivers)
        drivers_html = f'<section class="drivers"><h2>The drivers</h2><ol>{items}</ol></section>'

    market_url = v.get("market_url")
    venue_name = (v.get("market_venue") or "").title()
    cta_row = ""
    if market_url:
        cta_row = (
            '<div class="cta-row">'
            f'<a class="open-market" href="{escape(market_url)}" rel="nofollow noopener" target="_blank">'
            f'Open on {escape(venue_name) if venue_name else "market"} <span class="arr">↗</span></a>'
            '<span class="meta-note">Odds Primer is editorial. Trades happen at the venue, not here.</span>'
            '</div>'
        )

    return (
        chrome_head(f"{title} · Odds Primer")
        + chrome_masthead("matches")
        + '<main class="page">'
        + '<section class="page-header">'
          '<a class="crumb" href="/matches/"><span class="arr">←</span> All matches</a>'
          f'<h1>{escape(title)}</h1>'
          '</section>'
        + render_card(match, is_lead=True)
        + (f'<div class="blurb">{blurb_paras}</div>' if blurb_paras else "")
        + cta_row
        + drivers_html
        + '<aside class="voice">'
          '<h3>How to read this</h3>'
          '<p>The verdict compares our <em>model probability</em> against the <em>best available market probability</em>. '
          'A <em>Pick</em> means the model rates a side three or more percentage points higher than the market. '
          '<em>Pass</em> means the line is doing its job. <em>Avoid</em> means every side looks overpriced.</p>'
          '</aside>'
        + '</main>'
        + chrome_footer()
    )


# ─── Outrights ───

def render_outright_card(outright: dict) -> str:
    """Render an outright as an lv-card. Mirrors the match card shape."""
    v = outright.get("verdict", {})
    state = v.get("state", "pass")
    state_class = f"is-{state}"
    href = f"/o/{outright['outright_id']}"

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

    head = (
        f'<span class="lv-glyph" aria-hidden="true">{GLYPHS.get(state, "—")}</span>'
        f'<span class="lv-lab">{LABELS.get(state, "Pass")}</span>'
        f'<span class="lv-when">{escape(when)}</span>'
    )

    # The outright top-level carries market_url / market_venue; the
    # nested verdict only carries them on Pick state. Compose a single
    # dict the CTA helper can read from.
    cta_dict = {
        "market_url":   v.get("market_url")   or outright.get("market_url"),
        "market_venue": v.get("market_venue") or outright.get("market_venue"),
    }

    search_key = "World Cup 2026 winner"

    if state == "pass":
        cta_html = market_cta(cta_dict, search_key=search_key, detail_href=href)
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
        action = market_cta(cta_dict, price=v.get("price"), search_key=search_key, detail_href=href)
        foot = f'<div class="lv-foot"><div class="lv-reads">{reads}</div><div class="lv-action">{action}</div></div>'

    return (
        f'<div class="lv-card {state_class}">'
        f'<a class="lv-card-link" href="{href}" aria-label="Read the case"></a>'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{escape(candidate)}</h3>'
        f'<p class="lv-venue-meta">{escape(label)}</p>'
        f'<p class="lv-thesis">{escape(summary)}</p>'
        f'{foot}'
        '</div>'
    )


def render_outrights_index(outrights: list[dict]) -> str:
    if not outrights:
        return (
            chrome_head("Outright winners · Odds Primer")
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

    cards = "\n".join(render_outright_card(o) for o in outrights)
    return (
        chrome_head("Outright winners · Odds Primer")
        + chrome_masthead("outrights")
        + '<main class="page">'
          '<section class="page-header">'
          '<a class="crumb" href="/"><span class="arr">←</span> Home</a>'
          '<h1>Outright winners</h1>'
          '</section>'
        + cards
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
    market_url = v.get("market_url")
    venue_name = (v.get("market_venue") or "").title()
    cta_row = ""
    if market_url:
        cta_row = (
            '<div class="cta-row">'
            f'<a class="open-market" href="{escape(market_url)}" rel="nofollow noopener" target="_blank">'
            f'Open on {escape(venue_name) if venue_name else "market"} <span class="arr">↗</span></a>'
            '<span class="meta-note">Odds Primer is editorial. Trades happen at the venue, not here.</span>'
            '</div>'
        )

    return (
        chrome_head(f"{title} · Odds Primer")
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
    (SITE_OUT / "o").mkdir(exist_ok=True)
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
    global KALSHI_EVENT_INDEX
    KALSHI_EVENT_INDEX = _load_kalshi_event_index()
    log(f"Loaded kalshi  : {len(KALSHI_EVENT_INDEX)} WC26 events")

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

    # Outrights index
    (SITE_OUT / "outrights" / "index.html").write_text(render_outrights_index(outrights))
    log("Wrote          : outrights/index.html")

    # Per-outright pages
    for o in outrights:
        oid = o["outright_id"]
        (SITE_OUT / "o" / f"{oid}.html").write_text(render_outright_page(o))
    if outrights:
        log(f"Wrote          : {len(outrights)} outright page(s) in o/")

    log(f"\n✓ Site ready  : {SITE_OUT}")


if __name__ == "__main__":
    main()
