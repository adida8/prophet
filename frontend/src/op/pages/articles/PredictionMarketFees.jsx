// /learn/prediction-market-fees

import LearnArticle from "../LearnArticle";

export default function PredictionMarketFees({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="What are the fees?"
      eyebrow="The costs · 05"
      title="What are the fees on Polymarket and Kalshi?"
      standfirst={
        <>
          Fees are small per trade and easy to ignore — which is exactly why
          they add up. Here's how each venue charges, and how to read a price
          knowing the fee is hiding inside it.
        </>
      }
      meta="The Editors · 22 May 2026 · 4 min read"
      editionLeft="Learn · 05 of 06"
      editionRight="4 min read"
      nextHref="/learn/how-to-start"
      nextLabel="How do I start?"
      nextDescription="Next up · 06"
    >
      <p>
        Every venue takes a cut. On a sportsbook it's baked into the line (the{" "}
        <span className="em">vig</span>) so you never see it as a separate
        number. On a prediction market the fee is usually more explicit — a
        charge on the trade itself — but it still nudges the real price you pay
        away from the price on screen. Knowing the shape of each venue's fee is
        what stops it quietly eating your edge.
      </p>
      <p>
        Fee schedules change, and the exact numbers below the structure are the
        venue's to set — so treat this as <strong>how to think about fees</strong>,
        and check the live schedule before you trade.
      </p>

      <h2>The two fee models</h2>
      <p>
        <strong>Per-trade fee.</strong> A charge applied when you buy or sell,
        often scaled so it's largest on prices near the middle (around 50¢)
        and smallest on prices near the edges (near 1¢ or 99¢). The logic:
        a mid-priced contract has the most uncertainty, so the venue prices its
        risk highest there. This is closest to Kalshi's approach.
      </p>
      <p>
        <strong>Maker / taker spread.</strong> On an order-book venue, the
        cost can show up as the gap between the best buy and best sell price
        rather than a headline percentage. You "pay the spread" when you take
        the best available price instead of posting your own and waiting. This
        is closer to how trading costs work on Polymarket's order book, on top
        of any explicit fee the venue applies.
      </p>

      <div className="pullbox">
        <p>
          The fee you can see is the headline. The spread you pay by taking the
          market price instead of posting your own is the one most people miss.
        </p>
      </div>

      <h2>Why the fee changes what a price means</h2>
      <p>
        Say a contract is quoted at <span className="num">40¢</span> — the
        market's implied probability is 40%. If the venue charges you a couple
        of cents to get in, your <strong>break-even probability isn't 40%, it's
        higher</strong>. You need the true chance to clear the price{" "}
        <em>plus</em> the fee before the trade is worth making. On a single bet
        that's noise. Across a hundred trades, it's the difference between a
        thin edge and no edge.
      </p>
      <p>
        This is why we strip the fee out when we compare two venues on the
        board. A 3-cent gap between Polymarket and Kalshi can vanish entirely
        once each venue's fee is added back in — so the gap on screen isn't the
        edge in your pocket.{" "}
        <InternalLink navigate={navigate} href="/learn/how-prices-are-set">
          That's the price-as-probability idea in practice.
        </InternalLink>
      </p>

      <h2>What to actually check before you trade</h2>
      <p>
        Three things, in order. <strong>The headline fee</strong> for the price
        range you're trading in. <strong>The spread</strong> — how far apart the
        best buy and sell prices are right now; a wide spread is a hidden cost.
        And <strong>withdrawal or deposit fees</strong>, especially on
        crypto-rail venues where moving money on and off chain can carry a
        network cost separate from the trade.
      </p>

      <div className="notice">
        <p>
          <strong>Numbers move.</strong> Fee schedules are set by each venue and
          change without much notice. The venue's own fee page is the
          authoritative source — this primer is the map, not the territory.
        </p>
      </div>

      <p style={{ color: "var(--graphite)", fontStyle: "italic", fontSize: 15, marginTop: 28 }}>
        That's the cost side. Last primer: how to actually open an account and
        place your first trade without fumbling it.
      </p>
    </LearnArticle>
  );
}

function InternalLink({ navigate, href, children }) {
  const handle = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate(href);
  };
  return <a href={href} onClick={handle}>{children}</a>;
}
