# Odds Primer — handover-v4 site bundle

Every page of the site, concatenated for audit. Inline `<style>` blocks have been stripped to cut redundant chrome — the canonical design tokens live at the end of this document in `colors_and_type.css`.

Pages are grouped by audit priority:

- **Marketing & editorial** (7) — high-leverage, full audit
- **Trust & compliance** (3) — light audit
- **Legal** (3) — light audit, mostly compliance copy
- **Utility** (1) — error page

---

## `home.html` — Marketing & editorial

*Top of funnel; homepage. Must convert curiosity into a second click.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Odds Primer — Pick, Pass, or Avoid · World Cup 2026</title>
<meta name="description" content="We compare prices on the World Cup across Polymarket, Kalshi, and the sportsbooks. We explain what the numbers mean. We don't tip.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <!-- ============ 1. MASTHEAD + NAV ============ -->
  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>

      <nav class="site-nav" aria-label="Primary">
              <ul>
                <li><a href="./home.html" aria-current="page">Home</a></li>
                <li><a href="./outrights.html">Outright winners</a></li>
                <li><a href="./matches.html">Upcoming matches</a></li>
              </ul>
            </nav>

      <span class="nav-meta">Updated 14:08 ET</span>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./method.html">Method</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>

    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>Vol. 1 · World Cup 2026 · Matchday 2</span>
        <span class="live">Markets live</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">

    <!-- ============ 2. HERO ============ -->
    <section class="hero" aria-labelledby="hero-title">
      <h1 id="hero-title">The 2026 World Cup, priced.</h1>
      <p class="standfirst">
        Our <em class="ai-token">AI model</em> compares Polymarket and Kalshi prices
        with its own read of each World Cup market. Every market gets one verdict:
        <em class="vlead">Pick</em>, <em class="vlead">Pass</em>, or
        <em class="vlead">Avoid</em>. We show the price, the edge, and the reasoning.
        We don't tip.
      </p>
    </section>

    <!-- ============ 2.5 LEAD VERDICT — today's headline call ============ -->
    <section class="lead-verdict" aria-labelledby="lv-title">
      <div class="lv-eyebrow">Today's headline verdict · Matchday 2 · Saturday</div>

      <a class="lv-card is-pick" href="./market-v2-newspaper-deck.html">
        <span class="lv-bar"></span>

        <div class="lv-head">
          <span class="lv-glyph">▲</span>
          <span class="lv-lab">Pick</span>
          <span class="lv-when">Sat · 21:00 ET · Group F</span>
        </div>

        <h2 class="lv-teams" id="lv-title">
          France <span class="vs">v</span> Mexico
        </h2>
        <p class="lv-venue-meta">MEX · Estadio Azteca</p>

        <p class="lv-thesis">
          <em>France look four points underpriced.</em>
          Polymarket is pricing France lower than our model. Our model has France
          at 56% to win; the market has them at 52%. That gap is the edge.
        </p>

        <div class="lv-foot">
          <div class="lv-reads">
            <span class="rp"><span class="k">model</span><span class="v">56%</span></span>
            <span class="rp"><span class="k">market</span><span class="v">52%</span></span>
            <span class="edge">+4pp</span>
          </div>
          <div class="lv-action">
            <span class="venue">Polymarket</span>
            <span class="price">−180</span>
            <span class="cta">Read the market case <span class="arr">↗</span></span>
          </div>
        </div>
      </a>
      <p class="lv-method-link">
        <a href="./method.html#verdict">How we made this call <span class="arr">↗</span></a>
      </p>
      <p class="affiliate-note">
        Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.
      </p>

      <!-- ============ 3-step path explainer ============ -->
      <aside class="path-explainer" aria-label="How to read a verdict">
        <span class="step"><span class="num">1</span>Read the market case</span>
        <span class="path-arr">→</span>
        <span class="step"><span class="num">2</span>Compare the price</span>
        <span class="path-arr">→</span>
        <span class="step"><span class="num">3</span>View source on Polymarket or Kalshi</span>
      </aside>
    </section>

    <!-- ============ 2.6 VERDICT KEY — three states (below the lead, demo first then teach) ============ -->
    <section class="verdict-key" aria-label="How to read a verdict">
      <div class="vk-eyebrow">The verdict · three states</div>
      <div class="vk-grid">

        <div class="vk-card vk-pick">
          <div class="vk-head">
            <span class="vk-glyph">▲</span>
            <span class="vk-lab">Pick</span>
          </div>
          <p class="vk-what">
            <em>The model sees the market as underpriced.</em>
            Worth inspecting, not a guaranteed outcome.
          </p>
        </div>

        <div class="vk-card vk-pass">
          <div class="vk-head">
            <span class="vk-glyph">—</span>
            <span class="vk-lab">Pass</span>
          </div>
          <p class="vk-what">
            <em>No clear edge.</em>
            The market is close to our model.
          </p>
        </div>

        <div class="vk-card vk-avoid">
          <div class="vk-head">
            <span class="vk-glyph">✕</span>
            <span class="vk-lab">Avoid</span>
          </div>
          <p class="vk-what">
            <em>The price looks unattractive.</em>
            Interesting event, poor market structure.
          </p>
        </div>

      </div>
    </section>

    <!-- ============ 3. ARTICLE PREVIEWS — outrights + upcoming matches ============ -->
    <section class="article-previews" aria-label="Today's lead reads">
      <div class="prev-grid">

        <a class="article-preview prev-outrights" href="./outrights.html">
          <span class="kicker">Outright winners · World Cup 2026</span>
          <h2 class="prev-title">Three reads on who lifts the trophy.</h2>
          <p class="prev-deck">
            Where the model and the market disagree most.
            <em>France</em> and <em>Argentina</em> look underpriced;
            <em>Brazil</em> is the favourite priced thin.
          </p>
          <div class="prev-peek">
            <span class="peek-stat"><span class="pn">3</span><span class="pl">picks</span></span>
            <span class="peek-stat"><span class="pn">1</span><span class="pl">avoid</span></span>
            <span class="peek-stat"><span class="pn">+5pp</span><span class="pl">top edge</span></span>
          </div>
          <span class="prev-cta">Read the outright board <span class="arr">→</span></span>
        </a>

        <a class="article-preview prev-matches" href="./matches.html">
          <span class="kicker">Upcoming matches · Matchday 2</span>
          <h2 class="prev-title">Where today's prices look wrong.</h2>
          <p class="prev-deck">
            Eight fixtures across three groups — three Picks, four Passes,
            one rare two-way Avoid. <em>France v Mexico</em> is the
            headline read.
          </p>
          <div class="prev-peek">
            <span class="peek-stat"><span class="pn">3</span><span class="pl">picks</span></span>
            <span class="peek-stat"><span class="pn">4</span><span class="pl">passes</span></span>
            <span class="peek-stat"><span class="pn">1</span><span class="pl">avoid</span></span>
          </div>
          <span class="prev-cta">Read the match board <span class="arr">→</span></span>
        </a>

      </div>
    </section>

    <!-- ============ 6. HOW WE WORK ============ -->
    <section class="how" aria-labelledby="how-title">
      <h2 id="how-title">How we work</h2>
      <p class="lede">Three things every page on this site shows: a price, a comparison, and an explanation.</p>
      <div class="how-cols">
        <div class="how-col">
          <h3>We compare</h3>
          <p>Prices on Polymarket, Kalshi, and the major US sportsbooks, refreshed every minute. <span class="em">Best price</span> is bold ink, not a green badge — it isn't a buy signal.</p>
        </div>
        <div class="how-col">
          <h3>We explain</h3>
          <p>Plain English on what the market resolves to, how implied probability works, and why two venues might disagree on the same outcome.</p>
        </div>
        <div class="how-col">
          <h3>We don't tip</h3>
          <p>No hype, no tip-of-the-day, no instructions. The Desk flags fixtures where the line looks slow, fair, or both-sides expensive — a structural read on the prices, not a call on the outcome.</p>
        </div>
      </div>
      <div class="how-foot">
        <a class="link-secondary" href="./method.html">See the method in six stages →</a>
      </div>
    </section>

    <!-- ============ 7. FEATURED COLUMNS ============ -->
    <section class="features" aria-labelledby="features-title">
      <div class="f-head">
        <h2 id="features-title">Featured columns</h2>
        <a href="/columns">All columns <span class="arr">→</span></a>
      </div>
      <div class="f-grid">
        <a class="f-card" href="/columns/poly-kalshi-france">
          <span class="kicker">Outright winner</span>
          <span class="title">Why Polymarket and Kalshi don't agree on France</span>
          <p class="deck">A two-cent gap on a binary contract is a two-percentage-point gap on the same outcome. Small in the abstract, large for a market this liquid.</p>
          <span class="meta">6 min read · The Editors · 12 May</span>
        </a>
        <a class="f-card" href="/columns/what-plus-130-means">
          <span class="kicker">Reading the numbers</span>
          <span class="title">What +130 actually means</span>
          <p class="deck">American odds, decimal odds, and "cents" on a contract — three notations for the same idea. A short conversion table, with examples.</p>
          <span class="meta">4 min read · 10 May</span>
        </a>
        <a class="f-card" href="/columns/group-d-priced-closest">
          <span class="kicker">Group stage</span>
          <span class="title">Group D is priced as the closest in the tournament</span>
          <p class="deck">France is favored, but four cents separates the field. We look at why the books and the markets disagree most where the football is closest.</p>
          <span class="meta">5 min read · 09 May</span>
        </a>
      </div>
    </section>
  </main>

  <!-- ============ 8. NEWSLETTER ============ -->
  <section class="news" aria-labelledby="news-title">
    <div class="news-inner">
      <div>
        <h2 id="news-title">The matchday edition.</h2>
        <p>One short edition per matchday — what the prices moved, what's still off, what we read.</p>
      </div>
      <form onsubmit="event.preventDefault();">
        <label class="visually-hidden" for="news-email">Email address</label>
        <input id="news-email" type="email" placeholder="your.email@domain.com" required>
        <button type="submit">Subscribe</button>
        <div class="fine" style="flex-basis:100%;">No tips, no spam, one click to leave.</div>
      </form>
    </div>
  </section>

  <!-- ============ 9. FOOTER ============ -->
  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./method.html">Method</a></li>
            <li><a href="./methodology.html">Methodology (detail)</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>

      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <!-- ============ 10. STICKY MOBILE BOTTOM BAR ============ -->
  <div class="sticky-bar" role="navigation" aria-label="Quick actions">
    <a class="count" href="./matches.html">
      Today: <strong><span class="pp">3 picks</span> · top edge <span class="pp">+5pp</span></strong>
    </a>
    <a class="pill" href="./matches.html">See reads <span class="arr">↗</span></a>
  </div>

  <!-- styles stripped for bundle; see colors_and_type.css at the end -->

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref">
        <input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span>
      </label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>
</body>
</html>
```

---

## `method.html` — Marketing & editorial

*Six-stage 'how it works' visual explainer.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Method — Odds Primer</title>
<meta name="description" content="How The Desk reaches a verdict — six stages, from ingest to publication. Marketing-tuned overview of the Odds Primer engine.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./method.html" aria-current="page">Method</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">

    <div class="method-page-head">
      <div class="page-eyebrow">Method</div>
    </div>

    <div class="method-wrap">
      <section class="dd" aria-label="How The Desk works">

        <!-- Trust tease -->
        <div class="trust-tease" aria-label="What we publish">
          <div class="trust-stamps" aria-hidden="true">
            <span class="stamp-mini stamp-pick">Pick</span>
            <span class="stamp-mini stamp-pass">Pass</span>
            <span class="stamp-mini stamp-avoid">Avoid</span>
          </div>
          <p class="trust-line">Three verdicts. We use all three. <strong>Most prices don't clear our bar</strong> — and we say so out loud.</p>
        </div>

        <h1 class="dd-h">One match. Six stages. One verdict.</h1>
        <p class="dd-sub">We watch the markets. We do the maths. We say whether the price is worth taking.</p>
        <div class="dd-rule"></div>

        <!-- 01 INGEST -->
        <div class="stage">
          <div class="stage-head">
            <div class="stage-num">01</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Ingest</div>
              <h2 class="stage-title">Every fixture the market prices, we evaluate</h2>
              <p class="stage-cap">Multiple sources, joined on one fixture.</p>
            </div>
          </div>
          <div class="src-grid" aria-label="Data sources">
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#2A6FDB"></span><span class="src-name">POLYMARKET</span></div><div class="src-body">Live prices.</div></div>
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#00C46A"></span><span class="src-name">KALSHI</span></div><div class="src-body">Live prices.</div></div>
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#0E2240"></span><span class="src-name">TEAM RATINGS</span></div><div class="src-body">Strength over time.</div></div>
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#3A3F47"></span><span class="src-name">FIXTURE DATA</span></div><div class="src-body">Venue, stage, kickoff.</div></div>
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#B89968"></span><span class="src-name">CONDITIONS</span></div><div class="src-body">What changes on the day.</div></div>
            <div class="src"><div class="src-tag"><span class="src-swatch" style="background:#D9461C"></span><span class="src-name">NEWSROOM</span></div><div class="src-body">Vetted, sport-tagged.</div></div>
          </div>
          <div class="src-funnel" aria-hidden="true">
            <svg viewBox="0 0 200 24" preserveAspectRatio="none">
              <line x1="10"  y1="2" x2="80"  y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
              <line x1="60"  y1="2" x2="92"  y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
              <line x1="110" y1="2" x2="100" y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
              <line x1="100" y1="2" x2="108" y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
              <line x1="160" y1="2" x2="116" y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
              <line x1="190" y1="2" x2="120" y2="22" stroke="#D9D2C0" stroke-width="0.8"/>
            </svg>
          </div>
        </div>
        <div class="arrow-down"></div>

        <!-- 02 CONTEXT -->
        <div class="stage" id="verdict-context">
          <div class="stage-head">
            <div class="stage-num">02</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Context</div>
              <h2 class="stage-title">We watch the match all the way to kickoff</h2>
              <p class="stage-cap">Some context is stable. Some only matters at the end.</p>
            </div>
          </div>
          <div class="tl">
            <div class="tl-row"><div class="tl-pill stable" style="left:0%; right:0%;">Stable context</div></div>
            <div class="tl-row"><div class="tl-pill late"   style="left:62%; right:0%;">Late context</div></div>
            <div class="tl-axis">
              <div class="tl-tick" style="left:0%;"></div>   <div class="tl-tick-label" style="left:0%;">Weeks out</div>
              <div class="tl-tick" style="left:62%;"></div>
              <div class="tl-tick" style="left:100%;"></div> <div class="tl-tick-label" style="left:100%; transform:translateX(-100%);">Kickoff</div>
            </div>
            <p class="tl-caption">If a piece of context isn't ready yet, we wait — we don't guess.</p>
          </div>
        </div>
        <div class="arrow-down"></div>

        <!-- 03 MODEL -->
        <div class="stage">
          <div class="stage-head">
            <div class="stage-num">03</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Model</div>
              <h2 class="stage-title">We work out the odds — independently</h2>
              <p class="stage-cap">Our number, before we look at theirs.</p>
            </div>
          </div>
          <div class="pb">
            <div class="pb-row">
              <div class="pb-label">France</div>
              <div class="pb-track"><div class="pb-fill home" style="width:48%"></div></div>
              <div class="pb-pct">48.0%</div>
            </div>
            <div class="pb-row">
              <div class="pb-label">Draw</div>
              <div class="pb-track"><div class="pb-fill draw" style="width:27%"></div></div>
              <div class="pb-pct">27.0%</div>
            </div>
            <div class="pb-row">
              <div class="pb-label">Mexico</div>
              <div class="pb-track"><div class="pb-fill away" style="width:25%"></div></div>
              <div class="pb-pct">25.0%</div>
            </div>
            <div class="pb-sum">Trained on every priced match. Never reads the market it's about to evaluate.</div>
          </div>
        </div>
        <div class="arrow-down"></div>

        <!-- 04 VERDICT -->
        <div class="stage" id="verdict">
          <div class="stage-head">
            <div class="stage-num">04</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Verdict</div>
              <h2 class="stage-title">Pick, Pass, or Avoid</h2>
              <p class="stage-cap">Our number, against the best market price on the board.</p>
            </div>
          </div>
          <div class="vc">
            <div class="vc-bars">
              <div class="vc-label">The Desk<span class="meta">our model</span></div>
              <div class="vc-track"><div class="vc-fill desk" style="width:48%"></div></div>
              <div class="vc-pct">48.0%</div>
            </div>
            <div class="vc-bars">
              <div class="vc-label">Polymarket<span class="meta">best price</span></div>
              <div class="vc-track"><div class="vc-fill market" style="width:43.8%"></div></div>
              <div class="vc-pct">43.8%</div>
            </div>
            <div class="vc-edge">
              <span class="vc-edge-label">edge in our favour</span>
              <span class="vc-edge-value">+4.2pp</span>
            </div>

            <div class="ts">
              <div class="ts-label">where the edge lands</div>
              <div class="ts-scale">
                <div class="ts-band avoid">Avoid</div>
                <div class="ts-band pass">Pass</div>
                <div class="ts-band pick">Pick</div>
                <div class="ts-bar-label" style="left:30%;">market ahead</div>
                <div class="ts-bar-label" style="left:70%;">our bar</div>
                <div class="ts-here" style="left:84%;">
                  <span class="ts-here-flag">this match</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="arrow-down"></div>

        <!-- 05 EXPLAINER -->
        <div class="stage">
          <div class="stage-head">
            <div class="stage-num">05</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Editorial</div>
              <h2 class="stage-title">A verdict, in plain words</h2>
              <p class="stage-cap">What the reader actually sees.</p>
            </div>
          </div>
          <div class="pub-card">
            <span class="pub-stamp">Pick</span>
            <div class="pub-eyebrow">FIFA World Cup 2026 · Group D · 12 June</div>
            <h3 class="pub-title">France v Mexico · class shows</h3>
            <p class="pub-summary">Our number sits clear of the market on France. Group context, conditions in Guadalajara, and the spine of the squad all line up the same way.</p>
            <div class="pub-foot">
              <span class="pub-cite"><a href="#">View source on Polymarket ↗</a></span>
              <span class="pub-time">Updated 17:00 UTC</span>
            </div>
          </div>
        </div>
        <div class="arrow-down"></div>

        <!-- 06 REACH -->
        <div class="stage">
          <div class="stage-head">
            <div class="stage-num">06</div>
            <div class="stage-meta">
              <div class="stage-eyebrow">Reach</div>
              <h2 class="stage-title">Same verdict, wherever you read</h2>
              <p class="stage-cap">One call. Many surfaces.</p>
            </div>
          </div>
          <div class="reach">
            <div class="reach-row">
              <span class="reach-where">Site</span>
              <span class="reach-what">France · <span class="flame">PICK</span> · +4.2pp · <em>view source on Polymarket</em></span>
            </div>
            <div class="reach-row">
              <span class="reach-where">API</span>
              <span class="reach-what"><span class="mono">{ side: "France", state: "pick", edge_pp: 4.2 }</span></span>
            </div>
            <div class="reach-row">
              <span class="reach-where">Partners</span>
              <span class="reach-what">Embed-ready verdict tiles for editorial &amp; affiliate desks.</span>
            </div>
          </div>
          <p class="reach-cap">When the call changes, every surface updates together.</p>
        </div>

        <!-- Promise footer -->
        <div class="dd-rule-ink"></div>
        <div class="promise-head">What we won't do</div>
        <ul class="promises">
          <li>Let the market influence our own number.</li>
          <li>Quote tipsters or hide behind anonymous picks.</li>
          <li>Tell you how much to stake.</li>
          <li>Refuse to show our working.</li>
        </ul>
        <a class="methlink" href="./methodology.html">Read the full methodology ↗</a>

        <div class="dd-foot">From The Desk · odds primer</div>
      </section>
    </div>

  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./method.html">Method</a></li>
            <li><a href="./methodology.html">Methodology (detail)</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

</body>
</html>
```

---

## `methodology.html` — Marketing & editorial

*Deeper essay version of the method; linked from method.html.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Methodology — Odds Primer</title>
<meta name="description" content="How The Desk reads a market — market probability, model probability, edge, and the Pick / Pass / Avoid thresholds.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./method.html">Method</a></li>
          <li><a href="./methodology.html" aria-current="page">Methodology (detail)</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#analyze">What we analyze</a>
      <a href="#market">Market probability</a>
      <a href="#model">Model probability</a>
      <a href="#edge">The edge</a>
      <a href="#verdicts">Verdicts</a>
      <a href="#thresholds">Thresholds</a>
      <a href="#dont">What we don't do</a>
      <a href="#limits">Limitations</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Methodology · detail</div>
        <h1>How The Desk reads a market</h1>
        <p class="standfirst">Our goal is not to predict every result correctly. Our goal is to identify where the market price and the model disagree enough to deserve attention.</p>
        <p class="meta-line">Methodology · 8 min read · <a href="./method.html" style="color:var(--ink);">See the six-stage overview ↗</a></p>
        <div class="in-short"><span class="lbl">In short</span>The Desk compares market probability with model probability. When the gap is meaningful, we publish Pick, Pass, or Avoid. The verdict is an editorial read, not an instruction.</div>
        <section id="analyze">
          <h2>What we analyze</h2>
          <p>For each covered market, The Desk looks at:</p>
          <ul><li>The event being priced</li><li>The venue price</li><li>The implied probability of that price</li><li>The model probability</li><li>The gap between market and model</li><li>Relevant context around the event</li><li>Whether the gap is meaningful enough to publish a verdict</li></ul>
        </section>
        <section id="market">
          <h2>Market probability</h2>
          <p>Prediction markets express prices as probabilities.</p>
          <p>For example, a market price of 52% means the market is roughly pricing the outcome as a 52-in-100 event.</p>
          <p>Odds Primer translates market prices into plain-English probability terms so readers can understand what the market is saying.</p>
        </section>
        <section id="model">
          <h2>Model probability</h2>
          <p>Model probability is the independent estimate produced by The Desk.</p>
          <p>It may include structured inputs, market context, historical data, team information, and other relevant signals. The exact model may change over time as we improve the product.</p>
          <p>Model probability is not a guarantee. It is an estimate, and it can be wrong.</p>
        </section>
        <section id="edge">
          <h2>The edge</h2>
          <p>The edge is the difference between the model probability and the market-implied probability.</p>
          <ul><li>Model: 56%</li><li>Market: 52%</li><li>Edge: +4 percentage points</li></ul>
          <p>A positive edge means the model sees the outcome as more likely than the market currently prices it. It does not mean the outcome will happen.</p>
        </section>
        <section id="verdicts">
          <h2>Verdicts</h2>
          <p>Each market receives one editorial verdict.</p>
          <h3>Pick</h3>
          <p>The Desk sees the market as underpriced. This does not mean the outcome is guaranteed. It means the model and market disagree enough for the market to deserve closer inspection.</p>
          <h3>Pass</h3>
          <p>The model and market broadly agree. There may still be an interesting story, but we do not see a meaningful pricing gap.</p>
          <h3>Avoid</h3>
          <p>The price looks unattractive. This can happen when both sides of a market appear expensive, unclear, or poorly structured from a value perspective.</p>
        </section>
        <section id="thresholds">
          <h2>Thresholds</h2>
          <p>As a baseline, small gaps are usually Pass. Larger model-market gaps may become Pick or Avoid depending on liquidity, data quality, market structure, and sport.</p>
          <p>We generally look for a meaningful gap before publishing a Pick. Small differences between market and model are usually treated as Pass unless there is a strong reason to explain the discrepancy.</p>
        </section>
        <section id="dont">
          <h2>What we do not do</h2>
          <p>Odds Primer does not:</p>
          <ul><li>Take wagers</li><li>Hold reader funds</li><li>Execute trades</li><li>Offer personalized financial advice</li><li>Guarantee outcomes</li><li>Promise profit</li><li>Tell readers what to do with their money</li></ul>
          <p>The Desk does not know a reader’s location, finances, eligibility, or risk tolerance. A verdict is a read on the price, not a read on the reader.</p>
        </section>
        <section id="limits">
          <h2>Limitations</h2>
          <p>Markets move quickly. Prices can change after publication.</p>
          <p>Prices and model reads should show a last-updated timestamp on market pages, so readers can see how fresh a read is.</p>
          <p>Models can be wrong. Data can be incomplete. Sports outcomes are uncertain.</p>
          <p>Readers should always check the live source market before acting on anything they read.</p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./learn.html">Learn the basics</a><a href="./responsible-use.html">Responsible use</a><a href="./corrections.html">Corrections</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./method.html">Method</a></li>
            <li><a href="./methodology.html">Methodology (detail)</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `matches.html` — Marketing & editorial

*Match feed (verdict listings).*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Upcoming matches — Odds Primer</title>
<meta name="description" content="Eight fixtures, three groups, three Picks. Where today's prediction-market prices look slow, fair, or both-sides expensive.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <!-- ============ 1. MASTHEAD + NAV ============ -->
  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>

      <nav class="site-nav" aria-label="Primary">
              <ul>
                <li><a href="./home.html">Home</a></li>
                <li><a href="./outrights.html">Outright winners</a></li>
                <li><a href="./matches.html" aria-current="page">Upcoming matches</a></li>
              </ul>
            </nav>

      <span class="nav-meta">Updated 14:08 ET</span>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
        </ul>
      </details>

    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>Vol. 1 · World Cup 2026 · Matchday 2</span>
        <span class="live">Markets live</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
          <a href="./outrights.html">Winners</a>
          <a href="./matches.html" aria-current="page">Matches</a>
        </nav>
  </header>

  <main class="page">

    <!-- ============ HERO — MATCHES ============ -->
    <section class="hero" aria-labelledby="hero-title">
      <div class="h-eyebrow">Vol. 1 · Upcoming matches · Matchday 2</div>
      <h1 id="hero-title">Where today's prices look wrong.</h1>
      <p class="standfirst">
        Eight fixtures across three groups, priced in real time on Polymarket
        and Kalshi. Three Picks, four Passes, one rare two-way Avoid.
        Tap any row to read the case.
      </p>
    </section>

    <!-- ============ TODAY'S BOARD (ported from home-v2 body) ============ -->
    <section class="board-header" aria-labelledby="board-title">

      <!-- LEGEND -->
      <div class="legend">
        <span class="lbl">Verdict key</span>
        <div class="items">
          <div class="item pick">
            <div class="demo demo--pick"><div class="bar"></div><div class="glyph">▲</div></div>
            <div class="text"><span class="name">Pick</span><span class="what">the line is slow — clean value on the underpriced side</span></div>
          </div>
          <div class="item pass">
            <div class="demo demo--pass"><div class="bar"></div><div class="glyph">—</div></div>
            <div class="text"><span class="name">Pass</span><span class="what">the line is fair — no edge to play</span></div>
          </div>
          <div class="item avoid">
            <div class="demo demo--avoid"><div class="bar"></div><div class="glyph">✕</div></div>
            <div class="text"><span class="name">Avoid</span><span class="what">both sides overpriced — neither gives clean value</span></div>
          </div>
        </div>
        <div class="by">Color, glyph, and label all carry the call — any one is enough.</div>
      </div>

      <!-- GROUP F -->
      <div class="group-banner">
        <div class="gname">Group F<em>4 fixtures</em></div>
        <div class="grule"></div>
        <div class="gcount">2 picks · 1 pass · 1 avoid</div>
      </div>
      <div class="fixtures">
        <a class="fx is-pick" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">▲</span><span class="lab">Pick</span></div>
          <div class="match"><div class="teams">France <span class="vs">v</span> Mexico</div><div class="meta">MEX · Estadio Azteca · 21:00 local</div></div>
          <div class="thesis"><em>France look four points underpriced.</em> <span class="nm">Polymarket</span> is the slower of the two markets — that's where to read the price.</div>
          <div class="line"><span class="venue">Polymarket</span><span class="price">−180</span></div>
          <div class="action"><span class="when">Sat · 21:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <a class="fx is-pass" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">—</span><span class="lab">Pass</span></div>
          <div class="match"><div class="teams">Cameroon <span class="vs">v</span> Saudi Arabia</div><div class="meta">USA · MetLife · 18:00 local</div></div>
          <div class="thesis">Two markets within half a point — no edge. Skip the moneyline; total may have legs.</div>
          <div class="line"><span class="venue">Kalshi</span><span class="price">+135</span></div>
          <div class="action"><span class="when">Sat · 18:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <a class="fx is-pick" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">▲</span><span class="lab">Pick</span></div>
          <div class="match"><div class="teams">Cameroon <span class="vs">v</span> France</div><div class="meta">CAN · BMO Field · 15:00 local</div></div>
          <div class="thesis"><em>Total goals is mispriced.</em> Both teams need a result; over 2.5 has 6.5 points of room.</div>
          <div class="line"><span class="venue">Kalshi</span><span class="price">+108</span></div>
          <div class="action"><span class="when">Wed · 15:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <a class="fx is-avoid" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">✕</span><span class="lab">Avoid</span></div>
          <div class="match"><div class="teams">Mexico <span class="vs">v</span> Saudi Arabia</div><div class="meta">MEX · Guadalajara · 18:00 local</div></div>
          <div class="thesis">Mexico overpriced as the home favourite; Saudi Arabia priced as if they can't draw. Both sides cost too much.</div>
          <div class="line"><span class="venue">Polymarket</span><span class="price">−240</span></div>
          <div class="action"><span class="when">Tue · 18:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
      </div>

      <!-- GROUP A -->
      <div class="group-banner">
        <div class="gname">Group A<em>2 fixtures</em></div>
        <div class="grule"></div>
        <div class="gcount">1 pick · 1 pass</div>
      </div>
      <div class="fixtures">
        <a class="fx is-pick" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">▲</span><span class="lab">Pick</span></div>
          <div class="match"><div class="teams">Argentina <span class="vs">v</span> Canada</div><div class="meta">USA · Levi's Stadium · 19:00 local</div></div>
          <div class="thesis"><em>Canada +1.5 has clean value.</em> The handicap line hasn't tracked Canada's improved second half of 2025.</div>
          <div class="line"><span class="venue">Polymarket</span><span class="price">−108</span></div>
          <div class="action"><span class="when">Sun · 19:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <a class="fx is-pass" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">—</span><span class="lab">Pass</span></div>
          <div class="match"><div class="teams">Iceland <span class="vs">v</span> Tunisia</div><div class="meta">CAN · BC Place · 16:00 local</div></div>
          <div class="thesis">Pick'em with three-way uncertainty. The market is doing its job here — leave it.</div>
          <div class="line"><span class="venue">Kalshi</span><span class="price">+220</span></div>
          <div class="action"><span class="when">Sun · 16:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
      </div>

      <!-- GROUP B -->
      <div class="group-banner">
        <div class="gname">Group B<em>2 fixtures</em></div>
        <div class="grule"></div>
        <div class="gcount">2 passes</div>
      </div>
      <div class="fixtures">
        <a class="fx is-pass" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">—</span><span class="lab">Pass</span></div>
          <div class="match"><div class="teams">Brazil <span class="vs">v</span> Norway</div><div class="meta">USA · SoFi Stadium · 20:00 local</div></div>
          <div class="thesis">Both markets within 0.4 points of consensus. The line is doing its job.</div>
          <div class="line"><span class="venue">Polymarket</span><span class="price">−145</span></div>
          <div class="action"><span class="when">Mon · 20:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <a class="fx is-pass" href="./market-v2-newspaper-deck.html">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">—</span><span class="lab">Pass</span></div>
          <div class="match"><div class="teams">Egypt <span class="vs">v</span> Australia</div><div class="meta">USA · Hard Rock Stadium · 17:00 local</div></div>
          <div class="thesis">Tight three-way market; movement on draw odds is consistent across both venues. No edge to play.</div>
          <div class="line"><span class="venue">Kalshi</span><span class="price">+155</span></div>
          <div class="action"><span class="when">Tue · 17:00</span><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
      </div>
      <p class="affiliate-note">Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.</p>

      <div class="summary">
        <div class="v-pick"><div class="lbl">Picks today</div><div class="val">3</div><div class="sub">avg edge +3.4 points · highest conviction: France v Mexico</div></div>
        <div><div class="lbl">Passes</div><div class="val">4</div><div class="sub">markets within tolerance · check back at kickoff</div></div>
        <div><div class="lbl">Avoids</div><div class="val">1</div><div class="sub">both sides overpriced · the rare two-way no</div></div>
        <div><div class="lbl">Total fixtures</div><div class="val">8</div><div class="sub">across three groups · matchday 2 of 3</div></div>
      </div>
    </section>

  </main>

  <!-- ============ 8. NEWSLETTER ============ -->
  <section class="news" aria-labelledby="news-title">
    <div class="news-inner">
      <div>
        <h2 id="news-title">The matchday edition.</h2>
        <p>One short edition per matchday — what the prices moved, what's still off, what we read.</p>
      </div>
      <form onsubmit="event.preventDefault();">
        <label class="visually-hidden" for="news-email">Email address</label>
        <input id="news-email" type="email" placeholder="your.email@domain.com" required>
        <button type="submit">Subscribe</button>
        <div class="fine" style="flex-basis:100%;">No tips, no spam, one click to leave.</div>
      </form>
    </div>
  </section>

  <!-- ============ 9. FOOTER ============ -->
  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>

      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>


  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref">
        <input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span>
      </label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>
</body>
</html>
```

---

## `outrights.html` — Marketing & editorial

*Tournament outright winners.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outright winners — Odds Primer</title>
<meta name="description" content="Three outright reads on who wins the 2026 World Cup. Pick where the model has the field underpriced; Avoid where the favourite is priced thin.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <!-- ============ 1. MASTHEAD + NAV ============ -->
  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>

      <nav class="site-nav" aria-label="Primary">
              <ul>
                <li><a href="./home.html">Home</a></li>
                <li><a href="./outrights.html" aria-current="page">Outright winners</a></li>
                <li><a href="./matches.html">Upcoming matches</a></li>
              </ul>
            </nav>

      <span class="nav-meta">Updated 14:08 ET</span>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
        </ul>
      </details>

    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>Vol. 1 · World Cup 2026 · Matchday 2</span>
        <span class="live">Markets live</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
          <a href="./outrights.html" aria-current="page">Winners</a>
          <a href="./matches.html">Matches</a>
        </nav>
  </header>

  <main class="page">

    <!-- ============ HERO — OUTRIGHTS ============ -->
    <section class="hero" aria-labelledby="hero-title">
      <div class="h-eyebrow">Vol. 1 · Outright winners · World Cup 2026</div>
      <h1 id="hero-title">Three reads on who lifts the trophy.</h1>
      <p class="standfirst">
        Where the model and the market disagree most on the World Cup 2026
        winner. Pick where our model reads the line as slow; Avoid where
        the favourite is priced thin. The outright engine is <em>v0.1</em>.
      </p>
    </section>

    <!-- ============ OUTRIGHT PICKS ============ -->
    <section class="outright" id="outrights" aria-labelledby="o-title">

      <div class="o-section-head" style="margin-top:0;">
        <div class="o-eyebrow">Outright picks · World Cup 2026 winner</div>
        <h2 class="op-h2" id="o-title" style="font-family:var(--font-serif); font-weight:600; font-size:clamp(22px,2.8vw,28px); letter-spacing:-0.005em; color:var(--ink); margin:0 0 10px;">Where the model and the market disagree</h2>
        <p class="o-sub">
          Three outright reads. The Desk is in v0.1 on outright winners
          <span class="dag">†</span> — we show the model and the market side
          by side and let you read the gap.
        </p>
      </div>

      <div class="o-picks">

        <a class="opick is-pick" href="#">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">▲</span><span class="lab">Pick</span></div>
          <div class="who">
            <div class="team">France</div>
            <div class="meta">Group D · holders of form, priced like outsiders</div>
          </div>
          <div class="thesis">
            <em>The market has them four spots back in the field.</em>
            Our read on form and draw says the gap should be smaller.
          </div>
          <div class="reads">
            <span class="read-pair"><span class="k">model</span><span class="v">21%</span></span>
            <span class="read-pair"><span class="k">market</span><span class="v">16%</span></span>
            <span class="edge">+5pp</span>
          </div>
          <div class="line">
            <span class="venue">Polymarket</span>
            <span class="price">16¢</span>
          </div>
          <div class="action"><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <p class="affiliate-note">Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.</p>

        <a class="opick is-pick" href="#">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">▲</span><span class="lab">Pick</span></div>
          <div class="who">
            <div class="team">Argentina</div>
            <div class="meta">Group A · defending champions, Kalshi runs slow</div>
          </div>
          <div class="thesis">
            <em>The slower of the two venues.</em> Polymarket has them
            22¢; Kalshi sits at 18¢ — the read is the venue, not the team.
          </div>
          <div class="reads">
            <span class="read-pair"><span class="k">model</span><span class="v">22%</span></span>
            <span class="read-pair"><span class="k">market</span><span class="v">18%</span></span>
            <span class="edge">+4pp</span>
          </div>
          <div class="line">
            <span class="venue">Kalshi</span>
            <span class="price">18¢</span>
          </div>
          <div class="action"><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <p class="affiliate-note">Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.</p>

        <a class="opick is-avoid" href="#">
          <span class="bar"></span>
          <div class="verdict-cell"><span class="gly">✕</span><span class="lab">Avoid</span></div>
          <div class="who">
            <div class="team">Brazil</div>
            <div class="meta">Group B · favourite by clear daylight</div>
          </div>
          <div class="thesis">
            Tournament favourite at 22¢ both venues; our read has them
            closer to 18%. The model says the favourite is priced thin.
          </div>
          <div class="reads">
            <span class="read-pair"><span class="k">model</span><span class="v">18%</span></span>
            <span class="read-pair"><span class="k">market</span><span class="v">22%</span></span>
            <span class="edge edge-neg">−4pp</span>
          </div>
          <div class="line">
            <span class="venue">Polymarket</span>
            <span class="price">22¢</span>
          </div>
          <div class="action"><span class="open">Read <span class="arr">↗</span></span></div>
        </a>
        <p class="affiliate-note">Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.</p>

      </div>

      <div class="o-field-head">
        <div class="o-eyebrow">Where the field stands · Implied probability · Polymarket consensus, Kalshi best</div>
        <a class="o-source" href="#"
           aria-label="View the Outright Winner market source on Polymarket">
          View source on Polymarket <span class="arr">↗</span>
        </a>
      </div>

      <div class="o-bar-wrap">
        <div class="o-bar" role="img"
             aria-label="Outright winner implied probability: Brazil 22%, Argentina 18%, France 16%, England 12%, Spain 11%, Field 21%">
          <div class="seg-lead" style="width:22%"></div>
          <div class="seg-2"    style="width:18%"></div>
          <div class="seg-3"    style="width:16%"></div>
          <div class="seg-4"    style="width:12%"></div>
          <div class="seg-5"    style="width:11%"></div>
          <div class="seg-6"    style="width:21%"></div>
        </div>
        <div class="o-legend">
          <span class="pill lead"><span class="swatch" style="background:var(--flame)"></span>Brazil <span class="num">22%</span></span>
          <span class="pill"><span class="swatch" style="background:var(--ink-soft)"></span>Argentina <span class="num">18%</span></span>
          <span class="pill"><span class="swatch" style="background:var(--graphite)"></span>France <span class="num">16%</span></span>
          <span class="pill"><span class="swatch" style="background:#B89968"></span>England <span class="num">12%</span></span>
          <span class="pill"><span class="swatch" style="background:var(--paper-deep)"></span>Spain <span class="num">11%</span></span>
          <span class="pill"><span class="swatch" style="background:var(--paper-warm); border:1px solid var(--rule)"></span>Field <span class="num">21%</span></span>
        </div>
      </div>

      <div class="o-cards" role="list" aria-label="Outright winner standings">
        <a class="o-card is-lead" role="listitem" href="#"><span class="name">Brazil</span><span class="pct">22%</span><span class="src">Polymarket best</span></a>
        <a class="o-card"         role="listitem" href="#"><span class="name">Argentina</span><span class="pct">18%</span><span class="src">Kalshi best</span></a>
        <a class="o-card"         role="listitem" href="#"><span class="name">France</span><span class="pct">16%</span><span class="src">Polymarket best</span></a>
        <a class="o-card"         role="listitem" href="#"><span class="name">England</span><span class="pct">12%</span><span class="src">Polymarket best</span></a>
        <a class="o-card"         role="listitem" href="#"><span class="name">Spain</span><span class="pct">11%</span><span class="src">Kalshi best</span></a>
        <a class="o-card"         role="listitem" href="#"><span class="name">Field</span><span class="pct">21%</span><span class="src">28 other teams</span></a>
      </div>

      <p class="o-foot">
        <span class="dag">†</span> The outright model is in v0.1 — calibrated on
        WC-22 backtests, in production for v1.2. Until then, treat outright
        picks as editorial reads, not verdict-engine output.
      </p>
    </section>

  </main>

  <!-- ============ 8. NEWSLETTER ============ -->
  <section class="news" aria-labelledby="news-title">
    <div class="news-inner">
      <div>
        <h2 id="news-title">The matchday edition.</h2>
        <p>One short edition per matchday — what the prices moved, what's still off, what we read.</p>
      </div>
      <form onsubmit="event.preventDefault();">
        <label class="visually-hidden" for="news-email">Email address</label>
        <input id="news-email" type="email" placeholder="your.email@domain.com" required>
        <button type="submit">Subscribe</button>
        <div class="fine" style="flex-basis:100%;">No tips, no spam, one click to leave.</div>
      </form>
    </div>
  </section>

  <!-- ============ 9. FOOTER ============ -->
  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>

      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>


  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref">
        <input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span>
      </label>
      <label class="cb-pref">
        <input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span>
      </label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>
</body>
</html>
```

---

## `learn.html` — Marketing & editorial

*Beginner education.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prediction markets, explained simply — Odds Primer</title>
<meta name="description" content="Prediction markets, implied probability, the edge, and what Pick / Pass / Avoid mean. A plain-English primer.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#prediction-market">Prediction market</a>
      <a href="#not-sportsbooks">Not sportsbooks</a>
      <a href="#implied">Implied probability</a>
      <a href="#edge">The edge</a>
      <a href="#pick">Pick</a>
      <a href="#pass">Pass</a>
      <a href="#avoid">Avoid</a>
      <a href="#view-source">View source</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Learn the basics</div>
        <h1>Prediction markets, explained simply</h1>
        <p class="standfirst">Prediction markets price the likelihood of future events. Odds Primer helps readers understand those prices.</p>
        <p class="meta-line">Learn · 6 min read</p>
        <section id="prediction-market">
          <h2>What is a prediction market?</h2>
          <p>A prediction market lets people express a view on whether an event will happen.</p>
          <p>For example:</p>
          <div class="callout">"France to win the match"<br>If the market price is 52%, the market is roughly saying France has a 52-in-100 chance.</div>
          <p>Venues such as Polymarket and Kalshi run prediction markets on sports and other events. Odds Primer covers their prices. We do not operate these venues and we do not endorse any venue.</p>
        </section>
        <section id="not-sportsbooks">
          <h2>Prediction markets are not sportsbooks</h2>
          <p>A sportsbook sets the odds and takes the other side of your wager. A prediction market is a venue where participants trade contracts with each other, and the price moves with supply and demand.</p>
          <p>The practical difference for a reader: on a prediction market, the price itself is the crowd’s probability estimate. That is the number Odds Primer reads, compares with The Desk’s model, and explains.</p>
          <p>Odds Primer is neither a sportsbook nor a prediction market. We are an editorial site that explains the prices.</p>
        </section>
        <section id="implied">
          <h2>What is implied probability?</h2>
          <p>Implied probability is the chance suggested by a market price.</p>
          <p>A 52% price means the market currently believes the outcome is around 52% likely.</p>
          <p>It does not mean the outcome will happen.</p>
        </section>
        <section id="edge">
          <h2>What is an edge?</h2>
          <p>An edge is the gap between the market price and an independent estimate — in our case, The Desk’s model probability.</p>
          <p>Example:</p>
          <ul><li>Market: 52%</li><li>Model: 56%</li><li>Edge: +4 percentage points</li></ul>
          <p>That means the model sees the outcome as more likely than the market price suggests.</p>
          <div class="callout"><strong>Note on risk.</strong> An edge is not a guarantee. It only means the model and market disagree. The model can be wrong, prices can move, and outcomes remain uncertain.</div>
        </section>
        <section id="pick">
          <h2>What does Pick mean?</h2>
          <p>Pick means The Desk sees the market as underpriced.</p>
          <p>It does not mean the outcome is certain. It means the price deserves closer inspection.</p>
        </section>
        <section id="pass">
          <h2>What does Pass mean?</h2>
          <p>Pass means The Desk’s model and the market broadly agree.</p>
          <p>There may be no meaningful pricing gap.</p>
        </section>
        <section id="avoid">
          <h2>What does Avoid mean?</h2>
          <p>Avoid means the price looks unattractive.</p>
          <p>Sometimes the event is interesting, but the market price is not.</p>
        </section>
        <section id="view-source">
          <h2>What is "View source"?</h2>
          <p>Odds Primer does not take bets or execute trades.</p>
          <p>View source sends readers to the third-party venue where the live market price appears. Always check the live price, rules, fees, eligibility, and local laws before making any decision elsewhere.</p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./methodology.html">Methodology</a><a href="./responsible-use.html">Responsible use</a><a href="./affiliate-disclosure.html">Affiliate disclosure</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `about.html` — Marketing & editorial

*Masthead / who's behind it.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>About — Odds Primer</title>
<meta name="description" content="Odds Primer is an independent editorial desk for sports prediction markets. The Desk publishes Pick, Pass, or Avoid verdicts.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#intro">What we do</a>
      <a href="#desk">The Desk</a>
      <a href="#editorial">Editorial position</a>
      <a href="#contact">Contact</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">About</div>
        <h1>About Odds Primer</h1>
        <p class="standfirst">An independent editorial desk for sports prediction markets. We read market prices, compare them with The Desk, and explain where the price looks fair, mispriced, or unattractive.</p>
        <p class="meta-line">Editorial · independent · 4 min read</p>
        <section id="intro">
          <h2>What we do</h2>
          <p>Odds Primer is an independent editorial desk for sports prediction markets.</p>
          <p>We read market prices from venues such as Polymarket and Kalshi, compare them with our AI verdict engine, and explain where the price appears fair, mispriced, or unattractive.</p>
          <p>For each covered market, we publish one editorial verdict:</p>
          <ul><li><strong>Pick</strong> — The Desk sees the market as underpriced.</li><li><strong>Pass</strong> — The Desk and the market broadly agree.</li><li><strong>Avoid</strong> — the price looks unattractive, even if the event is interesting.</li></ul>
          <p>We do not take wagers, hold reader funds, execute trades, or act as a broker. We do not tell readers what to do with their money. Our job is to explain the market, the model read, and the gap between them.</p>
          <p>New to prediction markets? Start with <a href="./learn.html">Learn the basics</a>.</p>
        </section>
        <section id="desk">
          <h2>The Desk</h2>
          <p>The Desk is our AI verdict engine.</p>
          <p>It compares market probability with model probability, highlights meaningful gaps, and turns that analysis into plain-English market reads.</p>
          <p>Every read should answer five questions:</p>
          <ol><li>What event is being analyzed?</li><li>What does the market currently believe?</li><li>What does The Desk’s model believe?</li><li>Is there a meaningful edge?</li><li>What should the reader understand before acting elsewhere?</li></ol>
          <p>The full method is on the <a href="./methodology.html">Methodology</a> page.</p>
        </section>
        <section id="editorial">
          <h2>Editorial position</h2>
          <p>Odds Primer is closer to a sports data column than a sportsbook.</p>
          <p>We avoid hype, guarantees, and betting language. We publish reasoning, not promises.</p>
          <p>Affiliate relationships, if any, do not influence The Desk’s verdicts. How we earn is set out in full on the <a href="./affiliate-disclosure.html">Affiliate disclosure</a> page.</p>
          <p>Before acting on anything you read here, see <a href="./responsible-use.html">Responsible use</a>. If you spot an error, our <a href="./corrections.html">Corrections policy</a> explains how we handle it.</p>
        </section>
        <section id="contact">
          <h2>Contact</h2>
          <p>For general questions: <code>desk@oddsprimer.com</code></p>
          <p>For corrections: <code>corrections@oddsprimer.com</code></p>
          <p>For privacy requests: <code>privacy@oddsprimer.com</code></p>
          <p>For legal or affiliate matters: <code>legal@oddsprimer.com</code></p>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `corrections.html` — Trust & compliance

*Editorial corrections policy.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Corrections — Odds Primer</title>
<meta name="description" content="How Odds Primer handles corrections. We correct meaningful factual errors and note the change on the affected page.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#do">What we correct</a>
      <a href="#dont">What we don't</a>
      <a href="#report">Report an error</a>
      <a href="#updates">Updates</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Corrections</div>
        <h1>Corrections policy</h1>
        <p class="standfirst">We aim to publish clear, accurate, and transparent market analysis. Prediction markets move quickly, and prices may change after publication.</p>
        <p class="meta-line">Corrections · 2 min read</p>
        <section id="do">
          <h2>What we correct</h2>
          <p>We correct meaningful factual errors, including:</p>
          <ul><li>Incorrect market prices at the time of publication</li><li>Incorrect venue attribution</li><li>Incorrect team, event, or fixture details</li><li>Incorrect probability calculations</li><li>Incorrect explanation of market rules</li><li>Broken or misleading source links</li></ul>
        </section>
        <section id="dont">
          <h2>What we do not usually correct</h2>
          <p>We do not usually correct:</p>
          <ul><li>Price changes after publication</li><li>Model reads that later turn out to be wrong</li><li>Market outcomes that go against a Pick</li><li>Differences of opinion about interpretation</li></ul>
          <p>A price movement after publication is not automatically an error.</p>
        </section>
        <section id="report">
          <h2>How to report an error</h2>
          <p>Email <code>corrections@oddsprimer.com</code>. Please include:</p>
          <ul><li>The page URL</li><li>The issue</li><li>The correct information, if known</li><li>A source, if available</li></ul>
        </section>
        <section id="updates">
          <h2>Updates</h2>
          <p>When a material correction is made, we may add a note to the page explaining what changed.</p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./methodology.html">Methodology</a><a href="./terms.html">Terms of use</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `responsible-use.html` — Trust & compliance

*Responsible-use copy.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Responsible use — Odds Primer</title>
<meta name="description" content="Prediction-market trading involves risk. Odds Primer content is for informational purposes — a Pick is not an instruction.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#risk">Markets involve risk</a>
      <a href="#not-advice">Our content is not advice</a>
      <a href="#before">Before acting elsewhere</a>
      <a href="#if-not-fun">If markets stop being fun</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Responsible use</div>
        <h1>Responsible use</h1>
        <p class="standfirst">Odds Primer explains prediction-market prices and model disagreement. We do not take wagers, execute trades, hold funds, or provide personalized financial advice.</p>
        <p class="meta-line">Responsible use · 3 min read</p>
        <section id="risk">
          <h2>Prediction markets involve risk</h2>
          <p>Prediction-market prices move quickly. Outcomes are uncertain. You can lose money.</p>
          <p>Only use third-party venues if you understand the risks, meet the venue’s eligibility rules, and are legally allowed to participate in your location.</p>
        </section>
        <section id="not-advice">
          <h2>Our content is not advice</h2>
          <p>Odds Primer content is for informational and editorial purposes only.</p>
          <div class="callout">A <strong>Pick</strong> is not an instruction.<br>A <strong>Pass</strong> is not a prohibition.<br>An <strong>Avoid</strong> is not a guarantee that a market will perform badly.</div>
          <p>Each verdict is a market read, not personal advice.</p>
        </section>
        <section id="before">
          <h2>Before acting elsewhere</h2>
          <p>Before using any third-party venue, check:</p>
          <ul><li>The live market price</li><li>The venue’s rules</li><li>The market resolution criteria</li><li>Fees</li><li>Liquidity</li><li>Local laws</li><li>Your own risk tolerance</li></ul>
        </section>
        <section id="if-not-fun">
          <h2>If markets stop being fun</h2>
          <p>Do not use prediction markets if they create financial stress, emotional pressure, or compulsive behavior.</p>
          <p>Take breaks. Set limits. Do not chase losses.</p>
          <p>If you feel you may have a gambling or trading problem, seek support from a qualified professional or a responsible gambling support organization in your country.</p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./methodology.html">Methodology</a><a href="./learn.html">Learn the basics</a><a href="./affiliate-disclosure.html">Affiliate disclosure</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `affiliate-disclosure.html` — Trust & compliance

*Affiliate disclosure.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affiliate disclosure — Odds Primer</title>
<meta name="description" content="Odds Primer may earn referral revenue from partner venues. Editorial verdicts are independent of that revenue.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#intro">How we earn</a>
      <a href="#independence">Editorial independence</a>
      <a href="#venues">Third-party venues</a>
      <a href="#risk">Risk</a>
      <a href="#questions">Questions</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Affiliate disclosure</div>
        <h1>Affiliate disclosure</h1>
        <p class="standfirst">Odds Primer may earn revenue from some outbound links to third-party venues. Our editorial verdicts are independent of that revenue.</p>
        <p class="meta-line">Affiliate disclosure · 2 min read</p>
        <section id="intro">
          <h2>How we earn</h2>
          <p>Odds Primer may earn revenue from some outbound links to third-party venues.</p>
          <p>When a reader clicks a "View source" or similar link and later signs up, trades, or uses a partner venue, that venue or affiliate partner may share a referral fee or portion of its revenue with Odds Primer.</p>
        </section>
        <section id="independence">
          <h2>Editorial independence</h2>
          <p>Affiliate revenue does not determine our verdicts.</p>
          <p>Our Pick / Pass / Avoid calls are based on the market price, The Desk’s model read, and editorial analysis. We do not change verdicts because of an affiliate relationship.</p>
        </section>
        <section id="venues">
          <h2>Third-party venues</h2>
          <p>Odds Primer does not operate Polymarket, Kalshi, sportsbooks, exchanges, or any other trading venue.</p>
          <p>When you leave Odds Primer, you are subject to the rules, terms, fees, eligibility requirements, and risk disclosures of the third-party venue you visit.</p>
        </section>
        <section id="risk">
          <h2>Risk</h2>
          <p>Prediction-market trading involves risk. You can lose money.</p>
          <p>Check your local laws and venue eligibility before acting on any market. See <a href="./responsible-use.html">Responsible use</a>.</p>
        </section>
        <section id="questions">
          <h2>Questions</h2>
          <p>For affiliate or commercial questions, contact <code>legal@oddsprimer.com</code>.</p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./methodology.html">Methodology</a><a href="./responsible-use.html">Responsible use</a><a href="./terms.html">Terms of use</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `privacy.html` — Legal

*Privacy policy.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy policy — Odds Primer</title>
<meta name="description" content="Odds Primer privacy policy — what we collect, the legal basis, cookies and consent, third-party venues, and your rights.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#operator">Operator</a>
      <a href="#collect">What we collect</a>
      <a href="#why">Why we collect</a>
      <a href="#basis">Legal basis</a>
      <a href="#cookies">Cookies and consent</a>
      <a href="#affiliate">Affiliate measurement</a>
      <a href="#venues">Third-party venues</a>
      <a href="#providers">Service providers</a>
      <a href="#transfers">International transfers</a>
      <a href="#children">Children</a>
      <a href="#retention">Retention</a>
      <a href="#requests">Privacy requests</a>
      <a href="#changes">Changes</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Privacy</div>
        <h1>Privacy policy</h1>
        <p class="standfirst">What information we collect, why we collect it, the legal basis for it, and how to contact us. Last updated 13 May 2026.</p>
        <p class="meta-line">Privacy · 8 min read</p>
        <section id="operator">
          <h2>Operator — who we are</h2>
          <p>Odds Primer is an independent editorial website covering sports prediction markets.</p>
          <p>We are not a registered company, broker, or sportsbook. For privacy questions, contact <code>privacy@oddsprimer.com</code>.</p>
        </section>
        <section id="collect">
          <h2>Information we may collect</h2>
          <p>We may collect:</p>
          <ul><li>Website usage data, such as page views and clicks</li><li>Device and browser information</li><li>Approximate location derived from IP address</li><li>Cookie and tracking preferences</li><li>Outbound click data, including clicks to third-party venues</li></ul>
        </section>
        <section id="why">
          <h2>Why we collect information</h2>
          <p>We use this information to:</p>
          <ul><li>Understand how readers use the site</li><li>Improve the product and editorial experience</li><li>Measure outbound clicks to third-party venues</li><li>Maintain site security</li><li>Comply with legal obligations</li></ul>
        </section>
        <section id="basis">
          <h2>Legal basis</h2>
          <p>Where data protection law applies, we rely on legitimate interests for analytics, outbound-click measurement, and site security, and on consent for non-essential cookies and similar technologies.</p>
          <p>Where we rely on consent, you can withdraw it at any time through the cookie settings link in the footer.</p>
        </section>
        <section id="cookies">
          <h2>Cookies and consent</h2>
          <p>Essential cookies are always on — they are needed for the site to work and to remember your cookie choices.</p>
          <p>Non-essential cookies and similar technologies, including analytics and affiliate measurement, only run after you consent.</p>
          <p>You can change your preferences at any time through the cookie settings link in the footer. Full detail is on the <a href="./cookies.html">Cookie policy</a> page.</p>
        </section>
        <section id="affiliate">
          <h2>Affiliate measurement</h2>
          <p>Some outbound links may include referral or affiliate tracking.</p>
          <p>This helps us understand whether readers visit third-party venues from Odds Primer and may allow us to earn referral revenue.</p>
          <p>Affiliate tracking does not determine our editorial verdicts. See the <a href="./affiliate-disclosure.html">Affiliate disclosure</a> for more.</p>
        </section>
        <section id="venues">
          <h2>Third-party venues</h2>
          <p>Odds Primer links to third-party venues such as Polymarket and Kalshi.</p>
          <p>Once you leave Odds Primer, those venues may collect and process your data under their own privacy policies, which are separate from ours.</p>
          <p>Review their policies before using those services.</p>
        </section>
        <section id="providers">
          <h2>Service providers</h2>
          <p>We may share limited information with service providers that help operate the site, such as hosting providers, analytics providers, and affiliate tracking providers.</p>
          <p>We do not sell personal information.</p>
        </section>
        <section id="transfers">
          <h2>International transfers</h2>
          <p>Service providers we use may process data outside your country.</p>
          <p>Where required, we take steps intended to ensure appropriate safeguards for that data.</p>
        </section>
        <section id="children">
          <h2>Children</h2>
          <p>Odds Primer is not directed at children.</p>
          <p>We do not knowingly collect data from anyone under the age required to use prediction markets in their location.</p>
        </section>
        <section id="retention">
          <h2>Data retention</h2>
          <p>We keep personal information only as long as needed for the purposes described in this policy, unless a longer period is required by law.</p>
        </section>
        <section id="requests">
          <h2>Privacy requests</h2>
          <p>Depending on your location, you may have rights to:</p>
          <ul><li>Access your data</li><li>Correct your data</li><li>Delete your data</li><li>Object to certain processing</li><li>Withdraw consent</li><li>Request a copy of your data</li></ul>
          <p>To make a request, contact <code>privacy@oddsprimer.com</code>.</p>
        </section>
        <section id="changes">
          <h2>Changes to this policy</h2>
          <p>We may update this policy from time to time. The latest version will always appear on this page.</p>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `terms.html` — Legal

*Terms of use.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terms of use — Odds Primer</title>
<meta name="description" content="By using Odds Primer you agree to these terms. We are an editorial publication, not a broker, sportsbook, or financial adviser.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#is">What Odds Primer is</a>
      <a href="#not">What we are not</a>
      <a href="#guarantees">No guarantees</a>
      <a href="#reader">Reader responsibility</a>
      <a href="#third">Third-party links</a>
      <a href="#affiliate">Affiliate</a>
      <a href="#ip">Intellectual property</a>
      <a href="#corrections">Corrections</a>
      <a href="#liability">Liability</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Terms</div>
        <h1>Terms of use</h1>
        <p class="standfirst">By using Odds Primer, you agree to these terms. If you do not agree, do not use the site. Last updated 13 May 2026.</p>
        <p class="meta-line">Terms · 6 min read</p>
        <section id="is">
          <h2>What Odds Primer is</h2>
          <p>Odds Primer is an editorial website covering sports prediction markets.</p>
          <p>We publish market analysis, price comparisons, model probabilities, and Pick / Pass / Avoid verdicts.</p>
          <p>Odds Primer content is general editorial information only.</p>
        </section>
        <section id="not">
          <h2>What Odds Primer is not</h2>
          <p>Odds Primer is not:</p>
          <ul><li>A sportsbook</li><li>A prediction market</li><li>A broker</li><li>A financial adviser</li><li>A betting adviser</li><li>A trading venue</li><li>A custodian of funds</li></ul>
          <p>We do not take wagers, hold funds, execute trades, or provide personalized financial advice.</p>
        </section>
        <section id="guarantees">
          <h2>No guarantees</h2>
          <p>Our content may be wrong, incomplete, delayed, or outdated.</p>
          <p>Market prices may be delayed, incomplete, or change after publication.</p>
          <p>We do not guarantee accuracy, profitability, availability, or any specific outcome.</p>
        </section>
        <section id="reader">
          <h2>Reader responsibility</h2>
          <p>You are responsible for your own decisions.</p>
          <p>You are responsible for checking whether any third-party venue is legal and available where you live.</p>
          <p>We do not know your personal circumstances, financial situation, jurisdiction, eligibility, or risk tolerance.</p>
          <p>Before acting on any market, you should check the live source price, the venue rules, the market resolution criteria, fees, eligibility requirements, local laws, and your own risk tolerance.</p>
        </section>
        <section id="third">
          <h2>Third-party links</h2>
          <p>Odds Primer links to third-party websites and venues.</p>
          <p>We do not control those websites. Their terms, rules, privacy policies, and risk disclosures apply when you visit them.</p>
        </section>
        <section id="affiliate">
          <h2>Affiliate relationships</h2>
          <p>Odds Primer may earn referral revenue from some outbound links.</p>
          <p>Affiliate revenue does not determine our editorial verdicts. See our <a href="./affiliate-disclosure.html">Affiliate disclosure</a> for more information.</p>
        </section>
        <section id="ip">
          <h2>Intellectual property</h2>
          <p>All Odds Primer content, branding, design, and editorial material belong to Odds Primer unless otherwise stated.</p>
          <p>You may link to our pages. You may not copy, republish, scrape, or commercially reuse our content without permission.</p>
        </section>
        <section id="corrections">
          <h2>Corrections</h2>
          <p>We aim to correct meaningful factual errors. To report an error, contact <code>corrections@oddsprimer.com</code> or see our <a href="./corrections.html">Corrections policy</a>.</p>
        </section>
        <section id="liability">
          <h2>Limitation of liability</h2>
          <p>Use Odds Primer at your own risk.</p>
          <p>To the maximum extent permitted by law, Odds Primer is not liable for losses, damages, missed opportunities, trading losses, betting losses, or decisions made based on site content.</p>
          <p>For legal questions: <code>legal@oddsprimer.com</code></p>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `cookies.html` — Legal

*Cookie policy.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cookie policy — Odds Primer</title>
<meta name="description" content="How Odds Primer uses cookies — essential, analytics, and affiliate measurement.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <article class="content">
      <aside class="content-rail" aria-label="On this page">
      <span class="rail-lbl">On this page</span>
      <a href="#what">What cookies are</a>
      <a href="#types">Types</a>
      <a href="#choice">Your choice</a>
      <a href="#third">Third-party</a>
      <a href="#contact">Contact</a>
    </aside>
    <div class="content-prose">
        <div class="page-eyebrow">Cookies</div>
        <h1>Cookie policy</h1>
        <p class="standfirst">Odds Primer uses cookies and similar technologies to operate the site, understand usage, and measure outbound links. Last updated 13 May 2026.</p>
        <p class="meta-line">Cookie policy · 3 min read</p>
        <section id="what">
          <h2>What cookies are</h2>
          <p>Cookies are small files placed on your device when you visit a website.</p>
          <p>Similar technologies include pixels, scripts, local storage, and link tracking.</p>
        </section>
        <section id="types">
          <h2>Types of cookies we use</h2>
          <h3>Essential cookies</h3>
          <p>These are needed for the site to work properly. They may include cookies used for security, page functionality, and remembering cookie preferences.</p>
          <h3>Analytics cookies</h3>
          <p>These help us understand how readers use the site — which pages are visited, which links are clicked, and how readers move through the site.</p>
          <h3>Affiliate measurement</h3>
          <p>Some outbound links may include referral tracking. This helps us understand whether readers visit partner venues from Odds Primer and may allow us to earn referral revenue.</p>
        </section>
        <section id="choice">
          <h2>Your choice</h2>
          <p>Where required, non-essential cookies and similar technologies will only run after you consent.</p>
          <p>You can change your preferences at any time through the cookie settings link in the footer.</p>
        </section>
        <section id="third">
          <h2>Third-party cookies</h2>
          <p>Some tools used by Odds Primer may set third-party cookies.</p>
          <p>These providers may include analytics, hosting, or affiliate measurement services.</p>
        </section>
        <section id="contact">
          <h2>Contact</h2>
          <p>For privacy or cookie questions: <code>privacy@oddsprimer.com</code></p>
          <div class="related"><div class="rl-lbl">Related</div><a href="./privacy.html">Privacy policy</a><a href="./affiliate-disclosure.html">Affiliate disclosure</a></div>
        </section>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `404.html` — Utility

*Error page.*

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page not found — Odds Primer</title>
<meta name="description" content="The page you're looking for isn't here. Find your way back to Odds Primer's verdicts, methodology, and learn pages.">
<link rel="stylesheet" href="./colors_and_type.css">
<!-- styles stripped for bundle; see colors_and_type.css at the end -->
</head>
<body>

  <header class="site-masthead">
    <div class="inner">
      <a class="brand-lock" href="./home.html" aria-label="Odds Primer — the AI sports desk for market edge">
        <span class="wm-row">
          <svg viewBox="0 0 38 34" width="38" height="34" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
        </span>
        <span class="tag">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <ul>
          <li><a href="./home.html">Home</a></li>
          <li><a href="./outrights.html">Outright winners</a></li>
          <li><a href="./matches.html">Upcoming matches</a></li>
        </ul>
      </nav>
      <details class="burger">
        <summary class="burger-btn" aria-label="More links">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor"/>
            <rect y="5"  width="16" height="1.5" fill="currentColor"/>
            <rect y="10" width="16" height="1.5" fill="currentColor"/>
          </svg>
        </summary>
        <ul class="burger-menu">
          <li><a href="./about.html">About</a></li>
          <li><a href="./methodology.html">Methodology</a></li>
          <li><a href="./learn.html">Learn the basics</a></li>
          <li><a href="./corrections.html">Corrections</a></li>
        </ul>
      </details>
    </div>
    <div class="edition-strip">
      <div class="inner">
        <span>World Cup 2026 · Matchday 2</span>
        <span>Updated 13 May 2026</span>
      </div>
    </div>
    <nav class="pill-nav" aria-label="Primary (mobile)">
      <a href="./outrights.html">Winners</a>
      <a href="./matches.html">Matches</a>
    </nav>
  </header>

  <main class="page">
    <section class="notfound">
      <span class="code">Error 404</span>
      <h1>Page not found</h1>
      <p>The page you're looking for isn't here. It may have moved, or the link may be broken.</p>
      <div class="links">
        <a class="primary" href="./home.html">Home</a>
        <a href="./outrights.html">Outright winners</a>
        <a href="./matches.html">Upcoming matches</a>
        <a href="./learn.html">Learn the basics</a>
        <a href="./methodology.html">Methodology</a>
      </div>
      <p class="fine">
        If you followed a link on Odds Primer to get here, tell us at
        <a href="mailto:corrections@oddsprimer.com" style="color:var(--ink);">corrections@oddsprimer.com</a>
        so we can fix it.
      </p>
    </section>
  </main>

  <footer class="site-footer">
    <div class="foot-inner">
      <div class="foot-grid">
        <div class="foot-brand">
          <svg viewBox="0 0 38 34" width="44" height="40" aria-hidden="true">
            <line x1="0" y1="34" x2="38" y2="34" stroke="#0E2240" stroke-width="1"/>
            <rect x="2"  y="24" width="6" height="10" fill="#0E2240"/>
            <rect x="11" y="18" width="6" height="16" fill="#0E2240"/>
            <rect x="20" y="6"  width="6" height="28" fill="#D9461C"/>
            <rect x="29" y="20" width="6" height="14" fill="#0E2240"/>
          </svg>
          <span class="wm">Odds Primer</span>
          <span class="pub">The <span class="flame">AI</span> sports desk for <span class="flame">market edge</span>.</span>
        </div>
        <div class="foot-col">
          <h4>Editorial</h4>
          <ul>
            <li><a href="./home.html">Home</a></li>
            <li><a href="./outrights.html">Outright winners</a></li>
            <li><a href="./matches.html">Upcoming matches</a></li>
            <li><a href="./learn.html">Learn the basics</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>About</h4>
          <ul>
            <li><a href="./about.html">About Odds Primer</a></li>
            <li><a href="./methodology.html">Methodology</a></li>
            <li><a href="./corrections.html">Corrections policy</a></li>
            <li><a href="mailto:desk@oddsprimer.com">Contact the Desk</a></li>
          </ul>
        </div>
        <div class="foot-col">
          <h4>Legal</h4>
          <ul>
            <li><a href="./privacy.html">Privacy</a></li>
            <li><a href="./terms.html">Terms of use</a></li>
            <li><a href="./affiliate-disclosure.html">Affiliate disclosure</a></li>
            <li><a href="./responsible-use.html">Responsible use</a></li>
            <li><a href="./cookies.html">Cookie policy</a></li>
            <li><button type="button" onclick="document.getElementById('cookie-banner').hidden=false; document.getElementById('cookie-banner').classList.add('is-managing');">Cookie settings</button></li>
          </ul>
        </div>
      </div>
      <p class="foot-discl">
        <span class="dag">†</span> Odds Primer is editorial information only. We are not a sportsbook, broker, exchange,
        financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice.
        Prediction-market participation involves risk and may not be available in your location.
      </p>
      <p class="foot-affiliate">
        Some outbound source links may be affiliate links. Affiliate relationships do not determine our editorial verdicts.
      </p>
      <div class="foot-meta">
        <span>© 2026 Odds Primer</span>
        <span>An independent editorial website — not a registered company, broker, or sportsbook</span>
      </div>
    </div>
  </footer>

  <div id="cookie-banner" class="cookie-banner" role="dialog" aria-label="Cookie preferences">
    <div class="cb-msg">
      Odds Primer uses cookies and similar technologies to run the site, understand usage, and measure outbound links.
      You can accept, reject, or manage non-essential cookies.
    </div>
    <div class="cb-actions">
      <button type="button" onclick="document.getElementById('cookie-banner').classList.add('is-managing');">Manage</button>
      <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Reject</button>
      <button class="cb-accept" type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Accept</button>
    </div>
    <div class="cb-prefs">
      <label class="cb-pref"><input type="checkbox" checked disabled>
        <span><span class="cb-name">Essential cookies</span> — always on</span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Analytics cookies</span> — <span class="cb-desc">help us understand site usage</span></span></label>
      <label class="cb-pref"><input type="checkbox">
        <span><span class="cb-name">Affiliate measurement</span> — <span class="cb-desc">helps us measure outbound partner links</span></span></label>
      <div class="cb-actions" style="margin-top: 4px;">
        <button type="button" onclick="document.getElementById('cookie-banner').hidden=true;">Save preferences</button>
      </div>
    </div>
  </div>

</body>
</html>
```

---

## `colors_and_type.css` — design tokens (referenced by every page)

```css
/* ============================================================
   Odds Primer — Colors & Type
   Editorial register. Sports-desk voice. Charts are the art.
   ------------------------------------------------------------
   Three palette directions are defined. The DEFAULT palette
   (warm editorial) lives at :root. The other two are scoped
   to data-palette attributes on <html> or any container.
   ============================================================ */

/* ---------- WEB FONTS ----------
   Anthropic-adjacent stack, all free Google Fonts substitutes:
     - Inter Tight   ≈ Styrene B (display sans, tight)
     - Söhne is the closer reference; Inter Tight is the best free match
     - Source Serif 4 ≈ Tiempos Text (body serif, editorial)
     - JetBrains Mono ≈ for prices/odds (legible numerics)
   Substitutions are documented in README.md.
*/
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;0,8..60,700;1,8..60,400;1,8..60,500&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ============================================================
   PALETTE 1 — WARM EDITORIAL (default)
   The user's working draft, refined.
   - Flame orange shifted dustier (less alarm, more Penguin)
   - Cream paper instead of pure white (less screen, more page)
   - Navy retained as anchor; graphite as secondary structure
   ============================================================ */
:root,
[data-palette="warm-editorial"] {
  /* surfaces */
  --paper:        #FAF7F0;       /* cream, the page */
  --paper-pure:   #FFFFFF;       /* pure white for cards-on-paper */
  --paper-warm:   #F0ECE2;       /* soft warm block */
  --paper-deep:   #E8E2D2;       /* warm rule, divider blocks */

  /* ink */
  --ink:          #0E2240;       /* deep navy, primary type */
  --ink-soft:     #2A3957;       /* secondary type */
  --graphite:     #3A3F47;       /* tertiary structure */
  --graphite-soft:#6B7079;       /* meta, captions */
  --rule:         #D9D2C0;       /* hairline rules on paper */
  --rule-soft:    #EDE7D6;

  /* accent — single, used sparingly */
  --flame:        #D9461C;       /* dustier than #FF5A1F; reads editorial not alarm */
  --flame-deep:   #A8341A;       /* hover/press */
  --flame-tint:   #F7E4DA;       /* highlight wash */

  /* semantic — derived from ink, NOT traffic-light */
  --best-price:   #0E2240;       /* "best" is just bold ink, not green */
  --disagreement: #D9461C;       /* flame, used as "look here" */
  --consensus:   #6B7079;        /* muted, "everyone agrees" */

  /* chart palette — from the same family, orderable */
  --chart-1: #0E2240;            /* ink */
  --chart-2: #D9461C;            /* flame */
  --chart-3: #6B7079;            /* graphite-soft */
  --chart-4: #B89968;            /* warm tan */
  --chart-5: #2A3957;            /* ink-soft */
  --chart-6: #8A6F3D;            /* deep tan */

  /* venues — assigned, not invented */
  --venue-kalshi:     #00C46A;   /* their green, used at low saturation only */
  --venue-polymarket: #2A6FDB;   /* their blue */
  --venue-sportsbook: #6B7079;   /* generic graphite for "the books" */

  --selection-bg: var(--flame-tint);
  --selection-fg: var(--ink);
}

/* ============================================================
   TYPOGRAPHY
   Display sans (Inter Tight) for chrome, headlines, numerics-as-data.
   Body serif (Source Serif 4) for prose, footnotes, captions.
   Mono (JetBrains) for prices, odds, percentages — anywhere a number
   needs to align in a column.
   ============================================================ */
:root {
  --font-sans:    'Inter Tight', 'Söhne', 'Inter', system-ui, -apple-system, 'Helvetica Neue', sans-serif;
  --font-serif:   'Source Serif 4', 'Tiempos Text', 'Charter', 'Georgia', serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', 'Menlo', 'Monaco', monospace;

  /* type scale — editorial, not utility.
     The jumps are wider than a typical web product's;
     headlines are noticeably bigger than body, on purpose. */
  --t-display:    clamp(2.75rem, 5vw, 4.25rem);   /* 44–68px — page-level title */
  --t-h1:         clamp(2rem, 3.5vw, 3rem);       /* 32–48px */
  --t-h2:         clamp(1.5rem, 2.5vw, 2rem);     /* 24–32px */
  --t-h3:         1.25rem;                         /* 20px */
  --t-h4:         1.0625rem;                       /* 17px */
  --t-body:       1.0625rem;                       /* 17px reading */
  --t-body-sm:    0.9375rem;                       /* 15px UI body */
  --t-caption:    0.8125rem;                       /* 13px */
  --t-micro:      0.6875rem;                       /* 11px — tags, eyebrows */

  /* line-heights */
  --lh-display:   1.04;
  --lh-heading:   1.15;
  --lh-body:      1.55;       /* serif body, generous */
  --lh-ui:        1.4;
  --lh-mono:      1.3;

  /* tracking */
  --track-eyebrow: 0.08em;
  --track-display: -0.02em;
  --track-heading: -0.01em;
  --track-mono:    0;

  /* spacing scale — 4px base, editorial-generous.
     Most products stop at 64; we go to 128 because pages need air. */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  24px;
  --space-6:  32px;
  --space-7:  48px;
  --space-8:  64px;
  --space-9:  96px;
  --space-10: 128px;

  /* radii — modest. This is a magazine, not a SaaS app.
     Most things are square. Buttons get 4px. Cards 6px. Pills 999. */
  --radius-0:    0px;
  --radius-1:    2px;
  --radius-2:    4px;
  --radius-3:    6px;
  --radius-4:    8px;
  --radius-pill: 999px;

  /* hairlines & shadows — barely-there. No drama. */
  --hairline:        1px solid var(--rule);
  --hairline-soft:   1px solid var(--rule-soft);
  --hairline-strong: 1px solid var(--ink);

  --shadow-1: 0 1px 0 var(--rule);
  --shadow-2: 0 1px 2px rgba(14, 34, 64, 0.06), 0 0 0 1px var(--rule);
  --shadow-3: 0 8px 24px rgba(14, 34, 64, 0.08), 0 0 0 1px var(--rule);

  /* layout */
  --measure-prose:  62ch;       /* serif reading column */
  --measure-narrow: 38ch;       /* sidebar text */
  --gutter-page:    clamp(20px, 4vw, 64px);

  /* motion — short, restrained, no bounces */
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-emphasis: cubic-bezier(0.3, 0, 0, 1);
  --dur-fast:    120ms;
  --dur-base:    200ms;
  --dur-slow:    320ms;
}

/* ============================================================
   SEMANTIC TYPOGRAPHY CLASSES
   Use these directly OR copy the property block.
   ============================================================ */

.op-eyebrow {
  font-family: var(--font-sans);
  font-size: var(--t-micro);
  font-weight: 600;
  letter-spacing: var(--track-eyebrow);
  text-transform: uppercase;
  color: var(--graphite-soft);
}

.op-display {
  /* Now serif-led. Editorial register; closer to a weekly magazine than a SaaS app. */
  font-family: var(--font-serif);
  font-size: var(--t-display);
  font-weight: 600;
  line-height: 1.06;
  letter-spacing: -0.01em;
  color: var(--ink);
  text-wrap: balance;
}

.op-h1 {
  font-family: var(--font-serif);
  font-size: var(--t-h1);
  font-weight: 600;
  line-height: var(--lh-heading);
  letter-spacing: -0.005em;
  color: var(--ink);
  text-wrap: balance;
}

.op-h2 {
  font-family: var(--font-serif);
  font-size: var(--t-h2);
  font-weight: 600;
  line-height: 1.18;
  letter-spacing: -0.005em;
  color: var(--ink);
  text-wrap: balance;
}

.op-h3 {
  /* Sans for chrome subheads (in-product) */
  font-family: var(--font-sans);
  font-size: var(--t-h3);
  font-weight: 600;
  line-height: var(--lh-heading);
  color: var(--ink);
}

.op-headline-sans {
  /* alt headline — when chrome needs a sans display (rare) */
  font-family: var(--font-sans);
  font-size: var(--t-h1);
  font-weight: 700;
  line-height: var(--lh-heading);
  letter-spacing: var(--track-heading);
  color: var(--ink);
  text-wrap: balance;
}

.op-prose {
  font-family: var(--font-serif);
  font-size: var(--t-body);
  font-weight: 400;
  line-height: var(--lh-body);
  color: var(--ink);
  max-width: var(--measure-prose);
}

.op-prose p + p {
  margin-top: var(--space-4);
  text-indent: 1.25em;       /* book-style indented paragraphs after the first */
}
.op-prose > p:first-child { text-indent: 0; }

.op-ui {
  font-family: var(--font-sans);
  font-size: var(--t-body-sm);
  font-weight: 400;
  line-height: var(--lh-ui);
  color: var(--ink);
}

.op-caption {
  font-family: var(--font-sans);
  font-size: var(--t-caption);
  font-weight: 400;
  line-height: 1.45;
  color: var(--graphite-soft);
}

.op-footnote {
  font-family: var(--font-serif);
  font-size: var(--t-caption);
  font-style: italic;
  line-height: 1.5;
  color: var(--graphite);
}

.op-num {
  /* prices, odds, percentages */
  font-family: var(--font-mono);
  font-feature-settings: "tnum" 1, "ss01" 1;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--ink);
}

.op-num--display {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: var(--t-h1);
  letter-spacing: -0.01em;
  color: var(--ink);
}

.op-byline {
  font-family: var(--font-sans);
  font-size: var(--t-caption);
  font-weight: 500;
  color: var(--graphite);
}

.op-dagger {
  /* the footnote dagger — used as a system glyph and a footnote marker */
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--flame);
}

/* ============================================================
   GLOBAL DEFAULTS
   ============================================================ */
*, *::before, *::after { box-sizing: border-box; }

html, body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: var(--t-body-sm);
  line-height: var(--lh-ui);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

::selection {
  background: var(--selection-bg);
  color: var(--selection-fg);
}

a {
  color: var(--ink);
  text-decoration: underline;
  text-decoration-color: var(--rule);
  text-underline-offset: 2px;
  text-decoration-thickness: 1px;
  transition: text-decoration-color var(--dur-fast) var(--ease-standard),
              color var(--dur-fast) var(--ease-standard);
}
a:hover { text-decoration-color: var(--flame); color: var(--flame-deep); }
a:focus-visible {
  outline: 2px solid var(--flame);
  outline-offset: 2px;
  border-radius: 2px;
}

hr {
  border: 0;
  border-top: var(--hairline);
  margin: var(--space-6) 0;
}

/* ============================================================
   UTILITY HELPERS used across components
   ============================================================ */
.op-rule        { border-top: var(--hairline); }
.op-rule-strong { border-top: var(--hairline-strong); }
.op-block-warm  { background: var(--paper-warm); }
.op-block-deep  { background: var(--paper-deep); }
.op-tabular     { font-variant-numeric: tabular-nums; }
```
