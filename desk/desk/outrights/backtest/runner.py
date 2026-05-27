"""Outright backtest orchestrator.

Loads a frozen tournament (groups + Elo + true winner), runs the MC
sim, scores against the actual outcome, and renders a dashboard +
optional workbook.

The critical invariant — mirrors `desk/backtest/replay.py` — is that
the backtest path **never imports from the live ingest modules**. Live
runs (`desk outrights`) hit Polymarket gamma; backtests read frozen
JSON / CSV from `desk/data/backtest/`. A leak in either direction
would let today's data influence a 2022 verdict.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from desk.outrights.backtest.scoring import (
    ScoreBundle,
    score,
    uniform_distribution,
)
from desk.outrights.model import (
    BASE_SEED,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SIMS,
    SIMS,
    OutrightModelOutput,
    run_sim,
)

log = logging.getLogger("desk.outrights.backtest.runner")


# Knobs for the WC22 backtest tuned down from production for sane
# wall-clock: 5k point sims + 30 bootstrap samples × 200 sims ≈ 8s on
# a laptop. The full production budget (10k + 100×1k) takes ~30s and
# tightens the band by a few tenths of a pp — fine for a backtest.
BACKTEST_SIMS:              int = 5_000
BACKTEST_BOOTSTRAP_SAMPLES: int = 30
BACKTEST_BOOTSTRAP_SIMS:    int = 200


@dataclass(frozen=True)
class WC22BacktestResult:
    """Full backtest output — model output + scoring bundles for the
    model and each reference baseline (uniform; market when provided).
    """
    model:           OutrightModelOutput
    field:           tuple[str, ...]
    winner:          str
    model_score:     ScoreBundle
    uniform_score:   ScoreBundle
    market_score:    ScoreBundle | None    # None if no market reference
    elo_lookup:      dict[str, float]


def run_wc22(
    *,
    sims:              int = BACKTEST_SIMS,
    bootstrap_samples: int = BACKTEST_BOOTSTRAP_SAMPLES,
    bootstrap_sims:    int = BACKTEST_BOOTSTRAP_SIMS,
    seed:              int = BASE_SEED,
) -> WC22BacktestResult:
    """Replay WC 2022 outright winner against the engine.

    Inputs: frozen 2022-11-20 Elo + WC22 groups + R16 bracket.
    Output: per-team P(win) + scoring vs Argentina (the actual winner).
    """
    from desk.outrights.backtest.wc22_data import (
        MARKET_REFERENCE_P_WIN,
        TRUE_WINNER,
        field as wc22_field,
        load_elo_lookup,
        wc22_structure,
    )

    field = wc22_field()
    elo_lookup = load_elo_lookup()
    structure = wc22_structure()

    log.info("wc22 backtest: %d teams, %d sims + %d×%d bootstrap",
             len(field), sims, bootstrap_samples, bootstrap_sims)

    model = run_sim(
        structure,
        elo_lookup,
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
    )

    model_score = score(
        "model",
        model.p_win,
        winner=TRUE_WINNER,
        field=field,
    )
    uniform_score = score(
        "uniform",
        uniform_distribution(field),
        winner=TRUE_WINNER,
        field=field,
    )
    market_score = score(
        "market_consensus",
        MARKET_REFERENCE_P_WIN,
        winner=TRUE_WINNER,
        field=field,
    ) if MARKET_REFERENCE_P_WIN else None

    log.info(
        "wc22 backtest: model winner_rank=%d  winner_p=%.4f  brier=%.4f  log_score=%.4f",
        model_score.winner_rank,
        model_score.winner_p,
        model_score.brier,
        model_score.log_score,
    )

    return WC22BacktestResult(
        model=model,
        field=field,
        winner=TRUE_WINNER,
        model_score=model_score,
        uniform_score=uniform_score,
        market_score=market_score,
        elo_lookup=elo_lookup,
    )


def run_backtest(
    *,
    tournament_key:  str = "wc-2022",
    dashboard_path:  Path,
    sims:            int = BACKTEST_SIMS,
    bootstrap_samples: int = BACKTEST_BOOTSTRAP_SAMPLES,
    bootstrap_sims:  int = BACKTEST_BOOTSTRAP_SIMS,
    seed:            int = BASE_SEED,
) -> dict:
    """Top-level entry behind `desk outrights backtest`. Today only
    `wc-2022` is wired; add a dispatch table when a second tournament
    lands (Euro 2024, Copa 2024)."""
    from desk.outrights.backtest.writers import write_dashboard

    if tournament_key != "wc-2022":
        raise ValueError(
            f"unknown outright backtest tournament: {tournament_key!r}; "
            f"known: ['wc-2022']"
        )

    result = run_wc22(
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
    )
    write_dashboard(result, dashboard_path=dashboard_path)

    return {
        "tournament":    tournament_key,
        "winner":        result.winner,
        "winner_p":      round(result.model_score.winner_p, 4),
        "winner_rank":   result.model_score.winner_rank,
        "top3_hit":      result.model_score.top3_hit,
        "top5_hit":      result.model_score.top5_hit,
        "brier":         round(result.model_score.brier, 4),
        "log_score":     round(result.model_score.log_score, 4),
        "uniform_brier": round(result.uniform_score.brier, 4),
        "market_brier":  round(result.market_score.brier, 4) if result.market_score else None,
        "dashboard":     str(dashboard_path),
        "sims":          sims,
        "bootstrap":     f"{bootstrap_samples}×{bootstrap_sims}",
    }
