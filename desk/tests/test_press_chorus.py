"""Press-chorus tests — templated explainer's news-signals hook.

The chorus is the stopgap between "citations exist on the contract" and
"Haiku writes prose around them" (PR 5 of the Desk spec). When ≥2
distinct outlets cover a fixture, build_copy appends one extra
voice-safe sentence to the blurb so the reader-visible prose actually
moves when sources are added.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.explainer.stub import (
    _CHORUS_MIN_OUTLETS,
    _CHORUS_QUOTE_MAX_CHARS,
    _press_chorus,
    _truncate_quote,
    build_copy,
)
from desk.publish.contract import Citation

_NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _cite(outlet: str, quote: str = "A neutral line about the squad.",
          url: str | None = None) -> Citation:
    return Citation(
        outlet=outlet,
        url=url or f"https://example/{outlet.lower().replace(' ', '-')}/a",
        quote=quote,
        published_at=_NOW,
    )


# ── Below-threshold: stay silent ─────────────────────────────────────

def test_chorus_returns_none_when_no_citations() -> None:
    assert _press_chorus(None) is None
    assert _press_chorus([]) is None


def test_chorus_returns_none_with_one_citation() -> None:
    """A single outlet isn't "coverage" — naming it would read as an
    endorsement of one framing. Spec §_CHORUS_MIN_OUTLETS."""
    assert _CHORUS_MIN_OUTLETS == 2  # guard against silent threshold change
    assert _press_chorus([_cite("BBC Sport")]) is None


def test_chorus_returns_none_when_outlets_dedup_below_threshold() -> None:
    """Two citations from the SAME outlet count as one — distinct
    outlets is the gate, not raw row count."""
    out = _press_chorus([
        _cite("BBC Sport", url="https://example/bbc/a"),
        _cite("BBC Sport", url="https://example/bbc/b"),
    ])
    assert out is None


# ── Consensus shape (quote survives) ─────────────────────────────────

def test_chorus_consensus_quotes_top_reliability_outlet() -> None:
    """citations are pre-sorted by reliability desc — chorus features
    the first surviving (voice-clean) quote and names that outlet."""
    out = _press_chorus([
        _cite("The Guardian", quote="Deschamps signals an unchanged starting XI."),
        _cite("ESPN", quote="Squad arrived in Guadalajara on Monday."),
    ])
    assert out is not None
    assert "The Guardian" in out
    assert "Deschamps signals an unchanged starting XI." in out
    assert out.startswith("Coverage converged")


def test_chorus_consensus_truncates_overlong_quote() -> None:
    long_q = (
        "The manager has signalled an unchanged starting eleven after a closed-door "
        "session that the local press reported lasted nearly two hours and ended "
        "with the captain addressing the squad in the centre circle, sources said."
    )
    out = _press_chorus([
        _cite("The Guardian", quote=long_q),
        _cite("ESPN"),
    ])
    assert out is not None
    # The Guardian fragment is present but truncated with an ellipsis.
    assert "…" in out
    # No banned phrase or unsafe character leaked through.
    assert "!" not in out


# ── Count shape (no usable quote) ────────────────────────────────────

def test_chorus_falls_back_to_count_when_no_quote_is_voice_clean() -> None:
    """Every citation's quote fails the voice gate → no consensus
    sentence. With ≥2 distinct outlets we still ship the count shape."""
    bad = _cite("The Guardian", quote="A guaranteed win for France!")
    bad2 = _cite("ESPN",         quote="Smart money backs the hosts.")
    out = _press_chorus([bad, bad2])
    assert out is not None
    assert "Recent coverage from 2 outlets" in out
    assert "The Guardian" in out and "ESPN" in out


def test_chorus_count_shape_caps_named_outlets() -> None:
    cites = [_cite(name) for name in
             ["BBC Sport", "The Guardian", "ESPN", "Sky Sports", "France 24"]]
    # Wipe quotes to force the count shape.
    cites = [c.model_copy(update={"quote": "A neutral line."}) for c in cites]
    # …actually a neutral quote IS clean, so it'd take the consensus
    # shape. Strip quotes to trigger the count path by failing voice.
    cites = [c.model_copy(update={"quote": "Lock in this guaranteed bet!"}) for c in cites]
    out = _press_chorus(cites)
    assert out is not None
    assert "5 outlets" in out
    # Three are named, the rest summarised.
    assert "and 2 others" in out


# ── Voice safety ──────────────────────────────────────────────────────

def test_chorus_never_contains_banned_phrases() -> None:
    """Even when every quote contains banned phrases, the final chorus
    survives voice-cleanly (it's only the outlet names + a formulaic
    sentence)."""
    bad = [
        _cite("BBC Sport", quote="A guaranteed lock for the hosts!"),
        _cite("ESPN",      quote="Smart money is set to back the favourite."),
    ]
    out = _press_chorus(bad)
    assert out is not None
    for banned in ("guaranteed", "lock", "smart money", "back the", "is set to"):
        assert banned not in out.lower()
    assert "!" not in out


def test_chorus_returns_none_on_safety_total_failure(monkeypatch) -> None:
    """Defensive: even after pre-filter + re-check, if the final chorus
    string fails the voice gate, return None — the body still ships."""
    # Force is_voice_clean to always fail. Mirrors a future regression
    # where the chorus template itself contains a newly-banned phrase.
    import desk.explainer.stub as stub
    monkeypatch.setattr(stub, "is_voice_clean", lambda _t: False)
    out = stub._press_chorus([_cite("BBC Sport"), _cite("ESPN")])
    assert out is None


# ── Helpers ───────────────────────────────────────────────────────────

def test_truncate_quote_short_quote_rides_through_unchanged() -> None:
    q = "A short, clean line."
    assert _truncate_quote(q) == q


def test_truncate_quote_breaks_on_word_boundary_when_possible() -> None:
    q = "A" * 50 + " " + "word " * 40
    out = _truncate_quote(q, limit=120)
    assert len(out) <= 121          # body + the ellipsis
    assert out.endswith("…")
    assert "  " not in out          # no double spaces from the cut


# ── build_copy integration: blurb actually grows ─────────────────────

def _pick_inputs(**overrides) -> dict:
    base = dict(
        state="pick",
        side="France",
        edge_pp=4.2,
        market_venue="polymarket",
        price="-180",
        team_a="France",
        team_b="Mexico",
        competition="FIFA World Cup 2026",
        model_p_a=0.46, model_p_draw=0.27, model_p_b=0.27,
        market_p_a=0.42, market_p_draw=0.30, market_p_b=0.28,
    )
    base.update(overrides)
    return base


def test_pick_blurb_appends_chorus_when_citations_present() -> None:
    cites = [
        _cite("The Guardian", quote="Deschamps signals an unchanged starting XI."),
        _cite("ESPN",         quote="Squad in good spirits ahead of kick-off."),
    ]
    bare    = build_copy(_pick_inputs())
    with_cs = build_copy(_pick_inputs(editorial_citations=cites))
    assert len(with_cs.blurb) > len(bare.blurb)
    assert "The Guardian" in with_cs.blurb
    assert "Coverage converged" in with_cs.blurb


def test_pick_blurb_unchanged_when_no_citations() -> None:
    """Regression guard: a fixture without citations must produce
    byte-identical prose to the pre-chorus build."""
    a = build_copy(_pick_inputs())
    b = build_copy(_pick_inputs(editorial_citations=[]))
    c = build_copy(_pick_inputs(editorial_citations=None))
    assert a.blurb == b.blurb == c.blurb


def test_pass_blurb_appends_chorus_when_citations_present() -> None:
    cites = [
        _cite("The Guardian", quote="Both sides have named full-strength squads."),
        _cite("BBC Sport",    quote="Neutral venue conditions look benign."),
    ]
    inputs = dict(
        state="pass", side=None, edge_pp=None,
        market_venue=None, price=None,
        team_a="USA", team_b="Canada",
        competition="FIFA World Cup 2026",
        model_p_a=0.40, model_p_draw=0.28, model_p_b=0.32,
        market_p_a=0.41, market_p_draw=0.28, market_p_b=0.31,
        editorial_citations=cites,
    )
    out = build_copy(inputs)
    assert "Coverage converged" in out.blurb or "Recent coverage" in out.blurb


def test_avoid_blurb_appends_chorus_when_citations_present() -> None:
    cites = [
        _cite("ESPN",         quote="Market shape looks fully priced on both sides."),
        _cite("Sky Sports",   quote="Squad announcements were unsurprising."),
    ]
    inputs = dict(
        state="avoid", side=None, edge_pp=-6.0,
        market_venue=None, price=None,
        team_a="Manchester United", team_b="Liverpool",
        competition="Premier League",
        model_p_a=0.30, model_p_draw=0.30, model_p_b=0.30,
        market_p_a=0.35, market_p_draw=0.34, market_p_b=0.36,
        editorial_citations=cites,
    )
    out = build_copy(inputs)
    assert ("Coverage converged" in out.blurb
            or "Recent coverage" in out.blurb)
