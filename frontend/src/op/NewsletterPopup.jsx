// Engagement-triggered newsletter pop-up.
//
// Trigger:  50s on page OR 50% scroll depth, whichever first.
//           15s on high-intent paths (/matches, /match, /outrights).
// Suppress: never on /learn (interrupting a primer read is hostile).
// Memory:   dismissals remembered 10 days, subscribers remembered 365 days.
// A11y:     role=dialog + aria-modal, focus trap, ESC + backdrop close,
//           background scroll lock, return focus to prior element on close.

import { useCallback, useEffect, useRef, useState } from "react";

import useMailchimpSubscribe from "./hooks/useMailchimpSubscribe";

const POPUP_DELAY_MS    = 50000;
const HIGH_INTENT_MS    = 15000;
const SCROLL_TRIGGER    = 0.5;
const DISMISS_DAYS      = 10;
const SUBSCRIBED_DAYS   = 365;
const SUPPRESS_PATHS    = ["/learn"];
const HIGH_INTENT_PATHS = ["/matches", "/match", "/outrights"];
const STORAGE_KEY       = "op_newsletter_popup";
const HONEYPOT_NAME     = import.meta.env.VITE_MAILCHIMP_HONEYPOT_NAME || "b_5639b505d384d746edb6af404_51ee011415";
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])';

function startsWithAny(path, list) {
  return list.some((p) => path === p || path.startsWith(`${p}/`));
}

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (v && v.exp && Date.now() > v.exp) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return v ? v.status : null;
  } catch (_e) {
    return null;
  }
}

function writeStored(status, days) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      status,
      exp: Date.now() + days * 86400000,
    }));
  } catch (_e) {
    // localStorage unavailable — degrade silently.
  }
}

// Disabled for launch. Footer signup is the only capture point.
export default function NewsletterPopup() {
  return null;
}

function _NewsletterPopupImpl() {
  const [open, setOpen]     = useState(false);
  const [email, setEmail]   = useState("");
  const dialogRef           = useRef(null);
  const lastFocusRef        = useRef(null);
  const firedRef            = useRef(false);
  const { status, errorMsg, subscribe, reset } = useMailchimpSubscribe();

  const path = typeof window !== "undefined" ? window.location.pathname : "/";
  const suppressed = startsWithAny(path, SUPPRESS_PATHS);
  const highIntent = startsWithAny(path, HIGH_INTENT_PATHS);

  // ── trigger logic (timer + scroll, one-shot) ─────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    if (suppressed) return undefined;
    if (readStored()) return undefined;
    if (firedRef.current) return undefined;

    const delayMs = highIntent ? HIGH_INTENT_MS : POPUP_DELAY_MS;

    const fire = () => {
      if (firedRef.current) return;
      firedRef.current = true;
      setOpen(true);
    };

    const tid = window.setTimeout(fire, delayMs);

    const onScroll = () => {
      if (firedRef.current) return;
      const h = document.documentElement;
      const max = (h.scrollHeight - h.clientHeight) || 1;
      const depth = (h.scrollTop || document.body.scrollTop) / max;
      if (depth >= SCROLL_TRIGGER) fire();
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      window.clearTimeout(tid);
      window.removeEventListener("scroll", onScroll);
    };
  }, [suppressed, highIntent]);

  // ── close (memoised so the effects below can reference it) ────────
  const close = useCallback((markAs = "dismissed", days = DISMISS_DAYS) => {
    setOpen(false);
    if (markAs) writeStored(markAs, days);
    if (lastFocusRef.current && typeof lastFocusRef.current.focus === "function") {
      lastFocusRef.current.focus();
    }
  }, []);

  // ── while open: scroll-lock, focus trap, ESC, initial focus ──────
  useEffect(() => {
    if (!open) return undefined;
    lastFocusRef.current = document.activeElement;
    document.body.classList.add("op-noscroll");

    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close("dismissed", DISMISS_DAYS);
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const nodes = dialogRef.current.querySelectorAll(FOCUSABLE);
      if (!nodes.length) return;
      const first = nodes[0];
      const last  = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);

    const emailInput = dialogRef.current && dialogRef.current.querySelector('input[name="EMAIL"]');
    if (emailInput && typeof emailInput.focus === "function") emailInput.focus();

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("op-noscroll");
    };
  }, [open, close]);

  // Once a subscribe succeeds the storage flag is set inside the hook,
  // which already prevents re-show in future sessions. We keep the modal
  // open so the success state is readable; user closes when ready.

  const onSubmit = (e) => {
    e.preventDefault();
    if (status === "submitting") return;
    subscribe(email.trim());
  };

  const onEmailChange = (e) => {
    setEmail(e.target.value);
    if (status === "error") reset();
  };

  const onBackdrop = (e) => {
    if (e.target === e.currentTarget) close("dismissed", DISMISS_DAYS);
  };

  if (!open) return null;

  const submitting = status === "submitting";
  const succeeded  = status === "success";

  return (
    <div className="op-popup-overlay" onClick={onBackdrop}>
      <section
        ref={dialogRef}
        className="op-popup"
        role="dialog"
        aria-modal="true"
        aria-labelledby="op-popup-title"
      >
        <div className="op-popup__accent" aria-hidden="true" />
        <div className="op-popup__body">
          <button
            type="button"
            className="op-popup__close"
            aria-label="Close newsletter sign-up"
            onClick={() => close("dismissed", DISMISS_DAYS)}
          >
            <span aria-hidden="true">&times;</span>
          </button>

          <p className="op-popup__eyebrow">The newsletter</p>
          <h2 className="op-popup__title" id="op-popup-title">
            Read World Cup odds before the verdicts arrive.
          </h2>
          <p className="op-popup__lede">
            One weekly primer on prediction markets, sportsbooks, and how to understand a price.
            No betting advice. No hype.
          </p>

          {succeeded ? (
            <p className="op-popup__success" role="status">
              You&rsquo;re in &mdash; check your inbox.
            </p>
          ) : (
            <form onSubmit={onSubmit} noValidate>
              <label className="op-popup__field-label" htmlFor="op-popup-email">
                Email address
              </label>
              <input
                id="op-popup-email"
                className="op-popup__input"
                type="email"
                name="EMAIL"
                placeholder="you@email.com"
                value={email}
                onChange={onEmailChange}
                required
                autoComplete="email"
                disabled={submitting}
              />
              <div className="op-popup__hp" aria-hidden="true">
                <input
                  type="text"
                  name={HONEYPOT_NAME}
                  tabIndex={-1}
                  defaultValue=""
                  autoComplete="off"
                />
              </div>
              <button type="submit" className="op-popup__btn" disabled={submitting}>
                {submitting ? "Sending…" : "Get the weekly primer"}
              </button>
              {status === "error" ? (
                <p className="op-popup__error" role="alert">
                  {errorMsg || "Something went wrong. Please try again."}
                </p>
              ) : null}
            </form>
          )}

          <p className="op-popup__micro">
            Free. One email a week. Unsubscribe anytime.
          </p>
          <button
            type="button"
            className="op-popup__decline"
            onClick={() => close("dismissed", DISMISS_DAYS)}
          >
            Continue reading
          </button>
        </div>
      </section>
    </div>
  );
}
