# Research prompt — Prediction-market market-making infrastructure

> Paste this into ChatGPT Deep Research, Claude, Perplexity, Gemini, or hand to a human analyst.

---

You are a senior market analyst. I'm evaluating a specific B2B business idea and need you to stress-test it in one page.

**Background.** I have ~10 years of background at Playtech — sportsbook odds infrastructure, risk management, regulated gaming. I'm evaluating whether to build a **market-making infrastructure company for prediction markets** (Kalshi, Polymarket, and forthcoming competitors), together with one technical co-founder. The product has two revenue tiers:

- **Tier A — Licensed software.** Pricing engine + market-making stack. Customer runs it on their own infrastructure, with their own capital. Target ACV: **$5K–$50K/month** per customer.
- **Tier B — Managed service.** We operate the MM desk on the customer's behalf, using their capital. Management fee + performance share. Target ACV: **$20K–$200K/month** per customer + profit share.

**Customer targets:** (1) sportsbooks launching event-contract / PM products (DraftKings, FanDuel, Fanatics, BetMGM); (2) new / small prediction-market venues needing seed liquidity; (3) prop trading firms and quant funds trading PMs for alpha; (4) eventually Kalshi and Polymarket themselves.

**Constraints.** Goal is $50K–$150K/month MRR within 18–24 months. Side-project cadence (15–25 hrs/week per founder). No outside capital at start. Existing asset: a working Python paper-trading bot on Kalshi + Polymarket with Kelly-sized risk manager and a matched-markets engine.

**Your task: answer the seven questions below in one page max (≤ 600 words).** Prioritize named companies, specific pricing benchmarks, and recent (2025–2026) evidence. Call out where data is thin. Flag anything that invalidates the thesis.

1. **Market size.** How many prediction-market venues exist globally today (regulated + crypto-native)? How many sportsbooks are publicly evaluating or have launched event-contract products? Estimate how many realistic Tier-A buyers exist in the next 18 months.

2. **Incumbents.** Who already sells MM / pricing / risk infrastructure into prediction markets, sportsbooks, or exchange-traded derivatives? Investigate: Trading Technologies, SIS, Kaizen Gaming infra, CFH Systems, GR8 Tech, OpenMarkets, plus crypto-native MMs like Wintermute, Flowdesk, GSR, Amber. Who's the closest direct competitor in **prediction-market-specific** infra? What do they charge?

3. **Pain validation.** Is "insufficient liquidity" actually the #1 problem for PM venues and sportsbooks evaluating event contracts? Cite specific public statements, earnings-call mentions, interviews, or job postings from 2025–2026. Are these buyers actively paying for external MM infrastructure today, or is it built in-house by default?

4. **Technical moat.** How defensible is a PM-specific pricing + MM stack? What's the hard IP vs. what can a competent engineer with Claude Code replicate in 6 months? Specifically address: binary-contract pricing math, correlated-market risk (one news event moves 50 markets at once), adverse-selection detection, settlement handling.

5. **Regulatory reality.** Post-Kalshi Third Circuit ruling (April 2026) and pending CFTC Q3 2026 rulemaking — is it legally viable for a small US-based infra vendor to sell MM tech to CFTC-regulated venues and sportsbooks without becoming a registered entity itself? What's the real compliance overhead for Tier A vs. Tier B?

6. **Competitive window.** How fast could Kalshi, Polymarket, DraftKings, or Gambling.com Group (post-OddsJam) build this in-house and crush a small vendor? 6 months? 18 months? What's the realistic first-mover window before the wedge commoditizes?

7. **Capital requirements.** Tier A is pure software. Tier B either runs the customer's capital or backs the book. Realistically, how much working capital does a Tier-B deployment need per customer? At what revenue scale does the performance-fee component start to dominate the management fee?

**Output format.** ≤ 600 words. Short paragraphs or numbered structure matching the seven questions. End with a **bold one-sentence verdict — GO / GO-WITH-CHANGES / NO-GO — and the single strongest reason behind it.** Do not hedge. Do not repeat the question back.
