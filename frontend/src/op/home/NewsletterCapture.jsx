// Newsletter capture — the home "matchday edition" block. Wired to the
// shared subscribe hook → /api/subscribe → SendX.

import { useState } from "react";

import useMailchimpSubscribe from "../hooks/useMailchimpSubscribe";

export default function NewsletterCapture() {
  const [email, setEmail] = useState("");
  const { status, errorMsg, subscribe, reset } = useMailchimpSubscribe();

  const submitting = status === "submitting";
  const succeeded  = status === "success";

  const onSubmit = (e) => {
    e.preventDefault();
    if (submitting) return;
    subscribe(email.trim());
  };

  const onEmailChange = (e) => {
    setEmail(e.target.value);
    if (status === "error") reset();
  };

  return (
    <section className="news" aria-labelledby="news-title">
      <div className="news-inner">
        <div>
          <h2 id="news-title">The matchday edition.</h2>
          <p>One short edition per matchday — what the prices moved, what's still off, what we read.</p>
        </div>
        {succeeded ? (
          <p className="news-success" role="status">You&rsquo;re in &mdash; check your inbox.</p>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <label className="visually-hidden" htmlFor="news-email">Email address</label>
            <input
              id="news-email"
              type="email"
              placeholder="your.email@domain.com"
              value={email}
              onChange={onEmailChange}
              required
              autoComplete="email"
              disabled={submitting}
            />
            <button type="submit" disabled={submitting}>
              {submitting ? "Sending…" : "Subscribe"}
            </button>
            {status === "error" ? (
              <p className="news-error fine" role="alert" style={{ flexBasis: "100%" }}>
                {errorMsg || "Something went wrong. Please try again."}
              </p>
            ) : (
              <div className="fine" style={{ flexBasis: "100%" }}>
                No tips, no spam, one click to leave.
              </div>
            )}
          </form>
        )}
      </div>
    </section>
  );
}
