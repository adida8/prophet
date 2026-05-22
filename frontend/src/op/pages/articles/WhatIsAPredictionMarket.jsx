// /learn/what-is-a-prediction-market

import LearnArticle from "../LearnArticle";

export default function WhatIsAPredictionMarket({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="What is a prediction market?"
      eyebrow="The basics · 01"
      title="What is a prediction market?"
      standfirst={
        <>
          A market where you trade contracts that pay out on real-world events.
          Different from a sportsbook in one important way — the price <em>is</em>
          {" "}the probability.
        </>
      }
      meta="The Editors · 12 May 2026 · 3 min read"
      editionLeft="Learn · 01 of 06"
      editionRight="3 min read"
      nextHref="/learn/how-prices-are-set"
      nextLabel="How are prices set?"
      nextDescription="Next up · 02"
    >
      <p>
        A prediction market is a market where you trade contracts whose value
        depends on whether a real-world event happens. <strong>Will Brazil win
        the 2026 World Cup?</strong> Will the Fed cut rates at the next meeting?
        Will Bitcoin close above $200,000 by Friday? Each of those is a contract
        you can buy or sell — and the price of the contract is the market's
        best guess at the probability of the outcome.
      </p>
      <p>
        The standard form is a <strong>YES/NO binary</strong>. A YES contract
        pays out $1 if the event happens and $0 if it doesn't. If the market
        thinks there's a 27% chance Brazil wins the World Cup, the YES contract
        on "Brazil wins" trades at about 27 cents. Sell it and you get someone
        else's 27 cents now; if Brazil wins, you owe them a dollar. If Brazil
        doesn't, you keep their cents and they get nothing.
      </p>

      <h2>How is it different from sports betting?</h2>
      <p>
        On a sportsbook, you're betting against the house. The bookmaker sets
        the line, takes the other side of your wager, and earns a margin
        (the <span className="em">vig</span>) regardless of who's right. The line
        moves to balance the book, not to find the true probability.
      </p>
      <p>
        On a prediction market, you're trading with <strong>other users</strong>.
        The venue runs the order book and takes a small fee on each trade, but
        it doesn't take the other side. That changes what the price means:
        it stops being "what the bookmaker thinks will balance the book" and
        becomes "what the marginal buyer and the marginal seller agree on right now."
        The closer that is to the true probability, the harder it is to find an edge.
      </p>

      <div className="pullbox">
        <p>
          The headline difference: on a sportsbook the price tells you the
          {" "}<em>line</em>. On a prediction market the price tells you the
          {" "}<em>probability</em>.
        </p>
      </div>

      <h2>Where does it happen?</h2>
      <p>
        A short list. <strong>Polymarket</strong> is the largest and operates
        on a USDC-denominated order book; you'll see prices quoted in cents
        out of a dollar. <strong>Kalshi</strong> is the US-regulated venue,
        listed under the CFTC; prices are also in cents, with a smaller but
        mostly overlapping universe of markets. <strong>DraftKings Predictions</strong>
        {" "}and <strong>FanDuel Predicts</strong> sit closer to the sportsbook
        tradition but expose event-contract pricing. Several smaller venues
        round out the field.{" "}
        <InternalLink navigate={navigate} href="/learn/is-it-legal">
          Which ones you can use depends on where you are.
        </InternalLink>
      </p>

      <h2>Why does it matter?</h2>
      <p>
        Two reasons. First, prices move in real time — markets aggregate the
        information of everyone trading and reprice the instant new information
        arrives. That makes them <strong>useful as forecasts</strong> long after
        the news article goes stale. Second, two venues quoting the same outcome
        at different prices is a tell that one of them is wrong about something.
        Our job is to{" "}
        <InternalLink navigate={navigate} href="/" hash="today">show you which one,</InternalLink>{" "}
        and to tell you when neither is.
      </p>

      <p style={{ color: "var(--graphite)", fontStyle: "italic", fontSize: 15, marginTop: 28 }}>
        That's the whole idea. The next primer covers how the price is set
        on the order book, and how to read a quoted price as a probability.
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
