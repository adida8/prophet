# Verdict section — five directions

Five takes on the same problem. Each one demonstrates Pick / Pass / Avoid stacked on the same page, using the France v Mexico, Tunisia v Australia, and Germany v Japan fixtures.

The constants across all five:

- Single accent (flame), used for *best price* and *look here* only.
- No green/red on the verdict itself. Movement deltas can carry low-saturation green/red on charts elsewhere; the verdict can't.
- The handoff link is always **View source on Polymarket ↗** — venue named (citation, never destination), never anonymized, never "bet" or "buy." (Updated 2026-05-05 from "Open on" to make the citational stance explicit.)
- Sentence case everywhere. No emoji. No traffic-light shapes.
- The bars glyph is the state mark — growing for Pick, flat for Pass, declining for Avoid.

---

## 01 · Stamp

A magazine pull-quote treatment. Heavy 3px ink rule above the block, the action verb in display serif (`clamp(48px, 7vw, 78px)`), a thin venue/price sub-line, then a two-column "why" block, the score strip baked in, and the handoff link bottom-right under a hairline.

**Strengthens:** state-clarity. The headline does the work — at a glance you see *Back France*, *No edge here*, *Skip Germany v Japan*. It scales the typography down for Pass (italic, smaller) so the visual weight matches the message.

**Sacrifices:** density. The block takes ~520px of vertical space and reads as a "feature." If a user has six matches stacked, this becomes a lot of pages. Also the heaviest commitment to display type — if the editorial team wants flexibility in voice, this is the most opinionated container.

**Copy variants:**

| State | Verb-first | Subject-first | Editorial-first |
|---|---|---|---|
| Pick | "Back France. Polymarket has the slower line." | "France look four points underpriced. Polymarket has them at −180." | "Two markets, one match — and Polymarket is the slower of the two." |
| Pass | "Pass on Tunisia–Australia. The two markets agree." | "No edge here. Polymarket and Kalshi sit within a point." | "When the books agree, our model usually agrees too — and it does." |
| Avoid | "Skip Germany v Japan. The line is short on both venues." | "Germany v Japan sits inside our number on every venue." | "A market that ran past itself — both venues followed Japan's friendly too far." |

---

## 02 · Newspaper deck

Eyebrow, display headline, standfirst — the top of an Athletic column. The venue and price are absorbed into the standfirst sentence (`Our score puts France at 68.5% to win the match; Polymarket has them at −180...`). The handoff is a footer to the deck. A right rail carries the score model and tip chips.

**Strengthens:** justification. The standfirst sentence carries the reasoning, the comparison, and the venue at once — it reads like editorial because it *is* editorial. Reasonable people can disagree with the verdict without being shouted at. This direction is the most on-brand for "patient teacher."

**Sacrifices:** at-a-glance state-clarity. Pick / Pass / Avoid is a small eyebrow tag and a glyph; the headline carries reasoning, not action. A skimming user has to read the standfirst before they know what we think they should do.

**Copy variants:**

| State | Verb-first | Subject-first | Editorial-first |
|---|---|---|---|
| Pick | "Back France on Polymarket at −180. Kalshi is two cents short." | "France look four points underpriced. Polymarket is the better line at −180." | "France look four points underpriced. *Polymarket* is the slower of the two markets." (used in mockup) |
| Pass | "Pass. The two markets agree, and so do we." | "Tunisia–Australia is priced inside a point on both venues." | "No edge here. The two markets agree, and so do we." (used in mockup) |
| Avoid | "Skip Germany v Japan." | "Germany sit inside our number on both venues." | "Skip Germany–Japan. The line is short on both venues." (used in mockup) |

---

## 03 · Spec sheet

The verdict as a structured object: a five-cell row (Action / Venue / Line / Confidence / Tips) above an editorial paragraph and a tip-list sidebar, all wrapped in a 6px-radius card. The state changes the head bar's tint (flame for Pick, warm for Pass, deep for Avoid) and recolors the muted cells.

**Strengthens:** density and comparability. If a user reads three matches in a row, the spec sheet lets their eye track *Action* in column one across the page. It also handles the tip system most legibly — the right column actually shows the seven tips and what they say.

**Sacrifices:** editorial register. This is the closest of the five to "prediction-market dashboard widget." The card chrome and uniform grid pull it toward utility. The editorial paragraph below the grid is doing rear-guard work; if you removed it, the block would read as fintech.

**Copy variants:** (Action / Venue cells, plus the lede)

| State | Verb-first | Subject-first | Editorial-first |
|---|---|---|---|
| Pick | Action: *Back France*. Lede: "Back France — Polymarket is the slower number." | Action: *Back France*. Lede: "France are four points underpriced; Polymarket has the slower line." | Action: *Back France*. Lede: "France look four points underpriced, and Polymarket is the slower of the two markets pricing them." |
| Pass | Action: *No edge*. Lede: "Pass — both venues agree, no slower number to take." | Action: *No edge*. Lede: "The two markets agree within a point. There's nothing to do." | Action: *No edge*. Lede: "No edge here — the books agree." |
| Avoid | Action: *Skip the match*. Lede: "Skip Germany–Japan. Both venues are short of our number." | Action: *Skip the match*. Lede: "Germany v Japan sits inside our number on every venue compared." | Action: *Skip the match*. Lede: "Both venues sit inside our number — there's nothing to do here." |

---

## 04 · Ticket stub

A two-pane card with a perforated divider. The body is editorial — eyebrow, single-line headline, prose, two em-dashed reasons. The stub is structured — Action / Venue / Line / Implied / Op model / Spread, then the **Open ↗** link bottom-right where a serial number would be. The body and stub speak to each other across the perforation.

This direction has the most room to misfire as a casino card. The brief specifically warns against a "BETSLIP READY · Tap to bet" feel. The stub mockup tries to thread the needle: the perforation is a hairline dash (not a heavy serration), the typography is editorial on the body side, the stub uses sentence case and the bars glyph, the action label is *Back France* not *Bet France*, and the seq number is `№ FRA·MEX·01` (a magazine masthead device, not a barcode). It might still read as too "slip" for the brand — flagging that risk explicitly.

**Strengthens:** handoff. The stub literally is a handoff card; the **Open ↗** sits exactly where the eye expects to land after reading the body. No other direction makes the venue handoff this physical.

**Sacrifices:** brand safety. Even with the editorial restraint, this is the direction most likely to read as "casino" if someone screenshots it out of context. Also slightly weakens state-clarity in Pass — a perforated card with "no handoff" on the stub is doing a strange thing (offering a ticket for no journey).

**Copy variants:**

| State | Verb-first | Subject-first | Editorial-first |
|---|---|---|---|
| Pick | Headline: "Back France." Body: "Polymarket is the slower line." | Headline: "France look four points underpriced." Body: "Polymarket has them at −180." | Headline: "Two markets pricing France. One is slower." Body: "The slower one is Polymarket, at −180." |
| Pass | Headline: "Pass on Tunisia–Australia." | Headline: "No edge here." | Headline: "When the books agree, we usually agree." (used as mood, not exact mockup copy) |
| Avoid | Headline: "Skip Germany–Japan." | Headline: "Germany sit inside our number on both venues." | Headline: "A market that ran past itself." |

---

## 05 · Weather report

Smallest, calmest of the five. No card, no rules above, no display type. An eyebrow ("Today's read · Pick"), a kicker line, and the verdict as a single italic-serif sentence at 22px. Underneath, a single-row evidence strip — Kalshi, Polymarket, score, spread, tips — with hairline dividers between cells. The handoff link sits in the footer next to the "built from..." line, deliberately undersold.

**Strengthens:** brand voice and stackability. Five of these in a row would still feel like reading a column. It is the most editorial-on-brand of the five — the sentence is genuinely a sentence a human would write to open a paragraph. The evidence strip is the score model and tip chips compressed into one tabular line.

**Sacrifices:** moment-of-conviction. The verdict is so quietly stated that a Pick risks reading the same as a Pass at 12 feet of distance. The handoff is also visually the weakest — `Open France −180 on Polymarket ↗` is an underlined link, full stop. If conversion is the priority, this direction asks a lot of the reader.

**Copy variants:**

| State | Verb-first | Subject-first | Editorial-first |
|---|---|---|---|
| Pick | "Today's read: back France on Polymarket." | "France look four points underpriced. Polymarket has the slower line at −180." | "Two markets, one match — and Polymarket is the slower of the two." (used in mockup) |
| Pass | "Today's read: pass." | "Tunisia–Australia is priced inside a point on both venues." | "A quiet market, written off in one line — no edge here, the books agree." (used in mockup) |
| Avoid | "Today's read: skip Germany–Japan." | "Germany sit inside our number on every venue." | "A market that ran past itself — both venues followed Japan's friendly too far." (used in mockup) |

---

## Supporting structure decisions, by direction

|  | Score strip | Tip chips / list | Editorial prose |
|---|---|---|---|
| **01 Stamp** | Inside, a 3-cell strip below the verdict line | One italic line at the foot ("Built from xG, recent form, lineup, …") | Two columns of "why," inside the verdict block |
| **02 Newspaper deck** | Sidebar (right rail) | Sidebar chips with a +N more | Absorbed into the standfirst sentence |
| **03 Spec sheet** | Inside the spec grid (one cell of five) | Sidebar list with signal values | Inside the card, below the grid |
| **04 Ticket stub** | On the stub side, six rows | One italic line at the foot of the body | Body side, above the reasons |
| **05 Weather report** | Inside the evidence row | Inside the evidence row ("Tips: 7 of 7 align") | The verdict sentence *is* the prose |

---

## Anti-pattern check

- Casino card → 04 is the closest call; the perforation + stub gets there only with editorial restraint. 03 has card chrome but uses sentence case and serif prose.
- Confidence meter / star rating → none of the five use stars or 1–5 dots. 02 has a "spread to model" rail but it's a tabular meter, not a confidence rating; could be cut without loss.
- Prediction-market dashboard widget → 03 is closest; the editorial paragraph below the grid is what saves it.
- Glassmorphism / colored shadow / gradient → none.
- "Smart pick of the day" badge → none.

---

## Recommendation

**Take 02 (Newspaper deck) forward, with the score model treatment from 03.**

The brand reason: of the five, 02 is the only one that sounds like a column when you read it out loud. The verdict sentence — "France look four points underpriced. Polymarket is the slower of the two markets" — is a sentence a writer would write. The standfirst absorbs the venue, the price, and the reasoning into one paragraph the reader can quote. None of the others do this; they all sit the prose next to or under a structured block.

The product reason: 02 makes the handoff feel earned. The reader gets the reasoning *before* the link, and the link sits where the column would naturally end. 04's stub puts the link before the reasoning; 03's spec sheet puts the action *above* the reasoning. 02 is the one where the conversion moment matches the editorial moment.

The compromise: 02's right rail is doing useful work — the score model rows, the spread-to-model meter, the tip chips with a +N more — and we should keep that exactly as is. 03's sidebar tip-list (with signal values like *+1.8, match, deep*) is genuinely better than 02's chip cloud, and we should fold that in.

What 02 still needs to figure out before it ships:

1. **The Pass and Avoid handoff line.** The mockup uses an italic note ("The verdict here is to read, not to act"), which works but might calcify into boilerplate. Worth two more passes by editorial.
2. **The state glyph in the eyebrow** is doing a lot of the at-a-glance work that 01's display headline does for free. If the eyebrow gets cut for space on mobile, the state legibility collapses. Make the glyph mandatory; consider also coloring the eyebrow itself in flame for Pick and graphite for Pass/Avoid.
3. **Mobile.** The two-column layout collapses to single column nicely, but the right rail's score rows become a wall of small text. On mobile, consider compressing the score model to a single line: `Kalshi 60.2 · Polymarket 64.3 · Op 68.5 · spread +4.2`.

If 02 turns out to be too quiet for the homepage row-level verdict (`.ft-suggests` in `home-v2.html`), 05 (Weather report) is the right fallback for that smaller surface — it's the single-sentence form factor, and it's already the same voice.
