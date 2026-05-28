// The Desk · Ops social — draft approval queue.
//
// Mounted by OpsApp at /desk/ops/social. Reads from
// /api/desk/social/* (same Basic-auth gate as the rest of /desk/ops).
//
// Layout:
//   * List of drafts on the left, filtered by status (default Pending).
//   * Detail panel on the right when a draft is selected — slide
//     thumbnails, caption editors, action buttons.
//
// Phase 1 surface: Approve / Reject / Skip / Download bundle / Mark
// as posted. Phase 2 layers Publish on top without UX change here.

import { useCallback, useEffect, useMemo, useState } from "react";

import { fmtAgo, fmtClockUTC, fetchJson } from "./util";

const STATUS_TABS = [
  { id: "pending",        label: "Pending"        },
  { id: "approved",       label: "Approved"       },
  { id: "published",      label: "Published"      },
  { id: "publish_failed", label: "Failed"         },
  { id: "rejected",       label: "Rejected"       },
  { id: "skipped",        label: "Skipped"        },
];

const IG_MAX = 2200;
const X_MAX  = 280;

async function postJson(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    credentials: "same-origin",
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j && j.detail) detail = typeof j.detail === "string"
        ? j.detail
        : JSON.stringify(j.detail);
    } catch (_) { /* ignore */ }
    throw Object.assign(new Error(detail), { status: r.status });
  }
  return r.json();
}

function StatusBadge({ status }) {
  return <span className={`ops-social__badge ops-social__badge--${status}`}>{status}</span>;
}

function DraftRow({ draft, selected, onSelect }) {
  const label = draft.kind === "weekly_roundup"
    ? `Roundup · ${draft.week_starting || "—"}`
    : (draft.match_id || "—");
  return (
    <button
      className={`ops-social__row ${selected ? "is-selected" : ""}`}
      onClick={() => onSelect(draft.draft_id)}
    >
      <div className="ops-social__row-top">
        <span className="ops-social__row-label">{label}</span>
        <StatusBadge status={draft.status} />
      </div>
      <div className="ops-social__row-meta mono">
        {draft.kind} · created {fmtAgo(draft.created_at)}
      </div>
    </button>
  );
}

function CaptionEditor({ label, value, max, onSave, disabled }) {
  const [text, setText] = useState(value || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => { setText(value || ""); }, [value]);

  const len = text.length;
  const dirty = text !== (value || "");

  const submit = useCallback(async () => {
    if (!dirty) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(text);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }, [dirty, onSave, text]);

  return (
    <div className="ops-social__cap">
      <div className="ops-social__cap-head">
        <label>{label}</label>
        <span className={`ops-social__cap-count ${len > max ? "is-over" : ""}`}>
          {len} / {max}
        </span>
      </div>
      <textarea
        rows={label === "Instagram caption" ? 10 : 4}
        value={text}
        disabled={disabled || busy}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="ops-social__cap-actions">
        <button onClick={submit} disabled={!dirty || disabled || busy}>
          {busy ? "Saving…" : "Save caption"}
        </button>
        {error && <span className="ops-social__cap-error">{error}</span>}
      </div>
    </div>
  );
}

function DraftDetail({ draftId, onChange }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [igPermalink, setIgPermalink] = useState("");
  const [xTweetId, setXTweetId] = useState("");

  const reload = useCallback(async () => {
    if (!draftId) return;
    setLoading(true);
    setError(null);
    try {
      const d = await fetchJson(`/api/desk/social/drafts/${draftId}`);
      setDraft(d);
    } catch (e) {
      setError(e.message);
      setDraft(null);
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => { reload(); }, [reload]);

  const act = useCallback(async (toStatus, body) => {
    setBusy(true);
    setError(null);
    try {
      await postJson(`/api/desk/social/drafts/${draftId}/${toStatus}`, body);
      await reload();
      if (onChange) onChange();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }, [draftId, reload, onChange]);

  const editCaption = useCallback(async (platform, text) => {
    await postJson(`/api/desk/social/drafts/${draftId}/edit-caption`, {
      platform, text,
    });
    await reload();
    if (onChange) onChange();
  }, [draftId, reload, onChange]);

  const downloadBundle = useCallback(() => {
    window.location.href = `/api/desk/social/drafts/${draftId}/bundle.zip`;
  }, [draftId]);

  if (loading && !draft) return <div className="ops-social__detail-empty">Loading…</div>;
  if (error)            return <div className="ops-social__error">{error}</div>;
  if (!draft)            return <div className="ops-social__detail-empty">Select a draft from the list.</div>;

  const title = draft.kind === "weekly_roundup"
    ? `Weekly roundup · ${draft.week_starting}`
    : (draft.match_id || draft.draft_id);

  const canApprove = draft.status === "pending" || draft.status === "publish_failed";
  const canReject  = draft.status === "pending";
  const canSkip    = draft.status === "pending";
  const canBundle  = draft.status === "approved" || draft.status === "published" || draft.status === "publish_failed";
  const canMark    = draft.status === "approved" || draft.status === "publish_failed";
  const captionsLocked = ["published", "rejected", "skipped"].includes(draft.status);

  return (
    <div className="ops-social__detail">
      <header className="ops-social__detail-head">
        <div>
          <h2>{title}</h2>
          <div className="ops-social__detail-sub mono">
            {draft.draft_id} · created {fmtClockUTC(draft.created_at)}
          </div>
        </div>
        <StatusBadge status={draft.status} />
      </header>

      <div className="ops-social__slides">
        {(draft.slides || []).map((s) => (
          <a
            key={s.slide_no}
            href={`/api/desk/social/drafts/${draft.draft_id}/slides/${s.slide_no}.png`}
            target="_blank"
            rel="noopener noreferrer"
            className="ops-social__slide"
          >
            <img
              src={`/api/desk/social/drafts/${draft.draft_id}/slides/${s.slide_no}.png`}
              alt={`Slide ${s.slide_no}`}
            />
            <span className="ops-social__slide-no">Slide {s.slide_no}</span>
          </a>
        ))}
      </div>

      <CaptionEditor
        label="Instagram caption"
        value={draft.caption_ig}
        max={IG_MAX}
        disabled={captionsLocked || busy}
        onSave={(text) => editCaption("ig", text)}
      />
      <CaptionEditor
        label="X caption"
        value={draft.caption_x}
        max={X_MAX}
        disabled={captionsLocked || busy}
        onSave={(text) => editCaption("x", text)}
      />

      <div className="ops-social__actions">
        <button
          className="ops-social__btn ops-social__btn--approve"
          onClick={() => act("approve")}
          disabled={!canApprove || busy}
        >
          Approve
        </button>
        <button
          className="ops-social__btn ops-social__btn--reject"
          onClick={() => act("reject")}
          disabled={!canReject || busy}
        >
          Reject
        </button>
        <button
          className="ops-social__btn"
          onClick={() => act("skip")}
          disabled={!canSkip || busy}
        >
          Skip
        </button>
        <button
          className="ops-social__btn ops-social__btn--bundle"
          onClick={downloadBundle}
          disabled={!canBundle || busy}
        >
          Download bundle
        </button>
      </div>

      {canMark && (
        <div className="ops-social__mark">
          <h3>Mark as posted (phase 1)</h3>
          <p className="ops-social__hint">
            Phase 1 publish is manual — paste the live URLs after posting.
            Both fields are optional.
          </p>
          <label>IG permalink<input
            value={igPermalink}
            onChange={(e) => setIgPermalink(e.target.value)}
            placeholder="https://www.instagram.com/p/…"
          /></label>
          <label>X tweet id<input
            value={xTweetId}
            onChange={(e) => setXTweetId(e.target.value)}
            placeholder="1234567890123456789"
          /></label>
          <button
            className="ops-social__btn ops-social__btn--approve"
            disabled={busy}
            onClick={() => act("mark-posted", {
              ig_permalink: igPermalink || null,
              x_tweet_id:   xTweetId   || null,
            })}
          >
            Mark as posted
          </button>
        </div>
      )}

      {draft.edit_history && draft.edit_history.length > 0 && (
        <details className="ops-social__history">
          <summary>Edit history · {draft.edit_history.length}</summary>
          <ul>
            {draft.edit_history.map((h, i) => (
              <li key={i}>
                <span className="mono">{fmtClockUTC(h.at)}</span> ·
                {" "}{h.by || "anon"} edited {h.field}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function OpsSocial() {
  const [tab, setTab] = useState("pending");
  const [drafts, setDrafts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `/api/desk/social/drafts?status=${tab}&limit=200`;
      const j = await fetchJson(url);
      const next = j.drafts || [];
      setDrafts(next);
      // Keep the selection sticky if it's still in the list, else pick first.
      if (!selected || !next.find((d) => d.draft_id === selected)) {
        setSelected(next[0]?.draft_id || null);
      }
    } catch (e) {
      setError(e.message);
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  }, [tab, selected]);

  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [tab]);

  return (
    <>
      <header className="ops__header">
        <div>
          <div className="ops__title">The Desk · Social</div>
          <div className="ops__subtitle">
            Approve the carousel + captions before they go live.
          </div>
        </div>
        <div className="ops__header-right">
          <button className="ops__reload" onClick={load} disabled={loading}>
            ↻ Reload
          </button>
        </div>
      </header>

      <div className="ops-social__tabs">
        {STATUS_TABS.map((t) => (
          <button
            key={t.id}
            className={`ops-social__tab ${tab === t.id ? "is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="ops__error">{error}</div>}

      <div className="ops-social__layout">
        <div className="ops-social__list">
          {drafts.length === 0
            ? <div className="ops-social__empty">No {tab} drafts.</div>
            : drafts.map((d) => (
              <DraftRow
                key={d.draft_id}
                draft={d}
                selected={selected === d.draft_id}
                onSelect={setSelected}
              />
            ))}
        </div>
        <div className="ops-social__detail-wrap">
          {selected
            ? <DraftDetail draftId={selected} onChange={load} />
            : <div className="ops-social__detail-empty">Select a draft to review.</div>}
        </div>
      </div>
    </>
  );
}
