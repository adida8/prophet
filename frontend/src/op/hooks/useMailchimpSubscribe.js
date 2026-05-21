// Shared newsletter subscribe hook. Both the timed pop-up and the footer
// signup call this so submission logic, error surfacing, and the "remember
// subscribers" localStorage flag live in one place.
//
// Posts the email to the Prophet backend (/api/subscribe), which forwards
// it to SendX server-side — the SendX API key never reaches the browser.
// (Filename kept as-is from the prior Mailchimp implementation to avoid
// churn at the three call sites; the integration is SendX now.)

import { useCallback, useState } from "react";

const SUBSCRIBE_URL   = "/api/subscribe";
const STORAGE_KEY     = "op_newsletter_popup";
const SUBSCRIBED_DAYS = 365;
const REQUEST_TIMEOUT = 10000;

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

export default function useMailchimpSubscribe() {
  const [status, setStatus] = useState("idle");      // idle | submitting | success | error
  const [errorMsg, setErrorMsg] = useState("");

  const reset = useCallback(() => {
    setStatus("idle");
    setErrorMsg("");
  }, []);

  // `hp` is the optional honeypot value — real users leave it empty.
  const subscribe = useCallback(async (email, hp = "") => {
    if (!email) {
      setStatus("error");
      setErrorMsg("Enter an email address to subscribe.");
      return;
    }

    setStatus("submitting");
    setErrorMsg("");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

    try {
      const resp = await fetch(SUBSCRIBE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, hp }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (resp.ok) {
        setStatus("success");
        markSubscribed();
        return;
      }

      let detail = "";
      try {
        const data = await resp.json();
        detail = data && data.detail ? String(data.detail) : "";
      } catch (_e) {
        // Non-JSON error body — fall through to a generic message.
      }

      setStatus("error");
      if (resp.status === 429) {
        setErrorMsg("You're going a little fast — try again in a moment.");
      } else if (resp.status === 400) {
        setErrorMsg(detail || "Please enter a valid email address.");
      } else {
        setErrorMsg(detail || "Something went wrong. Please try again.");
      }
    } catch (err) {
      clearTimeout(timeoutId);
      setStatus("error");
      setErrorMsg(
        err && err.name === "AbortError"
          ? "That took longer than expected. Please try again."
          : "Could not reach the newsletter service. Please try again."
      );
    }
  }, []);

  return {
    status,
    errorMsg,
    subscribe,
    reset,
    configured: true,
  };
}
