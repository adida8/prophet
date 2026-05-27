"""Tests for the outright backtest harness.

Three layers of concern:
  1. Tournament structure refactor — model.run_sim handles WC22's
     8-group / R16 / top2 shape as cleanly as WC26's 12-group / R32 /
     top2+8thirds shape.
  2. Scoring functions are correct and well-behaved (uniform baseline
     has the expected Brier; the winner's probability dominates the
     log score).
  3. End-to-end WC22 backtest produces a credible ranking — Argentina
     in the top half, p_win sums to 1, dashboard renders without
     blowing up.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from desk.outrights.backtest.runner import run_backtest, run_wc22
from desk.outrights.backtest.scoring import (
    ScoreBundle,
    score,
    uniform_distribution,
)
from desk.outrights.backtest.wc22_data import (
    GROUPS,
    R16_TIES,
    TRUE_WINNER,
    field,
    load_elo_lookup,
    wc22_structure,
)
from desk.outrights.model import run_sim


# ── data sanity ─────────────────────────────────────────────────────


def test_wc22_field_is_32_unique_teams() -> None:
    f = field()
    assert len(f) == 32
    assert len(set(f)) == 32


def test_wc22_groups_are_8_of_4() -> None:
    assert len(GROUPS) == 8
    for letter, teams in GROUPS.items():
        assert len(teams) == 4, f"group {letter} has {len(teams)} teams"


def test_wc22_r16_has_8_ties_referencing_valid_slots() -> None:
    assert len(R16_TIES) == 8
    valid_slots = {f"{g}1" for g in GROUPS} | {f"{g}2" for g in GROUPS}
    for left, right in R16_TIES:
        assert left in valid_slots,  f"R16 tie slot {left!r} invalid"
        assert right in valid_slots, f"R16 tie slot {right!r} invalid"


def test_wc22_elo_loads_for_every_team() -> None:
    elo = load_elo_lookup()
    for team in field():
        assert team in elo, f"missing Elo for {team}"
        assert 1000 < elo[team] < 2500, f"{team} Elo out of range: {elo[team]}"


# ── model.run_sim handles WC22 structure ───────────────────────────


def test_run_sim_wc22_p_win_sums_to_one() -> None:
    elo = load_elo_lookup()
    out = run_sim(
        wc22_structure(),
        elo,
        sims=400,
        bootstrap_samples=3,
        bootstrap_sims=50,
    )
    s = sum(out.p_win.values())
    assert abs(s - 1.0) < 1e-6, f"p_win sums to {s}, expected 1.0"


def test_run_sim_wc22_top_contenders_lead_the_field() -> None:
    """Brazil + Argentina + France should be near the top — same Elo
    favourites as the historical consensus.
    """
    elo = load_elo_lookup()
    out = run_sim(
        wc22_structure(),
        elo,
        sims=1500,
        bootstrap_samples=3,
        bootstrap_sims=50,
    )
    top5 = sorted(out.p_win, key=lambda t: -out.p_win[t])[:5]
    favourites = {"Brazil", "Argentina", "France"}
    # All three should be in the top 5 of a credible model.
    assert favourites.issubset(set(top5)), (
        f"pre-WC22 Elo favourites not in top 5; got {top5}"
    )


# ── scoring ─────────────────────────────────────────────────────────


def test_uniform_brier_matches_closed_form() -> None:
    """Uniform 1/N over N teams against one winner: Brier =
    (1 − 1/N)² + (N−1)·(1/N)² = (N−1)/N. For N=32 → ~0.9688.
    """
    f = field()
    n = len(f)
    expected = (n - 1) / n
    s = score("uniform", uniform_distribution(f), winner=TRUE_WINNER, field=f)
    assert abs(s.brier - expected) < 1e-9
    # Winner is in the field, so log_score should be log(N).
    import math
    assert abs(s.log_score - math.log(n)) < 1e-9


def test_score_returns_zero_brier_for_perfect_prediction() -> None:
    """Distribution that puts all mass on the winner scores Brier 0."""
    f = field()
    perfect = {t: 1.0 if t == TRUE_WINNER else 0.0 for t in f}
    s = score("perfect", perfect, winner=TRUE_WINNER, field=f)
    assert s.brier == 0.0
    assert s.winner_rank == 1
    assert s.top3_hit and s.top5_hit and s.top8_hit


def test_score_winner_rank_is_1_indexed() -> None:
    f = ("A", "B", "C", "D")
    p = {"A": 0.1, "B": 0.5, "C": 0.3, "D": 0.1}
    s = score("test", p, winner="B", field=f)
    assert s.winner_rank == 1
    s = score("test", p, winner="C", field=f)
    assert s.winner_rank == 2
    s = score("test", p, winner="D", field=f)
    # Tie between A and D at 0.1 each — rank index depends on iteration
    # order. The sorted call is stable, so D (later in field) ranks
    # behind A — rank 4 deterministically. But we only assert the loose
    # property: winner not in top 2.
    assert s.winner_rank > 2


# ── end-to-end ──────────────────────────────────────────────────────


def test_run_wc22_argentina_in_top_8() -> None:
    """Sanity check on the engine — the actual winner should land
    somewhere credible in our pre-tournament distribution. Argentina
    was a top-5 pick by every major book; if our model ranks them
    outside the top 8, something's badly miscalibrated.
    """
    result = run_wc22(sims=1500, bootstrap_samples=3, bootstrap_sims=50)
    assert result.model_score.top8_hit, (
        f"Argentina ranked #{result.model_score.winner_rank} pre-WC22 — "
        f"engine should put a top-5 historical favourite in the top 8."
    )


def test_run_backtest_writes_dashboard() -> None:
    """End-to-end smoke: backtest runs, dashboard file appears and is
    non-trivial."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "dashboard.html"
        summary = run_backtest(
            tournament_key="wc-2022",
            dashboard_path=path,
            sims=400,
            bootstrap_samples=3,
            bootstrap_sims=50,
        )
        assert path.exists()
        body = path.read_text(encoding="utf-8")
        assert "Outright backtest" in body
        assert "WC 2022" in body
        assert "Argentina" in body
        assert summary["winner"] == "Argentina"
        assert summary["tournament"] == "wc-2022"


def test_run_backtest_rejects_unknown_tournament() -> None:
    import pytest
    with pytest.raises(ValueError, match="unknown outright backtest tournament"):
        run_backtest(
            tournament_key="bogus-2099",
            dashboard_path=Path("/tmp/should-not-write.html"),
        )
