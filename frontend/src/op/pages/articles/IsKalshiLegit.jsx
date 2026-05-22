// /learn/is-kalshi-legit

import LearnArticle from "../LearnArticle";

export default function IsKalshiLegit({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="Is Kalshi legit?"
      eyebrow="Trust + safety · 04"
      title="Is Kalshi legit and safe?"
      standfirst={
        <>
          Short answer: yes — Kalshi is a real, federally regulated exchange,
          not an offshore app. Here's what "regulated" actually buys you, and
          where the genuine risk still sits.
        </>
      }
      meta="The Editors · 22 May 2026 · 4 min read"
      editionLeft="Learn · 04 of 06"
      editionRight="4 min read"
      nextHref="/learn/prediction-market-fees"
      nextLabel="What are the fees?"
      nextDescription="Next up · 05"
    >
      <p>
        Kalshi is the only US prediction-market venue listed with the{" "}
        <strong>Commodity Futures Trading Commission</strong> as a Designated
        Contract Market — the same category of regulator that oversees the
        futures exchanges where oil, wheat, and interest rates trade. That's
        not marketing language. It means every market Kalshi lists has been
        filed with a federal regulator, and the exchange operates under rules
        it can be audited against.
      </p>
      <p>
        So when people ask "is Kalshi a scam," the honest answer is no — it's
        about as far from a scam as a venue in this space gets. The questions
        worth asking are narrower: is my money safe, is my data safe, and what
        can still go wrong.
      </p>

      <h2>What "regulated" actually buys you</h2>
      <p>
        Three concrete things. <strong>Segregated funds</strong> — customer
        money is held separately from the company's own operating cash, so the
        balance you see is yours, not working capital. <strong>Filed
        markets</strong> — Kalshi can't spin up an arbitrary market and settle
        it however it likes; the contract terms and the settlement source are
        defined up front. And <strong>a complaints path</strong> — there's a
        federal regulator you can escalate to, which is not true of an offshore
        venue.
      </p>

      <div className="pullbox">
        <p>
          Regulation doesn't mean you'll win. It means the venue can't move the
          goalposts on how a market settles — and your balance isn't the
          company's spending money.
        </p>
      </div>

      <h2>Where the real risk sits</h2>
      <p>
        <strong>You can still lose your stake.</strong> Regulation protects the
        integrity of the market, not the wisdom of your trade. A contract that
        settles NO takes your money to zero exactly the way a losing bet does.
      </p>
      <p>
        <strong>Settlement disputes are rare but real.</strong> Most markets
        resolve cleanly. The friction shows up on markets where the underlying
        event is ambiguous — a result that's contested, a source that changes
        its number after the fact. Kalshi publishes the settlement source for
        each market; reading it before you trade is the single best habit.
      </p>
      <p>
        <strong>It's still gambling-shaped for your brain.</strong> Federal
        oversight doesn't change the fact that fast, frequent, binary trading
        is easy to overdo. The protections are financial, not psychological.
      </p>

      <h2>Kalshi vs an offshore app</h2>
      <p>
        The contrast that matters: an unregulated offshore venue can hold your
        funds however it likes, change its terms, restrict withdrawals, and
        leave you with no regulator to call. Kalshi's whole pitch is that it
        doesn't do those things, and it's structurally accountable if it tries.
        That's the difference "legit" is really pointing at.{" "}
        <InternalLink navigate={navigate} href="/learn/is-it-legal">
          Whether you can use it depends on your state.
        </InternalLink>
      </p>

      <div className="notice">
        <p>
          <strong>We're not your financial adviser.</strong> "Regulated" and
          "safe to trade with" are not the same as "a good idea for you."
          Only stake money you can afford to lose, and check the venue's
          current terms — they're the authoritative source, not us.
        </p>
      </div>

      <p style={{ color: "var(--graphite)", fontStyle: "italic", fontSize: 15, marginTop: 28 }}>
        That's the trust question. The next primer covers the part that quietly
        eats your returns: fees.
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
