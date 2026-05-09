"""Polymarket price parser — extracts {a, draw, b} from a gamma event."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.ingest.polymarket_prices import prices_from_polymarket_event


def _ev(markets: list[dict]) -> dict:
    return {"slug": "fifwc-fra-mex-20260612", "title": "France vs. Mexico", "markets": markets}


def _market(question: str, yes_p: float) -> dict:
    return {
        "question": question,
        "outcomes": '["Yes", "No"]',
        "outcomePrices": json.dumps([str(yes_p), str(round(1 - yes_p, 4))]),
    }


def test_three_way_match_extracts_a_draw_b() -> None:
    ev = _ev([
        _market("Will France win on 2026-06-12?", 0.46),
        _market("Will France vs. Mexico end in a draw?", 0.27),
        _market("Will Mexico win on 2026-06-12?", 0.28),
    ])
    snap = prices_from_polymarket_event(
        ev, match_id="fb-wc26-fra-mex-20260612",
        team_a="France", team_b="Mexico",
    )
    by_side = {p.side: p.implied_p for p in snap.prices}
    assert by_side == pytest.approx({"a": 0.46, "draw": 0.27, "b": 0.28})
    assert all(p.venue == "polymarket" for p in snap.prices)


def test_handles_outcome_prices_as_already_decoded_list() -> None:
    ev = _ev([{
        "question": "Will France win on 2026-06-12?",
        "outcomes": ["Yes", "No"],
        "outcomePrices": ["0.5", "0.5"],
    }])
    snap = prices_from_polymarket_event(
        ev, match_id="fb-wc26-fra-mex-20260612",
        team_a="France", team_b="Mexico",
    )
    assert len(snap.prices) == 1
    assert snap.prices[0].implied_p == 0.5


def test_skips_markets_with_unparseable_prices() -> None:
    ev = _ev([
        _market("Will France win on 2026-06-12?", 0.46),
        {
            "question": "Will France vs. Mexico end in a draw?",
            "outcomes": ["Yes", "No"],
            "outcomePrices": "garbage",
        },
    ])
    snap = prices_from_polymarket_event(
        ev, match_id="fb-wc26-fra-mex-20260612",
        team_a="France", team_b="Mexico",
    )
    assert {p.side for p in snap.prices} == {"a"}


def test_normalises_accents_so_munich_umlauts_match() -> None:
    """Polymarket sometimes ships accent-stripped market questions."""
    ev = _ev([
        _market("Will FC Bayern Munchen win on 2026-05-06?", 0.20),
    ])
    snap = prices_from_polymarket_event(
        ev, match_id="fb-ucl-bay-psg-20260506",
        team_a="FC Bayern München", team_b="Paris Saint-Germain FC",
    )
    assert {p.side for p in snap.prices} == {"a"}


# ── End-to-end sanity against the saved gamma fixture ────────────────

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_can_extract_prices_from_real_polymarket_response() -> None:
    """At least some events in the saved live response should yield
    parseable prices. Guards against schema drift on Polymarket's side.
    """
    events = json.loads((FIXTURES_DIR / "polymarket_soccer_games.json").read_text())
    parseable_with_at_least_one_side = 0
    for ev in events:
        title = ev.get("title", "")
        if " vs." not in title:
            continue
        team_a, team_b = title.split(" vs.", 1)
        team_b = team_b.strip().removesuffix(" - More Markets")
        snap = prices_from_polymarket_event(
            ev, match_id="fb-test", team_a=team_a.strip(), team_b=team_b,
            asof=datetime(2026, 5, 9, tzinfo=timezone.utc),
        )
        if snap.prices:
            parseable_with_at_least_one_side += 1
    assert parseable_with_at_least_one_side > 0, "no events yielded prices — schema drift?"
