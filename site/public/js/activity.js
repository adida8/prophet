/* Activity signals — Editorial design, per activity_signals_mockup.html.
 *
 * Renders inside every match card. Layout:
 *   • "Readers" strip — paper-warm box. "Read today · N" always (when N ≥ 10);
 *     "Aligned with the Pick · X%" + sentiment bar are Pick-only.
 *   • "Your read on the call" — four chip buttons (Sharp call · Fair call ·
 *     Off the mark · Wait and see) for Pick verdicts; neutral labels on
 *     Pass/Avoid (Agree · Lean agree · Disagree · Wait and see).
 *   • Italic hint line: "One click · anonymous · no account".
 *
 * The widget lives INSIDE the .lv-card CSS grid with grid-column: 1 / -1 so
 * it spans the full card width edge-to-edge, and pointer-events: auto so it
 * captures its own clicks instead of falling through to the card overlay link
 * that makes the whole card clickable on listing pages. Chip clicks call
 * stopPropagation so voting never accidentally navigates to /m/{id}.
 */

(function () {
  "use strict";

  const POLL_MS = 90_000;
  const API = "/api/activity";

  const REACTION_KEYS = ["sharp_call", "fair_call", "off_mark", "wait_see"];
  const PICK_LABELS = {
    sharp_call: "Sharp call",
    fair_call: "Fair call",
    off_mark: "Off the mark",
    wait_see: "Wait and see",
  };
  const PASS_AVOID_LABELS = {
    sharp_call: "Agree",
    fair_call: "Lean agree",
    off_mark: "Disagree",
    wait_see: "Wait and see",
  };

  const VIEW_DISPLAY_MIN = 10;
  const VOTE_DISPLAY_MIN = 5;

  // -------------------- styles (injected once) ---------------

  const STYLE_ID = "op-activity-style";

  const CSS = `
.op-activity {
  grid-column: 1 / -1;
  margin-top: 14px;
  padding: 14px 26px 16px 28px;   /* aligns with the card's content column */
  border-top: 1px solid var(--card-rule, #E2C9BD);
  pointer-events: auto;
  position: relative;
  z-index: 3;
  font-family: 'Inter Tight', system-ui, sans-serif;
  color: var(--ink, #0E2240);
}
.lv-card.is-pick .op-activity { border-top-color: rgba(216, 70, 28, 0.32); }

.op-readers {
  padding: 12px 14px;
  background: var(--paper-warm, #F0ECE2);
  border-left: 2px solid var(--rule, #D9D2C0);
  margin-bottom: 14px;
}
.op-readers .op-lbl {
  font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--graphite-soft, #6B7079);
  margin-bottom: 8px;
}
.op-readers-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 12px 18px; align-items: baseline;
}
.op-readers .op-k {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 13px; color: var(--ink-soft, #2A3957); font-style: italic;
}
.op-readers .op-v {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px; color: var(--ink, #0E2240);
  font-weight: 500; text-align: right; font-variant-numeric: tabular-nums;
}
.op-readers .op-sentiment {
  grid-column: 1 / -1;
  height: 6px; background: #fff; border: 1px solid var(--rule, #D9D2C0);
  position: relative; margin-top: 6px;
}
.op-readers .op-sb-fill { position: absolute; inset: 0 auto 0 0; background: var(--ink, #0E2240); transition: width 250ms ease; }
.op-readers .op-sb-mark { position: absolute; top: -3px; bottom: -3px; left: 50%; width: 0; border-left: 2px solid var(--flame, #D9461C); }
.op-readers .op-sb-cap {
  grid-column: 1 / -1;
  display: flex; justify-content: space-between;
  margin-top: 4px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 10px; color: var(--graphite-soft, #6B7079);
  letter-spacing: 0.04em; text-transform: uppercase;
}

.op-react .op-lbl {
  font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--graphite-soft, #6B7079);
  margin-bottom: 8px;
}
.op-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.op-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 12px;
  background: #fff;
  border: 1px solid var(--rule, #D9D2C0);
  font-family: 'Inter Tight', system-ui, sans-serif;
  font-size: 12.5px; color: var(--ink, #0E2240);
  cursor: pointer;
  transition: background 120ms, border-color 120ms;
}
.op-chip:hover { border-color: var(--ink, #0E2240); }
.op-chip[disabled] { opacity: 0.6; cursor: not-allowed; }
.op-chip .op-count {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px; color: var(--graphite-soft, #6B7079);
}
.op-chip.is-on { background: var(--paper-warm, #F0ECE2); border-color: var(--ink, #0E2240); }
.op-chip.is-on .op-count { color: var(--ink, #0E2240); }

.op-voted-hint {
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

  // -------------------- rendering ---------------------------

  function labelsFor(verdict) {
    return verdict === "pick" ? PICK_LABELS : PASS_AVOID_LABELS;
  }

  function render(root, state) {
    const r = state.data || {};
    const isPick = state.verdict === "pick";
    const labels = labelsFor(state.verdict);
    const showViews = (r.views_24h || 0) >= VIEW_DISPLAY_MIN;
    const showVotes = (r.votes_total || 0) >= VOTE_DISPLAY_MIN;
    const aligned = isPick && r.aligned_pct != null ? r.aligned_pct : null;

    // Readers strip — render whenever we have any displayable data so the
    // box isn't an empty rectangle on a fresh match page.
    let readers = "";
    if (showViews || (showVotes && aligned != null)) {
      const rows = [];
      if (showViews) {
        rows.push(`<div class="op-k">Read today</div><div class="op-v">${r.views_24h}</div>`);
      }
      if (showVotes && aligned != null) {
        rows.push(`<div class="op-k">Aligned with the Pick</div><div class="op-v">${aligned}%</div>`);
        rows.push(`<div class="op-sentiment"><span class="op-sb-fill" style="width:${aligned}%"></span><span class="op-sb-mark"></span></div>`);
        rows.push(`<div class="op-sb-cap"><span>Disagree</span><span>Mid</span><span>Agree</span></div>`);
      }
      readers = `
        <div class="op-readers">
          <div class="op-lbl">Readers</div>
          <div class="op-readers-grid">${rows.join("")}</div>
        </div>
      `;
    }

    const chips = REACTION_KEYS.map((k) => {
      const count = (r.by_reaction || {})[k] || 0;
      const isOn = r.your_vote === k;
      const countHtml = showVotes ? `<span class="op-count">${count}</span>` : "";
      return `<button class="op-chip${isOn ? " is-on" : ""}" data-reaction="${k}" type="button">${labels[k]} ${countHtml}</button>`;
    }).join("");

    root.innerHTML = `
      ${readers}
      <div class="op-react">
        <div class="op-lbl">${isPick ? "Your read on the call" : "Your read on the market"}</div>
        <div class="op-chips">${chips}</div>
        <div class="op-voted-hint">One click · anonymous · no account</div>
      </div>
    `;
    wireChips(root, state);
  }

  // -------------------- interaction ------------------------

  function wireChips(root, state) {
    const chips = root.querySelectorAll(".op-chip");
    chips.forEach((c) => {
      c.addEventListener("click", async (ev) => {
        // Listing pages put an overlay link over the whole card; without
        // this we'd vote AND navigate to /m/{id}.
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
            state.data.your_vote = body.your_vote;
            render(root, state);
            refresh(root, state);
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
    document.querySelectorAll(".op-activity[data-match-id]").forEach((root) => {
      const matchId = root.dataset.matchId;
      const state = {
        matchId,
        verdict: root.dataset.verdictState || "pass",
        data: null,
      };
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
