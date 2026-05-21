"""Ops dashboard tests — PR 1 (record).

Covers: RunReport assembly via run_once(), Recorder persistence +
retention, status classification, and the sport-boundary guard.

Hermetic: `_FakeSport` provides priced fixtures + optional ingest stats
directly, so no live ingest is exercised.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from desk.ops import (
    FixtureRow,
    IngestStats,
    Recorder,
    RunReport,
    RunStatus,
    SourceStatus,
)
from desk.ops.report import (
    SourceFreshness,
    fixture_row_from_match,
    manifest_entry_from_report,
    run_id_for,
)
from desk.publish.contract import Copy, MarketVenue, Verdict, VerdictState
from desk.runner import run_once
from desk.sport import FixtureRef
from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.decide import DecisionMeta


# ── Test doubles ────────────────────────────────────────────────────

class _FakeSport:
    code       = "football"
    short_code = "fb"
    label      = "Football"

    def __init__(
        self,
        priced: list[tuple[FixtureRef, MarketSnapshot]],
        verdicts: dict[str, Verdict] | None = None,
        stats: IngestStats | None = None,
        metas: dict[str, DecisionMeta] | None = None,
        model_sources: list[SourceStatus] | None = None,
    ) -> None:
        self._priced = priced
        self._verdicts = verdicts or {}
        self._stats = stats
        self._metas = metas or {}
        self._model_sources = model_sources

    def market_outcomes(self):
        return ("a", "draw", "b")

    def list_priced_fixtures(self) -> Iterable[tuple[FixtureRef, MarketSnapshot]]:
        return iter(self._priced)

    def last_ingest_stats(self) -> IngestStats | None:
        return self._stats

    def last_model_sources(self) -> list[SourceStatus]:
        return list(self._model_sources or [])

    def decide(self, fx: FixtureRef, snapshot: MarketSnapshot) -> Verdict:
        return self._verdicts.get(fx.match_id, Verdict(state=VerdictState.PASS))

    def decide_and_explain(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
    ) -> tuple[Verdict, Copy, DecisionMeta]:
        """Return the 3-tuple shape introduced in PR 2. Tests opt into
        this path by registering a meta for a given fixture; otherwise
        the meta is a vanilla, non-forced one.

        Delegates to `self.decide()` so subclasses that override `decide`
        (e.g. to raise) win without having to re-override this method.
        """
        v = self.decide(fx, snapshot)
        m = self._metas.get(fx.match_id, DecisionMeta())
        return v, Copy(), m


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


def _snap(match_id: str, *, venues: tuple[str, ...] = ()) -> MarketSnapshot:
    prices = tuple(
        VenuePrice(venue=v, side=s, implied_p=0.33)
        for v in venues for s in ("a", "draw", "b")
    )
    return MarketSnapshot(
        match_id=match_id,
        asof=datetime.now(tz=timezone.utc),
        prices=prices,
    )


@pytest.fixture
def two_priced() -> list[tuple[FixtureRef, MarketSnapshot]]:
    return [
        (_fx("fb-wc26-fra-mex-20260612",
             datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
             team_a="France", team_b="Mexico"),
         _snap("fb-wc26-fra-mex-20260612", venues=("polymarket", "kalshi"))),
        (_fx("fb-wc26-usa-can-20260613",
             datetime(2026, 6, 13, 20, 0, tzinfo=timezone.utc),
             team_a="USA", team_b="Canada"),
         _snap("fb-wc26-usa-can-20260613", venues=("polymarket",))),
    ]


def _stats_ok(*, raw_events: int, after_filter: int, priced: int,
              kalshi_hits: int = 0) -> IngestStats:
    now = datetime.now(tz=timezone.utc)
    return IngestStats(
        raw_events=raw_events,
        after_filter=after_filter,
        priced=priced,
        kalshi_hits=kalshi_hits,
        priced_note=f"{kalshi_hits} of {priced} with kalshi coverage",
        sources=[
            SourceStatus(id="polymarket_gamma", status=SourceFreshness.FRESH,
                         last_ok=now, detail="fixture-of-record"),
            SourceStatus(id="kalshi_kxwcgame", status=SourceFreshness.FRESH,
                         last_ok=now, detail="2nd venue"),
        ],
    )


# ── RunReport assembly: internal consistency ─────────────────────────

def test_run_report_funnel_is_internally_consistent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_priced,
) -> None:
    """Funnel + verdicts must agree:

    - verdict_eligible == priced − sum(forced_pass.*)   (PR 1: forced_pass = 0)
    - pick+pass+avoid == published
    """
    sport = _FakeSport(
        two_priced,
        stats=_stats_ok(raw_events=50, after_filter=2, priced=2, kalshi_hits=1),
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")

    rec = Recorder(root=tmp_path / "output" / "ops")
    report = rec.latest()
    assert report is not None

    by_stage = {s.stage: s.n for s in report.funnel}
    assert by_stage["polymarket_events"]        == 50
    assert by_stage["after_competition_filter"] == 2
    assert by_stage["priced_fixtures"]          == 2
    assert by_stage["verdict_eligible"] == by_stage["priced_fixtures"] - report.forced_pass.total()
    assert by_stage["published"]                == 2
    assert (report.verdicts.pick
            + report.verdicts.pass_
            + report.verdicts.avoid) == by_stage["published"]


def test_run_report_records_pick_in_snapshot_with_edge_and_venues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    two_priced,
) -> None:
    """Snapshot rows carry verdict shape + venue set so PR 3's diff
    engine has everything it needs without re-reading per-match JSON."""
    pick = Verdict(
        state=VerdictState.PICK, side="France", market_venue=MarketVenue.POLYMARKET,
        price="-180", edge_pp=4.2,
        market_url="https://polymarket.com/event/fifwc-fra-mex-2026-06-12",
        model_p=0.46, market_p=0.42,
    )
    sport = _FakeSport(
        two_priced,
        verdicts={"fb-wc26-fra-mex-20260612": pick},
        stats=_stats_ok(raw_events=50, after_filter=2, priced=2, kalshi_hits=1),
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    report = Recorder(root=tmp_path / "output" / "ops").latest()
    rows_by_id = {r.match_id: r for r in report.snapshot}

    fra = rows_by_id["fb-wc26-fra-mex-20260612"]
    assert fra.verdict_state == "pick"
    assert fra.pick_side == "France"
    assert fra.edge_pp == 4.2
    assert fra.venues == ["kalshi", "polymarket"]   # sorted

    usa = rows_by_id["fb-wc26-usa-can-20260613"]
    assert usa.verdict_state == "pass"
    assert usa.pick_side is None
    assert usa.venues == ["polymarket"]


# ── Status classification ───────────────────────────────────────────

def test_status_partial_when_kalshi_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, two_priced,
) -> None:
    """A Kalshi failure with Polymarket still working → `partial`."""
    stats = IngestStats(
        raw_events=50, after_filter=2, priced=2, kalshi_hits=0,
        sources=[
            SourceStatus(id="polymarket_gamma", status=SourceFreshness.FRESH,
                         last_ok=datetime.now(tz=timezone.utc), detail="ok"),
            SourceStatus(id="kalshi_kxwcgame", status=SourceFreshness.FAILED,
                         last_ok=None, detail="pull failed: 503"),
        ],
    )
    sport = _FakeSport(two_priced, stats=stats)
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    assert Recorder(root=tmp_path / "output" / "ops").latest().status == "partial"


def test_status_fail_when_polymarket_returns_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No priced fixtures and the gamma source failed → `fail`."""
    stats = IngestStats(
        raw_events=None, after_filter=0, priced=0,
        sources=[
            SourceStatus(id="polymarket_gamma", status=SourceFreshness.FAILED,
                         last_ok=None, detail="fetch failed"),
        ],
    )
    sport = _FakeSport([], stats=stats)
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    assert Recorder(root=tmp_path / "output" / "ops").latest().status == "fail"


def test_status_ok_on_clean_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, two_priced,
) -> None:
    sport = _FakeSport(
        two_priced,
        stats=_stats_ok(raw_events=2, after_filter=2, priced=2, kalshi_hits=2),
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    assert Recorder(root=tmp_path / "output" / "ops").latest().status == "ok"


# ── Per-fixture errors land in the structured log ────────────────────

def test_decide_failure_appears_in_errors_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, two_priced,
) -> None:
    class _BlowupSport(_FakeSport):
        def decide(self, fx, snapshot):
            if fx.match_id == "fb-wc26-fra-mex-20260612":
                raise RuntimeError("synthetic decide failure")
            return Verdict(state=VerdictState.PASS)

    monkeypatch.setattr(
        "desk.runner.active_sports",
        lambda: [_BlowupSport(
            two_priced,
            stats=_stats_ok(raw_events=2, after_filter=2, priced=2),
        )],
    )

    run_once(output_dir=tmp_path / "output")
    report = Recorder(root=tmp_path / "output" / "ops").latest()
    assert any(
        e.stage == "decide" and "fb-wc26-fra-mex-20260612" in e.message
        for e in report.errors
    )
    # An errors list is enough to demote ok → partial.
    assert report.status == "partial"


# ── Recorder: atomic write, manifest, retention ─────────────────────

def _bare_report(*, run_id: str, finished_at: datetime) -> RunReport:
    return RunReport(
        run_id=run_id,
        started_at=finished_at,
        finished_at=finished_at,
        duration_s=0.0,
        trigger="manual",
        status="ok",
        competitions=["wc26"],
    )


def test_recorder_writes_canonical_json_per_run(tmp_path: Path) -> None:
    rec = Recorder(root=tmp_path / "ops")
    ts = datetime(2026, 5, 21, 6, 0, 0, tzinfo=timezone.utc)
    r = _bare_report(run_id=run_id_for(ts), finished_at=ts)
    rec.persist(r)

    path = tmp_path / "ops" / "runs" / "run-20260521T060000Z.json"
    assert path.exists()
    # Round-trips cleanly + the dashboard-key alias is in the JSON.
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["run_id"] == "run-20260521T060000Z"
    assert "pass" in body["verdicts"]  # not "pass_"


def test_recorder_manifest_lists_newest_first(tmp_path: Path) -> None:
    rec = Recorder(root=tmp_path / "ops")
    for i, hour in enumerate([6, 7, 8]):
        ts = datetime(2026, 5, 21, hour, 0, 0, tzinfo=timezone.utc)
        rec.persist(_bare_report(run_id=run_id_for(ts), finished_at=ts))

    manifest = rec.manifest()
    assert [e.run_id for e in manifest.runs] == [
        "run-20260521T080000Z",
        "run-20260521T070000Z",
        "run-20260521T060000Z",
    ]


def test_recorder_retention_prunes_oldest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_OPS_RETENTION", "3")
    rec = Recorder(root=tmp_path / "ops")
    for i, hour in enumerate([6, 7, 8, 9, 10]):
        ts = datetime(2026, 5, 21, hour, 0, 0, tzinfo=timezone.utc)
        rec.persist(_bare_report(run_id=run_id_for(ts), finished_at=ts))

    runs_dir = tmp_path / "ops" / "runs"
    surviving = sorted(p.stem for p in runs_dir.iterdir() if p.suffix == ".json")
    assert surviving == [
        "run-20260521T080000Z",
        "run-20260521T090000Z",
        "run-20260521T100000Z",
    ]
    # Manifest agrees with what's on disk.
    assert {e.run_id for e in rec.manifest().runs} == set(surviving)


def test_recorder_previous_snapshot_returns_prior_run(tmp_path: Path) -> None:
    """The diff engine in PR 3 needs this: given run-id N, hand back the
    snapshot from the most recent run strictly before N."""
    rec = Recorder(root=tmp_path / "ops")
    ts1 = datetime(2026, 5, 21, 6, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 5, 21, 7, 0, 0, tzinfo=timezone.utc)
    r1 = _bare_report(run_id=run_id_for(ts1), finished_at=ts1)
    r1.snapshot.append(FixtureRow(
        match_id="fb-wc26-fra-mex-20260612",
        verdict_state="pass",
        copy_hash="0" * 64,
    ))
    rec.persist(r1)
    rec.persist(_bare_report(run_id=run_id_for(ts2), finished_at=ts2))

    prev = rec.previous_snapshot(before_run_id=run_id_for(ts2))
    assert prev is not None
    assert len(prev) == 1
    # First run ever → no prior snapshot.
    assert rec.previous_snapshot(before_run_id=run_id_for(ts1)) is None


# ── PR 2: forced-Pass reasons + verdict_eligible math ──────────────

def test_forced_pass_counts_break_down_by_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Two stub-Elo fixtures + one illiquid fixture → `forced_pass`
    breaks down 2 / 1 and `verdict_eligible` = priced − 3."""
    pairs = [
        (_fx(f"fb-wc26-aaa-bbb-2026061{i}",
             datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc)),
         _snap(f"fb-wc26-aaa-bbb-2026061{i}", venues=("polymarket",)))
        for i in range(4)
    ]
    metas = {
        pairs[0][0].match_id: DecisionMeta(forced_pass_reason="stub_elo"),
        pairs[1][0].match_id: DecisionMeta(forced_pass_reason="stub_elo"),
        pairs[2][0].match_id: DecisionMeta(forced_pass_reason="illiquid"),
        # pairs[3] → no forced pass, vanilla Pass
    }
    sport = _FakeSport(
        pairs, metas=metas,
        stats=_stats_ok(raw_events=10, after_filter=4, priced=4),
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    report = Recorder(root=tmp_path / "output" / "ops").latest()

    assert report.forced_pass.stub_elo == 2
    assert report.forced_pass.illiquid == 1

    by_stage = {s.stage: s for s in report.funnel}
    assert by_stage["priced_fixtures"].n   == 4
    assert by_stage["verdict_eligible"].n  == 4 - 3
    assert "stub_elo" in (by_stage["verdict_eligible"].note or "")
    assert "illiquid" in (by_stage["verdict_eligible"].note or "")


def test_runner_appends_model_derived_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, two_priced,
) -> None:
    """A sport's `last_model_sources()` row lands in `report.sources`."""
    elo_seed = SourceStatus(
        id="elo_seed",
        status=SourceFreshness.FROZEN,
        last_ok=None,
        detail="model prior · 1 of 2 fixtures on stub",
    )
    sport = _FakeSport(
        two_priced,
        stats=_stats_ok(raw_events=2, after_filter=2, priced=2, kalshi_hits=1),
        model_sources=[elo_seed],
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output")
    report = Recorder(root=tmp_path / "output" / "ops").latest()
    rows = {s.id: s for s in report.sources}
    assert "elo_seed" in rows
    assert rows["elo_seed"].detail == "model prior · 1 of 2 fixtures on stub"


# ── PR 6: scheduled-trigger entry point ────────────────────────────

def test_scheduled_trigger_persists_with_correct_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, two_priced,
) -> None:
    """The main-ladder PR 6 scheduler will call `run_once(trigger=
    RunTrigger.SCHEDULED)`; the recorded report should reflect that.
    No-op until that scheduler lands — this test only proves the
    handshake works.
    """
    from desk.ops import RunTrigger
    sport = _FakeSport(
        two_priced,
        stats=_stats_ok(raw_events=2, after_filter=2, priced=2),
    )
    monkeypatch.setattr("desk.runner.active_sports", lambda: [sport])

    run_once(output_dir=tmp_path / "output", trigger=RunTrigger.SCHEDULED)
    r = Recorder(root=tmp_path / "output" / "ops").latest()
    assert r.trigger == "scheduled"


# ── Sport-boundary guard ────────────────────────────────────────────

def test_ops_modules_do_not_import_from_sports() -> None:
    """`desk/ops/` is sport-agnostic. If a future change accidentally
    imports from `desk/sports/`, the boundary guarantee in CLAUDE.md +
    THE_DESK_OPS_DASHBOARD_SPEC.md §3 breaks. Asserted by string-scan.
    """
    ops_dir = Path(__file__).resolve().parent.parent / "desk" / "ops"
    forbidden = "desk.sports."
    for f in ops_dir.iterdir():
        if f.suffix != ".py":
            continue
        body = f.read_text(encoding="utf-8")
        assert forbidden not in body, (
            f"{f.name} imports from {forbidden} — that violates the "
            "sport-boundary contract for desk/ops/"
        )


# ── Helpers used independently ──────────────────────────────────────

def test_fixture_row_from_match_hashes_copy(fra_mex_pick) -> None:
    row = fixture_row_from_match(fra_mex_pick, venues=["polymarket"])
    assert row.match_id == fra_mex_pick.match_id
    assert row.verdict_state == "pick"
    assert row.pick_side == "France"
    assert row.edge_pp == 4.2
    assert len(row.copy_hash) == 64
    # Changing the copy changes the hash.
    other = fra_mex_pick.model_copy(update={"copy": Copy(title="x", summary="y", blurb="z")})
    other_row = fixture_row_from_match(other, venues=["polymarket"])
    assert other_row.copy_hash != row.copy_hash


def test_manifest_entry_picks_up_published_from_funnel() -> None:
    from desk.ops.report import StageCount, VerdictCounts
    ts = datetime(2026, 5, 21, 6, 0, 0, tzinfo=timezone.utc)
    r = _bare_report(run_id=run_id_for(ts), finished_at=ts)
    r.funnel.append(StageCount(stage="published", n=7))
    r.verdicts = VerdictCounts(pick=2, pass_=4, avoid=1)
    entry = manifest_entry_from_report(r)
    assert entry.published == 7
    assert entry.picks == 2
    assert entry.change_count == 0
