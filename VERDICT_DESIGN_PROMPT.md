# Verdict section — design brief for Claude Design

A self-contained brief for a Claude Design session. Attach the Odds Primer Design System folder so Claude Design can pick up the tokens, type, and voice rules automatically. Then paste the brief below.

---

## How to use this in Claude Design

1. **Attach the design system.** Connect the `Odds Primer Design System/` folder so Claude Design reads `colors_and_type.css` (tokens), `README.md` (voice + content rules), and the existing mockups (`market-v2.html`, `home-v2.html`).
2. **Paste the brief.** Use the section headed "Brief" below as your initial description.
3. **Iterate, don't re-describe.** Claude Design's strength is the refine loop — once you have a first version, use chat, inline comments, and the layout sliders to push it. Resist starting over.
4. **Ask for variants explicitly.** When you want to compare directions, say *"Show me a stamp version, a newspaper-deck version, and a spec-sheet version side by side"* — don't ask in one go. Claude Design works best one direction at a time.
5. **Export when a direction is locked.** PDF / URL / PPTX, then drop the URL into the team for review.

---

## Brief

> Paste from here ↓

Design the **verdict section** for Odds Primer — an editorial oddschecker for prediction markets, launching with a 2026 World Cup edition. The verdict is the heart of the product. It's where the price comparison, the price-history chart, the score model, and the editorial reasoning all converge into one decisive statement, and it's the moment we hand the reader off to Kalshi or Polymarket via "Open on [venue] ↗".

The verdict has to do three jobs at once:

1. **Tell the reader what to do (or not do) at a glance** — Pick / Pass / Avoid.
2. **Justify the call without being preachy** — two short reasons, anchored in the data.
3. **Carry the venue handoff** when there's a pick — venue, price, a clear way to open.

It must read as editorial, anti-promo, decisive but never pushy. A magazine column printing its conclusion at the top, not a tipster shouting a lock.

### The three states

| State | Example | What it conveys |
|---|---|---|
| **Pick** | Back France on Polymarket at −180 | Side, venue, line, why, a CTA to open |
| **Pass** | No edge — markets agree within 1pp | Nothing to do, why we're sitting it out |
| **Avoid** | Skip Germany v Japan — line short on both | Both venues priced inside our number, no value, **no venue link** |

Pass and Avoid must look different from Pick (not actionable in the same way) and from each other (Avoid is a stronger, named opinion; Pass is a quiet shrug). All three must read as the same product.

### Constraints — non-negotiable

These come from the locked design system. Claude Design should already enforce most of them via the attached files; calling them out here so they're not lost in the iteration.

- No traffic-light colors. Best price is bold ink + a flame underline + a "best" eyebrow tag. Green/red is reserved for low-saturation movement deltas on charts.
- No promo language. Never "bet now," "buy now," "cash in," "lock," "free bet," "smart money." The handoff is `Open on Polymarket ↗` — neutral, named, never anonymized.
- Sentence case for every label, headline, and button.
- No emoji. Footnote daggers (`†`, `‡`, `§`), em-dashes, and the bars glyph are the only ornaments.
- Editorial voice — informed but humble, second-person when teaching, first-person plural for editorial decisions, never "I." Short paragraphs, no exclamation marks.
- Source Serif 4 for headlines + body, Inter Tight for chrome, JetBrains Mono for prices. CSS variables only.
- The bars glyph is the system mark. Growing bars for Pick. Declining bars for Avoid. Use the glyph; don't invent new icons unless language is slower than a glyph.

### Anti-patterns

If a direction starts to feel like any of these, kill it and try another:

- A sportsbook callout — even with neutral language, if the visual reads "casino card," it's wrong.
- A confidence meter or star rating — we don't tip, we explain.
- A prediction-market dashboard widget — too utility, not editorial enough.
- Glassmorphism, gradients, or colored shadows — explicitly excluded by the design system.
- A "smart pick of the day" badge — that's tipster vocabulary.

### What I want to see first

Start with **one** direction — your best take — that demonstrates all three states stacked on a single page, using these fixtures:

- Pick: France v Mexico, Group D, 12 Jun. Score 68%, Polymarket −180.
- Pass: Tunisia v Australia, Group D, 12 Jun. Markets agree within 1pp.
- Avoid: Germany v Japan, Group E, 13 Jun. Both venues priced inside our 54% score.

Show the verdict block by itself first — no surrounding page chrome — so we can judge it on its own merits. Once we've landed the verdict, we'll talk about how it sits inside the match page.

### What I'll ask next

After the first version, I'll likely want to:

- Try a different visual direction (stamp / newspaper deck / spec sheet / ticket stub / weather report).
- See three different copy variants for the verdict line — verb-first, subject-first, and editorial-first — to feel out the voice.
- Decide whether the score strip (Kalshi implied / Polymarket implied / our score) and the tip chips ("Built from 7 tips") sit inside the verdict block or below it.

Don't pre-emptively show all of these. One direction, well-resolved, then we iterate.

> ↑ End of paste.

---

## Reference: the current state

The existing verdict block is in `Odds Primer Design System/mockups/market-v2.html` (selector: `.verdict-block`). It's a working starting point — flame left-border, display-serif action verb, mono price line with venue dot, ink button for "Open on Polymarket". Claude Design should treat it as a baseline to evolve from, not a constraint to preserve.
