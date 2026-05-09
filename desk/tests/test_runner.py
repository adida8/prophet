"""Runner tests — `run_once` writes per-match JSON + sport-partitioned index.

We stub `Sport.list_fixtures` so this test is hermetic; live ingest is
exercised separately in `test_fixtures.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from desk.publish import MatchOutput, OutputIndex
from desk.runner import run_once
from desk.sport import FixtureRef


class _FakeSport:
    code = "football"
    short_code = "fb"
    label = "Football"

    def __init__(self, fixtures: list[FixtureRef]) -> None:
        self._fxs = fixtures

    def market_outcomes(self):
        return ("a", "draw", "b")

    def list_fixtures(self) -> Iterable[FixtureRef]:
        return iter(self._fxs)


@pytest.fixture
def two_fixtures() -> list[FixtureRef]:
    return [
        FixtureRef(
            match_id="fb-wc26-fra-mex-20260612",
            sport="football",
            competition_code="wc26",
            competition_label="FIFA World Cup 2026",
            competition_stage="group_d",
            team_a="France",
            team_b="Mexico",
            kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
            market_outcomes=("a", "draw", "b"),
            venue_city=None, venue_stadium=None, venue_country=None,
        ),
        FixtureRef(
            match_id="fb-wc26-usa-can-20260613",
            sport="football",
            competition_code="wc26",
            competition_label="FIFA World Cup 2026",
            competition_stage="group_a",
            team_a="USA",
            team_b="Canada",
            kickoff_utc=datetime(2026, 6, 13, 20, 0, tzinfo=timezone.utc),
            market_outcomes=("a", "draw", "b"),
            venue_city=None, venue_stadium=None, venue_country=None,
        ),
    ]


def test_run_once_writes_each_fixture_and_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_fixtures: list[FixtureRef],
) -> None:
    fake_sport = _FakeSport(two_fixtures)
    monkeypatch.setattr("desk.runner.active_sports", lambda: [fake_sport])

    written = run_once(output_dir=tmp_path / "output")

    paths = written["football"]
    json_paths = [p for p in paths if p.name != "index.json"]
    assert len(json_paths) == len(two_fixtures)

    for fx in two_fixtures:
        path = tmp_path / "output" / "football" / f"{fx.match_id}.json"
        assert path.exists()
        m = MatchOutput.model_validate_json(path.read_text())
        assert m.verdict.state == "pass"
        assert m.verdict.market_venue is None
        assert m.copy.title == ""

    idx_path = tmp_path / "output" / "football" / "index.json"
    assert idx_path.exists()
    idx = OutputIndex.model_validate_json(idx_path.read_text())
    assert {e.match_id for e in idx.matches} == {fx.match_id for fx in two_fixtures}


def test_run_once_isolates_per_fixture_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_fixtures: list[FixtureRef],
) -> None:
    """A bad fixture must not poison the rest. Spec §9 failure-mode rule."""
    bad = FixtureRef(
        match_id="not a valid match id",            # will fail Pydantic regex
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage=None,
        team_a="X", team_b="Y",
        kickoff_utc=datetime(2026, 7, 1, 19, 0, tzinfo=timezone.utc),
        market_outcomes=("a", "draw", "b"),
        venue_city=None, venue_stadium=None, venue_country=None,
    )
    fake_sport = _FakeSport(two_fixtures + [bad])
    monkeypatch.setattr("desk.runner.active_sports", lambda: [fake_sport])

    written = run_once(output_dir=tmp_path / "output")
    json_paths = [p for p in written["football"] if p.name != "index.json"]
    assert len(json_paths) == 2     # the two good ones, not three

    idx_path = tmp_path / "output" / "football" / "index.json"
    idx = OutputIndex.model_validate_json(idx_path.read_text())
    assert len(idx.matches) == 2
