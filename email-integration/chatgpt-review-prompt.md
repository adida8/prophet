# ChatGPT review prompt — Odds Primer email integration

Copy everything below the line into ChatGPT, and **attach the three HTML files**
(`newsletter-popup.html`, `footer-signup.html`, `welcome-email.html`). If your
ChatGPT can't read attachments, paste each file's source inline instead.

---

You are reviewing three front-end assets for **Odds Primer**, an educational
publication about prediction markets and sports betting odds. Act as two
reviewers in one pass: (1) a **brand/design director** checking consistency, and
(2) a **conversion/lifecycle-marketing specialist** optimising signup and
activation. Be specific and critical — I want the sharpest issues, not praise.

## What Odds Primer is
- An **educational** oddschecker, not a tipster. It compares prices across
  prediction markets (Polymarket, Kalshi) and sportsbooks and *explains* them.
  It does **not** give betting advice or take wagers. Free. 18+.
- The current flagship "issue" is the **World Cup 2026**. Masthead framing:
  "Odds Primer is the masthead; the World Cup is the issue."
- The product wedge is the **verdict** (Pick / Pass / Avoid) on each match, but
  the newsletter strategy here is **education-first**: lead new subscribers into
  the `/learn` primers before the live verdicts.

## Brand system (judge consistency against this)
- **Voice:** editorial, sports-desk, plain-English. Calm and credible, never
  hype. **Hard rules: no exclamation marks, no emoji.** No "tips", no "guaranteed",
  no urgency-bait.
- **Palette:** cream paper `#FAF7F0`, deep navy ink `#0E2240`, single accent
  "flame" orange `#D9461C` (used sparingly), warm rules `#D9D2C0`. Semantics are
  ink-based, **not** traffic-light green/red.
- **Type:** Inter Tight (chrome/UI/wordmark), Source Serif 4 (headlines + prose),
  JetBrains Mono (numbers/odds only). Wordmark is Inter Tight 700.
- **Layout:** mobile-first (designed at ~375px first), generous whitespace,
  modest radii, hairline rules. Magazine, not SaaS.

## The three assets
1. **newsletter-popup.html** — timed-delay pop-up (~18s), once per session,
   single email field posting to Mailchimp.
2. **footer-signup.html** — global site footer (navy) with the same email signup
   plus nav, legal disclaimer, and unsubscribe context.
3. **welcome-email.html** — Mailchimp welcome automation, education-first: hero
   welcome, three `/learn` primers as the primary CTA, a secondary nudge to the
   verdicts, and a compliant footer.

## What I want from you
For **each** asset, give:

1. **Brand consistency** — flag anything off-voice (especially any exclamation,
   emoji, hype, or tipster framing), off-palette, wrong typeface role, or
   un-magazine-like. Quote the exact offending text/style.
2. **Conversion / UX** — concretely improve signup rate and activation:
   - Pop-up: timing, trigger, friction, value proposition, dismissal, mobile
     behaviour, single-field vs. double opt-in trade-offs.
   - Footer: visibility, whether it earns the signup at end-of-page, microcopy.
   - Email: subject line + preheader suggestions, hierarchy, CTA clarity,
     education-first vs. verdict-first ordering, deliverability/spam risks,
     send timing.
3. **Copy rewrites** — propose tighter alternatives for headlines, lede, button
   labels, and (for the email) 3–5 subject-line options. Keep every rewrite
   inside the voice rules above (no exclamation marks, no emoji).
4. **Accessibility & compliance** — call out contrast, labels, focus states, and
   anything that risks CAN-SPAM / Mailchimp footer requirements.

Finish with a **prioritised punch list** (max 10 items) ranked by likely impact
on signups and activation, marking each as quick-win or larger-effort.
Be concrete — point to specific lines or elements rather than general advice.
