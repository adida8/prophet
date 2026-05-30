"""Unit tests for desk/pricing/consensus.py."""

from __future__ import annotations

import math

import pytest

from desk.pricing.consensus import DEFAULT_SHARP_WEIGHTS, consensus_fair


def test_uniform_weights_equal_simple_mean() -> None:
    """With every weight equal, the blend is just the arithmetic mean."""
    pairs = [("a", 0.20), ("b", 0.18), ("c", 0.22)]
    blend = consensus_fair(pairs, weights={"a": 1.0, "b": 1.0, "c": 1.0})
    assert math.isclose(blend, (0.20 + 0.18 + 0.22) / 3.0, rel_tol=1e-12)


def test_sharp_anchor_dominates_consumer_books() -> None:
    """Pinnacle weight 3, William Hill weight 1 → Pinnacle's number
    pulls the consensus closer to itself than to William Hill."""
    pairs = [("pinnacle", 0.168), ("williamhill", 0.146)]
    blend_default = consensus_fair(pairs)
    assert abs(blend_default - 0.168) < abs(blend_default - 0.146)
    # And the blend stays between the two opinions — no overshoot.
    assert 0.146 < blend_default < 0.168


def test_missing_venue_gets_weight_one() -> None:
    """Unknown venue → default weight 1.0 (counts equally)."""
    pairs = [("pinnacle", 0.20), ("some_new_venue", 0.30)]
    blend = consensus_fair(pairs)
    # pinnacle weight 3, new venue weight 1 → (0.6 + 0.3) / 4 = 0.225
    assert math.isclose(blend, (3.0 * 0.20 + 1.0 * 0.30) / 4.0, rel_tol=1e-12)


def test_default_table_weights_match_scope_doc_anchor() -> None:
    """Sharp anchors (Pinnacle + Betfair exchange) carry weight 3."""
    assert DEFAULT_SHARP_WEIGHTS["pinnacle"]       == 3.0
    assert DEFAULT_SHARP_WEIGHTS["betfair_ex_uk"]  == 3.0
    assert DEFAULT_SHARP_WEIGHTS["betfair_ex_eu"]  == 3.0
    assert DEFAULT_SHARP_WEIGHTS["williamhill"]    == 1.0
    assert DEFAULT_SHARP_WEIGHTS["skybet"]         == 1.0


def test_empty_pairs_raises() -> None:
    with pytest.raises(ValueError, match="no venues"):
        consensus_fair([])


def test_all_zero_weights_raises() -> None:
    pairs = [("a", 0.5), ("b", 0.5)]
    with pytest.raises(ValueError, match="all venue weights are zero"):
        consensus_fair(pairs, weights={"a": 0.0, "b": 0.0})


def test_out_of_range_fair_p_raises() -> None:
    with pytest.raises(ValueError, match="out of \\[0,1\\]"):
        consensus_fair([("pinnacle", 1.4)])


def test_negative_weight_raises() -> None:
    with pytest.raises(ValueError, match="must be ≥ 0"):
        consensus_fair([("a", 0.5)], weights={"a": -1.0})
