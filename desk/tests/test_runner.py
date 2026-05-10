"""Runner tests — full pipeline from fixtures to published JSON.

Hermetic: a `_FakeSport` provides priced fixtures + verdicts directly,
so neither network nor live model code runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from desk.publish import MatchOutput, OutputIndex
from desk.publish.contract import MarketVenue, Verdict, VerdictState
from desk.runner import run_once
from desk.sport import FixtureRef
from desk.verdict.compare import MarketSnapshot


class _FakeSport:
    code       = "football"
    short_code = "fb"
    label      = "Football"

    def __init__(
        self,
        priced: list[tuple[FixtureRef, MarketSnapshot]],
        verdicts: dict[str, Verdict] | None = None,
    ) -> None:
        self._priced = priced
        self._verdicts = verdicts or {}

    def market_outcomes(self):
        return ("a", "draw", "b")

    def list_priced_fixtures(self) -> Iterable[tuple[FixtureRef, MarketSnapshot]]:
        return iter(self._priced)

    def decide(self, fx: FixtureRef, snapshot: MarketSnapshot) -> Verdict:
        return self._verdicts.get(fx.match_id, Verdict(state=VerdictState.PASS))


def _fx(match_id: str, kickoff: datetime, *, team_a="A", team_b="B") -> FixtureRef:
    return FixtureRef(
        match_id=match_id,
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage=None,
        team_a=team_a, team_b=team_b,
        kickoff_utc=kickoff,
        market_outcomes=("a", "draw", "b"),
        venue_city=None, venue_stadium=None, venue_country=None,
    )


def _empty_snap(match_id: str) -> MarketSnapshot:
    return MarketSnapshot(
        match_id=match_id,
        asof=datetime.now(tz=timezone.utc),
        prices=(),
    )


@pytest.fixture
def two_priced() -> list[tuple[FixtureRef, MarketSnapshot]]:
    return [
        (_fx("fb-wc26-fra-mex-20260612",
             datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
             team_a="France", team_b="Mexico"),
         _empty_snap("fb-wc26-fra-mex-20260612")),
        (_fx("fb-wc26-usa-can-20260613",
             datetime(2026, 6, 13, 20, 0, tzinfo=timezone.utc),
             team_a="USA", team_b="Canada"),
         _empty_snap("fb-wc26-usa-can-20260613")),
    ]


# ── Pipeline writes per-match + index ────────────────────────────────

def test_run_once_writes_each_fixture_and_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_priced,
) -> None:
    sport = _FakeSport(two_priced)
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    written = run_once(output_dir=tmp_path / "output")
    paths = written["football"]
    json_paths = [p for p in paths if p.name != "index.json"]
    assert len(json_paths) == len(two_priced)

    for fx, _ in two_priced:
        path = tmp_path / "output" / "football" / f"{fx.match_id}.json"
        m = MatchOutput.model_validate_json(path.read_text())
        assert m.verdict.state == "pass"
        assert m.match_id == fx.match_id

    idx_path = tmp_path / "output" / "football" / "index.json"
    idx = OutputIndex.model_validate_json(idx_path.read_text())
    assert {e.match_id for e in idx.matches} == {fx.match_id for fx, _ in two_priced}


# ── Pick verdicts surface intact through the pipeline ────────────────

def test_run_once_carries_pick_verdict_through_to_disk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_priced,
) -> None:
    pick = Verdict(
        state=VerdictState.PICK,
        side="France",
        market_venue=MarketVenue.POLYMARKET,
        price="-180",
        edge_pp=4.2,
        market_url="https://polymarket.com/event/fifwc-fra-mex-2026-06-12",
    )
    sport = _FakeSport(
        two_priced,
        verdicts={"fb-wc26-fra-mex-20260612": pick},
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    m = MatchOutput.model_validate_json(
        (tmp_path / "output" / "football" / "fb-wc26-fra-mex-20260612.json").read_text()
    )
    assert m.verdict.state == "pick"
    assert m.verdict.side == "France"
    assert m.verdict.market_venue == "polymarket"
    assert m.verdict.edge_pp == 4.2


# ── Per-fixture failures don't poison the rest ──────────────────────

def test_run_once_isolates_decide_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_priced,
) -> None:
    """A failing decide() must fall back to Pass for that one fixture; the
    others must still publish. Spec §9 failure-mode rule.
    """
    class _BlowupSport(_FakeSport):
        def decide(self, fx, snapshot):
            if fx.match_id == "fb-wc26-fra-mex-20260612":
                raise RuntimeError("synthetic decide failure")
            return Verdict(state=VerdictState.PASS)

    monkeypatch.setattr("desk.runner.active_sports", lambda: [_BlowupSport(two_priced)])

    run_once(output_dir=tmp_path / "output")
    fail_match = MatchOutput.model_validate_json(
        (tmp_path / "output" / "football" / "fb-wc26-fra-mex-20260612.json").read_text()
    )
    assert fail_match.verdict.state == "pass"
