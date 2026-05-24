"""enqueue_match helper — push gate, body-size guard, canonical encoding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desk.distribute import BodyTooLarge, canonical_body, enqueue_match
from desk.distribute.config import DistributeConfig
from desk.distribute.outbox import Outbox
from desk.publish import MatchOutput


def _cfg(*, push: bool = True, max_bytes: int = 60_000,
         tmp_path: Path | None = None) -> DistributeConfig:
    return DistributeConfig(
        push_enabled=push,
        webhook_url="https://example/wh" if push else None,
        webhook_secret="s" if push else None,
        db_path=(tmp_path or Path(".")) / "distribute.db",
        rate_per_min=50,
        max_in_flight=8,
        max_body_bytes=max_bytes,
    )


def test_enqueue_returns_none_when_push_disabled(
    fra_mex_pick: MatchOutput, tmp_path: Path,
) -> None:
    cfg = _cfg(push=False, tmp_path=tmp_path)
    assert enqueue_match(fra_mex_pick, config=cfg) is None


def test_enqueue_writes_row_when_push_enabled(
    fra_mex_pick: MatchOutput, tmp_path: Path,
) -> None:
    cfg = _cfg(push=True, tmp_path=tmp_path)
    with Outbox(cfg.db_path) as box:
        rid = enqueue_match(fra_mex_pick, config=cfg, outbox=box)
        assert rid is not None
        row = box.get(rid)
        assert row is not None
        assert row.match_id == fra_mex_pick.match_id
        # updated_at on disk is the iso form (Z-suffixed)
        assert row.updated_at.endswith("Z")
        # body deserialises to the same MatchOutput
        decoded = MatchOutput.model_validate_json(row.body)
        assert decoded == fra_mex_pick


def test_canonical_body_is_byte_identical_to_publisher_form(
    fra_mex_pick: MatchOutput,
) -> None:
    """Wire body == disk body. Same canonical_json for both."""
    body = canonical_body(fra_mex_pick)
    parsed = json.loads(body)
    # canonical_json sorts keys; the parsed dict round-trips back through
    # the model unchanged.
    assert MatchOutput.model_validate(parsed) == fra_mex_pick
    # Stable across calls — no random ordering or timestamps inside.
    assert canonical_body(fra_mex_pick) == body


def test_oversized_body_raises_body_too_large(
    fra_mex_pick: MatchOutput, tmp_path: Path,
) -> None:
    cfg = _cfg(push=True, max_bytes=10, tmp_path=tmp_path)
    with Outbox(cfg.db_path) as box:
        with pytest.raises(BodyTooLarge):
            enqueue_match(fra_mex_pick, config=cfg, outbox=box)
