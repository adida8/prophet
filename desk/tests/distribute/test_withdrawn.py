"""Withdrawn detection — prior index ∖ current run → withdrawn payloads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from desk.distribute.withdrawn import (
    detect_and_emit,
    load_prior_index,
    snapshot_prior_index,
)
from desk.publish import MatchOutput, Publisher
from desk.publish.contract import VerdictState


def _publish_three(pub: Publisher, fra_mex_pick: MatchOutput,
                   usa_can_pass: MatchOutput) -> list[MatchOutput]:
    """Seed disk with three matches in the football index. The third
    is a copy of fra_mex_pick with a different slug so we have a
    detectable third entry to withdraw."""
    third = fra_mex_pick.model_copy(update={
        "match_id": "fb-wc26-arg-sau-20260615",
        "team_a":   "Argentina",
        "team_b":   "Saudi Arabia",
        "kickoff_utc": datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc),
        # Verdict.side="France" wouldn't validate against the new teams
        # → drop the pick fields by switching to pass.
        "verdict": fra_mex_pick.verdict.model_copy(update={
            "state":        "pass",
            "side":         None,
            "market_venue": None,
            "price":        None,
            "edge_pp":      None,
            "market_url":   None,
            "model_p":      None,
            "market_p":     None,
        }),
    })
    matches = [fra_mex_pick, usa_can_pass, third]
    for m in matches:
        pub.write_match(m)
    pub.write_index("football", matches)
    return matches


def test_snapshot_returns_none_when_no_prior_index(tmp_publisher: Publisher) -> None:
    assert snapshot_prior_index(tmp_publisher, "football") is None


def test_detect_emits_withdrawn_for_missing_match_ids(
    tmp_publisher: Publisher,
    fra_mex_pick: MatchOutput,
    usa_can_pass: MatchOutput,
) -> None:
    seeded = _publish_three(tmp_publisher, fra_mex_pick, usa_can_pass)
    prior = snapshot_prior_index(tmp_publisher, "football")
    assert prior is not None and len(prior.matches) == 3

    # New run publishes only the first two; the third disappears.
    current_ids = [seeded[0].match_id, seeded[1].match_id]
    now = datetime.now(tz=timezone.utc) + timedelta(hours=1)

    withdrawn = detect_and_emit(
        sport="football",
        publisher=tmp_publisher,
        prior_index=prior,
        current_match_ids=current_ids,
        now=now,
    )

    assert len(withdrawn) == 1
    w = withdrawn[0]
    assert w.match_id == seeded[2].match_id
    assert w.verdict.state == VerdictState.WITHDRAWN.value
    assert w.verdict.side is None
    assert w.verdict.price is None
    assert w.team_a == seeded[2].team_a
    assert w.team_b == seeded[2].team_b
    assert w.updated_at == now
    # Disk reflects the withdrawn write.
    on_disk = tmp_publisher.read_match("football", w.match_id)
    assert on_disk.verdict.state == VerdictState.WITHDRAWN.value


def test_detect_is_noop_when_nothing_missing(
    tmp_publisher: Publisher,
    fra_mex_pick: MatchOutput,
    usa_can_pass: MatchOutput,
) -> None:
    seeded = _publish_three(tmp_publisher, fra_mex_pick, usa_can_pass)
    prior = snapshot_prior_index(tmp_publisher, "football")
    current_ids = [m.match_id for m in seeded]
    now = datetime.now(tz=timezone.utc)
    assert detect_and_emit(
        sport="football", publisher=tmp_publisher, prior_index=prior,
        current_match_ids=current_ids, now=now,
    ) == []


def test_detect_skips_already_withdrawn(
    tmp_publisher: Publisher,
    fra_mex_pick: MatchOutput,
    usa_can_pass: MatchOutput,
) -> None:
    """A match that's already in withdrawn state on disk doesn't
    re-emit. Defence against an operator manually un-pruning the index."""
    seeded = _publish_three(tmp_publisher, fra_mex_pick, usa_can_pass)
    prior = snapshot_prior_index(tmp_publisher, "football")

    now = datetime.now(tz=timezone.utc)
    withdrawn = detect_and_emit(
        sport="football", publisher=tmp_publisher, prior_index=prior,
        current_match_ids=[seeded[0].match_id, seeded[1].match_id], now=now,
    )
    assert len(withdrawn) == 1

    # Run detection again with the same prior_index. The withdrawn match
    # is still on disk (already withdrawn). Detection sees it in prior,
    # absent from current, but read_match returns the withdrawn verdict
    # so it doesn't re-emit.
    again = detect_and_emit(
        sport="football", publisher=tmp_publisher, prior_index=prior,
        current_match_ids=[seeded[0].match_id, seeded[1].match_id], now=now,
    )
    assert again == []


def test_single_shot_lifecycle(
    tmp_publisher: Publisher,
    fra_mex_pick: MatchOutput,
    usa_can_pass: MatchOutput,
) -> None:
    """End-to-end of the ADR invariant: a fixture withdrawn this run
    isn't in the NEXT run's prior_index (because the writer overwrites
    the index with live matches only), so it can't fire again."""
    seeded = _publish_three(tmp_publisher, fra_mex_pick, usa_can_pass)
    prior_run1 = snapshot_prior_index(tmp_publisher, "football")
    now = datetime.now(tz=timezone.utc)

    # Run 1: third match disappears, emits withdrawn.
    detect_and_emit(
        sport="football", publisher=tmp_publisher, prior_index=prior_run1,
        current_match_ids=[seeded[0].match_id, seeded[1].match_id], now=now,
    )

    # Simulate the runner rewriting the index with live matches only.
    tmp_publisher.write_index("football", [seeded[0], seeded[1]])

    # Run 2: prior_index no longer carries the withdrawn id.
    prior_run2 = snapshot_prior_index(tmp_publisher, "football")
    assert prior_run2 is not None
    assert seeded[2].match_id not in {e.match_id for e in prior_run2.matches}

    # Detect should be a no-op now.
    withdrawn = detect_and_emit(
        sport="football", publisher=tmp_publisher, prior_index=prior_run2,
        current_match_ids=[seeded[0].match_id, seeded[1].match_id], now=now,
    )
    assert withdrawn == []


def test_load_prior_index_handles_corrupt_file(tmp_publisher: Publisher) -> None:
    """Best-effort read — a corrupt file returns None, not a raise. The
    runner shouldn't crash on a file the writer half-wrote."""
    sport_dir = tmp_publisher.output_dir / "football"
    sport_dir.mkdir(parents=True, exist_ok=True)
    (sport_dir / "index.json").write_text("{not-json", encoding="utf-8")
    assert load_prior_index(tmp_publisher, "football") is None
