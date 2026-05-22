// /learn/is-it-legal

import LearnArticle from "../LearnArticle";

export default function IsItLegal({ navigate, currentPath }) {
  return (
    <LearnArticle
      navigate={navigate}
      currentPath={currentPath}
      crumbLabel="Is it legal?"
      eyebrow="Geo + age · 03"
      title="Is it legal?"
      standfirst="Mostly yes, in the United States, with state-by-state caveats. We're not lawyers — but we've read the rules, and here's what you need to know before you open an account anywhere."
      meta="The Editors · 12 May 2026 · 4 min read"
      editionLeft="Learn · 03 of 06"
      editionRight="4 min read"
      nextHref="/learn/is-kalshi-legit"
      nextLabel="Is Kalshi legit?"
      nextDescription="Next up · 04"
    >
      <p>
        Three different legal frames apply to the venues we cover. They each
        read your trade as a different kind of thing. The shorthand version
        first; the nuance afterwards.
      </p>

      <h2>Three frames, three regulators</h2>

      <table className="venues">
        <thead>
          <tr>
            <th scope="col">Venue</th>
            <th scope="col">Regulator</th>
            <th scope="col">What your trade is, legally</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Kalshi</strong></td>
            <td>CFTC (federal)</td>
            <td>An event contract on a Designated Contract Market.</td>
          </tr>
          <tr>
            <td><strong>Polymarket</strong></td>
            <td>None in the US <span className="dag">†</span></td>
            <td>An offshore crypto-denominated derivative.</td>
          </tr>
          <tr>
            <td><strong>DraftKings Predictions</strong></td>
            <td>State gaming commission</td>
            <td>A wager under state gambling rules.</td>
          </tr>
          <tr>
            <td><strong>FanDuel Predicts</strong></td>
            <td>State gaming commission</td>
            <td>A wager under state gambling rules.</td>
          </tr>
        </tbody>
      </table>

      <h2>Kalshi — the regulated route</h2>
      <p>
        Kalshi is the only US prediction-market venue listed with the{" "}
        <strong>Commodity Futures Trading Commission</strong> as a Designated
        Contract Market. That federal listing means it can offer event
        contracts to residents of every US state — at least, that's what the
        Third Circuit confirmed earlier this year on the sports-event-contract
        question. The CFTC has rulemaking on the subject due later in 2026;
        the legal frame could narrow.
      </p>
      <p>
        One state-level wrinkle: <strong>Nevada</strong> has blocked Kalshi's
        sports-event contracts under state gambling law. Most other states
        haven't. Age minimum is <span className="num">18+</span>.
      </p>

      <h2>Polymarket — open internationally, restricted in the US</h2>
      <p>
        Polymarket is the largest prediction market by volume, but it operates
        outside the US regulatory perimeter. <strong>US residents in eight
        states</strong> — AZ, IL, MA, MD, MI, MT, NV, and OH — are blocked
        outright. Several countries are blocked too. The venue checks your
        IP and asks you to confirm residency on signup.
      </p>
      <p>
        Internationally Polymarket is generally available, with the usual
        jurisdictional caveats. If you're in the UK, the EU, most of Asia,
        or most of Latin America, you can trade. If you're in the US, your
        state determines whether you can.
      </p>

      <h2>DraftKings Predictions and FanDuel Predicts — the sportsbook route</h2>
      <p>
        These are operated by US sportsbooks under their existing state
        gambling licences. That means they're available <strong>only in states
        where the parent sportsbook is licensed</strong>, with the same
        state-by-state patchwork sports betting already lives inside.
        Age minimum is <span className="num">21+</span> in most states.
      </p>
      <p>
        Functionally they look like prediction markets — but legally they're
        wagers, not derivatives. The user experience is closer to a sportsbook.
      </p>

      <h2>The age line</h2>
      <p>
        <strong>18+</strong> at Kalshi and Polymarket. <strong>21+</strong> at
        DraftKings Predictions and FanDuel Predicts (state-dependent; a few
        states like New Jersey allow 18+ for sportsbook products).
        Every venue runs identity verification.
      </p>

      <div className="notice">
        <p>
          <strong>We're not lawyers.</strong> Nothing on this page is legal
          advice. The rules are state-by-state, they shift, and the{" "}
          <span className="em">venue's own geo-restriction page</span> is the
          authoritative read. Check it before you open an account, and
          again if you've moved.
        </p>
      </div>

      <p style={{
        marginTop: 28,
        fontFamily: "var(--font-serif)",
        fontSize: 13,
        fontStyle: "italic",
        color: "var(--graphite-soft)",
        maxWidth: "62ch",
      }}>
        <span className="dag">†</span> Polymarket settled with the CFTC in 2022 and
        currently operates as a non-US venue. Whether that status changes is
        one of the live regulatory questions in this space.
      </p>
    </LearnArticle>
  );
}
