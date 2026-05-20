// Newsletter signup embedded at the top of the global site footer.
// Shares useMailchimpSubscribe with NewsletterPopup so both forms feed
// the same audience and remember subscribers identically.
//
// Stacks vertically on mobile; the input + button go inline at ≥600px.

import { useState } from "react";

import useMailchimpSubscribe from "./hooks/useMailchimpSubscribe";

const HONEYPOT_NAME = import.meta.env.VITE_MAILCHIMP_HONEYPOT_NAME || "";

export default function FooterSignup({ navigate }) {
  const [email, setEmail] = useState("");
  const { status, errorMsg, subscribe, reset } = useMailchimpSubscribe();

  const onSubmit = (e) => {
    e.preventDefault();
    if (status === "submitting") return;
    subscribe(email.trim());
  };

  const onEmailChange = (e) => {
    setEmail(e.target.value);
    if (status === "error") reset();
  };

  const onPrimerLink = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn/read-a-price");
  };

  const submitting = status === "submitting";
  const succeeded  = status === "success";

  return (
    <section className="foot-signup" aria-labelledby="foot-signup-title">
      <div className="foot-signup__inner">
        <p className="foot-signup__eyebrow">New to prediction markets?</p>
        <h2 className="foot-signup__title" id="foot-signup-title">
          Start with the weekly primer.
        </h2>
        <p className="foot-signup__lede">
          Plain-English notes on prediction markets, sportsbooks, and World Cup prices
          before you read the verdicts.
        </p>

        {succeeded ? (
          <p className="foot-signup__success" role="status">
            You&rsquo;re in &mdash; check your inbox.
          </p>
        ) : (
          <form className="foot-signup__form" onSubmit={onSubmit} noValidate>
            <label className="visually-hidden" htmlFor="foot-signup-email">
              Email address
            </label>
            <input
              id="foot-signup-email"
              type="email"
              name="EMAIL"
              placeholder="you@email.com"
              value={email}
              onChange={onEmailChange}
              required
              autoComplete="email"
              disabled={submitting}
            />
            <div className="foot-signup__hp" aria-hidden="true">
              <input
                type="text"
                name={HONEYPOT_NAME}
                tabIndex={-1}
                defaultValue=""
                autoComplete="off"
              />
            </div>
            <button type="submit" disabled={submitting}>
              {submitting ? "Sending…" : "Get the primer"}
            </button>
            {status === "error" ? (
              <p className="foot-signup__error" role="alert">
                {errorMsg || "Something went wrong. Please try again."}
              </p>
            ) : null}
          </form>
        )}

        <p className="foot-signup__micro">
          Free. Weekly. Educational only. Unsubscribe anytime.
        </p>

        <p className="foot-signup__alt">
          Prefer to just read? Start here:{" "}
          <a href="/learn/read-a-price" onClick={onPrimerLink}>
            How to read a price
          </a>
        </p>
      </div>
    </section>
  );
}
