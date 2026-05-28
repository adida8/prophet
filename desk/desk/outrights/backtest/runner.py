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
class OutrightBacktestResult:
    """Full backtest output — model output + scoring bundles for the
    model and each reference baseline (uniform; market when provided).
    """
    tournament_key:  str
    tournament_name: str
    model:           OutrightModelOutput
    field:           tuple[str, ...]
    winner:          str
    model_score:     ScoreBundle
    uniform_score:   ScoreBundle
    market_score:    ScoreBundle | None    # None if no market reference
    elo_lookup:      dict[str, float]


# Backwards-compat alias — kept so external test code that imports
# WC22BacktestResult keeps working. Today every result is an
# OutrightBacktestResult; this type name was a v1 misnomer.
WC22BacktestResult = OutrightBacktestResult


# Tournament dispatch table. Adding a new historical tournament =
# new data module + one row here. The dispatch returns a tuple of
# (display name, field, elo_lookup, structure, true_winner,
#  market_reference). Each tournament module is imported lazily so
# unused tournaments don't pay the import cost.
def _wc22_payload():
    from desk.outrights.backtest.wc22_data import (
        MARKET_REFERENCE_P_WIN, TRUE_WINNER,
        field, load_elo_lookup, wc22_structure,
    )
    return (
        "FIFA World Cup 2022", field(), load_elo_lookup(),
        wc22_structure(), TRUE_WINNER, MARKET_REFERENCE_P_WIN,
    )


def _euro_2024_payload():
    from desk.outrights.backtest.euro_2024_data import (
        MARKET_REFERENCE_P_WIN, TRUE_WINNER,
        field, load_elo_lookup, euro_2024_structure,
    )
    return (
        "UEFA Euro 2024", field(), load_elo_lookup(),
        euro_2024_structure(), TRUE_WINNER, MARKET_REFERENCE_P_WIN,
    )


def _copa_2024_payload():
    from desk.outrights.backtest.copa_2024_data import (
        MARKET_REFERENCE_P_WIN, TRUE_WINNER,
        field, load_elo_lookup, copa_2024_structure,
    )
    return (
        "Copa América 2024", field(), load_elo_lookup(),
        copa_2024_structure(), TRUE_WINNER, MARKET_REFERENCE_P_WIN,
    )


TOURNAMENTS = {
    "wc-2022":   _wc22_payload,
    "euro-2024": _euro_2024_payload,
    "copa-2024": _copa_2024_payload,
}


def _run_tournament(
    tournament_key: str,
    *,
    sims:              int,
    bootstrap_samples: int,
    bootstrap_sims:    int,
    seed:              int,
) -> OutrightBacktestResult:
    """Generic single-tournament replay. Looks up the tournament data
    via the dispatch table, runs the MC sim, scores against the true
    winner + reference baselines."""
    if tournament_key not in TOURNAMENTS:
        raise ValueError(
            f"unknown outright backtest tournament: {tournament_key!r}; "
            f"known: {sorted(TOURNAMENTS)}"
        )

    name, field, elo_lookup, structure, true_winner, market_ref = \
        TOURNAMENTS[tournament_key]()

    log.info(
        "%s backtest: %d teams, %d sims + %d×%d bootstrap",
        tournament_key, len(field), sims, bootstrap_samples, bootstrap_sims,
    )

    model = run_sim(
        structure,
        elo_lookup,
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
    )

    model_score   = score("model",        model.p_win,
                          winner=true_winner, field=field)
    uniform_score = score("uniform",      uniform_distribution(field),
                          winner=true_winner, field=field)
    market_score  = score("market_consensus", market_ref,
                          winner=true_winner, field=field) if market_ref else None

    log.info(
        "%s backtest: model winner_rank=%d  winner_p=%.4f  brier=%.4f  log_score=%.4f",
        tournament_key,
        model_score.winner_rank,
        model_score.winner_p,
        model_score.brier,
        model_score.log_score,
    )

    return OutrightBacktestResult(
        tournament_key=tournament_key,
        tournament_name=name,
        model=model,
        field=field,
        winner=true_winner,
        model_score=model_score,
        uniform_score=uniform_score,
        market_score=market_score,
        elo_lookup=elo_lookup,
    )


# Backwards-compat alias — older callers used run_wc22().
def run_wc22(
    *,
    sims:              int = BACKTEST_SIMS,
    bootstrap_samples: int = BACKTEST_BOOTSTRAP_SAMPLES,
    bootstrap_sims:    int = BACKTEST_BOOTSTRAP_SIMS,
    seed:              int = BASE_SEED,
) -> OutrightBacktestResult:
    return _run_tournament(
        "wc-2022",
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
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
    """Top-level entry behind `python -m desk.outrights.backtest`.

    Dispatches to the right tournament data module + renders an HTML
    dashboard. Returns a summary dict for the CLI to print.
    """
    from desk.outrights.backtest.writers import write_dashboard

    result = _run_tournament(
        tournament_key,
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
    )
    write_dashboard(result, dashboard_path=dashboard_path)

    return {
        "tournament":    tournament_key,
        "name":          result.tournament_name,
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
