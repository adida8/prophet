"""Tests for the hard-signals → outright sim wiring.

Three concerns:
  1. Tag builder produces a usable resolver query for the WC26 field.
  2. `apply_hard_signals` matches teams, caps per-team penalty, builds
     an audit row per applied signal.
  3. `model.run(elo_overrides=...)` shifts the perturbed team's P(win)
     in the expected direction.
  4. `build_payload` surfaces the adjustments under `model.*` when given.

The Polymarket fetch is not exercised here — it's hit by the smoke
test in `test_outrights.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.outrights.explainer import build_copy
from desk.outrights.decide import decide
from desk.outrights.hard_signals import (
    OutrightHardSignalAdjustment,
    apply_hard_signals,
)
from desk.outrights.ingest_polymarket import OutrightPrice, OutrightSnapshot
from desk.outrights.model import run as run_model
from desk.outrights.publish import build_payload
from desk.outrights.signals_glue import tags_for_outright
from desk.outrights.wc26_data import field
from desk.signals.models import Signal, SignalType, Source
from desk.sports.football.hard_signals import (
    INJURY_ELO_PENALTY,
    MAX_TOTAL_PENALTY_ELO,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_source(
    *,
    id: str = "reuters-sport",
    reliability: float = 0.95,
    tier: str = "trusted_core",
    bias_flag: str = "none",
    coverage_tags=("global", "sport:football"),
) -> Source:
    return Source(
        id=id,
        name="Reuters Sport",
        feed_type="rss",
        feed_ref="https://example.com/feed.xml",
        language="en",
        coverage_tags=frozenset(coverage_tags),
        reliability=reliability,
        bias_flag=bias_flag,
        tier=tier,
    )


def _make_signal(
    *,
    type: SignalType = SignalType.INJURY,
    team: str = "Argentina",
    source_id: str = "reuters-sport",
    claim: str = "Player X out with ACL tear",
) -> Signal:
    return Signal(
        type=type,
        team=team,
        claim=claim,
        quote="He will miss the tournament.",
        source_id=source_id,
        url="https://example.com/x",
        published_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        confidence=0.95,
    )


def _fake_snapshot() -> OutrightSnapshot:
    teams = field()
    yes = 1.0 / len(teams)
    prices = tuple(
        OutrightPrice(
            team=t, yes_p=yes, no_p=1.0 - yes,
            market_url=f"https://polymarket.com/event/wc-{i}",
        )
        for i, t in enumerate(teams)
    )
    return OutrightSnapshot(
        event_id="test-event",
        event_slug="2026-fifa-world-cup-winner-test",
        title="2026 FIFA World Cup Winner",
        resolution_utc=datetime(2026, 7, 20, tzinfo=timezone.utc),
        asof=datetime(2026, 5, 27, tzinfo=timezone.utc),
        prices=prices,
        overround=0.0,
    )


# ── tag builder ──────────────────────────────────────────────────────


def test_tags_for_outright_includes_base_set() -> None:
    tags = tags_for_outright(("Argentina", "France"))
    assert "global" in tags
    assert "sport:football" in tags
    assert "league:wc26" in tags


def test_tags_for_outright_adds_country_per_team() -> None:
    tags = tags_for_outright(("Argentina", "France", "Brazil"))
    assert "country:ar" in tags
    assert "country:fr" in tags
    assert "country:br" in tags


def test_tags_for_outright_full_wc26_field_covers_major_countries() -> None:
    tags = tags_for_outright(field())
    # Spot-check a handful — England maps via _ISO3_TO_ISO2's "gb".
    for iso2 in ("ar", "fr", "br", "es", "de", "mx", "us"):
        assert f"country:{iso2}" in tags, f"missing country:{iso2}"


# ── apply_hard_signals ──────────────────────────────────────────────


def test_apply_hard_signals_matches_team_case_insensitive() -> None:
    src = _make_source()
    sig = _make_signal(team="argentina")  # lower-case
    deltas, audit = apply_hard_signals(field(), signals=[(sig, src)])
    assert deltas.get("Argentina") == -INJURY_ELO_PENALTY
    assert len(audit) == 1
    assert audit[0].team == "Argentina"
    assert audit[0].delta_elo == -INJURY_ELO_PENALTY
    assert audit[0].capped is False


def test_apply_hard_signals_drops_unknown_team() -> None:
    src = _make_source()
    sig = _make_signal(team="Liechtenstein")  # not in WC26 field
    deltas, audit = apply_hard_signals(field(), signals=[(sig, src)])
    assert deltas == {}
    assert audit == []


def test_apply_hard_signals_resolves_aliases_via_registry() -> None:
    """Signal team 'United States' must bind to field name 'USA' so a
    US-injury news story actually nudges the model. Same shape for
    'South Korea' ↔ 'Korea Republic' and 'Ivory Coast' ↔ 'Côte d'Ivoire'.
    """
    src = _make_source()
    pairs = [
        (_make_signal(team="United States"), src),
        (_make_signal(team="South Korea"),   src),
        (_make_signal(team="Ivory Coast"),   src),
    ]
    deltas, audit = apply_hard_signals(field(), signals=pairs)
    assert "USA"             in deltas
    assert "Korea Republic"  in deltas
    assert "Côte d'Ivoire"   in deltas
    # Each row's audit should carry the *field*'s canonical name, not
    # the signal's variant — that's what the published JSON renders.
    teams_in_audit = {a.team for a in audit}
    assert teams_in_audit == {"USA", "Korea Republic", "Côte d'Ivoire"}


def test_apply_hard_signals_confirmed_lineup_no_delta() -> None:
    src = _make_source()
    sig = _make_signal(type=SignalType.CONFIRMED_LINEUP)
    deltas, audit = apply_hard_signals(field(), signals=[(sig, src)])
    assert deltas == {}
    assert audit == []


def test_apply_hard_signals_caps_per_team_total() -> None:
    """Stack many injuries on one team — total penalty clips at the cap."""
    src = _make_source()
    # 6 × -8 = -48, but cap is -30 — final delta should be -30 with the
    # last applied row flagged `capped=True`.
    sigs = [(_make_signal(claim=f"injury {i}"), src) for i in range(6)]
    deltas, audit = apply_hard_signals(field(), signals=sigs)
    assert deltas["Argentina"] == -MAX_TOTAL_PENALTY_ELO
    # Sum of applied deltas in the audit also equals the cap.
    total_applied = sum(a.delta_elo for a in audit)
    assert abs(total_applied - (-MAX_TOTAL_PENALTY_ELO)) < 1e-6
    # At least one row should be flagged `capped` once we hit the gate.
    assert any(a.capped for a in audit)


def test_apply_hard_signals_independent_teams_cumulate() -> None:
    src = _make_source()
    sigs = [
        (_make_signal(team="Argentina"), src),
        (_make_signal(team="France"),    src),
    ]
    deltas, audit = apply_hard_signals(field(), signals=sigs)
    assert deltas["Argentina"] == -INJURY_ELO_PENALTY
    assert deltas["France"]    == -INJURY_ELO_PENALTY
    assert len(audit) == 2


# ── model accepts overrides ─────────────────────────────────────────


def test_model_elo_overrides_shifts_p_win() -> None:
    """Drop Argentina by 100 Elo via override — its P(win) should
    drop relative to the no-override run on the same seed.

    Tiny budget for speed — relative direction is the assertion, not
    a precise number.
    """
    base = run_model(field(), sims=600, bootstrap_samples=2, bootstrap_sims=50, seed=11)
    nerfed = run_model(
        field(),
        sims=600, bootstrap_samples=2, bootstrap_sims=50, seed=11,
        elo_overrides={"Argentina": -100.0},
    )
    assert nerfed.p_win["Argentina"] < base.p_win["Argentina"], (
        f"Argentina P(win) should drop with -100 Elo override: "
        f"base={base.p_win['Argentina']:.4f} nerfed={nerfed.p_win['Argentina']:.4f}"
    )


def test_model_elo_overrides_unknown_team_silently_ignored() -> None:
    """Override for a team not in the field is a no-op — doesn't crash."""
    out = run_model(
        field(),
        sims=200, bootstrap_samples=2, bootstrap_sims=50, seed=7,
        elo_overrides={"Liechtenstein": -100.0},
    )
    # Same shape, same field — sum still 1.
    assert abs(sum(out.p_win.values()) - 1.0) < 1e-6


# ── publish surfaces adjustments ────────────────────────────────────


def test_build_payload_surfaces_hard_signal_adjustments() -> None:
    snap = _fake_snapshot()
    model = run_model(field(), sims=500, bootstrap_samples=2, bootstrap_sims=50)
    verdict = decide(snap, model)
    copy = build_copy(snap, model, verdict)
    adj = OutrightHardSignalAdjustment(
        team="Argentina",
        delta_elo=-8.0,
        capped=False,
        reason="Player X out with ACL tear",
        signal_url="https://example.com/x",
        signal_type="injury",
        source_id="reuters-sport",
        source_name="Reuters Sport",
        published_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )
    payload = build_payload(snap, model, verdict, copy, hard_signal_adjustments=[adj])
    rows = payload["model"].get("hard_signal_adjustments")
    assert rows and len(rows) == 1
    assert rows[0]["team"] == "Argentina"
    assert rows[0]["delta_elo"] == -8.0
    assert rows[0]["signal_type"] == "injury"
    assert rows[0]["source_id"] == "reuters-sport"


def test_constrained_third_assignment_respects_allowed_groups() -> None:
    """3RD@{groups} slots should only get thirds from one of the
    allowed source groups when one is available."""
    from desk.outrights.model import _assign_constrained_thirds
    # 8 thirds, one per group A-H. The R32 has a "3RD@CDFGH" slot —
    # it should pick the highest-ranked among C/D/F/G/H, not from A or B.
    thirds = [
        ("TeamA", "A"), ("TeamB", "B"), ("TeamC", "C"), ("TeamD", "D"),
        ("TeamE", "E"), ("TeamF", "F"), ("TeamG", "G"), ("TeamH", "H"),
    ]
    seeds = (
        ("A1", "3RD@CDFGH"),
        ("B1", "3RD@AB"),    # constrained to A/B specifically
    )
    assigned = _assign_constrained_thirds(thirds, seeds)
    # First slot prefers thirds from {C,D,F,G,H} — TeamC is highest ranked.
    assert assigned["3RD@CDFGH"] == "TeamC"
    # Second slot can only take A or B — TeamA is highest available.
    assert assigned["3RD@AB"] == "TeamA"


def test_constrained_third_assignment_fallback_when_no_eligible() -> None:
    """When no remaining third matches the constraint, fall back to
    the highest-ranked unassigned team rather than crashing."""
    from desk.outrights.model import _assign_constrained_thirds
    thirds = [("TeamA", "A"), ("TeamB", "B")]
    seeds = (("X1", "3RD@CDEFG"),)  # no eligible team — fallback to A
    assigned = _assign_constrained_thirds(thirds, seeds)
    assert assigned["3RD@CDEFG"] == "TeamA"


def test_build_payload_omits_adjustments_when_empty() -> None:
    snap = _fake_snapshot()
    model = run_model(field(), sims=500, bootstrap_samples=2, bootstrap_sims=50)
    verdict = decide(snap, model)
    copy = build_copy(snap, model, verdict)
    payload = build_payload(snap, model, verdict, copy)
    assert "hard_signal_adjustments" not in payload["model"]
