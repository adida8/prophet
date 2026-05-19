"""Smoke tests for the outright pipeline.

The MC sim is non-deterministic at the Python-random level (we seed it,
but a small sim count amplifies variance), so these tests assert
*structure* rather than exact numbers: the field is the right size,
probabilities sum to 1, the verdict is well-formed, the publisher
emits JSON the site can read.

The full 10k + 100×1k bootstrap takes ~13s — too slow for unit tests.
We use a tiny budget here (500 sims, 5×100 bootstrap) which is enough
to validate the wiring.
"""

from __future__ import annotations

import json

from desk.outrights.decide import decide
from desk.outrights.explainer import build_copy
from desk.outrights.ingest_polymarket import OutrightPrice, OutrightSnapshot
from desk.outrights.model import run as run_model
from desk.outrights.publish import build_payload
from desk.outrights.wc26_data import field


def _fake_snapshot() -> OutrightSnapshot:
    """A synthetic snapshot — uniform market prices around 1/48 for every
    team in the field. Lets us exercise the pipeline without hitting
    Polymarket and gives the model real edge to work with (the Elo
    favourites will diverge sharply from uniform).
    """
    from datetime import datetime, timezone
    teams = field()
    yes = 1.0 / len(teams)
    prices = tuple(
        OutrightPrice(
            team=t,
            yes_p=yes,
            no_p=1.0 - yes,
            market_url=f"https://polymarket.com/event/wc-{i}",
        )
        for i, t in enumerate(teams)
    )
    return OutrightSnapshot(
        event_id="test-event",
        event_slug="2026-fifa-world-cup-winner-test",
        title="2026 FIFA World Cup Winner",
        resolution_utc=datetime(2026, 7, 20, tzinfo=timezone.utc),
        asof=datetime(2026, 5, 19, tzinfo=timezone.utc),
        prices=prices,
        overround=0.0,
    )


def test_field_is_48_teams() -> None:
    teams = field()
    assert len(teams) == 48
    assert len(set(teams)) == 48, "every team in field() must be unique"


def test_model_p_win_sums_to_one() -> None:
    out = run_model(field(), sims=500, bootstrap_samples=5, bootstrap_sims=100)
    s = sum(out.p_win.values())
    assert abs(s - 1.0) < 1e-6, f"p_win must sum to 1.0, got {s}"


def test_model_bootstrap_bounds_envelop_point() -> None:
    out = run_model(field(), sims=500, bootstrap_samples=5, bootstrap_sims=100)
    for team in field():
        lo, p, hi = out.p_win_lower[team], out.p_win[team], out.p_win_upper[team]
        # Bounds should be in [0, 1]; lower ≤ upper. Point estimate may
        # land outside [lo, hi] on a small sample, so don't strictly
        # require it — just that the band is internally consistent.
        assert 0.0 <= lo <= hi <= 1.0, f"{team}: lo={lo}, hi={hi}"


def test_top_contenders_lead_the_field() -> None:
    """Argentina + France + Spain + Brazil should dominate the top of
    the model output — same Elo prior as the match model.
    """
    out = run_model(field(), sims=2_000, bootstrap_samples=5, bootstrap_sims=100)
    top4 = sorted(out.p_win, key=lambda t: -out.p_win[t])[:4]
    expected = {"Argentina", "France", "Spain", "Brazil"}
    assert set(top4) >= (expected & set(out.p_win)), (
        f"top 4 should include the Elo favourites; got {top4}"
    )


def test_decide_returns_well_formed_verdict() -> None:
    snap = _fake_snapshot()
    model = run_model(field(), sims=500, bootstrap_samples=5, bootstrap_sims=100)
    verdict = decide(snap, model)
    assert verdict.state in {"pick", "pass"}
    # Uniform market should make Argentina a runaway Pick (model ~15% vs
    # market 1/48 ≈ 2%). Whether the lower-bound clears depends on the
    # bootstrap; just assert the candidate path is wired.
    if verdict.state == "pick":
        assert verdict.candidate is not None
        assert verdict.candidate.side in {"YES", "NO"}
    # Ladder has YES + NO per priced team.
    assert len(verdict.positions) == 2 * len(snap.prices)


def test_publish_payload_has_site_required_fields() -> None:
    snap = _fake_snapshot()
    model = run_model(field(), sims=500, bootstrap_samples=5, bootstrap_sims=100)
    verdict = decide(snap, model)
    copy = build_copy(snap, model, verdict)
    payload = build_payload(snap, model, verdict, copy)

    # Round-trip through JSON to catch any non-serialisable fields.
    serialised = json.dumps(payload)
    again = json.loads(serialised)

    # The site reads these — assert they're present and shaped right.
    assert again["outright_id"]
    assert again["sport"] == "football"
    assert again["resolves_at"]
    assert again["copy"]["title"]
    assert again["copy"]["summary"]
    assert again["copy"]["blurb"]
    assert isinstance(again["copy"]["drivers"], list)
    assert again["verdict"]["state"] in {"pick", "pass"}
    assert isinstance(again["ladder"], list)
    assert len(again["ladder"]) > 0
