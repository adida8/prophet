/* Market Pulse — activity-signals island for each match page.
 *
 * Reads its slot's data-* attributes, fires POST /view once, polls
 * GET /api/activity/{id} every 90s, wires stance chips to POST /vote.
 *
 * Layout (per activity-signals-mockup-v2.html):
 *   • 3-up Pulse grid: Read today · 24h movement · Desk alignment
 *   • Sentiment bar (vote-to-reveal — hidden until the reader votes)
 *   • Italic movement note (when movement data is available)
 *   • Four stance chips — "Price still cheap" etc. (positions vs the
 *     market, not grades of the editor)
 *   • Follow this call email-gate strip
 *
 * Vote-to-reveal: alignment % + chip counts + sentiment bar are all
 * hidden until the user votes. Solves the empty-N humiliation problem
 * — low traffic looks "locked" instead of "dead".
 *
 * 24h movement: shows "—" until the backend wires a snapshot job
 * (follow-up). The cell is always rendered so the layout doesn't shift.
 *
 * Stance vocabulary is mapped onto the existing four reaction DB keys
 * (sharp_call / fair_call / off_mark / wait_see) — no schema change.
 *
 * See ACTIVITY_SIGNALS_SPEC.md + activity-signals-mockup-v2.html.
 */

(function () {
  "use strict";

  const POLL_MS = 90_000;
  const API = "/api/activity";

  // Mapping DB key → v2 display label. The DB keeps the original four
  // values; only the UI re-labels them as market positions.
  const STANCE_KEYS = ["sharp_call", "fair_call", "off_mark", "wait_see"];
  const STANCE_LABELS = {
    sharp_call: "Price still cheap",
    fair_call: "Market looks right",
    off_mark: "Desk is early",
    wait_see: "Waiting",
  };

  const VIEW_DISPLAY_MIN = 10;

  // -------------------- styles (injected once) ---------------

  const STYLE_ID = "op-pulse-style";

  const CSS = `
.op-activity { font-family: 'Inter Tight', system-ui, sans-serif; color: var(--ink, #0E2240); margin-top: 16px; padding: 16px 18px; background: var(--flame-tint, #F7E4DA); border: 1px solid var(--flame, #D9461C); border-left: 4px solid var(--flame, #D9461C); }
.op-activity .op-pulse-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.op-activity .op-pulse-kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 700; color: var(--graphite-soft, #6B7079); }
.op-activity .op-pulse-live { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; color: var(--flame, #D9461C); display: inline-flex; align-items: center; gap: 5px; }
.op-activity .op-pulse-live::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--flame, #D9461C); animation: op-pulse 1.8s ease-in-out infinite; }
@keyframes op-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }

.op-activity .op-pulse-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
.op-activity .op-pulse-item { background: var(--paper-warm, #F0ECE2); padding: 10px 12px; border-left: 2px solid var(--rule, #D9D2C0); }
.op-activity .op-pulse-item.is-flame { border-left-color: var(--flame, #D9461C); }
.op-activity .op-pulse-label { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--graphite-soft, #6B7079); margin-bottom: 6px; }
.op-activity .op-pulse-value { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 17px; color: var(--ink, #0E2240); font-variant-numeric: tabular-nums; }
.op-activity .op-pulse-value.is-up { color: var(--flame-deep, #A8341A); }
.op-activity .op-pulse-value.is-locked { color: var(--graphite-soft, #6B7079); font-size: 13px; font-family: 'Source Serif 4', Georgia, serif; font-style: italic; font-weight: 400; }

.op-activity .op-sentiment-wrap { margin-bottom: 16px; }
.op-activity .op-sentiment-bar { position: relative; height: 8px; background: #fff; border: 1px solid var(--rule, #D9D2C0); overflow: hidden; }
.op-activity .op-sentiment-fill { position: absolute; inset: 0 auto 0 0; background: var(--ink, #0E2240); transition: width 300ms ease; }
.op-activity .op-sentiment-mid { position: absolute; left: 50%; top: -2px; bottom: -2px; border-left: 2px solid var(--flame, #D9461C); }
.op-activity .op-sentiment-scale { margin-top: 6px; display: flex; justify-content: space-between; font-size: 10px; color: var(--graphite-soft, #6B7079); }

.op-activity .op-movement-note { font-family: 'Source Serif 4', Georgia, serif; font-style: italic; font-size: 13px; color: var(--ink-soft, #2A3957); margin-bottom: 18px; line-height: 1.5; }

.op-activity .op-stance-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--graphite-soft, #6B7079); margin-bottom: 10px; }
.op-activity .op-stance-row { display: flex; flex-wrap: wrap; gap: 8px; }
.op-activity .op-stance { background: #fff; border: 1px solid var(--rule, #D9D2C0); padding: 10px 12px; font-family: 'Inter Tight', system-ui, sans-serif; font-size: 13px; color: var(--ink, #0E2240); display: inline-flex; align-items: center; gap: 8px; cursor: pointer; transition: border-color 120ms, background 120ms; }
.op-activity .op-stance:hover { border-color: var(--ink, #0E2240); }
.op-activity .op-stance[disabled] { opacity: 0.6; cursor: not-allowed; }
.op-activity .op-stance .op-count { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: var(--graphite-soft, #6B7079); }
.op-activity .op-stance.is-active { background: var(--paper-warm, #F0ECE2); border-color: var(--ink, #0E2240); }
.op-activity .op-stance.is-active .op-count { color: var(--ink, #0E2240); }
.op-activity .op-stance .op-count-hidden { font-style: italic; font-family: 'Source Serif 4', Georgia, serif; color: var(--graphite-soft, #6B7079); font-size: 11px; }

.op-activity .op-follow-strip { margin-top: 18px; padding-top: 16px; border-top: 1px dashed var(--card-rule, #E2C9BD); display: flex; justify-content: space-between; gap: 14px; align-items: center; }
.op-activity .op-follow-copy { font-size: 13.5px; font-weight: 600; color: var(--ink, #0E2240); flex: 1; min-width: 0; }
.op-activity .op-follow-copy span { display: block; font-weight: 400; font-size: 11.5px; color: var(--graphite-soft, #6B7079); margin-top: 3px; line-height: 1.4; }
.op-activity .op-follow-btn { background: var(--ink, #0E2240); color: var(--paper, #FAF7F0); border: none; padding: 11px 14px; font-family: 'Inter Tight', system-ui, sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; cursor: pointer; white-space: nowrap; }
.op-activity .op-follow-btn:hover { background: var(--ink-soft, #2A3957); }
.op-activity .op-follow-btn.is-tracking { background: var(--flame-deep, #A8341A); cursor: default; }

@media (max-width: 480px) {
  .op-activity .op-pulse-grid { gap: 8px; }
  .op-activity .op-pulse-item { padding: 9px 10px; }
  .op-activity .op-pulse-value { font-size: 15px; }
  .op-activity .op-follow-strip { flex-direction: column; align-items: stretch; gap: 12px; }
  .op-activity .op-follow-btn { width: 100%; padding: 13px; }
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

  function fmtMovement(pp) {
    if (pp == null || Number.isNaN(pp)) return "—";
    const sign = pp > 0 ? "+" : "";
    return `${sign}${pp.toFixed(1)}pp`;
  }

  function render(root, state) {
    const r = state.data || {};
    const voted = !!r.your_vote;
    const showViews = (r.views_24h || 0) >= VIEW_DISPLAY_MIN;

    const viewsCell = showViews
      ? `<div class="op-pulse-value">${r.views_24h}</div>`
      : `<div class="op-pulse-value is-locked">Soon</div>`;

    const movePp = r.movement_24h_pp;
    const moveCell = movePp == null
      ? `<div class="op-pulse-value is-locked">—</div>`
      : `<div class="op-pulse-value${movePp > 0 ? " is-up" : ""}">${fmtMovement(movePp)}</div>`;

    const alignmentCell = (voted && r.aligned_pct != null)
      ? `<div class="op-pulse-value">${r.aligned_pct}%</div>`
      : `<div class="op-pulse-value is-locked">Vote to see</div>`;

    const sentimentWrap = (voted && r.aligned_pct != null) ? `
      <div class="op-sentiment-wrap">
        <div class="op-sentiment-bar">
          <span class="op-sentiment-fill" style="width:${r.aligned_pct}%"></span>
          <span class="op-sentiment-mid"></span>
        </div>
        <div class="op-sentiment-scale"><span>Disagree</span><span>Mid</span><span>Agree</span></div>
      </div>
    ` : "";

    const moveNote = (movePp != null)
      ? `<div class="op-movement-note">Market probability has ${movePp > 0 ? "drifted toward" : "drifted away from"} the Desk's side since publication.</div>`
      : "";

    const stances = STANCE_KEYS.map((k) => {
      const n = (r.by_reaction || {})[k] || 0;
      const isActive = r.your_vote === k;
      const countHtml = voted
        ? `<span class="op-count">${n}</span>`
        : `<span class="op-count-hidden">vote</span>`;
      return `<button class="op-stance${isActive ? " is-active" : ""}" data-reaction="${k}">${STANCE_LABELS[k]} ${countHtml}</button>`;
    }).join("");

    root.innerHTML = `
      <div class="op-pulse-head">
        <span class="op-pulse-kicker">Market Pulse</span>
        <span class="op-pulse-live">LIVE</span>
      </div>
      <div class="op-pulse-grid">
        <div class="op-pulse-item">
          <div class="op-pulse-label">Read today</div>
          ${viewsCell}
        </div>
        <div class="op-pulse-item is-flame">
          <div class="op-pulse-label">24h movement</div>
          ${moveCell}
        </div>
        <div class="op-pulse-item">
          <div class="op-pulse-label">Desk alignment</div>
          ${alignmentCell}
        </div>
      </div>
      ${sentimentWrap}
      ${moveNote}
      <div>
        <div class="op-stance-label">Your read on the market</div>
        <div class="op-stance-row">${stances}</div>
      </div>
      <div class="op-follow-strip">
        <div class="op-follow-copy">
          Follow this call
          <span>Get notified if the edge disappears or the market moves &gt;5pp.</span>
        </div>
        <button class="op-follow-btn" type="button">Track market</button>
      </div>
    `;
    wireStances(root, state);
    wireFollow(root, state);
  }

  // -------------------- interaction ------------------------

  function wireStances(root, state) {
    const buttons = root.querySelectorAll(".op-stance");
    buttons.forEach((b) => {
      b.addEventListener("click", async () => {
        buttons.forEach((x) => (x.disabled = true));
        try {
          const res = await fetch(API + "/vote", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              match_id: state.matchId,
              reaction: b.dataset.reaction,
            }),
          });
          if (res.ok) {
            const body = await res.json();
            state.data = state.data || {};
            state.data.your_vote = body.your_vote;
            // Optimistic: mark voted so the vote-to-reveal layer
            // unlocks before the next refresh round-trip.
            render(root, state);
            refresh(root, state);
          } else {
            // 409 (locked) / 429 (cooldown) — silent; next refresh
            // restores the correct state.
          }
        } catch (_e) {
          /* non-fatal */
        } finally {
          buttons.forEach((x) => (x.disabled = false));
        }
      });
    });
  }

  function wireFollow(root, state) {
    const btn = root.querySelector(".op-follow-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      // TODO: wire to a real email-capture endpoint. For now, visual-only
      // state change matching the v2 mockup so the interaction is testable.
      if (btn.classList.contains("is-tracking")) return;
      btn.classList.add("is-tracking");
      btn.textContent = "Tracking ✓";
      btn.disabled = true;
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
