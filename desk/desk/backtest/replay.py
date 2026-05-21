"""Replay engine — re-run model + verdict against historical inputs.

Critical invariant: this module never imports from
`desk/sports/football/ingest/`. Historical Elo / market / venue data
flows through `desk/backtest/historical/` only. That's how we
guarantee no test silently uses today's Elo for a 2022 match.

Output: one `SnapshotRow` per (match × window). For a single
tournament that's ~64 matches × 4 windows = ~256 rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal

from desk.backtest.historical.elo import LookaheadError, get_elo, load_intl_elo_snapshot
from desk.backtest.historical.markets import HistoricalMatch
from desk.backtest.tournaments import Tournament
from desk.publish.contract import VerdictState
from desk.sports.football.data.elo_seed import is_altitude_acclimatised
from desk.sports.football.model import FootballFeatures, compute as compute_model
from desk.sports.football.teams import is_international_competition
from desk.sports.football.metadata.fifa import host_iso3_for_competition
from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.decide import decide as decide_verdict
from desk.verdict.persistence import WindowVerdict, apply_persistence_rule
from desk.verdict.thresholds import Thresholds, current as current_thresholds

log = logging.getLogger("desk.backtest.replay")

Window = Literal["T-38", "T-5", "T-1h", "KO"]
WINDOW_OFFSET: dict[Window, timedelta] = {
    "T-38": timedelta(days=38),
    "T-5":  timedelta(days=5),
    "T-1h": timedelta(hours=1),
    "KO":   timedelta(0),
}


@dataclass(frozen=True)
class SnapshotRow:
    """One backtest row: features + model + verdict + actual outcome."""
    match_id:    str
    window:      Window
    asof:        datetime

    # Features
    elo_a: float
    elo_b: float
    host_bonus_pp: float       # 0 or 75, applied to whichever side won it
    altitude_m: float
    weather_factor: float
    injury_factor: float

    # Model
    p_a: float
    p_draw: float
    p_b: float

    # Market (closing)
    market_p_a: float
    market_p_draw: float
    market_p_b: float

    # Actual (only at KO; else 0)
    actual_a: int
    actual_draw: int
    actual_b: int

    # Verdict
    verdict_state: str         # "pick" / "pass" / "avoid"
    verdict_side:  str | None
    verdict_market_venue: str | None
    verdict_edge_pp: float | None

    # Carried for the writer
    competition:  str = ""
    season:       str = ""
    tournament:   str = ""
    stage:        str = ""
    kickoff_utc:  datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    team_a:       str = ""
    team_b:       str = ""
    is_example:   str = ""

    @property
    def brier(self) -> float:
        """Three-way Brier: sum of squared errors of (p, outcome)."""
        return (
            (self.p_a    - self.actual_a)    ** 2
            + (self.p_draw - self.actual_draw) ** 2
            + (self.p_b    - self.actual_b)    ** 2
        )

    @property
    def market_brier(self) -> float:
        return (
            (self.market_p_a    - self.actual_a)    ** 2
            + (self.market_p_draw - self.actual_draw) ** 2
            + (self.market_p_b    - self.actual_b)    ** 2
        )


def _asof_for(window: Window, kickoff: datetime) -> datetime:
    return kickoff - WINDOW_OFFSET[window]


def _build_features(
    match: HistoricalMatch,
    *,
    elo_a: float,
    elo_b: float,
) -> FootballFeatures:
    competition_code = "wc26" if match.competition == "wc" and match.season == "2026" else f"{match.competition}{match.season[-2:]}"
    international = is_international_competition(competition_code) or match.competition in {"wc", "euro", "cma"}

    # Host iso3 — for WC 2022 the host was Qatar; for non-WC tournaments
    # we don't fire the bonus (host_iso3_for_competition returns ∅).
    venue_host_iso3: str | None = None
    if international and match.competition == "wc" and match.season == "2022":
        if match.team_a_iso3 == "qat" or match.team_b_iso3 == "qat":
            venue_host_iso3 = "qat"

    return FootballFeatures(
        team_a_name=match.team_a,
        team_b_name=match.team_b,
        team_a_elo=elo_a,
        team_b_elo=elo_b,
        is_international=international,
        team_a_iso3=match.team_a_iso3,
        team_b_iso3=match.team_b_iso3,
        venue_host_iso3=venue_host_iso3,
        venue_stadium=None,
        venue_altitude_m=match.venue_altitude_m,
        team_a_altitude_acclimatised=is_altitude_acclimatised(match.team_a_iso3),
        team_b_altitude_acclimatised=is_altitude_acclimatised(match.team_b_iso3),
    )


def _market_snapshot_from_close(match: HistoricalMatch) -> MarketSnapshot:
    """Build a one-venue MarketSnapshot from the closing odds we curated.

    The contract's `MarketVenue` enum only accepts the live venues
    (kalshi / polymarket), so historical closing odds are labelled
    "polymarket" to keep the published Verdict valid. The label is
    cosmetic — the verdict logic only uses the snapshot's prices, not
    the venue identity, and the backtest dashboard surfaces the closing
    line baseline separately under its own column.
    """
    return MarketSnapshot(
        match_id=match.match_id,
        asof=match.kickoff_utc,
        prices=(
            VenuePrice(venue="polymarket", side="a",    implied_p=match.market_p_a),
            VenuePrice(venue="polymarket", side="draw", implied_p=match.market_p_draw),
            VenuePrice(venue="polymarket", side="b",    implied_p=match.market_p_b),
        ),
    )


def replay_match(
    match: HistoricalMatch,
    *,
    window: Window,
    tour: Tournament,
    thresholds: Thresholds | None = None,
) -> SnapshotRow:
    """Reconstruct features at `window`, run model + verdict, return the row."""
    th = thresholds if thresholds is not None else current_thresholds()
    asof_dt = _asof_for(window, match.kickoff_utc)
    asof_d  = asof_dt.date()

    # Lookahead-safe Elo lookup. We use the latest snapshot ≤ asof.
    try:
        snap = load_intl_elo_snapshot(asof_d)
    except LookaheadError:
        # If `asof` predates everything we have, fall back to the
        # tournament's pinned pre-tournament snapshot date.
        pinned = datetime.strptime(tour.asof_elo_snapshot, "%Y%m%d").date()
        snap = load_intl_elo_snapshot(pinned)

    elo_a = get_elo(snap, match.team_a_iso3)
    elo_b = get_elo(snap, match.team_b_iso3)
    # Provenance: "wiki" if we found a real value in the snapshot; else "stub".
    src_a = "wiki" if match.team_a_iso3 in snap else "stub"
    src_b = "wiki" if match.team_b_iso3 in snap else "stub"

    import dataclasses
    features = _build_features(match, elo_a=elo_a, elo_b=elo_b)
    features = dataclasses.replace(
        features, team_a_elo_source=src_a, team_b_elo_source=src_b,
    )
    model_out = compute_model(features)
    market = _market_snapshot_from_close(match)

    # Backtest never drives a live CTA, but the contract requires a Pick
    # to carry a market_url. Pass a synthetic placeholder so the
    # algorithmic path produces the same verdicts it always did — this
    # URL is never written to disk for backtest output.
    verdict, _meta = decide_verdict(
        model_p={"a": model_out.p_a, "draw": model_out.p_draw, "b": model_out.p_b},
        model_p_lower={
            "a":    model_out.p_a_lower,
            "draw": model_out.p_draw_lower,
            "b":    model_out.p_b_lower,
        },
        market=market,
        sides=("a", "draw", "b"),
        elo_sources=(src_a, src_b),  # type: ignore[arg-type]
        match_id=match.match_id,
        team_a=match.team_a,
        team_b=match.team_b,
        thresholds=th,
        market_url=f"https://polymarket.com/event/{match.match_id}",
    )

    is_ko = window == "KO"
    actual_a    = 1 if (is_ko and match.winner_90min == "a")    else 0
    actual_draw = 1 if (is_ko and match.winner_90min == "draw") else 0
    actual_b    = 1 if (is_ko and match.winner_90min == "b")    else 0

    host_bonus = (
        max(0.0, model_out.elo_a_adj - elo_a) +
        max(0.0, model_out.elo_b_adj - elo_b)
    )

    return SnapshotRow(
        match_id=match.match_id,
        window=window,
        asof=asof_dt,
        elo_a=elo_a,
        elo_b=elo_b,
        host_bonus_pp=host_bonus,
        altitude_m=match.venue_altitude_m,
        weather_factor=1.0,
        injury_factor=1.0,
        p_a=round(model_out.p_a, 6),
        p_draw=round(model_out.p_draw, 6),
        p_b=round(model_out.p_b, 6),
        market_p_a=round(market.prices[0].implied_p, 6),
        market_p_draw=round(market.prices[1].implied_p, 6),
        market_p_b=round(market.prices[2].implied_p, 6),
        actual_a=actual_a,
        actual_draw=actual_draw,
        actual_b=actual_b,
        verdict_state=str(verdict.state),
        verdict_side=verdict.side,
        verdict_market_venue=verdict.market_venue if verdict.state == VerdictState.PICK.value or verdict.state == VerdictState.PICK else None,
        verdict_edge_pp=verdict.edge_pp,
        competition=tour.competition,
        season=tour.season,
        tournament=tour.name,
        stage=match.stage,
        kickoff_utc=match.kickoff_utc,
        team_a=match.team_a,
        team_b=match.team_b,
        is_example=f"BACKTEST {tour.competition} {tour.season}",
    )


def replay_tournament(
    matches: Iterable[HistoricalMatch],
    *,
    tour: Tournament,
    windows: tuple[Window, ...] = ("T-38", "T-5", "T-1h", "KO"),
    thresholds: Thresholds | None = None,
) -> list[SnapshotRow]:
    rows: list[SnapshotRow] = []
    for match in matches:
        for w in windows:
            try:
                rows.append(replay_match(match, window=w, tour=tour, thresholds=thresholds))
            except Exception as e:                # noqa: BLE001
                log.warning("replay failed for %s @ %s: %s", match.match_id, w, e)
    return _apply_multi_window_persistence(rows)


def _window_verdict_from_row(row: SnapshotRow) -> WindowVerdict:
    """Project a snapshot's verdict fields onto the persistence input."""
    return WindowVerdict(state=row.verdict_state, side=row.verdict_side)


def _apply_multi_window_persistence(rows: list[SnapshotRow]) -> list[SnapshotRow]:
    """Phase A.3 — gate each match's KO Pick on T-5 and T-1h agreement.

    A Pick at KO survives only when the same side was Picked at T-1h
    (and at T-5, when computed). Otherwise the KO row is rewritten to
    a Pass with no side / venue / edge — exactly as the live engine
    will publish it once PR 6 wires the persistence cache.

    Earlier-window rows (T-38 / T-5 / T-1h) are left untouched: the
    backtest workbook still surfaces them so the dashboard can show
    Pick churn across windows. Only KO is the published verdict.
    """
    import dataclasses

    by_match: dict[str, dict[str, SnapshotRow]] = {}
    for r in rows:
        by_match.setdefault(r.match_id, {})[r.window] = r

    out: list[SnapshotRow] = []
    for r in rows:
        if r.window != "KO":
            out.append(r)
            continue
        prior = {
            window: _window_verdict_from_row(snap)
            for window, snap in by_match[r.match_id].items()
            if window in ("T-5", "T-1h")
        }
        result = apply_persistence_rule(_window_verdict_from_row(r), prior_verdicts=prior)
        if result.persistent:
            out.append(r)
        else:
            out.append(dataclasses.replace(
                r,
                verdict_state="pass",
                verdict_side=None,
                verdict_market_venue=None,
                verdict_edge_pp=None,
            ))
    return out
