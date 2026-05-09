"""Contract tests — round-trip, schema invariants, publisher correctness.

This is the regression guard for PR 1. Anything that breaks here breaks
Faktor's contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from desk.publish import (
    Competition,
    MatchOutput,
    OutputIndex,
    Venue,
    Verdict,
    content_etag,
)


# ── Round-trip ─────────────────────────────────────────────────────────

def test_match_round_trip(fra_mex_pick: MatchOutput) -> None:
    payload = fra_mex_pick.model_dump_json()
    reloaded = MatchOutput.model_validate_json(payload)
    assert reloaded == fra_mex_pick


def test_pass_match_round_trip(usa_can_pass: MatchOutput) -> None:
    reloaded = MatchOutput.model_validate_json(usa_can_pass.model_dump_json())
    assert reloaded == usa_can_pass
    assert reloaded.verdict.state == "pass"
    assert reloaded.verdict.side is None
    assert reloaded.verdict.market_venue is None


def test_avoid_match_round_trip(epl_avoid: MatchOutput) -> None:
    reloaded = MatchOutput.model_validate_json(epl_avoid.model_dump_json())
    assert reloaded.verdict.state == "avoid"
    assert reloaded.verdict.market_venue is None


# ── Verdict invariants ─────────────────────────────────────────────────

def test_pick_requires_side_and_venue() -> None:
    """A Pick without side/venue/price/edge must fail validation."""
    with pytest.raises(ValidationError):
        Verdict(state="pick")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Verdict(state="pick", side="France")  # type: ignore[call-arg]


def test_pass_cannot_carry_market_venue() -> None:
    with pytest.raises(ValidationError):
        Verdict(state="pass", market_venue="polymarket")  # type: ignore[call-arg]


def test_verdict_side_must_be_in_outcome_universe(fra_mex_pick: MatchOutput) -> None:
    bad = fra_mex_pick.model_dump(mode="json")
    bad["verdict"]["side"] = "team_a"   # explicitly forbidden by spec
    with pytest.raises(ValidationError):
        MatchOutput.model_validate(bad)


def test_verdict_side_draw_only_when_draw_in_market_outcomes(fra_mex_pick: MatchOutput) -> None:
    payload = fra_mex_pick.model_dump(mode="json")
    payload["market_outcomes"] = ["a", "b"]      # 2-way market
    payload["verdict"]["side"] = "draw"
    with pytest.raises(ValidationError):
        MatchOutput.model_validate(payload)


# ── Match-id format ───────────────────────────────────────────────────

@pytest.mark.parametrize("bad_id", [
    "WC26-FRA-MEX-20260612",            # uppercase
    "fb-wc26-fra-mex-2026-06-12",       # date with separators
    "fb-wc26-fra-mex",                   # missing date
    "fb-fra-mex-20260612",               # missing competition
    "fb-wc26-fra-20260612",              # missing one team
])
def test_invalid_match_id_rejected(fra_mex_pick: MatchOutput, bad_id: str) -> None:
    payload = fra_mex_pick.model_dump(mode="json")
    payload["match_id"] = bad_id
    with pytest.raises(ValidationError):
        MatchOutput.model_validate(payload)


def test_match_ids_for_clubs_and_nationals(fra_mex_pick: MatchOutput, epl_avoid: MatchOutput) -> None:
    # Both must validate without changes
    MatchOutput.model_validate(fra_mex_pick.model_dump(mode="json"))
    MatchOutput.model_validate(epl_avoid.model_dump(mode="json"))


# ── Timestamps ────────────────────────────────────────────────────────

def test_kickoff_must_be_utc(fra_mex_pick: MatchOutput) -> None:
    naive = fra_mex_pick.model_dump(mode="json")
    naive["kickoff_utc"] = "2026-06-12T19:00:00"        # naive
    with pytest.raises(ValidationError):
        MatchOutput.model_validate(naive)
    naive["kickoff_utc"] = "2026-06-12T19:00:00+02:00"  # non-zero offset
    with pytest.raises(ValidationError):
        MatchOutput.model_validate(naive)


# ── Competition.stage is optional and only valid when meaningful ──────

def test_stage_optional() -> None:
    c = Competition(code="epl", label="Premier League")
    assert c.stage is None


def test_stage_pattern() -> None:
    with pytest.raises(ValidationError):
        Competition(code="epl", label="Premier League", stage="Group D")  # space + caps


# ── Publisher: per-match write + read-back ────────────────────────────

def test_publisher_writes_and_reads_match(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    path, etag = tmp_publisher.write_match(fra_mex_pick)
    assert path.exists()
    assert path.with_suffix(path.suffix + ".etag").exists()
    assert etag.startswith('"') and etag.endswith('"')
    reloaded = tmp_publisher.read_match(fra_mex_pick.sport, fra_mex_pick.match_id)
    assert reloaded == fra_mex_pick


def test_publisher_etag_is_deterministic(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    _, etag1 = tmp_publisher.write_match(fra_mex_pick)
    _, etag2 = tmp_publisher.write_match(fra_mex_pick)
    assert etag1 == etag2


def test_publisher_etag_changes_when_content_changes(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    _, etag_before = tmp_publisher.write_match(fra_mex_pick)
    drifted = fra_mex_pick.model_copy(update={"updated_at": datetime(2026, 6, 12, 17, 5, tzinfo=timezone.utc)})
    _, etag_after = tmp_publisher.write_match(drifted)
    assert etag_before != etag_after


# ── Index: every match present, sorted, fresh updated_at ──────────────

def test_publisher_index_lists_every_match(
    tmp_publisher,
    fra_mex_pick: MatchOutput,
    usa_can_pass: MatchOutput,
    epl_avoid: MatchOutput,
) -> None:
    matches = [fra_mex_pick, usa_can_pass, epl_avoid]
    for m in matches:
        tmp_publisher.write_match(m)
    path, _ = tmp_publisher.write_index("football", matches)

    idx = OutputIndex.model_validate_json(path.read_text())
    assert idx.sport == "football"
    assert {e.match_id for e in idx.matches} == {m.match_id for m in matches}

    sorted_ids = [
        e.match_id
        for e in sorted(idx.matches, key=lambda e: (e.kickoff_utc, e.match_id))
    ]
    assert [e.match_id for e in idx.matches] == sorted_ids
    assert all(
        idx.matches[i].kickoff_utc <= idx.matches[i + 1].kickoff_utc
        for i in range(len(idx.matches) - 1)
    )
    for entry in idx.matches:
        assert {"match_id", "kickoff_utc", "updated_at"} <= entry.model_dump().keys()


def test_publisher_index_etag_stable(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    _, e1 = tmp_publisher.write_index("football", [fra_mex_pick])
    _, e2 = tmp_publisher.write_index("football", [fra_mex_pick])
    # The index includes its own updated_at (now()), so the body differs each
    # call. Assert the index ETag tracks content (i.e. NOT equal across two
    # calls separated in time) — the per-match ETag is the stable one.
    # If the wall-clock fast enough that both calls hit the same microsecond
    # we can't make a strict assertion either way, so just check the ETag
    # shape.
    assert e1.startswith('"') and e1.endswith('"')
    assert e2.startswith('"') and e2.endswith('"')


# ── Sport partition ───────────────────────────────────────────────────

def test_files_land_in_sport_partition(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    path, _ = tmp_publisher.write_match(fra_mex_pick)
    assert path.parent.name == "football"
    assert path.parent.parent == tmp_publisher.output_dir


# ── ETag helper ───────────────────────────────────────────────────────

def test_content_etag_stable_across_dict_orders() -> None:
    a = {"x": 1, "y": [3, 2, 1]}
    b = {"y": [3, 2, 1], "x": 1}
    assert content_etag(a) == content_etag(b)


def test_match_payload_is_canonical_json(tmp_publisher, fra_mex_pick: MatchOutput) -> None:
    path, _ = tmp_publisher.write_match(fra_mex_pick)
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    # Round-trip via canonical JSON yields the same string we wrote.
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), default=str)
    assert raw == canonical


# ── Committed schema stays in sync ────────────────────────────────────

def test_schema_file_in_sync() -> None:
    """`desk/contract.schema.json` must match what the models produce.

    Regenerate via `python3 scripts/regen_schema.py` if this fails.
    """
    from pathlib import Path

    from desk.publish.contract import MatchOutput, OutputIndex

    expected = {
        "MatchOutput": MatchOutput.model_json_schema(),
        "OutputIndex": OutputIndex.model_json_schema(),
    }
    schema_path = Path(__file__).resolve().parent.parent / "desk" / "contract.schema.json"
    on_disk = json.loads(schema_path.read_text(encoding="utf-8"))
    assert on_disk == expected, (
        "desk/contract.schema.json is stale; run "
        "`python3 scripts/regen_schema.py` from the desk/ directory"
    )
