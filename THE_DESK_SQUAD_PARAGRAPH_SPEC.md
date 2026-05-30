# The Desk — Dedicated squad paragraph (XI + injuries + cards)

**Status:** v0.1, 2026-05-30. Author: Adi.

## Shipping status

- ✅ **PR Q1 — card-accumulation data path** (this commit). `desk/data/api_football/cards.py` + `card_accumulation` cache table + `CARD_RULES` + sanity gates (`check_card_counts`, `check_at_risk_not_suspended`). Off the hot path; nothing touches a published verdict yet. **Operator action pending:** confirm the WC26 yellow-card reset rule (wipe-after-QF) against the actual 2026 FIFA tournament regulations before `DESK_CARD_FETCH=1` goes live.
- ⬜ PR Q2 — fold cards into `TeamNews` (CardStatus + reconcile)
- ⬜ PR Q3 — match-blurb dedicated-paragraph mandate
- ⬜ PR Q4 — outright per-team squad_note
- ⬜ PR Q5 — `desk fetch-cards` + daily-tick wiring
**Extends:** `THE_DESK_TEAM_NEWS_BLURB_SPEC.md` (Slices A+B+C, shipped to staging 2026-05-30).
**Companion to:** `desk/VOICE.md`, `THE_DESK_OPTIMIZATION_SPEC.md` (B.3 injuries), `THE_DESK_DATA_LAYER_SPEC.md` (§5).

---

## Why

The team-news subsystem already fuses injuries + confirmed XI into the blurb, but it weaves them through the verdict prose. A reader scanning a Pick can't find "who's actually playing" without reading the whole thing. We want a **dedicated squad paragraph** in every match blurb (and the per-team outright surface) that does one job: tell the reader the opening XI, who's out, and who's a card away from being out.

This is a presentation + coverage change, not a model change. The verdict and Elo numbers don't move. We're making the squad picture a first-class, predictable block of prose.

## What "squad paragraph" means (decisions locked 2026-05-30)

1. **Structure — mandated paragraph inside `copy.blurb`.** No new contract field, no ADR. Haiku is instructed to write the squad picture as its own self-contained paragraph within the existing blurb. The website renders `copy.blurb` as it does today; the squad content is just a recognisable paragraph inside it.
2. **Cards — confirmed bans AND at-risk.** Cover players actually suspended (red-card sending-off ban or yellow-accumulation ban already triggered) *and* players "one booking away" from a ban. At-risk needs card-accumulation data we don't fetch today — see PR Q1.
3. **Surfaces — match pages AND outright/per-team.** Both the per-match blurb and the WC26 per-team ladder surface get a squad summary.

## Scope of one squad paragraph

Per side, in priority order, as available:

- **Opening XI** — starters + formation when `lineup.state="confirmed"` (already in `LineupStatus.starters` / `.formation`). Name 1–2 recognisable starters, not the full 11.
- **Out** — injuries + confirmed suspensions (already in `TeamNews.absences`, types `injury` / `suspension`).
- **At-risk** — players carrying enough yellow cards that one more booking = a ban. NEW. See PR Q1.

When none of the above is known for either side, **no squad paragraph is written** (same silence rule as `materiality=none` today).

---

## Audit — what already exists vs. the gap

| Capability | Where | Status |
|---|---|---|
| Confirmed XI (starters + formation) | `LineupRow` / `LineupStatus`, `desk fetch-lineups` | Live (Slice B). |
| Injuries + confirmed suspensions | `InjuryRow.type ∈ {Missing Fixture, Suspended}`, `TeamNews.absences` | Live (Slice A + B.3). |
| Per-team materiality directive | `TeamNews.materiality` | Live (Slice A). |
| Blurb addresses team news in prose | `haiku.py:_SYSTEM_PROMPT` TEAM NEWS POLICY | Live — but woven, not a dedicated paragraph. |
| **Yellow-card accumulation / at-risk** | — | **Does not exist.** api-football `/injuries` only reports an *already-triggered* `Suspended`. Nothing tracks "2 yellows, one from a ban". |
| **Squad paragraph on outright/per-team surface** | — | **Does not exist.** Outright explainer (`desk/outrights/explainer.py`) has no team-news input. |

**The gap is two-sided:** (a) a new data path for at-risk cards, and (b) a prompt/render contract that forces the squad picture into its own paragraph on both surfaces.

---

## Spec — five PRs

PRs Q1–Q2 build the **data path** (at-risk cards → payload).
PR Q3 is the **match-blurb prompt** (dedicated paragraph mandate + post-checks).
PR Q4 extends the **outright/per-team surface**.
PR Q5 is the **cadence** (card data refresh).

### PR Q1 — card-accumulation data path

api-football has no "at-risk" field, so derive it. Two viable sources; pick by cost:

- **Preferred:** `/fixtures/players?fixture={id}` per played tournament fixture → per-player `cards.yellow` / `cards.red`. Accumulate yellows per player across the tournament's played fixtures, apply the competition's threshold + reset rule.
- **Cheaper fallback:** `/players?team={id}&season={year}&league={wc26_league_id}` → `statistics[].cards.yellow`. Coarser (season totals, not tournament-scoped) but one call per team instead of per fixture. Acceptable for v1 if the per-fixture cost trips the budget.

New module `desk/data/api_football/cards.py` + a `card_accumulation` cache table:

```sql
CREATE TABLE IF NOT EXISTS card_accumulation (
    api_football_team_id  INTEGER NOT NULL,
    player_id             INTEGER NOT NULL,
    player_name           TEXT    NOT NULL,
    position              TEXT,
    yellows               INTEGER NOT NULL,   -- accumulated this competition
    reds                  INTEGER NOT NULL,   -- sending-offs this competition
    at_risk               INTEGER NOT NULL,   -- 1 when yellows == threshold-1
    competition           TEXT    NOT NULL,   -- "wc26" — scopes the reset rule
    computed_at           TEXT    NOT NULL,
    source_endpoint       TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (api_football_team_id, player_id, competition)
);
```

Delete-then-insert per team per refresh, exactly like `injuries`.

**Competition card rules** live in config, not hard-coded. WC 2026: a player is suspended after **two yellow cards in separate matches**; accumulated yellows are **wiped after the quarter-finals** (standard FIFA rule — confirm against the final WC26 tournament regulations before flipping live). So:

```python
CARD_RULES = {
    "wc26": {"yellow_ban_threshold": 2, "wipe_after_stage": "quarter_final"},
}
```

`at_risk = (yellows == threshold - 1)` and the player is in the next fixture's squad and not already suspended. Stage-wipe handling: when the tournament passes the wipe stage, accumulated yellows reset to 0 (the refresh recomputes from fixtures, so this falls out naturally if we only count fixtures after the wipe boundary).

**Sanity gates** (mirror `api_football/sanity.py`): reject negative card counts, reject `yellows > 20` (data error), reject a player flagged both `Suspended` (injuries) and `at_risk` (cards) for the same fixture — a player can't be at-risk *and* already banned; prefer the suspension.

Gate fetch on `DESK_CARD_FETCH=1`. Off by default.

### PR Q2 — fold cards into `TeamNews`

Extend `PlayerAbsence` (or add a sibling) so the payload carries at-risk separately from out:

```python
@dataclass(frozen=True)
class CardStatus:
    name:        str
    position:    str | None
    yellows:     int
    state:       Literal["at_risk", "banned"]   # banned = already suspended
    source:      str            # "api-football"
    source_url:  str | None     # set when an RSS outlet covered it
    importance:  Literal["high", "medium", "low"]
```

Add `cards: tuple[CardStatus, ...]` to `TeamNews`. Build it in `team_news.py:build_team_news` from the `card_accumulation` cache (`at_risk=1` → `state="at_risk"`), and reconcile with `absences`: a player already in `absences` as a `suspension` is dropped from `cards` (no double-count). `banned` entries in `cards` are redundant with `absences` — keep `cards` to `at_risk` only in v1; `banned` is reserved for a future merge.

**Materiality:** at-risk does NOT raise materiality on its own (it's an availability *risk*, not a *fact*). A squad paragraph still fires whenever there's a confirmed XI or any absence; at-risk players ride along when the paragraph exists. If the only thing known is "one player at risk", that's `materiality=low` — optional mention.

Builder never raises; cold card cache → empty `cards` tuple → identical to today.

### PR Q3 — match-blurb dedicated-paragraph mandate

Update `_SYSTEM_PROMPT` in `desk/explainer/haiku.py`. Replace the woven TEAM NEWS POLICY guidance with a **SQUAD PARAGRAPH** mandate:

```
SQUAD PARAGRAPH

When either side has a confirmed XI, an absence, or an at-risk player,
the blurb MUST contain ONE dedicated paragraph covering the squad
picture, kept separate from the verdict/edge paragraph. It covers, in
order, only what is known:

  1. Opening XI — when lineup.state="confirmed", name the formation
     once and 1-2 recognisable starters. ("France open 4-3-3 with
     Mbappé and Dembélé.") Never list all 11.
  2. Out — name absent players (injury / suspension), attributing to an
     outlet when source_url is present, stating the fact unattributed
     when source is api-football.
  3. At-risk — name players one booking from a ban, phrased as risk,
     never as fact. ("Tchouaméni is one yellow from a suspension.")

If only some of the three are known, write only those. If none are
known for either side, write NO squad paragraph and say nothing about
availability — silence is the rule when there's no data.

NEVER invent a starter, an absence, a formation, or a card count.
NEVER name a player who is not in starters[], absences[], or cards[].
NEVER present at-risk as a confirmed ban.
```

`_format_team_news` already renders absences + lineup; extend it to render the `cards` block (name, yellows, state) so Haiku sees the at-risk list.

**Post-checks** (`post_check`, strict under `DESK_TEAM_NEWS_BLURB_REQUIRED=1`):

- Existing `materiality=high` → must name an absent player (unchanged).
- NEW: when a side has at-risk cards AND the blurb mentions a ban/suspension keyword, an at-risk player named must be phrased as risk, not as already out. (Heuristic: if an at-risk player's name is within N words of "suspended/banned/out", warn — soft guard, fall back only in strict mode.)
- Existing `materiality=none` both sides → no availability keywords (unchanged; "at risk" / "one booking" added to the keyword set so a hallucinated card story is caught).

Word budget: a dedicated paragraph pushes the blurb longer. Raise `_BLURB_MAX_WORDS` to **240** when either side has a non-empty squad picture (lineup confirmed OR absences OR at-risk). Keep 220 otherwise.

### PR Q4 — outright / per-team squad summary

The outright surface (`desk/outrights/`) has no team-news input today. Add a **compact** squad line per team to the per-team ladder JSON — not a full paragraph (the ladder is dense). Shape:

```json
{
  "team": "France",
  "squad_note": "Out: Saliba (injury). One booking from a ban: Tchouaméni."
}
```

- Reuse `build_team_news` keyed on the team's ISO3 (no fixture context, so `lineup` will usually be `unknown` between matches — that's fine; the outright surface is about availability, not next-match XI).
- Render via a small deterministic template (NOT Haiku — the ladder has 48 teams; a per-team Haiku call is overkill and the line is mechanical). Template: `Out: {names}. One booking from a ban: {names}.`, omitting empty clauses, empty string when nothing known.
- `squad_note` is internal to the outright JSON's ladder rows; surfacing it on the website is a frontend task (Adi's surface) tracked separately.

This is additive to the outright ladder row — confirm whether it needs the outright contract's ADR treatment (the per-match contract is frozen; the outright JSON is looser). If yes, raise the ADR before shipping Q4.

### PR Q5 — card-data refresh cadence

Cards change per match, not per minute, so the daily tick is enough — no T-90m loop needed (unlike confirmed XI). Add `desk fetch-cards` to the daily refresh tick in `desk_refresh_loop.py`, gated on `DESK_CARD_FETCH=1`, running after `desk fetch-injuries`. Cost: ~1 call/team/tick on the cheaper `/players` path (~48 calls), or ~1 call per played tournament fixture on the per-fixture path. Both sit well inside the Pro cap; confirm with `desk rate-budget` before flipping live.

---

## Voice rules (additions to `desk/VOICE.md`)

- **At-risk is a risk, never a fact.** "One yellow from a ban" / "a booking away from missing the next round". Never "will be suspended".
- **Squad paragraph stands alone.** It is its own paragraph, not a clause bolted onto the edge statement.
- **Name players, not positions** (existing rule, restated — applies to at-risk too).
- **Don't pad.** If only the XI is known, the squad paragraph is one or two sentences. No "no other injury concerns" filler.

---

## Env vars (new)

| Variable | Default | Purpose |
|---|---|---|
| `DESK_CARD_FETCH` | `0` | Set to `1` to fetch card accumulation per team on the daily tick. Needs `API_FOOTBALL_KEY`. Off by default. |
| `DESK_CARD_AT_RISK` | `1` | When `1`, at-risk players are threaded into the squad paragraph. Set `0` to ship bans-only while the at-risk derivation is being validated. |

(`DESK_TEAM_NEWS_BLURB_REQUIRED` from the team-news spec also gates the new squad post-checks.)

---

## Acceptance criteria

1. A WC26 match with a confirmed XI + one injury produces a blurb whose squad content is a **single dedicated paragraph** naming the formation, ≥1 starter, and the injured player — separate from the edge paragraph.
2. A WC26 match where a player has 1 yellow (threshold 2) produces a blurb that names that player as "one booking from a ban", phrased as risk. The `card_accumulation` row shows `at_risk=1`.
3. A player who is already `Suspended` (injuries) is NOT also listed as at-risk — the reconcile in Q2 drops the duplicate.
4. A match with no XI, no absences, no at-risk produces a blurb with **no squad paragraph** and no availability keywords (materiality=none guard holds).
5. The outright per-team ladder carries a deterministic `squad_note` string (empty when nothing known); no Haiku call per team.
6. `DESK_BLURB_HAIKU=0` (stub) and `DESK_CARD_FETCH=0` both leave today's behaviour byte-identical. Backtest unchanged.

---

## Open questions / risks

- **WC26 card-reset rule must be confirmed** against the published 2026 tournament regulations before `DESK_CARD_FETCH=1` goes live. The "wipe after QF" assumption follows 2022; FIFA occasionally adjusts. Wrong rule → false at-risk flags after the QFs.
- **At-risk needs tournament-scoped yellows.** The cheaper `/players?season=` path gives season totals, which over-counts (friendlies, qualifiers). If accuracy matters, the per-fixture `/fixtures/players` path is correct but costs more calls. Start on the cheap path; upgrade if the operator sees wrong flags.
- **Word budget creep.** A dedicated squad paragraph + the model/market framing + the press chorus all compete. The 240-word allowance helps, but watch for Haiku dropping the edge statement. If it does, the post-check that requires the edge framing should stay; squad paragraph compresses first.
- **Outright `squad_note` contract.** Confirm whether the outright JSON is frozen enough to need an ADR for the new field. Per-match contract is; the outright shape predates the waist refactor and is looser.
- **Card data latency.** A red card in a match that just kicked off won't show until api-football settles the fixture (similar to the 30h settle on results). At-risk for the *next* match is computed from *settled* fixtures, so a same-day double-booking edge case can lag. Acceptable for v1.

---

## Out of scope

- Surfacing `squad_note` visually on the website (Adi's frontend surface — separate task).
- Per-player injury severity / return-date estimates.
- In-match card tracking / live updates (engine is pre-kickoff only).
- Non-WC competitions' card rules (add to `CARD_RULES` when those competitions are ingested).
