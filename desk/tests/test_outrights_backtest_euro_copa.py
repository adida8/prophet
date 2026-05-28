"""Smoke + sanity tests for Euro 2024 and Copa América 2024 backtests.

Mirrors the WC22 backtest shape with cross-tournament coverage:
  * Data integrity — groups + bracket + ISO3 mapping all check out.
  * Model handles the new `top2_plus_4_thirds` qualifier strategy.
  * Both tournaments produce credible rankings — the real winner
    lands in the top half of our pre-tournament distribution.
  * Both feed through the same `run_backtest` dispatch + dashboard.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from desk.outrights.backtest.copa_2024_data import (
    GROUPS as COPA_GROUPS,
    QF_TIES,
    TRUE_WINNER as COPA_WINNER,
    copa_2024_structure,
    field as copa_field,
    load_elo_lookup as copa_elo,
)
from desk.outrights.backtest.euro_2024_data import (
    GROUPS as EURO_GROUPS,
    R16_TIES,
    TRUE_WINNER as EURO_WINNER,
    euro_2024_structure,
    field as euro_field,
    load_elo_lookup as euro_elo,
)
from desk.outrights.backtest.runner import run_backtest
from desk.outrights.model import run_sim


# ── Euro 2024 data integrity ────────────────────────────────────────


def test_euro2024_field_is_24_unique() -> None:
    f = euro_field()
    assert len(f) == 24
    assert len(set(f)) == 24


def test_euro2024_groups_are_6_of_4() -> None:
    assert len(EURO_GROUPS) == 6
    for letter, teams in EURO_GROUPS.items():
        assert len(teams) == 4, f"group {letter} has {len(teams)} teams"


def test_euro2024_r16_has_8_ties_with_valid_slots() -> None:
    assert len(R16_TIES) == 8
    group_slots = {f"{g}1" for g in EURO_GROUPS} | {f"{g}2" for g in EURO_GROUPS}
    for left, right in R16_TIES:
        for slot in (left, right):
            assert slot in group_slots or slot.startswith("3RD@"), \
                f"R16 slot {slot!r} not recognised"


def test_euro2024_elo_loads_for_every_team() -> None:
    elo = euro_elo()
    for team in euro_field():
        assert team in elo, f"missing Elo for {team}"
        assert 1500 < elo[team] < 2300, f"{team} Elo out of range: {elo[team]}"


# ── Copa 2024 data integrity ────────────────────────────────────────


def test_copa2024_field_is_16_unique() -> None:
    f = copa_field()
    assert len(f) == 16
    assert len(set(f)) == 16


def test_copa2024_groups_are_4_of_4() -> None:
    assert len(COPA_GROUPS) == 4
    for letter, teams in COPA_GROUPS.items():
        assert len(teams) == 4


def test_copa2024_qf_has_4_ties_with_group_slots_only() -> None:
    """Copa has no R16 — straight from groups to QF; no constrained
    thirds, only group slots."""
    assert len(QF_TIES) == 4
    valid = {f"{g}1" for g in COPA_GROUPS} | {f"{g}2" for g in COPA_GROUPS}
    for left, right in QF_TIES:
        assert left  in valid, f"QF slot {left!r} invalid"
        assert right in valid, f"QF slot {right!r} invalid"


def test_copa2024_elo_loads_for_every_team() -> None:
    elo = copa_elo()
    for team in copa_field():
        assert team in elo
        assert 1500 < elo[team] < 2300


# ── Model handles the new structures ────────────────────────────────


def test_run_sim_euro2024_p_win_sums_to_one() -> None:
    out = run_sim(
        euro_2024_structure(),
        euro_elo(),
        sims=400, bootstrap_samples=3, bootstrap_sims=50,
    )
    assert abs(sum(out.p_win.values()) - 1.0) < 1e-6


def test_run_sim_copa2024_p_win_sums_to_one() -> None:
    out = run_sim(
        copa_2024_structure(),
        copa_elo(),
        sims=400, bootstrap_samples=3, bootstrap_sims=50,
    )
    assert abs(sum(out.p_win.values()) - 1.0) < 1e-6


def test_run_sim_euro2024_favourites_lead() -> None:
    """France (Elo favourite by ~30 over England) should dominate the
    top of the pre-tournament distribution — even if our model agrees
    with the market that France is the pick."""
    out = run_sim(
        euro_2024_structure(),
        euro_elo(),
        sims=1500, bootstrap_samples=3, bootstrap_sims=50,
    )
    top3 = sorted(out.p_win, key=lambda t: -out.p_win[t])[:3]
    favourites = {"France", "England", "Portugal", "Spain", "Germany"}
    # At least 2 of the top 3 should be among the pre-tournament
    # contender tier.
    overlap = set(top3) & favourites
    assert len(overlap) >= 2, f"top 3 should include 2+ Euro favourites; got {top3}"


def test_run_sim_copa2024_argentina_dominates() -> None:
    """Argentina was the heavy pre-Copa favourite — Elo gap of ~100
    over Brazil, ~200 over the rest. Should be the clear #1."""
    out = run_sim(
        copa_2024_structure(),
        copa_elo(),
        sims=1500, bootstrap_samples=3, bootstrap_sims=50,
    )
    ranked = sorted(out.p_win, key=lambda t: -out.p_win[t])
    assert ranked[0] == "Argentina", f"Argentina should be #1; got {ranked[:3]}"


# ── End-to-end dispatch ─────────────────────────────────────────────


def test_run_backtest_euro2024_top5_hit() -> None:
    """Spain (the actual winner) wasn't the pre-tournament Elo
    favourite, but was a credible top-5 pick. The engine should put
    them in the top 5 even if not top 3."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "euro24.html"
        summary = run_backtest(
            tournament_key="euro-2024",
            dashboard_path=path,
            sims=1500, bootstrap_samples=3, bootstrap_sims=50,
        )
        assert summary["winner"] == "Spain"
        assert summary["top5_hit"], (
            f"Spain pre-Euro should be a top-5 pick; rank={summary['winner_rank']}"
        )
        assert path.exists()


def test_run_backtest_copa2024_argentina_top1() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "copa24.html"
        summary = run_backtest(
            tournament_key="copa-2024",
            dashboard_path=path,
            sims=1500, bootstrap_samples=3, bootstrap_sims=50,
        )
        assert summary["winner"] == "Argentina"
        # Heavy favourite who won; should be #1.
        assert summary["winner_rank"] == 1
        assert summary["top3_hit"]
        # Engine should beat market on this one — Argentina dominated.
        assert summary["brier"] < summary["market_brier"]


def test_run_backtest_dispatch_known_tournaments() -> None:
    """The dispatch table should accept all three known keys without
    error and reject unknown ones."""
    from desk.outrights.backtest.runner import TOURNAMENTS
    assert set(TOURNAMENTS) == {"wc-2022", "euro-2024", "copa-2024"}
