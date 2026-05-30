# The Desk — Team news in blurbs (injuries + lineups)

**Status:** v0.1 draft, 2026-05-30. Author: Adi.
**Companion to:** `THE_DESK_OPTIMIZATION_SPEC.md` (B.3), `THE_DESK_DATA_LAYER_SPEC.md` (§5), `THE_DESK_NEWS_SIGNALS_SPEC.md` (PR D + F), `desk/VOICE.md`.

---

## Why

Today the model can quietly absorb an injury via Elo penalty and the blurb stays silent on it. A reader looking at a Pick on Mexico without knowing Mexico's striker tore an ACL last Tuesday won't trust the call — even when the model already priced it in. The blurb has to **say what it knows about team news**, every time it's material.

Two specific surfaces the blurb must address:

1. **Injuries / suspensions** — who's out, why, how confident the source is.
2. **Lineups** — confirmed XI when announced (~1h pre-kickoff), expected XI changes otherwise.

Both already exist as plumbing somewhere in the engine. None of them reach Haiku's prompt today.

---

## Audit — what already exists

| Capability | Source | Status |
|---|---|---|
| Injury Elo penalty (position-weighted, capped) | `desk/data/api_football/injuries.py` + `injury_penalty.py` | Shadow. `DESK_INJURY_FETCH=1` fetches; `DESK_INJURY_PENALTY=1` applies. Audit passes (`desk b3-audit`). |
| Injury signals via RSS (Guardian, BBC, AS, Marca, etc.) | `desk/signals/hard_track.py` + `sports/football/hard_signals.py` | **Live in prod.** 5d late-binding window, -8 Elo each, -30 cap. Produces a `HardSignalAdjustment` audit row per signal applied. |
| `confirmed_lineup` signal type | `desk/signals/models.py:SignalType` + `extract.py` | Extracted by Haiku, routes to hard track when source `can_feed_model`. **Applies 0 Elo delta** (no v1 hook). |
| `predicted_lineup` signal type | same | Routes to editorial track. Surfaces as a `Citation` if it lands in `editorial_citations`. |
| api-football `/fixtures/lineups?fixture=X` | `desk/data/api_football/rate_budget.py:106` | **Reserved budget slot. Not implemented.** |
| Editorial citations on `MatchOutput.copy.editorial_citations` | `desk/signals/editorial.py` | Live. Up to 6 citations per match. |
| Haiku blurb writer (`DESK_BLURB_HAIKU=1`) | `desk/explainer/haiku.py` | Live, gated. System prompt sources `desk/VOICE.md`. |
| Haiku `Inputs` carries injury / lineup data | `desk/explainer/stub.py:Inputs` | **No.** Only Elo numbers + `editorial_citations`. |
| Haiku system prompt mandates addressing team news | `desk/explainer/haiku.py:_SYSTEM_PROMPT` | **No.** Voice doc covers tone, not topic coverage. |

**The gap:** the engine knows who's missing. The blurb writer doesn't.

---

## Spec — six PRs

PRs N1–N3 build the **data path**: get injuries + lineups into a structured per-fixture `TeamNews` object on Haiku's `Inputs`.
PRs N4–N5 build the **prompt path**: tell Haiku to address team news, and verify it does.
PR N6 is the **late-binding cadence** for confirmed XI.

### PR N1 — `TeamNews` payload type + Inputs wiring

Add a `TeamNews` dataclass that aggregates everything the blurb needs about one team's availability:

```python
@dataclass(frozen=True)
class PlayerAbsence:
    name:        str
    position:    str | None        # "Defender" / "Midfielder" / etc.
    type:        Literal["injury", "suspension"]
    reason:      str | None        # "Knock" / "Yellow accumulation" / etc.
    source:      str               # "api-football" or outlet name
    source_url:  str | None        # set when source is an outlet
    importance:  Literal["high", "medium", "low"]  # GK/CB/captain = high

@dataclass(frozen=True)
class LineupStatus:
    state:       Literal["confirmed", "predicted", "unknown"]
    formation:   str | None        # "4-3-3" / "3-5-2" — only when confirmed
    changes:     tuple[str, ...]   # short notes: "Mbappé replaces Dembélé"
    source:      str
    source_url:  str | None
    announced_at: datetime | None  # for confirmed XI freshness

@dataclass(frozen=True)
class TeamNews:
    team:        str
    absences:    tuple[PlayerAbsence, ...]
    lineup:      LineupStatus
    materiality: Literal["high", "medium", "low", "none"]  # see N4
```

Add two keys to `Inputs`:

```python
team_a_news: TeamNews | None
team_b_news: TeamNews | None
```

`materiality` is the **flag that tells Haiku whether to weight this heavily** — see PR N4. Computed deterministically from absence importance + Elo penalty magnitude (high if penalty ≥ 30 Elo or any GK/captain absence; medium 10–30 Elo; low <10 Elo; none = empty).

### PR N2 — TeamNews builder from existing sources

Build `TeamNews` in `desk/sports/football/team_news.py` (new module). Pulls from three sources, in priority order:

1. **api-football injuries cache** (`InjuryRow` rows for the team's `api_football_team_id`). Each row → `PlayerAbsence(source="api-football", source_url=None, importance=…)`.
2. **Hard-track Signals** (the same list that produced `HardSignalAdjustment`s). Each `INJURY` / `SUSPENSION` signal → a `PlayerAbsence` with `source=source_name`, `source_url=signal_url`. **Dedupe against (1)** by player-name match — when both agree, prefer the api-football row but carry the citation URL from the signal.
3. **`CONFIRMED_LINEUP` / `PREDICTED_LINEUP` signals** → `LineupStatus`. Confirmed wins over predicted. If neither, `LineupStatus(state="unknown")`.

Thread the builder into `FootballSport.decide_and_explain` right after `hard_adjustments` are computed (so we reuse the same `pairs`). Add the resulting `TeamNews` to the `build_copy` payload.

**Failure modes:** the builder never raises. If api-football cache is cold, the absences list just comes from RSS. If both are cold, `materiality="none"` and Haiku gets no team-news content — same as today.

### PR N3 — api-football lineups fetcher

Implement the reserved slot. New module `desk/data/api_football/lineups.py` mirroring `injuries.py`:

- `fetch_for_fixture(fixture_id, *, client)` → `(status, LineupRow | None)`.
- Cache key: `(fixture_id, fetched_at)`. New sqlite table `lineup_resolution`.
- `LineupRow` carries: formation, starters (11), substitutes, coach.
- Resolver: needs fixture-id mapping per match. Add `resolve_fixture_id(home_iso3, away_iso3, kickoff_utc)` to `desk/data/api_football/fixtures.py` (currently we only fetch last-N per team). Cache the resolution in `fixture_resolution`.
- Gate fetch on `DESK_LINEUP_FETCH=1`. Off by default.

Confirmed XI lands ~1h pre-kickoff. The daily 06:00 UTC tick will miss most matches. PR N6 handles that.

### PR N4 — Haiku prompt mandate for team news

Update `_SYSTEM_PROMPT` in `desk/explainer/haiku.py`. New section:

```
TEAM NEWS POLICY

You are given `team_a_news` and `team_b_news` — structured injury / 
suspension lists plus lineup status — for each side. The blurb MUST 
address team news according to this materiality matrix:

  materiality=high   → at least one sentence on the absences + their
                       impact. Name the player(s). Cite the source.
  materiality=medium → one short sentence noting the most important
                       absence.
  materiality=low    → optional; mention only if it fits the verdict
                       narrative (e.g. a Pick that depends on knowing
                       a key starter is fit).
  materiality=none   → say nothing about availability.

When lineup.state=="confirmed", lead with that: "Mexico go 4-3-3 with 
Vázquez in for Pizarro." Always cite the lineup source.

When you name a player whose absence comes from an RSS source (the
PlayerAbsence has a source_url), attribute to that outlet using the
allowed-attribution rules. When the absence comes from api-football
(no source_url), state the fact without attribution — api-football is
not an editorial outlet.

NEVER speculate about an absence we did not give you. NEVER invent
formations.
```

Add `_format_team_news()` to `build_user_message`. Rendered block right after the editorial_citations block. Compact JSON-ish, same style as citations.

### PR N5 — Blurb post-checks for team news

Extend `post_check` in `haiku.py`:

- When `materiality=="high"` for either side, the blurb MUST contain at least one player name from that side's absence list. Substring match, case-insensitive. Fail → stub fallback.
- When `lineup.state=="confirmed"` for either side, the blurb MUST mention the formation OR at least one named change. Fail → stub fallback.
- When `materiality=="none"` for both sides, the blurb MUST NOT contain injury / suspension / lineup-attribution keywords ("out", "injured", "suspended", "ruled out", "starting XI", "formation"). Prevents hallucinated team news.

These are mechanical guards: cheap, deterministic, fall-back-safe. If Haiku ignores the mandate the stub ships — better silent than wrong.

### PR N6 — Hourly tick for confirmed XI (T-90m polling)

Confirmed XI lands ~1h pre-kickoff. The daily tick misses it. Three options:

- **Option A (recommended):** Add a separate `desk lineups-refresh-loop.py` at the project root, polling every 15 min for fixtures with kickoff in the next 2h. Only calls `desk fetch-lineups --window 2h` + the publisher for affected matches. Costs ≈ (matches in next 2h × 4 polls / hr) — a typical WC26 day has ~4 matches → 16 calls/hr, well inside the 7,500/day Pro cap.
- **Option B:** Re-use the Ops dashboard schedule. Add a per-fixture entry "T-90m" that the loop honours. More work; less flexible.
- **Option C:** Ship without this loop. The daily tick catches lineups for fixtures whose kickoff lands ≥18h after the tick. For early-morning matches, blurbs ship with `lineup.state="predicted"` or `"unknown"` and Haiku says so explicitly.

Default to A. Gate on `DESK_LINEUP_LOOP_ENABLED=1`.

---

## Voice rules

Already in `desk/VOICE.md`; restating the specifics that matter here:

- **No tipster certainty.** Never "Mbappé will be the difference." Always "the model rates France at X% with Mbappé available."
- **Name the player, not the position.** "Mbappé out" beats "France's striker out".
- **Cite the source the first time you name a player.** "Per Guardian, Mbappé will miss the match with a calf strain." Subsequent references in the same blurb don't need re-attribution.
- **Don't combine api-football facts with a fake outlet attribution.** If the only source is api-football, state the fact unattributed. If a real RSS outlet covers it, prefer the outlet.
- **Confirmed XI > predicted XI > nothing.** Never present a predicted XI as confirmed.

---

## Env vars (new)

| Variable | Default | Purpose |
|---|---|---|
| `DESK_LINEUP_FETCH` | `0` | Set to `1` to enable api-football lineups fetch on every scheduled tick. Needs `API_FOOTBALL_KEY`. |
| `DESK_LINEUP_LOOP_ENABLED` | `0` | Set to `1` to run the T-90m lineup loop. |
| `DESK_LINEUP_LOOP_TICK_SEC` | `900` | Lineup-loop cadence (15 min). |
| `DESK_LINEUP_LOOP_WINDOW_HOURS` | `2` | How far ahead the lineup loop scans for kickoffs. |
| `DESK_TEAM_NEWS_BLURB_REQUIRED` | `0` | When `1`, materiality=high forces a stub fallback if Haiku doesn't name an absent player. When `0`, post-check is a soft warning (logged but not enforced). Ship `0` for the first week, `1` after the operator has eyeballed enough blurbs to trust the prompt. |

---

## Acceptance criteria

1. A WC26 match where api-football flags 3+ injuries (any of them GK / CB / captain) produces a published blurb that names at least one of those players, with `materiality=high` recorded in the run report.
2. A WC26 match within 90 minutes of kickoff, after `DESK_LINEUP_LOOP_ENABLED=1`, produces a published blurb that includes the confirmed formation OR at least one named change. Lineup loop logs show the api-football call landed within the window.
3. A WC26 match with no injuries, no suspensions, and an unknown lineup produces a published blurb that **does not** contain "out / injured / suspended / starting XI / formation". The materiality=none post-check would flag a regression if Haiku ever drifted.
4. `DESK_BLURB_HAIKU=0` (stub mode) still works; stub doesn't see `team_news` and prose is unchanged from today. No backward-incompatible Inputs changes.
5. Backtest stays byte-identical with `DESK_INJURY_PENALTY=0` (Shadow). The data flow into Haiku changes; the verdict doesn't.

---

## Open questions / risks

- **api-football injury position field is coarse** (`Defender` / `Midfielder` / `Attacker` / `Goalkeeper`). We can't distinguish a centre-back from a fullback without a `position_detailed` field that the audit hasn't confirmed exists. Importance ranking will be approximate. Acceptable for v1 — refine when the audit surfaces sub-position data.
- **Lineup source attribution.** api-football lineups are not an editorial outlet. When confirmed XI lands via api-football (not via an RSS confirmed_lineup signal), the blurb has to say "official lineup confirms…" without naming a press outlet. Voice rule needs explicit allowance for "official lineup" / "team announcement" as a bare attribution.
- **Word-count budget.** Adding mandatory team-news content to a 120–180-word blurb means other content compresses. The model + market gap statement, the cited press chorus, and now team news all compete for prose. Watch this — Haiku may start cutting the model/market framing. If so, widen `_BLURB_MAX_WORDS` to 240 for `materiality=high` only.
- **Same-player double-counting.** PR N2 dedupe is by player-name string match. Players with diacritic-stripping mismatches ("Vázquez" vs "Vazquez") will dupe. Cheap fix: NFD-normalise both sides of the comparison.
- **Stale lineup loop.** If the T-90m loop fails or the kickoff window is wrong (DST / TZ edge), the blurb ships with predicted-or-unknown. Acceptable — `materiality` defaults safe.
- **Phase B.3 graduation interaction.** PR N4's prompt mandate goes live whether `DESK_INJURY_PENALTY` is on or off. That's deliberate — the blurb addressing injuries is a separate decision from whether the model penalises Elo for them. The blurb can name an absence without the model having moved the number.

---

## Out of scope

- Manager quotes about lineups ("we'll rotate the XI") — already covered by the existing `MANAGER_QUOTE` signal track.
- Weather-driven lineup changes — Phase B.2's job.
- Outright winner blurb integration — handle when Phase B.3 penalty graduates and the outright sim absorbs injury Elo.
- Real-time push during a match — engine is pre-kickoff only by design.
