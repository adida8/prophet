/* Activity-signals island — vanilla JS injected into each match page.
 *
 * Reads its slot's data-* attributes, fires POST /view once, polls
 * GET /api/activity/{id} every 90s, wires reaction chips to POST /vote.
 *
 * Two design modes — "editorial" (default) and "literal" — chosen via
 *   ?design=literal|editorial  (URL query, wins)
 *   or the op_design cookie    (sticky)
 *   defaults to editorial
 *
 * The toggle link at the corner of the widget flips between modes and
 * persists the choice in the cookie. Useful for A/B-testing on staging.
 *
 * See ACTIVITY_SIGNALS_SPEC.md.
 */

(function () {
  "use strict";

  const POLL_MS = 90_000;
  const API = "/api/activity";

  const REACTION_KEYS = ["sharp_call", "fair_call", "off_mark", "wait_see"];
  const VIEW_DISPLAY_MIN = 10;
  const VOTE_DISPLAY_MIN = 5;

  // Labels are picked by (design × verdict_state). For Pass/Avoid both
  // designs converge on neutral "agree/disagree" vocabulary — the Literal
  // set ("Bullish / Trap line") truly only makes sense when the Desk has
  // called a side, and Editorial's "Sharp call" implies a Pick exists.
  const LABELS = {
    editorial: {
      pick:  { sharp_call: "Sharp call", fair_call: "Fair call",
               off_mark: "Off the mark", wait_see: "Wait and see" },
      other: { sharp_call: "Agree",      fair_call: "Lean agree",
               off_mark: "Disagree",     wait_see: "Wait and see" },
    },
    literal: {
      pick:  { sharp_call: "Bullish",    fair_call: "Value",
               off_mark: "Trap line",    wait_see: "Overpriced" },
      other: { sharp_call: "Agree",      fair_call: "Lean agree",
               off_mark: "Disagree",     wait_see: "Wait and see" },
    },
  };

  function labelsFor(design, verdict) {
    return LABELS[design][verdict === "pick" ? "pick" : "other"];
  }

  const EMOJI = {
    sharp_call: "🐂",
    fair_call: "💎",
    off_mark: "🪤",
    wait_see: "💸",
  };

  // -------------------- design preference --------------------

  function readDesign() {
    const qs = new URLSearchParams(window.location.search);
    const q = qs.get("design");
    if (q === "literal" || q === "editorial") {
      writeDesignCookie(q);
      return q;
    }
    const m = document.cookie.match(/(?:^|;\s*)op_design=(literal|editorial)/);
    return m ? m[1] : "literal";
  }

  function writeDesignCookie(d) {
    document.cookie =
      "op_design=" + d + "; path=/; max-age=" + 60 * 60 * 24 * 365 + "; SameSite=Lax";
  }

  // -------------------- styles (injected once) ---------------

  const STYLE_ID = "op-activity-style";

  const CSS = `
.op-activity { font-family: 'Inter Tight', system-ui, sans-serif; color: var(--ink, #0E2240); margin-top: 24px; }
.op-activity[data-design="literal"] .op-ed { display: none; }
.op-activity[data-design="editorial"] .op-lit { display: none; }
.op-activity .op-ghost { display: none; }
.op-activity.is-loaded .op-ghost { display: block; }
.op-activity .op-toggle { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--graphite-soft, #6B7079); text-decoration: none; border-bottom: 1px dashed var(--rule, #D9D2C0); padding-bottom: 1px; }
.op-activity .op-toggle:hover { color: var(--ink, #0E2240); }
.op-activity .op-toggle-row { display: flex; justify-content: flex-end; margin-top: 12px; }

/* ── EDITORIAL ── */
.op-ed-readers { padding: 12px 14px; background: var(--paper-warm, #F0ECE2); border-left: 2px solid var(--rule, #D9D2C0); }
.op-ed-readers .op-lbl { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--graphite-soft, #6B7079); margin-bottom: 8px; }
.op-ed-readers-grid { display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; align-items: baseline; }
.op-ed-readers .op-k { font-family: 'Source Serif 4', Georgia, serif; font-size: 13px; color: var(--ink-soft, #2A3957); font-style: italic; }
.op-ed-readers .op-v { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px; color: var(--ink, #0E2240); font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; }
.op-ed-readers .op-sentiment { grid-column: 1 / -1; height: 6px; background: #fff; border: 1px solid var(--rule, #D9D2C0); position: relative; margin-top: 6px; }
.op-ed-readers .op-sb-fill { position: absolute; inset: 0 auto 0 0; background: var(--ink, #0E2240); }
.op-ed-readers .op-sb-mark { position: absolute; top: -3px; bottom: -3px; left: 50%; width: 0; border-left: 2px solid var(--flame, #D9461C); }
.op-ed-readers .op-sb-cap { grid-column: 1 / -1; display: flex; justify-content: space-between; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 10px; color: var(--graphite-soft, #6B7079); letter-spacing: 0.04em; text-transform: uppercase; margin-top: 4px; }
.op-ed-react { margin-top: 14px; }
.op-ed-react .op-lbl { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--graphite-soft, #6B7079); margin-bottom: 8px; }
.op-ed-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.op-chip { display: inline-flex; align-items: center; gap: 8px; padding: 9px 12px; font-family: 'Inter Tight', system-ui, sans-serif; font-size: 12.5px; color: var(--ink, #0E2240); cursor: pointer; transition: background 120ms, border-color 120ms; background: #fff; border: 1px solid var(--rule, #D9D2C0); }
.op-chip:hover { border-color: var(--ink, #0E2240); }
.op-chip[disabled] { opacity: 0.7; cursor: not-allowed; }
.op-chip .op-count { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: var(--graphite-soft, #6B7079); }
.op-chip.is-on { background: var(--paper-warm, #F0ECE2); border-color: var(--ink, #0E2240); }
.op-chip.is-on .op-count { color: var(--ink, #0E2240); }
.op-voted-hint { font-family: 'Source Serif 4', Georgia, serif; font-style: italic; font-size: 11.5px; color: var(--graphite-soft, #6B7079); margin-top: 10px; }

/* ── LITERAL ── */
.op-lit-strip { padding: 12px 0; border-bottom: 1px dashed var(--card-rule, #E2C9BD); }
.op-lit-strip .op-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--ink-soft, #2A3957); }
.op-lit-strip .op-row + .op-row { margin-top: 6px; }
.op-lit-strip .op-bold { font-weight: 600; color: var(--ink, #0E2240); }
.op-lit-strip .op-eye { margin-right: 4px; }
.op-lit-react { margin-top: 14px; }
.op-lit-react .op-lbl { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--graphite-soft, #6B7079); margin-bottom: 8px; }
.op-lit-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.op-lit-chips .op-chip { border-radius: 999px; }
.op-lit-chips .op-em { font-size: 15px; line-height: 1; }
.op-lit-chips .op-chip.is-on { background: var(--flame-tint, #F7E4DA); border-color: var(--flame, #D9461C); }
.op-lit-chips .op-chip.is-on .op-count { color: var(--flame-deep, #A8341A); }
`;

  function injectStyleOnce() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // -------------------- rendering ---------------------------

  function renderEditorial(state) {
    const r = state.data || {};
    const labels = labelsFor("editorial", state.verdict);
    const showViews = (r.views_24h || 0) >= VIEW_DISPLAY_MIN;
    const showVotes = (r.votes_total || 0) >= VOTE_DISPLAY_MIN;
    const aligned = r.aligned_pct == null ? null : r.aligned_pct;

    const isPick = state.verdict === "pick";

    let readers = "";
    if (showViews || showVotes) {
      const lines = [];
      if (showViews) {
        lines.push(`<div class="op-k">Read today</div><div class="op-v">${r.views_24h}</div>`);
      }
      if (showVotes && isPick && aligned != null) {
        lines.push(`<div class="op-k">Aligned with the Pick</div><div class="op-v">${aligned}%</div>`);
        lines.push(`<div class="op-sentiment"><span class="op-sb-fill" style="width:${aligned}%"></span><span class="op-sb-mark"></span></div>`);
        lines.push(`<div class="op-sb-cap"><span>Disagree</span><span>Mid</span><span>Agree</span></div>`);
      }
      readers = `<div class="op-ed-readers"><div class="op-lbl">Readers</div><div class="op-ed-readers-grid">${lines.join("")}</div></div>`;
    }

    const chips = REACTION_KEYS.map((k) => {
      const count = (r.by_reaction || {})[k] || 0;
      const isOn = r.your_vote === k;
      const showCount = showVotes ? `<span class="op-count">${count}</span>` : "";
      return `<button class="op-chip${isOn ? " is-on" : ""}" data-reaction="${k}">${labels[k]} ${showCount}</button>`;
    }).join("");

    return `
      ${readers}
      <div class="op-ed-react">
        <div class="op-lbl">Your read on the call</div>
        <div class="op-ed-chips">${chips}</div>
        <div class="op-voted-hint">One click · anonymous · no account</div>
      </div>
    `;
  }

  function renderLiteral(state) {
    const r = state.data || {};
    const labels = labelsFor("literal", state.verdict);
    // Emoji only render on Pick verdicts — they're tied to the directional
    // vocabulary ("Bullish 🐂"); on Pass/Avoid we use neutral labels with
    // no emoji to match.
    const useEmoji = state.verdict === "pick";
    const showViews = (r.views_24h || 0) >= VIEW_DISPLAY_MIN;
    const showVotes = (r.votes_total || 0) >= VOTE_DISPLAY_MIN;

    let strip = "";
    if (showViews || showVotes) {
      const rows = [];
      if (showViews) {
        rows.push(`<div class="op-row"><span class="op-eye">👁</span><span><span class="op-bold">${r.views_24h} reads</span> in the last day</span></div>`);
      }
      if (showVotes) {
        const top = topReaction(r.by_reaction || {});
        if (top) {
          rows.push(`<div class="op-row"><span>Most picked: <span class="op-bold">${labels[top]}</span></span></div>`);
        }
        const leaning = communityLeaning(r.by_reaction || {});
        if (leaning) {
          rows.push(`<div class="op-row"><span>Community leaning: <span class="op-bold">${leaning}</span></span></div>`);
        }
      }
      strip = `<div class="op-lit-strip">${rows.join("")}</div>`;
    }

    const chips = REACTION_KEYS.map((k) => {
      const count = (r.by_reaction || {})[k] || 0;
      const isOn = r.your_vote === k;
      const showCount = showVotes ? `<span class="op-count">${count}</span>` : "";
      const em = useEmoji ? `<span class="op-em">${EMOJI[k]}</span> ` : "";
      return `<button class="op-chip${isOn ? " is-on" : ""}" data-reaction="${k}">${em}${labels[k]} ${showCount}</button>`;
    }).join("");

    return `
      ${strip}
      <div class="op-lit-react">
        <div class="op-lbl">React to this market</div>
        <div class="op-lit-chips">${chips}</div>
        <div class="op-voted-hint">Anonymous · one click · no account</div>
      </div>
    `;
  }

  function topReaction(counts) {
    let best = null;
    let bestN = 0;
    for (const k of REACTION_KEYS) {
      const n = counts[k] || 0;
      if (n > bestN) { best = k; bestN = n; }
    }
    return best;
  }

  function communityLeaning(counts) {
    const agree = (counts.sharp_call || 0) + (counts.fair_call || 0);
    const dis = counts.off_mark || 0;
    const wait = counts.wait_see || 0;
    if (agree === 0 && dis === 0 && wait === 0) return null;
    if (agree >= dis && agree >= wait) return "PICK";
    if (dis >= agree && dis >= wait) return "AVOID";
    return "PASS";
  }

  function toggleHtml(current) {
    const other = current === "editorial" ? "literal" : "editorial";
    return `<div class="op-toggle-row"><a href="?design=${other}" class="op-toggle">Switch to ${other}</a></div>`;
  }

  function render(root, state) {
    const inner =
      state.design === "literal" ? renderLiteral(state) : renderEditorial(state);
    root.innerHTML =
      `<div class="op-${state.design === "literal" ? "lit" : "ed"}">${inner}</div>` +
      toggleHtml(state.design);
    root.dataset.design = state.design;
    root.classList.add("is-loaded");
    wireChips(root, state);
  }

  function wireChips(root, state) {
    const chips = root.querySelectorAll(".op-chip");
    chips.forEach((c) => {
      c.addEventListener("click", async () => {
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
          if (res.status === 429 || res.status === 409) {
            // Silent — the next refresh will re-disable / hold state.
          } else if (res.ok) {
            const body = await res.json();
            state.data = state.data || {};
            state.data.your_vote = body.your_vote;
            render(root, state);
            refresh(root, state); // pull fresh counts shortly after a vote
          }
        } catch (_e) {
          /* swallow — non-fatal */
        } finally {
          chips.forEach((x) => (x.disabled = false));
        }
      });
    });
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
      state.data = await res.json();
      render(root, state);
    } catch (_e) { /* non-fatal */ }
  }

  // -------------------- boot -------------------------------

  function boot() {
    injectStyleOnce();
    const roots = document.querySelectorAll(".op-activity[data-match-id]");
    roots.forEach((root) => {
      const matchId = root.dataset.matchId;
      const verdict = root.dataset.verdictState || "pass";
      const state = {
        matchId,
        verdict,
        design: readDesign(),
        data: null,
      };
      // Render a skeleton immediately so the toggle link is reachable
      // even before the first GET lands.
      render(root, state);
      postView(matchId);
      refresh(root, state);
      setInterval(() => refresh(root, state), POLL_MS);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
