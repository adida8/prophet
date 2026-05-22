// /learn/how-to-start

import LearnArticle from "../LearnArticle";

export default function HowToStart({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="How do I start?"
      eyebrow="Your first trade · 06"
      title="How to start: your first prediction-market trade"
      standfirst={
        <>
          Five steps from "never done this" to a placed trade you understand.
          No jargon you haven't already met in the earlier primers.
        </>
      }
      meta="The Editors · 22 May 2026 · 5 min read"
      editionLeft="Learn · 06 of 06"
      editionRight="5 min read"
      nextHref="/#today"
      nextLabel="See today's board"
      nextDescription="You've finished the primers"
    >
      <p>
        You've read what a prediction market is, how the price works, who's
        allowed in, and what the fees do. This is the practical part: opening an
        account and placing one trade you actually understand. The point of the
        first trade isn't to win — it's to learn the mechanics with small money.
      </p>

      <h2>1 · Pick a venue you can legally use</h2>
      <p>
        Start from where you live, not from which app looks slickest. In the US,
        Kalshi is the federally regulated route available in most states;
        Polymarket is restricted in several. Internationally, Polymarket is
        generally open.{" "}
        <InternalLink navigate={navigate} href="/learn/is-it-legal">
          The legality primer has the state-by-state read
        </InternalLink>{" "}
        — check it before you sign up, not after.
      </p>

      <h2>2 · Open the account and verify</h2>
      <p>
        Expect identity verification on any regulated venue: name, date of
        birth, sometimes a photo ID. This is a feature, not friction — it's part
        of what makes the venue accountable.{" "}
        <InternalLink navigate={navigate} href="/learn/is-kalshi-legit">
          It's also why a regulated venue is safer than an offshore one.
        </InternalLink>{" "}
        Age minimum is 18+ on Kalshi and Polymarket, higher on the
        sportsbook-run products.
      </p>

      <h2>3 · Fund a small amount</h2>
      <p>
        Deposit an amount you'd be genuinely fine losing — for a first trade,
        think the price of a coffee, not a car payment. Regulated venues take
        normal bank methods; crypto-rail venues may need you to move funds on
        chain, which can carry a separate network fee.{" "}
        <InternalLink navigate={navigate} href="/learn/prediction-market-fees">
          The fees primer covers what to watch for.
        </InternalLink>
      </p>

      <h2>4 · Read the market before you click</h2>
      <p>
        Find a market you actually have a view on. Read two things first: the{" "}
        <strong>settlement source</strong> (how does this resolve, and who
        decides?) and the <strong>price</strong> (a contract at 40¢ means the
        market thinks 40% — do you think it's higher or lower?). If you can't
        say why you disagree with the price, you don't have a trade yet, you
        have a hunch.
      </p>

      <div className="pullbox">
        <p>
          A trade is a disagreement with the market price, backed by a reason.
          No reason, no trade — that's the whole discipline.
        </p>
      </div>

      <h2>5 · Place it, then watch what happens</h2>
      <p>
        Buy YES if you think the chance is higher than the price; buy NO if you
        think it's lower. Start with one contract. Then — and this is the part
        most people skip — <strong>watch how the price moves and why</strong>.
        News drops, the price repriced; that's the market learning in real time.
        Sitting with one small position teaches you more than reading ten
        explainers.
      </p>

      <h2>Where we fit</h2>
      <p>
        Our job isn't to open the account for you — it's to tell you when a
        price looks wrong and why.{" "}
        <InternalLink navigate={navigate} href="/" hash="today">
          The board flags where the model and the market disagree,
        </InternalLink>{" "}
        with the case behind every call. Read the market yourself, read our
        take, then decide. That's the order that keeps you in charge.
      </p>

      <div className="notice">
        <p>
          <strong>Start small, stay sober.</strong> Trade only money you can
          afford to lose, set a limit before you start, and walk away if it
          stops being fun. Nothing here is financial advice.
        </p>
      </div>

      <p style={{ color: "var(--graphite)", fontStyle: "italic", fontSize: 15, marginTop: 28 }}>
        That's the lot. You can now read a market, read a price, and place a
        trade you understand. The board's where it gets interesting.
      </p>
    </LearnArticle>
  );
}

function InternalLink({ navigate, href, hash, children }) {
  const handle = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (!navigate) return;
    if (hash) {
      navigate(href);
      setTimeout(() => {
        const t = document.getElementById(hash);
        if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    } else {
      navigate(href);
    }
  };
  return <a href={href} onClick={handle}>{children}</a>;
}
