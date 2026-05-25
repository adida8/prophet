# Pass / Avoid copy variants — drop-in spec

Closes the duplicate-content gap: today `_pass_copy` and `_avoid_copy` in
`desk/desk/explainer/stub.py` are **one hardcoded paragraph each**, while
`_pick_*` already rotates through hash-keyed variant pools. Since ~half the
board is Pass/Avoid, that one paragraph is what makes the site feel
"copied 300 times."

Fix: give Pass and Avoid the same `_variant_index(salt, n)` treatment Pick
uses. Copy below is voice-clean (checked against `voice.py` banned-substring
list — note "bet"/"lock" are substrings, so no "between"/"better"/"block").
Each variant makes one point and sources only against market + model, so the
press chorus still appends separately via `_with_chorus`.

## Variables available to the templates

Mirror what `_pick_blurb` already pulls. For Pass/Avoid the wiring needs:

```python
a, b              = i["team_a"], i["team_b"]
p_a, p_d, p_b     = model three-way   (model_p_a / model_p_draw / model_p_b)
mp_a, mp_d, mp_b  = market three-way  (market_p_a / market_p_draw / market_p_b)
edge              = i["edge_pp"] or 0.0          # Pass: smallest |gap|; Avoid: most-negative
venue_label       = (i.get("market_venue") or "the market").title()
# favourite, by model probability — used by a couple of Pass framings:
_sides   = [(a, p_a), ("the draw", p_d), (b, p_b)]
fav, fav_mp = max(_sides, key=lambda s: s[1])
fav_kp   = {a: mp_a, "the draw": mp_d, b: mp_b}[fav]   # market p of the favourite side
salt     = f"{a}|{b}|pass"     # or |avoid
def pick(key, opts): return opts[_variant_index(salt + "/" + key, len(opts))]
```

`_pct()` already exists in the file.

---

## PASS

### Titles (pool)

```python
pass_title_options = [
    f"{a} v {b} · model and market agree",
    f"{a} v {b} · the price looks fair",
    f"{a} v {b} · no gap to call",
    f"{a} v {b} · model lands on the line",
]
title = pick("pass-title", pass_title_options)
```

### Summaries (pool — 1–2 sentences)

```python
pass_summary_options = [
    # 1 · agreement
    f"The model and {venue_label} land within a point of each other on all three "
    f"sides of {a} v {b}. No gap to publish — the state reads Pass.",
    # 2 · market-efficient
    f"{venue_label}'s line on {a} v {b} already sits where the model does, to within "
    f"a point on every side. Pass: the price has done the work.",
    # 3 · clear favourite priced right
    f"{fav} should win, and at {_pct(fav_kp)} the market already prices it that way — "
    f"the model agrees to within a point. Pass.",
    # 4 · close match, no separation
    f"{a} v {b} reads close to both the model and the market, and neither finds a "
    f"side worth separating. Pass — nothing stands out.",
    # 5 · low-confidence
    f"Where a small gap exists on {a} v {b}, it sits inside the model's own "
    f"uncertainty. Not enough conviction to call. Pass.",
    # 6 · news-pending
    f"Today the model and {venue_label} agree on {a} v {b} to within a point. Nothing "
    f"has moved the prior yet. Pass, for now.",
    # 7 · discipline
    f"On {a} v {b} the honest read is no edge: model and market sit a point apart at "
    f"most. Pass — we won't manufacture one.",
]
summary = pick("pass-summary", pass_summary_options)
```

### Blurbs (pool — 5–8 sentences, ~110–150 words)

```python
pass_blurb_options = [
    # 1 · agreement-as-signal (model alignment)
    f"For {a} versus {b}, the model and {venue_label} arrive at the same answer from "
    f"different directions — within a point of each other on all three sides. That "
    f"agreement is the story, not an empty result: two independent ways of estimating "
    f"the same match converging is itself a signal that the price is about right. "
    f"There is no side where the model sees value the market has missed, and none where "
    f"it sees the reverse. So there is nothing to surface here beyond the convergence. "
    f"We'll look again closer to kickoff, when confirmed line-ups and any late news can "
    f"pull the two numbers apart.",

    # 2 · market-efficiency
    f"{venue_label}'s line on {a} versus {b} is already sitting where the model would "
    f"put it, to within a point on every side. A market this efficient is doing its "
    f"job: the available information is priced, and there's no slow-moving line for the "
    f"engine to catch. The model's three-way read — {a} at {_pct(p_a)}, the draw at "
    f"{_pct(p_d)}, {b} at {_pct(p_b)} — tracks the market's shape closely enough that "
    f"the difference is noise, not edge. Pass is the right call when the price has "
    f"nothing left to give away. The interesting fixtures are the ones where the line "
    f"lags; today, this is not one of them.",

    # 3 · clear favourite priced right
    f"{fav} should win this one, and the price already knows it — the model lands "
    f"within a point of {venue_label} on all three sides, both pricing {fav} as the "
    f"clear favourite. The agreement is the point: when a strong side is also a short "
    f"price, there's rarely a gap to find, and forcing one would be the opposite of "
    f"useful. The model rates {fav} at {_pct(fav_mp)}; the market has them at "
    f"{_pct(fav_kp)}. Close enough that the only honest verdict is Pass. We'll revisit "
    f"near kickoff, when the confirmed eleven and any fitness news land — those are what "
    f"move a settled favourite, not the prior.",

    # 4 · close / even match
    f"{a} versus {b} is a genuinely close fixture, and both the model and {venue_label} "
    f"see it that way — no side carries enough probability to stand out, and the draw "
    f"holds real weight. The model's split reads {a} {_pct(p_a)}, draw {_pct(p_d)}, "
    f"{b} {_pct(p_b)}; the market's shape is the same to within a point. On a match this "
    f"even, a small gap on any one side is well inside the model's own margin, so there's "
    f"no conviction to publish. Pass is the call. A close game can swing on a single piece "
    f"of team news, so this is one to check again as kickoff approaches.",

    # 5 · low-confidence / uncertainty bands
    f"On {a} versus {b}, wherever the model and {venue_label} differ, the gap is smaller "
    f"than the model's own uncertainty about its number. The engine carries a confidence "
    f"band around every estimate, and here the market price sits comfortably inside it on "
    f"all three sides. That means any apparent edge is more likely measurement noise than "
    f"a real disagreement worth acting on. The model rates the three sides at {_pct(p_a)} "
    f"/ {_pct(p_d)} / {_pct(p_b)}, close to the market throughout. When the signal is "
    f"inside the noise, the honest verdict is Pass. We'll re-evaluate as the bands tighten "
    f"nearer kickoff.",

    # 6 · news-pending / late-binding
    f"For now, the model and {venue_label} agree on {a} versus {b} to within a point on "
    f"every side — and 'for now' is the operative phrase. The inputs that usually separate "
    f"two numbers — the confirmed eleven, fresh injury and fitness news, weather at the "
    f"venue — haven't landed yet, so today there's nothing pulling the prior away from the "
    f"price. That makes Pass the correct read today, not a permanent one. The model's "
    f"three-way ({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) sits on top of the market's "
    f"shape. The engine refreshes as kickoff nears; if news moves enough of the prior, "
    f"this can turn into a Pick. Until then, there's no gap to show.",

    # 7 · discipline / won't manufacture
    f"The honest read on {a} versus {b} is that there's no edge here: the model and "
    f"{venue_label} sit a point apart at most, on every side. Manufacturing a disagreement "
    f"out of that — talking up a tenth of a point as though it meant something — is the one "
    f"thing this desk won't do. The model's numbers ({_pct(p_a)} / {_pct(p_d)} / "
    f"{_pct(p_b)}) line up with the market's, and a verdict that admits as much is worth "
    f"more than a forced call. Pass means exactly what it says: we looked, the price is "
    f"fair, there's nothing to add today. We'll look again when there's something new to "
    f"weigh.",
]
blurb = pick("pass-blurb", pass_blurb_options)
```

---

## AVOID

(Per VOICE.md, Avoid is near-impossible on single-venue odds today, so this
register is mostly theoretical — but it should still vary. `edge` here is the
most-negative signed gap.)

### Titles (pool)

```python
avoid_title_options = [
    f"{a} v {b} · every side priced rich",
    f"{a} v {b} · the whole market reads short",
    f"{a} v {b} · no side offers value",
]
title = pick("avoid-title", avoid_title_options)
```

### Summaries (pool)

```python
avoid_summary_options = [
    f"Across {a} v {b}, every side is priced shorter than the model — the most-negative "
    f"gap is {edge:+.1f}pp. The state reads Avoid: no side offers value.",
    f"On {a} v {b}, {venue_label} is asking more than the model thinks any outcome is "
    f"worth, on all three sides. Avoid — no edge to take, even on the side closest to fair.",
    f"{venue_label} prices every outcome of {a} v {b} above the model's number. Avoid: "
    f"the whole market reads rich, not just one side.",
    f"The model sits below the market on all three sides of {a} v {b}, by as much as "
    f"{edge:+.1f}pp. Avoid — nothing here is priced in the reader's favour.",
    f"Every side of {a} v {b} is shorter on the market than on the model. That's an "
    f"Avoid, reported plainly so it doesn't read like a near-miss Pass.",
]
summary = pick("avoid-summary", avoid_summary_options)
```

### Blurbs (pool — 5–8 sentences, ~100–140 words)

```python
avoid_blurb_options = [
    # 1 · every-side-rich
    f"In {a} versus {b}, the model's number comes in below {venue_label}'s on all three "
    f"sides — the market is asking more for every outcome than the engine thinks it's "
    f"worth. The widest of those gaps is {edge:+.1f}pp. Avoid is the plain way to say "
    f"that nothing on this market is priced in the reader's favour, including the side "
    f"that comes closest to fair. There's no clever angle to add: when every outcome reads "
    f"rich, the useful thing is to point it out and move on. We report Avoid separately "
    f"from Pass so it isn't mistaken for a close call — this is a market to leave alone, "
    f"not one sitting on the edge of a Pick.",

    # 2 · discipline / why-separate
    f"{venue_label} prices every side of {a} versus {b} shorter than the model does, the "
    f"largest gap running to {edge:+.1f}pp. Where a Pass means the price is fair, an Avoid "
    f"means it's rich across the board — and the two deserve different words, because they "
    f"tell the reader different things. The model's three-way ({_pct(p_a)} / {_pct(p_d)} / "
    f"{_pct(p_b)}) sits under the market on each outcome. None of the three offers a gap "
    f"worth taking. The honest call is to step back: there's no side of this market the "
    f"engine would describe as good value, so we say so and leave it there.",

    # 3 · plain / no-drama
    f"For {a} versus {b}, the model rates all three outcomes lower than the market is "
    f"charging for them — the most-negative gap is {edge:+.1f}pp. There's nothing dramatic "
    f"to read into that; it simply means the whole market is priced ahead of the engine's "
    f"view, with no single side standing out as the culprit. Avoid is the right label, and "
    f"it's a quiet one. The model's split reads {_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}, "
    f"under the market throughout. We'll keep refreshing as kickoff nears — a rich market "
    f"can come back toward fair as money and news arrive — but as it stands, there's no "
    f"edge on offer here.",

    # 4 · closest-side-still-rich
    f"Every side of {a} versus {b} is priced above what the model makes it, so even the "
    f"outcome closest to fair doesn't clear into value — the best of a poor set is still "
    f"{edge:+.1f}pp short. That's what separates an Avoid from a Pass: here the market "
    f"isn't merely efficient, it's asking a premium on all three sides. The model's numbers "
    f"({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) sit under the market across the board. The "
    f"reader's takeaway is simple: there's no side of this one the engine would point to. "
    f"We surface it as Avoid so the absence of a good side is stated, not left to inference.",

    # 5 · short / leave-alone
    f"On {a} versus {b}, the market is shorter than the model on all three sides — the "
    f"widest gap is {edge:+.1f}pp against the reader. Avoid means what it says: this is a "
    f"market to leave alone. There's no outcome where the price and the model line up in a "
    f"way that would interest the engine, and pretending otherwise wouldn't help anyone. "
    f"The three-way model read ({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) stays under the "
    f"market throughout. It's a plain verdict for a plain situation — every side rich, "
    f"nothing to take.",
]
blurb = pick("avoid-blurb", avoid_blurb_options)
```

---

## Claude Code wiring notes (task 3)

1. In `_pass_copy` / `_avoid_copy`, compute the `fav` / `fav_kp` / `salt` /
   `pick()` locals shown above, then swap the single string for `pick(...)`.
2. Keep the existing `_with_chorus(blurb, i.get("editorial_citations"), salt=...)`
   call — the chorus still appends on top.
3. Keep `drivers` as-is (or vary later; not the duplicate-content driver).
4. `pytest` must stay green; `build_copy` already voice-checks every field, so a
   bad variant fails closed to empty `Copy()` rather than shipping.
5. Regenerate (`desk run --once` → `site/generate.py`), eyeball two Pass pages
   that previously read identical (e.g. Colombia–Portugal vs Panama–Croatia),
   push to `staging`.
