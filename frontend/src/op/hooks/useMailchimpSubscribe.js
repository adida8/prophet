// Shared Mailchimp subscribe hook — both the newsletter pop-up and the
// footer signup call this so submission logic, error surfacing, and the
// "remember subscribers" localStorage flag live in one place.
//
// Mailchimp embedded forms don't allow cross-origin POST + JSON response,
// so we use their JSON-P endpoint: swap /post → /post-json and supply a
// &c={callbackName} parameter. Mailchimp invokes window[callbackName]
// with { result: 'success' | 'error', msg: '…' }.

import { useCallback, useState } from "react";

// Public, non-secret Mailchimp embed identifiers (audience "Oddsprimer", dc us2).
// Env vars override the baked defaults so prod works without per-host config.
const FORM_ACTION   = import.meta.env.VITE_MAILCHIMP_FORM_ACTION
  || "https://oddsprimer.us2.list-manage.com/subscribe/post?u=5639b505d384d746edb6af404&id=51ee011415";
const HONEYPOT_NAME = import.meta.env.VITE_MAILCHIMP_HONEYPOT_NAME
  || "b_5639b505d384d746edb6af404_51ee011415";

const STORAGE_KEY      = "op_newsletter_popup";
const SUBSCRIBED_DAYS  = 365;
const REQUEST_TIMEOUT  = 10000;

function markSubscribed() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      status: "subscribed",
      exp: Date.now() + SUBSCRIBED_DAYS * 86400000,
    }));
  } catch (_e) {
    // localStorage may be disabled (private mode, etc.) — non-fatal.
  }
}

function toJsonpAction(action) {
  // Mailchimp embeds give you /subscribe/post?u=…&id=… — convert to
  // /subscribe/post-json?u=…&id=… so the response can fire our callback.
  if (action.includes("/post-json?")) return action;
  return action.replace("/post?", "/post-json?");
}

export default function useMailchimpSubscribe() {
  const [status, setStatus] = useState("idle");      // idle | submitting | success | error
  const [errorMsg, setErrorMsg] = useState("");

  const reset = useCallback(() => {
    setStatus("idle");
    setErrorMsg("");
  }, []);

  const subscribe = useCallback((email) => {
    if (!FORM_ACTION || !HONEYPOT_NAME) {
      setStatus("error");
      setErrorMsg("The newsletter is not configured yet. Please try again later.");
      return;
    }
    if (!email) {
      setStatus("error");
      setErrorMsg("Enter an email address to subscribe.");
      return;
    }

    setStatus("submitting");
    setErrorMsg("");

    const cbName = `op_mc_cb_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
    let script = null;
    let settled = false;

    const cleanup = () => {
      if (script && script.parentNode) script.parentNode.removeChild(script);
      try { delete window[cbName]; } catch (_e) { window[cbName] = undefined; }
    };

    const timeoutId = setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      setStatus("error");
      setErrorMsg("That took longer than expected. Please try again.");
    }, REQUEST_TIMEOUT);

    window[cbName] = (response) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutId);
      cleanup();
      const ok = response && response.result === "success";
      if (ok) {
        setStatus("success");
        markSubscribed();
        return;
      }
      // Mailchimp returns messages prefixed with HTML codes like "0 - …" —
      // strip that and any embedded markup before showing the reader.
      const raw = (response && response.msg) ? String(response.msg) : "";
      const cleaned = raw.replace(/^\d+\s*-\s*/, "").replace(/<[^>]+>/g, "").trim();
      setStatus("error");
      setErrorMsg(cleaned || "Something went wrong. Please try again.");
    };

    const base = toJsonpAction(FORM_ACTION);
    const joiner = base.includes("?") ? "&" : "?";
    const url =
      `${base}${joiner}EMAIL=${encodeURIComponent(email)}` +
      `&${encodeURIComponent(HONEYPOT_NAME)}=` +
      `&c=${cbName}`;

    script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutId);
      cleanup();
      setStatus("error");
      setErrorMsg("Could not reach the newsletter service. Please try again.");
    };
    document.body.appendChild(script);
  }, []);

  return {
    status,
    errorMsg,
    subscribe,
    reset,
    configured: Boolean(FORM_ACTION && HONEYPOT_NAME),
  };
}
