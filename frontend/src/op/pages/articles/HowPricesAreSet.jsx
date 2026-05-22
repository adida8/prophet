// /learn/how-prices-are-set

import LearnArticle from "../LearnArticle";

export default function HowPricesAreSet({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="How are prices set?"
      eyebrow="Reading the numbers · 02"
      title="How are prices set?"
      standfirst="An order book, an implied probability, and a worked example. By the end of this you should be able to look at any quoted price and know what the market thinks the probability is."
      meta="The Editors · 12 May 2026 · 5 min read"
      editionLeft="Learn · 02 of 06"
      editionRight="5 min read"
      nextHref="/learn/is-it-legal"
      nextLabel="Is it legal?"
      nextDescription="Next up · 03"
    >
      <p>
        A prediction market is an <strong>order book</strong>. Buyers post how
        much they're willing to pay for a YES contract. Sellers post how little
        they're willing to accept. When a buyer's bid meets a seller's ask,
        the trade happens at that price. The price you see quoted on the
        screen — <span className="num">27¢</span>, <span className="num">$0.27</span>,
        or simply <span className="num">27</span> — is the most recent agreed
        price between a willing buyer and a willing seller.
      </p>
      <p>
        That's it. There's no bookmaker setting a line, no algorithm balancing
        the book. The price moves the way the price of any traded thing moves:
        someone wants in, someone wants out, they meet at a number.
      </p>

      <h2>Price as probability</h2>
      <p>
        Here's the part that makes prediction-market prices useful. A YES
        contract pays out <strong>$1.00 if the event happens</strong> and
        {" "}<strong>$0 if it doesn't</strong>. So if you'd pay 27¢ for it, you're
        saying "I think the probability is at least 27%." If you wouldn't,
        you're saying "I think it's less than 27%." The price the market
        settles on is the place where those two views balance.
      </p>
      <p>
        Translation rule: <strong>price in cents = implied probability in
        percent</strong>. A contract at <span className="num">27¢</span> means
        the market thinks there's a <span className="num">27%</span> chance the
        event happens. A contract at <span className="num">62¢</span> means 62%.
        That's the whole conversion.
      </p>

      <h2>What about American odds?</h2>
      <p>
        You'll still see sportsbook prices quoted as <span className="num">−180</span>
        {" "}or <span className="num">+130</span>. Convert them to implied probability
        with two short formulas, or just keep this table close to hand:
      </p>

      <table className="conv">
        <thead>
          <tr>
            <th scope="col">American odds</th>
            <th scope="col">Implied probability</th>
            <th scope="col">Decimal odds</th>
            <th scope="col">Contract price</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><span className="num">−400</span></td><td><span className="num">80.0%</span></td><td><span className="num">1.25</span></td><td><span className="num">80¢</span></td></tr>
          <tr><td><span className="num">−250</span></td><td><span className="num">71.4%</span></td><td><span className="num">1.40</span></td><td><span className="num">71¢</span></td></tr>
          <tr><td><span className="num">−180</span></td><td><span className="num">64.3%</span></td><td><span className="num">1.56</span></td><td><span className="num">64¢</span></td></tr>
          <tr><td><span className="num">−110</span></td><td><span className="num">52.4%</span></td><td><span className="num">1.91</span></td><td><span className="num">52¢</span></td></tr>
          <tr><td><span className="num">+100</span></td><td><span className="num">50.0%</span></td><td><span className="num">2.00</span></td><td><span className="num">50¢</span></td></tr>
          <tr><td><span className="num">+130</span></td><td><span className="num">43.5%</span></td><td><span className="num">2.30</span></td><td><span className="num">43¢</span></td></tr>
          <tr><td><span className="num">+250</span></td><td><span className="num">28.6%</span></td><td><span className="num">3.50</span></td><td><span className="num">29¢</span></td></tr>
          <tr><td><span className="num">+400</span></td><td><span className="num">20.0%</span></td><td><span className="num">5.00</span></td><td><span className="num">20¢</span></td></tr>
        </tbody>
      </table>

      <p>
        When you see a row on our board read <span className="em">−180</span>,
        you're looking at the same number as a 64-cent contract — give or
        take the venue's fee. We standardise to implied probability so a
        Polymarket cent quote and a sportsbook line can sit on the same row.
      </p>

      <h2>Why two venues can disagree</h2>
      <p>
        If Polymarket says Brazil is 22¢ to win the World Cup and Kalshi says
        25¢, who's right? Often neither, and the gap is the interesting thing.
        Three things can move two venues out of line with each other:
      </p>
      <p>
        <strong>Different traders.</strong> Polymarket is crypto-native and
        international; Kalshi is US-regulated. Different audiences with
        different information sometimes agree on the underlying probability
        but disagree on how confident to be in it.
      </p>
      <p>
        <strong>Different liquidity.</strong> The thinner the order book,
        the more a single large trade moves the price. A 3-cent gap on a
        market with $500K of depth means something different from the same
        gap on a market with $5K of depth.
      </p>
      <p>
        <strong>Different fees.</strong> Each venue charges a trading fee,
        which slightly nudges the price you actually pay versus the price
        you see. We strip the fee out when we compare; the venue still
        charges it when you trade.
      </p>

      <div className="notice">
        <p>
          <strong>Worked example · 12 May 2026.</strong> 2026 World Cup winner — Brazil (YES).
          Polymarket quotes <span className="num">22¢</span> (22.0%); Kalshi quotes
          {" "}<span className="num">25¢</span> (25.0%).{" "}
          <span className="em">3pp gap</span> — the market thinks Brazil is between
          22% and 25% to lift the trophy. Whether the gap is a real edge or just
          thin-book noise depends on Kalshi's depth on the day, which is exactly
          the read we'd publish on the column.
        </p>
      </div>

      <p style={{ color: "var(--graphite)", fontStyle: "italic", fontSize: 15, marginTop: 28 }}>
        That's how the price gets there, and how to read it once it does.
        The last primer covers where you can use any of these venues — it
        depends a lot on where you live.
      </p>
    </LearnArticle>
  );
}
