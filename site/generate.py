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

.burger {
  width: 36px; height: 36px;
  border: var(--hairline); background: var(--paper-pure);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer;
}
@media (min-width: 820px) { .burger { display: none; } }
.burger svg { display: block; }

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
  transition: background var(--dur-fast) var(--ease-standard);
}
.lv-card .lv-action .cta .arr { color: var(--flame); transition: transform var(--dur-fast) var(--ease-standard); }
.lv-card:hover .lv-action .cta,
.lv-card .lv-action .cta:hover { background: var(--flame-deep); }
.lv-card:hover .lv-action .cta .arr,
.lv-card .lv-action .cta:hover .arr { color: var(--paper); transform: translate(2px, -2px); }

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
  display: flex; flex-wrap: wrap; gap: 6px 16px; justify-content: space-between;
  font-family: var(--font-sans); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--graphite-soft);
}
.site-foot .left { color: var(--ink); }

/* OUTRIGHT LADDER — table of every priced participant + per-team verdict */
.ladder { margin: 40px 0 0; }
.ladder .section-label { margin-top: 0; }
.ladder .legend {
  margin: 14px 0 12px; font-family: var(--font-sans); font-size: 13px;
  color: var(--graphite); display: flex; flex-wrap: wrap; gap: 12px 24px;
}
.ladder .legend strong { color: var(--ink); }
.ladder-table-wrap { overflow-x: auto; }
.ladder-table {
  width: 100%; border-collapse: collapse; margin: 0;
  font-family: var(--font-sans); font-size: 13px;
  font-variant-numeric: tabular-nums; color: var(--ink);
}
.ladder-table thead th {
  text-align: right; padding: 10px 12px;
  border-bottom: var(--hairline-strong);
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--graphite-soft); white-space: nowrap;
}
.ladder-table thead th.left { text-align: left; }
.ladder-table tbody td {
  padding: 9px 12px; border-bottom: var(--hairline-soft);
  text-align: right; white-space: nowrap;
}
.ladder-table tbody td.left { text-align: left; }
.ladder-table tbody tr:hover { background: var(--rule-soft); }
.ladder-table .team { font-weight: 600; }
.ladder-table .ci { color: var(--graphite-soft); font-size: 11.5px; }
.ladder-table .edge.pos { color: var(--flame-deep); font-weight: 600; }
.ladder-table .edge.neg { color: var(--graphite-soft); }
.ladder-table .vbadge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase;
}
.ladder-table .vbadge.is-pick {
  background: var(--flame-tint); color: var(--flame-deep);
}
.ladder-table .vbadge.is-pass {
  background: var(--paper-warm); color: var(--graphite-soft);
}
@media (max-width: 720px) {
  .ladder-table thead th, .ladder-table tbody td { padding: 8px 9px; font-size: 12px; }
  .ladder-table .ci { display: none; }
}
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
        <li><a href="/outrights/"{cur('outrights')}>Outright winners</a></li>
        <li><a href="/matches/"{cur('matches')}>Upcoming matches</a></li>
      </ul>
    </nav>
    <span class="nav-meta">{updated}</span>
    <button class="burger" aria-label="More links">
      <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
        <path d="M0 1h16M0 6h16M0 11h16" stroke="currentColor" stroke-width="1.5"/>
      </svg>
    </button>
  </div>
</header>
<div class="edition-strip">
  <div class="inner">
    <span class="vol">Vol. 1 · {escape(edition_label)}</span>
    <span class="live">Markets live</span>
  </div>
</div>
"""


def chrome_footer() -> str:
    today = datetime.now(timezone.utc).strftime("%-d %b %Y")
    return f"""<footer class="site-foot page">
  <span class="left">Odds Primer · educational, not advice</span>
  <span>The Desk · v1.1 · {today}</span>
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

    # Foot — different for pick/avoid vs pass
    if state == "pass":
        foot = (
            '<div class="lv-foot">'
            f'<span class="lv-flat-msg">Markets agree — within 1pp on every side. <strong>Read the case →</strong></span>'
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

        venue = (v.get("market_venue") or "").title()
        price = v.get("price") or ""
        action_bits = ''
        if venue: action_bits += f'<span class="venue">{escape(venue)}</span>'
        if price: action_bits += f'<span class="price">{escape(str(price))}</span>'
        action_bits += '<span class="cta">Read the case <span class="arr">↗</span></span>'

        foot = (
            '<div class="lv-foot">'
            f'<div class="lv-reads">{reads}</div>'
            f'<div class="lv-action">{action_bits}</div>'
            '</div>'
        )

    return (
        f'<a class="lv-card {state_class}" href="{href}">'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{title}</h3>'
        f'<p class="lv-venue-meta">{vmeta}</p>'
        f'<p class="lv-thesis">{thesis}</p>'
        f'{foot}'
        '</a>'
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

    if state == "pass":
        foot = (
            '<div class="lv-foot">'
            '<span class="lv-flat-msg">Markets agree on this field. <strong>Read the case →</strong></span>'
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
        venue = (v.get("market_venue") or "").title()
        price = v.get("price") or ""
        action = ''
        if venue: action += f'<span class="venue">{escape(venue)}</span>'
        if price: action += f'<span class="price">{escape(str(price))}</span>'
        action += '<span class="cta">Read the case <span class="arr">↗</span></span>'
        foot = f'<div class="lv-foot"><div class="lv-reads">{reads}</div><div class="lv-action">{action}</div></div>'

    return (
        f'<a class="lv-card {state_class}" href="{href}">'
        '<span class="lv-bar" aria-hidden="true"></span>'
        f'<div class="lv-head">{head}</div>'
        f'<h3 class="lv-teams">{escape(candidate)}</h3>'
        f'<p class="lv-venue-meta">{escape(label)}</p>'
        f'<p class="lv-thesis">{escape(summary)}</p>'
        f'{foot}'
        '</a>'
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

    # Card + full ladder per outright. Today there's only one (WC26
    # winner) so this just stacks them; future outrights (group winner,
    # golden boot) will land below.
    cards = "\n".join(
        render_outright_card(o) + render_outright_ladder(o) for o in outrights
    )
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


def render_outright_ladder(outright: dict) -> str:
    """Full per-team ladder — one row per priced participant, sorted by
    model P(win) desc. Shows model probability with bootstrap band,
    both market sides, edge in pp, and a per-team verdict badge.
    """
    rows = outright.get("ladder") or []
    if not rows:
        return ""

    body_rows = []
    for r in rows:
        team = escape(r.get("team", ""))
        model_p = r.get("model_p", 0)
        lo = r.get("model_p_lower")
        hi = r.get("model_p_upper")
        ci = ""
        if lo is not None and hi is not None:
            ci = f' <span class="ci">[{fmt_pct(lo)}–{fmt_pct(hi)}]</span>'

        yes_p = r.get("yes_market_p", 0)
        no_p  = r.get("no_market_p", 0)
        yes_edge = r.get("yes_edge_pp")
        no_edge  = r.get("no_edge_pp")

        def edge_cell(e):
            if e is None: return '<td>—</td>'
            cls = "pos" if e > 0 else ("neg" if e < 0 else "")
            return f'<td class="edge {cls}">{fmt_edge(e)}</td>'

        v_state = r.get("verdict", "pass")
        pick_side = r.get("pick_side")
        v_label = "Pass"
        if v_state == "pick" and pick_side:
            v_label = f"Pick · {pick_side}"
        badge = f'<span class="vbadge is-{v_state}">{escape(v_label)}</span>'

        body_rows.append(
            "<tr>"
            f'<td class="left team">{team}</td>'
            f'<td>{fmt_pct(model_p)}{ci}</td>'
            f'<td>{fmt_pct(yes_p)}</td>'
            f'{edge_cell(yes_edge)}'
            f'<td>{fmt_pct(no_p)}</td>'
            f'{edge_cell(no_edge)}'
            f'<td>{badge}</td>'
            "</tr>"
        )

    n = len(rows)
    n_pick = sum(1 for r in rows if r.get("verdict") == "pick")
    legend = (
        '<div class="legend">'
        f'<span><strong>{n} priced teams</strong> · sorted by model P(win)</span>'
        f'<span><strong>{n_pick} Pick{"s" if n_pick != 1 else ""}</strong> · '
        f'{n - n_pick} Pass</span>'
        '<span>Edge = model − market, in percentage points</span>'
        '</div>'
    )

    return (
        '<section class="ladder">'
        '<div class="section-label"><span>The field · per-team verdict</span></div>'
        + legend
        + '<div class="ladder-table-wrap"><table class="ladder-table">'
          '<thead><tr>'
          '<th class="left">Team</th>'
          '<th>Model P(win)</th>'
          '<th>Market YES</th>'
          '<th>Edge YES</th>'
          '<th>Market NO</th>'
          '<th>Edge NO</th>'
          '<th>Verdict</th>'
          '</tr></thead>'
          '<tbody>'
        + "".join(body_rows)
        + '</tbody></table></div>'
          '</section>'
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
        + render_outright_ladder(outright)
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
