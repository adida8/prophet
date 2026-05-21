"""Trust-gate logic on `Source` + `Signal.track` routing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from desk.signals.models import Signal, SignalType, Source


def _source(**overrides) -> Source:
    base = dict(
        id="test-src",
        name="Test Source",
        feed_type="rss",
        feed_ref="https://example.com/rss",
        language="en",
        coverage_tags="global|sport:football",
        reliability=0.9,
        bias_flag="none",
        parent_org="example",
        tier="trusted_core",
        enabled=True,
    )
    base.update(overrides)
    return Source.model_validate(base)


# ── can_feed_model gate ────────────────────────────────────────────────

def test_can_feed_model_passes_when_all_three_conditions_met():
    s = _source(reliability=0.9, bias_flag="none", tier="trusted_core")
    assert s.can_feed_model
    assert not s.editorial_only


def test_can_feed_model_blocked_by_low_reliability():
    s = _source(reliability=0.79, bias_flag="none", tier="trusted_core")
    assert not s.can_feed_model
    assert s.editorial_only


def test_can_feed_model_blocked_by_national_bias():
    s = _source(reliability=0.95, bias_flag="national", tier="trusted_core")
    assert not s.can_feed_model


def test_can_feed_model_blocked_by_club_bias():
    s = _source(reliability=0.95, bias_flag="club", tier="trusted_core")
    assert not s.can_feed_model


def test_can_feed_model_blocked_by_long_tail_tier():
    s = _source(reliability=0.95, bias_flag="none", tier="long_tail")
    assert not s.can_feed_model


# ── coverage_tags parsing ──────────────────────────────────────────────

def test_coverage_tags_split_from_pipe_separated_string():
    s = _source(coverage_tags="global|sport:football|country:ar")
    assert s.coverage_tags == frozenset({"global", "sport:football", "country:ar"})


def test_coverage_tags_accept_iterable():
    s = _source(coverage_tags=["global", "sport:football"])
    assert s.coverage_tags == frozenset({"global", "sport:football"})


def test_coverage_tags_must_be_nonempty():
    with pytest.raises(ValidationError):
        _source(coverage_tags="")


def test_coverage_tags_accept_json_array_string():
    s = _source(coverage_tags='["global", "sport:football", "country:ar"]')
    assert s.coverage_tags == frozenset({"global", "sport:football", "country:ar"})


# ── feed_type=none invariant ──────────────────────────────────────────

def test_feed_type_none_requires_empty_feed_ref():
    with pytest.raises(ValidationError, match="feed_type='none' must have empty"):
        _source(feed_type="none", feed_ref="https://something/rss")


def test_non_none_feed_type_requires_feed_ref():
    with pytest.raises(ValidationError, match="requires.*feed_ref"):
        _source(feed_type="rss", feed_ref="")


def test_feed_type_none_with_empty_feed_ref_loads():
    s = _source(feed_type="none", feed_ref="")
    assert s.feed_type == "none"
    assert s.feed_ref == ""


def test_feed_type_none_with_high_reliability_still_can_feed_model():
    # Reuters / AP / AFP route here: feed_type=none, reliability=0.9.
    # They're "in the trust framework" — the gate doesn't care about
    # fetchability, only trust. A future API ingest can wire them in.
    s = _source(feed_type="none", feed_ref="", reliability=0.9,
                bias_flag="none", tier="trusted_core")
    assert s.can_feed_model


# ── notes round-trip ──────────────────────────────────────────────────

def test_notes_optional_and_round_trips():
    s = _source(notes="Verified 2026-05-21; English desk only.")
    assert s.notes == "Verified 2026-05-21; English desk only."


def test_notes_defaults_to_none():
    s = _source()
    assert s.notes is None


# ── Signal.track — source gate dominates type ──────────────────────────

def _signal(source_id: str, type: SignalType) -> Signal:
    return Signal(
        type=type,
        team="France",
        claim="Mbappé out with calf strain",
        quote="Mbappé will miss tomorrow's match with a calf strain.",
        source_id=source_id,
        url="https://example.com/article/1",
        confidence=0.9,
    )


def test_hard_track_when_type_eligible_and_source_can_feed_model():
    src = _source(id="bbc", reliability=0.95, bias_flag="none", tier="trusted_core")
    sig = _signal("bbc", SignalType.INJURY)
    assert sig.track(src) == "hard"


def test_editorial_track_when_hard_type_from_biased_source():
    # The classic failure mode the spec calls out: an injury from a
    # homer outlet must never become a model feature.
    src = _source(id="ole", reliability=0.85, bias_flag="national", tier="trusted_core")
    sig = _signal("ole", SignalType.INJURY)
    assert sig.track(src) == "editorial"


def test_editorial_track_for_predicted_lineup_even_from_trusted_source():
    # Only confirmed XI is hard; predicted is editorial colour.
    src = _source(id="bbc", reliability=0.95)
    sig = _signal("bbc", SignalType.PREDICTED_LINEUP)
    assert sig.track(src) == "editorial"


def test_hard_track_for_confirmed_lineup_from_trusted_source():
    src = _source(id="bbc", reliability=0.95)
    sig = _signal("bbc", SignalType.CONFIRMED_LINEUP)
    assert sig.track(src) == "hard"


def test_editorial_track_for_non_hard_types_even_from_trusted_source():
    src = _source(id="bbc", reliability=0.95)
    for t in (SignalType.MORALE, SignalType.MANAGER_QUOTE, SignalType.FORM, SignalType.OTHER):
        sig = _signal("bbc", t)
        assert sig.track(src) == "editorial", t


def test_track_rejects_mismatched_source():
    src = _source(id="bbc")
    sig = _signal("ole", SignalType.INJURY)
    with pytest.raises(ValueError):
        sig.track(src)
