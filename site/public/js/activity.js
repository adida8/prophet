/* Activity signals — Literal design, per activity_signals_mockup.html.
 *
 * Renders inside every match card. Layout:
 *   • Top activity strip (3 lines):
 *       - "N users viewed this market today" (when N ≥ 10)
 *       - "Most picked: <side>"                (when votes ≥ 5 and side known)
 *       - "Community leaning: <PICK/PASS/AVOID>" (when votes ≥ 5)
 *   • Reaction chips: 🐂 Bullish · 💸 Overpriced · 🪤 Trap line · 💎 Value.
 *   • Italic hint: "Anonymous · one click · no account".
 *
 * The widget lives INSIDE the .lv-card CSS grid (grid-column: 1 / -1) so
 * it spans the full card width edge-to-edge. The card's own CSS sets
 * pointer-events: none on every child via `.lv-card > *:not(.lv-card-link)`,
 * which has (0, 2, 0) specificity — to beat it we need a selector with
 * at least the same specificity that comes later in cascade order, hence
 * `.lv-card .op-activity { pointer-events: auto }`.
 *
 * Chip clicks call stopPropagation so voting on a listing card never
 * triggers the whole-card overlay-link navigation.
 *
 * Chip labels (DB key → Literal display):
 *   sharp_call → 🐂 Bullish   (positive — agrees with Pick)
 *   wait_see   → 💸 Overpriced (negative — side is overpriced)
 *   off_mark   → 🪤 Trap line  (negative — line is wrong)
 *   fair_call  → 💎 Value      (positive — sees value)
 */

(function () {
  "use strict";

  const POLL_MS = 90_000;
  const API = "/api/activity";

  // Chip order matches the v1 Literal mockup. The DB key on the right
  // stays the same as PR-3 (no schema change).
  const CHIPS = [
    { key: "sharp_call", em: "🐂", label: "Bullish",    pos: true  },
    { key: "wait_see",   em: "💸", label: "Overpriced", pos: false },
    { key: "off_mark",   em: "🪤", label: "Trap line",  pos: false },
    { key: "fair_call",  em: "💎", label: "Value",      pos: true  },
  ];

  // Spec asked for 10/5 to avoid empty-N humiliation, but with the seed
  // engine off on staging the user can't reach those thresholds manually.
  // Showing whenever we have any data trades that floor for testability.
  const VIEW_DISPLAY_MIN = 1;
  const VOTE_DISPLAY_MIN = 1;

  // -------------------- styles (injected once) ---------------

  const STYLE_ID = "op-activity-style";

  // Selectors are scoped under `.lv-card` so they beat the card's own
  // `.lv-card > *:not(.lv-card-link)` rules (same specificity, later in
  // cascade wins).
  const CSS = `
.lv-card .op-activity {
  grid-column: 1 / -1;
  margin-top: 14px;
  padding: 0 26px 16px 28px;
  pointer-events: auto;
  position: relative;
  z-index: 3;
  font-family: 'Inter Tight', system-ui, sans-serif;
  color: var(--ink, #0E2240);
}

.lv-card .op-strip {
  padding: 12px 0;
  border-top: 1px dashed var(--card-rule, #E2C9BD);
  border-bottom: 1px dashed var(--card-rule, #E2C9BD);
  margin-bottom: 14px;
}
.lv-card .op-strip .op-row {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--ink-soft, #2A3957);
  line-height: 1.5;
}
.lv-card .op-strip .op-row + .op-row { margin-top: 4px; }
.lv-card .op-strip .op-bold { color: var(--ink, #0E2240); font-weight: 600; }
.lv-card .op-strip .op-eye { font-size: 15px; line-height: 1; }

.lv-card .op-react-label {
  font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--graphite-soft, #6B7079);
  margin-bottom: 8px;
}
.lv-card .op-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.lv-card .op-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid var(--rule, #D9D2C0);
  border-radius: 999px;
  font-family: 'Inter Tight', system-ui, sans-serif;
  font-size: 13px;
  color: var(--ink, #0E2240);
  cursor: pointer;
  transition: background 120ms, border-color 120ms;
}
.lv-card .op-chip:hover { border-color: var(--ink, #0E2240); }
.lv-card .op-chip[disabled] { opacity: 0.6; cursor: not-allowed; }
.lv-card .op-chip .op-em { font-size: 15px; line-height: 1; }
.lv-card .op-chip .op-count {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px; color: var(--graphite-soft, #6B7079);
}
.lv-card .op-chip.is-on {
  background: var(--flame-tint, #F7E4DA);
  border-color: var(--flame, #D9461C);
}
.lv-card .op-chip.is-on .op-count { color: var(--flame-deep, #A8341A); }

.lv-card .op-voted-hint {
  font-family: 'Source Serif 4', Georgia, serif;
  font-style: italic; font-size: 11.5px;
  color: var(--graphite-soft, #6B7079);
  margin-top: 10px;
}
`;

  function injectStyleOnce() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // -------------------- derived strings --------------------

  function pickerSide(state) {
    // The Desk's pick side is supplied by render_card via data-pick-side.
    // Falls back to nothing if no pick — Most picked line hides.
    return state.pickSide || null;
  }

  function communityLeaning(byReaction) {
    const positive = (byReaction.sharp_call || 0) + (byReaction.fair_call || 0);
    const negative = (byReaction.off_mark || 0) + (byReaction.wait_see || 0);
    if (positive === 0 && negative === 0) return null;
    if (positive > negative * 1.2) return "PICK";
    if (negative > positive * 1.2) return "AVOID";
    return "PASS";
  }

  // -------------------- rendering --------------------------

  function render(root, state) {
    const r = state.data || {};
    const byReaction = r.by_reaction || {};
    const showViews = (r.views_24h || 0) >= VIEW_DISPLAY_MIN;
    // Treat "this reader has voted" as enough to unlock the counts row,
    // even if the aggregator hasn't republished match_aggregates yet
    // (aggregator runs every 60s; the user expects their click to land
    // visibly faster than that).
    const showVotes = (r.votes_total || 0) >= VOTE_DISPLAY_MIN || !!r.your_vote;

    // Top strip — only render rows whose data crosses display thresholds.
    const stripRows = [];
    if (showViews) {
      const n = r.views_24h;
      const unit = n === 1 ? "user" : "users";
      stripRows.push(`<div class="op-row"><span class="op-eye">👁</span><span><span class="op-bold">${n} ${unit}</span> viewed this market today</span></div>`);
    }
    if (showVotes) {
      const side = pickerSide(state);
      if (side) {
        stripRows.push(`<div class="op-row"><span>Most picked: <span class="op-bold">${side}</span></span></div>`);
      }
      const leaning = communityLeaning(byReaction);
      if (leaning) {
        stripRows.push(`<div class="op-row"><span>Community leaning: <span class="op-bold">${leaning}</span></span></div>`);
      }
    }
    const strip = stripRows.length
      ? `<div class="op-strip">${stripRows.join("")}</div>`
      : "";

    // Chips — always rendered (without counts until threshold hit).
    const chips = CHIPS.map((c) => {
      const n = byReaction[c.key] || 0;
      const isOn = r.your_vote === c.key;
      const count = showVotes ? `<span class="op-count">${n}</span>` : "";
      return `<button class="op-chip${isOn ? " is-on" : ""}" data-reaction="${c.key}" type="button"><span class="op-em">${c.em}</span> ${c.label} ${count}</button>`;
    }).join("");

    root.innerHTML = `
      ${strip}
      <div class="op-react-label">React to this market</div>
      <div class="op-chips">${chips}</div>
      <div class="op-voted-hint">Anonymous · one click · no account</div>
    `;
    wireChips(root, state);
  }

  // -------------------- interaction ------------------------

  function wireChips(root, state) {
    const chips = root.querySelectorAll(".op-chip");
    chips.forEach((c) => {
      c.addEventListener("click", async (ev) => {
        // Stop the click bubbling to the card's overlay <a> (listing pages).
        ev.stopPropagation();
        ev.preventDefault();
        chips.forEach((x) => (x.disabled = true));
        try {
          const res = await fetch(API + "/vote", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              match_id: state.matchId,
              reaction: c.dataset.reaction,
            }),
          });
          if (res.ok) {
            const body = await res.json();
            state.data = state.data || {};
            // Optimistic local bump so the count shows the user's own
            // vote before the 60s aggregator catches up. Reconciled by
            // the next refresh() below (or by interval poll).
            const prev = state.data.your_vote;
            const next = body.your_vote;
            state.data.by_reaction = state.data.by_reaction || {};
            if (prev && prev !== next) {
              state.data.by_reaction[prev] = Math.max(
                0, (state.data.by_reaction[prev] || 0) - 1
              );
            }
            if (next && prev !== next) {
              state.data.by_reaction[next] = (state.data.by_reaction[next] || 0) + 1;
              if (!prev) {
                state.data.votes_total = (state.data.votes_total || 0) + 1;
              }
            }
            state.data.your_vote = next;
            render(root, state);
            // Intentionally NOT calling refresh() here. The 60s aggregator
            // hasn't caught up yet, so a refresh would return stale counts
            // and wipe out the optimistic bump above. The next interval
            // poll (90s) runs after the aggregator has caught up, and
            // reconcile() guards against any remaining drift.
          }
          // 409 / 429 are silent — the next refresh pulls true state.
        } catch (_e) {
          /* non-fatal */
        } finally {
          chips.forEach((x) => (x.disabled = false));
        }
      });
    });
  }

  // -------------------- reconciliation --------------------

  // The aggregator job runs every 60s; in that window the GET response's
  // `by_reaction` counts are stale w.r.t. recent votes. `your_vote` is
  // read live and is always fresh — so we treat it as the source of truth
  // and patch counts back up locally when they conflict.
  function reconcile(data) {
    if (!data) return data;
    data.by_reaction = data.by_reaction || {};
    if (data.your_vote && !data.by_reaction[data.your_vote]) {
      data.by_reaction[data.your_vote] = 1;
      data.votes_total = Math.max(data.votes_total || 0, 1);
    }
    return data;
  }

  // -------------------- site-page ping --------------------
  //
  // Match pages already fire postView() per widget. For non-match pages
  // (home, matches index, outrights, learn, about) we fire a single
  // sentinel view with match_id `site:<slug>` so daily_report's unique-
  // anon count covers the whole site, not just match-page traffic.
  //
  // Returns null to skip (match-page paths handle themselves; unknown
  // paths aren't tracked to keep the sentinel set tight).
  function siteKeyForPath(pathname) {
    if (!pathname || pathname.startsWith("/m/") || pathname.startsWith("/o/")) {
      return null;
    }
    if (pathname === "/" || pathname === "/index.html") return "site:home";
    if (pathname === "/matches" || pathname.startsWith("/matches/")) return "site:matches";
    if (pathname === "/outrights" || pathname.startsWith("/outrights/")) return "site:outrights";
    if (pathname === "/learn" || pathname.startsWith("/learn/")) return "site:learn";
    if (pathname === "/about" || pathname.startsWith("/about")) return "site:about";
    return null;
  }

  // -------------------- network ----------------------------

  async function postView(matchId) {
    try {
      await fetch(API + "/view", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id: matchId }),
      });
    } catch (_e) { /* non-fatal */ }
  }

  async function refresh(root, state) {
    try {
      const res = await fetch(API + "/" + encodeURIComponent(state.matchId), {
        credentials: "same-origin",
      });
      if (!res.ok) return;
      state.data = reconcile(await res.json());
      render(root, state);
    } catch (_e) { /* non-fatal */ }
  }

  // -------------------- boot -------------------------------

  // -------------------- CTA beacon -------------------------
  //
  // Capture-phase delegated listener fires once per CTA click — for any
  // <a data-cta-venue="..."> anywhere on the page. Capture phase is
  // required because the listing-card overlay link calls preventDefault
  // + navigates in the bubble phase, so a bubble listener never sees
  // the click on those cards.
  //
  // navigator.sendBeacon is the primary path: it survives the
  // unload/navigation that follows a click on an external CTA. fetch
  // with keepalive is the fallback for the (small) set of browsers
  // without sendBeacon. Both are fire-and-forget; the response is
  // ignored — the daily report only needs the row to land.

  function postCtaBeacon(matchId, venue) {
    if (!matchId || !venue) return;
    const url = API + "/cta";
    const body = JSON.stringify({ match_id: matchId, venue: venue });
    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([body], { type: "application/json" });
        if (navigator.sendBeacon(url, blob)) return;
      }
    } catch (_e) { /* fall through */ }
    try {
      fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: body,
        keepalive: true,
      });
    } catch (_e) { /* non-fatal */ }
  }

  function wireCtaBeacon() {
    document.addEventListener(
      "click",
      function (ev) {
        // Walk up from the click target — listing-card pills wrap the
        // anchor in <span class="cta-stack">, so the literal target can
        // be the inner <span class="arr"> or a text node.
        let el = ev.target;
        while (el && el !== document) {
          if (el.tagName === "A" && el.dataset && el.dataset.ctaVenue) {
            postCtaBeacon(el.dataset.matchId, el.dataset.ctaVenue);
            return;
          }
          el = el.parentNode;
        }
      },
      true, // capture
    );
  }

  function boot() {
    injectStyleOnce();
    wireCtaBeacon();
    const widgets = document.querySelectorAll(".op-activity[data-match-id]");
    widgets.forEach((root) => {
      const matchId = root.dataset.matchId;
      const state = {
        matchId,
        verdict: root.dataset.verdictState || "pass",
        pickSide: root.dataset.pickSide || null,
        data: null,
      };
      render(root, state);
      postView(matchId);
      refresh(root, state);
      setInterval(() => refresh(root, state), POLL_MS);
    });

    // Non-match pages: fire one sentinel view so site-wide uniques cover
    // home/matches/outrights/learn/about, not just match-page traffic.
    if (widgets.length === 0) {
      const siteKey = siteKeyForPath(window.location.pathname);
      if (siteKey) postView(siteKey);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
