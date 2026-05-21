# The Desk — Voice

The guide for every word The Desk publishes: titles, summaries, blurbs.
The engine reads this (PR 5's blurb-writer prompt points here); Faktor
reads this; humans reviewing copy read this. `desk/desk/explainer/voice.py`
enforces the hard "never" rules in code — **this file is the "how to sound."**

## The voice in one line

A columnist who happens to write about probability. Dry, confident, never
a tipster. The Athletic, not a sportsbook. We show the reader where the
market might be wrong — we never tell them what to do about it.

## The four rules that matter most

**1. Every blurb has a point.** One load-bearing sentence that says *why the
verdict is what it is*, in words a person would actually speak. If a blurb
could be swapped onto any other match without changing, it has no point —
rewrite it. The point is usually the gap (or the absence of one) and what
causes it.

**2. Give it room.** A blurb is **5–8 sentences, roughly 120–180 words** —
long enough to make a point, give the reason behind it, and ground it in a
source, but not so long it turns into the full article. Title: one line.
Summary: 1–2 sentences. Past ~190 words, you're writing the article, not the
blurb.

**3. Smart, but not too smart.** Use exactly one real insight per blurb — the
kind that makes a reader nod. Don't stack jargon to sound clever; don't hedge
like an academic. If a term needs defining, the body shouldn't stop to do it
(that's the footnote's job, or cut the term). The test: a sharp friend who's
new to prediction markets should never feel either talked-down-to or lost.

**4. Every blurb is sourced — and we never invent a source.** Every claim
traces back to something. Price claims trace to the market (Polymarket /
Kalshi — already carried in the verdict). Any real-world claim — form, an
injury, a manager's quote, momentum — must come from a cited source, be
attributed in the text, and be carried in `copy.editorial_citations` (outlet,
deep link, verbatim quote). If a sentence asserts something the model can't
see and no source backs it, cut the sentence. We say "the Guardian
reported…", never "word is that…".

> **When no editorial source exists** (a quiet fixture the news pipeline found
> nothing for), source the blurb against the **market and model only** — and
> say nothing that would need a citation. Never manufacture a quote or an
> outlet to satisfy this rule. A thinner, fully-sourced blurb beats a richer
> invented one, every time.

## Register by verdict

Same writer, different gear:

- **Pick** — most assertive. State the gap, name the side, give the one reason
  it exists. Confidence, not hype.
- **Pass** — quietly interesting. The absence of an edge *is* the story;
  agreement between model and market is a signal, not a non-event. Never
  apologetic, never filler.
- **Avoid** — rare and plain. Every side looks overpriced; say so without
  drama. (Structurally near-impossible on single-venue odds — see
  `desk/desk/verdict/decide.py` — so this register is mostly theoretical today.)

## Worked examples

**Pick — good:**

> The model rates Bosnia at 34% to advance; the market prices that side at 22%.
> The 11-point gap is the widest on the board. Part of it traces to their
> qualifying form — the Guardian noted they "went unbeaten through the back
> half of the group," a run the market seems slow to price in.† The model,
> which weights that record directly, doesn't share the hesitation. That
> disagreement is the basis for the Pick — not a prediction, a gap worth seeing.
>
> *† The Guardian (football), 19 May 2026 — carried in `editorial_citations`.*

*~85 words, sourced, one clear point.*

**Pass — good (no editorial source available):**

> Mexico should win, and the price already knows it — our model lands within a
> point of the market on all three sides, with both pricing the same shape
> against Polymarket's line. That agreement is the story, not a non-event: two
> different ways of estimating the same question arriving at the same answer.
> There's no live injury or form signal pulling them apart yet, so there's
> nothing to trade. Inventing an edge here is the one thing this desk won't do.
> We'll look again near kickoff, when the confirmed line-ups land.

*~90 words. No news source existed, so it sources cleanly against market and
model — and claims nothing that would need a citation.*

**Bad (any verdict):**

> Our Elo prior, adjusted for venue and altitude, agrees with the closing line
> within a percentage point on every side. Pass is the honest call when
> calibration is in agreement.

*Why it fails: accurate but mechanical. "Calibration is in agreement" is
too-smart jargon with no point a reader can feel, and nothing is attributed.
This is the current templated stub — what we are replacing.*

## Hard rules (enforced in `voice.py`)

- **No exclamation marks. No emoji.** Em-dashes welcome. Footnote daggers (†)
  encouraged.
- **Banned: tipster-speak** — "bet", "back the", "lock", "free bet", "boost",
  "smart money", "no-brainer", "will win", "guaranteed", "cash in", "buy now".
  We say "best price", "biggest disagreement", "the gap".
- **Never "I."** Editorial "we" for our calls, sparingly. "You" when teaching.
- **Sentence case** everywhere except the masthead and proper nouns.
- **No certainty.** "The model rates France at 16%" — never "France will win."
- **Never traffic-light bets.** We surface the disagreement; the reader decides.

---

*Source lineage: brand voice from `Odds Primer Design System/README.md`
(CONTENT FUNDAMENTALS); hard rules mirror `desk/desk/explainer/voice.py`;
voice direction (V1 — dry wit with a spine, footnotes carry teaching) locked
2026-05-22.*
