"""Replay-engine tests.

Frozen feature vectors per spec §3.2 acceptance — Argentina v Saudi
2022 at T−5 and KO. The Elo snapshot is the bundled 2022-11-20 file.
"""

from __future__ import annotations

import math

import pytest

from desk.backtest.historical.markets import load_tournament_matches
from desk.backtest.replay import replay_match, replay_tournament
from desk.backtest.tournaments import TOURNAMENTS


@pytest.fixture(scope="module")
def wc_2022_matches():
    return load_tournament_matches(TOURNAMENTS["wc-2022"])


@pytest.fixture
def arg_sau(wc_2022_matches):
    return next(m for m in wc_2022_matches if m.match_id == "wc22-c-arg-sau-20221122")


# ── Frozen vector: Argentina v Saudi Arabia at T-5 ───────────────────

def test_argentina_v_saudi_t5_replay(arg_sau) -> None:
    """Argentina's pre-WC Elo (~2142) vs Saudi (~1635) gives a heavy
    Argentina favourite. Closing line agrees. Verdict should be Pass —
    model and market both rate Argentina near 80%, edge < 3pp.
    """
    row = replay_match(arg_sau, window="T-5", tour=TOURNAMENTS["wc-2022"])
    assert row.window == "T-5"
    assert 0.78 <= row.p_a <= 0.92            # Argentina heavily favoured
    assert row.p_a > row.p_draw > row.p_b
    assert math.isclose(row.p_a + row.p_draw + row.p_b, 1.0, abs_tol=1e-9)
    # Pre-KO windows have all-zero outcomes by design.
    assert (row.actual_a, row.actual_draw, row.actual_b) == (0, 0, 0)
    assert row.market_p_a > 0.7
    assert row.verdict_state in {"pick", "pass", "avoid"}


# ── Frozen vector: Argentina v Saudi Arabia at KO ────────────────────

def test_argentina_v_saudi_ko_replay(arg_sau) -> None:
    """KO row attaches the actual 90' winner (Saudi → 'b'). Brier is
    huge for the model and the market because both confidently picked
    Argentina."""
    row = replay_match(arg_sau, window="KO", tour=TOURNAMENTS["wc-2022"])
    assert row.window == "KO"
    assert (row.actual_a, row.actual_draw, row.actual_b) == (0, 0, 1)
    # Both Brier scores should be > 1.0 — confidently wrong on the favourite.
    assert row.brier        > 1.0
    assert row.market_brier > 1.0
    # Sanity: probabilities still normalise.
    assert math.isclose(row.p_a + row.p_draw + row.p_b, 1.0, abs_tol=1e-9)


# ── Tournament-level invariants ──────────────────────────────────────

def test_replay_tournament_emits_one_row_per_match_and_window(wc_2022_matches) -> None:
    rows = replay_tournament(
        wc_2022_matches[:5], tour=TOURNAMENTS["wc-2022"],
        windows=("T-38", "T-5", "T-1h", "KO"),
    )
    assert len(rows) == 5 * 4

    by_match: dict[str, set] = {}
    for r in rows:
        by_match.setdefault(r.match_id, set()).add(r.window)
    assert all(ws == {"T-38", "T-5", "T-1h", "KO"} for ws in by_match.values())


def test_replay_does_not_import_live_ingest() -> None:
    """Critical invariant from spec §3.2: replay never reaches into the
    live football ingest paths. We assert by inspecting `replay`'s
    module imports.
    """
    import desk.backtest.replay as r
    forbidden_prefixes = (
        "desk.sports.football.ingest",
        "desk.ingest.polymarket_prices",
        "desk.ingest.kalshi_prices",
    )
    src = r.__file__
    with open(src, encoding="utf-8") as f:
        body = f.read()
    for prefix in forbidden_prefixes:
        assert prefix not in body, (
            f"replay.py must not import {prefix} — that would let "
            "today's data leak into a historical replay"
        )


# ── Brier scoring sanity ─────────────────────────────────────────────

def test_brier_is_zero_for_perfect_call() -> None:
    """If we ever get a row where p_winner=1.0 exactly, brier is 0."""
    from datetime import datetime, timezone

    from desk.backtest.replay import SnapshotRow

    row = SnapshotRow(
        match_id="x", window="KO", asof=datetime.now(tz=timezone.utc),
        elo_a=2000, elo_b=1500, host_bonus_pp=0, altitude_m=0,
        weather_factor=1, injury_factor=1,
        p_a=1.0, p_draw=0.0, p_b=0.0,
        market_p_a=0.7, market_p_draw=0.2, market_p_b=0.1,
        actual_a=1, actual_draw=0, actual_b=0,
        verdict_state="pass", verdict_side=None,
        verdict_market_venue=None, verdict_edge_pp=None,
    )
    assert row.brier == pytest.approx(0.0, abs=1e-9)
