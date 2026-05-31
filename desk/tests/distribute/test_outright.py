"""Outright wire transform + enqueue_outright.

Covers the two MTA-contract adjustments (content_type discriminator +
hard_signal_adjustments lifted to a top-level object list), spine
preservation, the byte-size guard, the push gate, and outbox collapse
keyed on outright_id.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from desk.distribute import (
    BodyTooLarge,
    canonical_body_outright,
    enqueue_outright,
    outright_wire_payload,
)
from desk.distribute.config import DistributeConfig
from desk.distribute.outbox import Outbox
from desk.distribute.signing import sign, verify
from desk.publish.etag import canonical_json


def _cfg(*, push: bool = True, max_bytes: int = 60_000,
         tmp_path: Path | None = None,
         include_cross_venue: bool = True) -> DistributeConfig:
    return DistributeConfig(
        push_enabled=push,
        webhook_url="https://example/wh" if push else None,
        webhook_secret="s" if push else None,
        db_path=(tmp_path or Path(".")) / "distribute.db",
        rate_per_min=50,
        max_in_flight=8,
        max_body_bytes=max_bytes,
        include_cross_venue=include_cross_venue,
    )


@pytest.fixture
def published_pick() -> dict:
    """A published outright dict shaped like build_payload's output, with
    a pick verdict + a hard-signal nudge nested under `model`."""
    return {
        "outright_id": "fb-wc26-winner",
        "sport": "football",
        "competition": {"code": "wc26", "label": "FIFA World Cup 2026",
                        "stage": "pre_tournament"},
        "market_label": "World Cup 2026 — outright winner",
        "market_venue": "polymarket",
        "market_url": "https://polymarket.com/event/2026-fifa-world-cup-winner-595",
        "candidate": "Argentina",
        "resolves_at": "2026-07-20T00:00:00Z",
        "asof": "2026-05-28T17:44:23.055015Z",
        "verdict": {
            "state": "pick", "candidate": "YES Argentina", "side": "YES",
            "team": "Argentina", "edge_pp": 10.33, "lower_edge_pp": 3.35,
            "model_p": 0.1878, "model_p_lower": 0.118, "model_p_upper": 0.254,
            "market_p": 0.0845, "market_venue": "polymarket",
            "market_url": "https://polymarket.com/event/2026-fifa-world-cup-winner-595",
            "price": "+1083",
        },
        "copy": {
            "title": "Argentina · the model leans yes",
            "summary": "...", "blurb": "...", "drivers": ["a", "b"],
        },
        "model": {
            "sims": 10000, "bootstrap_samples": 100, "seed": 42,
            "overround_pp": 3.5,
            "hard_signal_adjustments": [
                {
                    "team": "USA", "delta_elo": -8.0, "capped": False,
                    "reason": "Chris Richards ligament injury.",
                    "signal_type": "injury",
                    "signal_url": "https://www.espn.com/soccer/story/_/id/1",
                    "source_id": "espn-soccer", "source_name": "ESPN (soccer)",
                    "published_at": "2026-05-21T15:58:17-05:00",
                },
            ],
        },
        "ladder": [
            {"team": "Argentina", "model_p": 0.1878, "model_p_lower": 0.118,
             "model_p_upper": 0.254, "yes_market_p": 0.0845,
             "no_market_p": 0.9155, "yes_edge_pp": 10.33, "no_edge_pp": -10.33,
             "yes_lower_edge_pp": 3.35, "no_lower_edge_pp": -16.95,
             "verdict": "pick", "pick_side": "YES"},
        ],
        "updated_at": "2026-05-28T17:44:38.157322Z",
    }


@pytest.fixture
def published_pass() -> dict:
    """A pass outright — verdict carries only state + null candidate, and
    no hard-signal adjustments under model."""
    return {
        "outright_id": "fb-wc26-winner",
        "sport": "football",
        "competition": {"code": "wc26", "label": "FIFA World Cup 2026",
                        "stage": "pre_tournament"},
        "market_label": "World Cup 2026 — outright winner",
        "market_venue": "polymarket",
        "market_url": "https://polymarket.com/event/x",
        "candidate": "—",
        "resolves_at": "2026-07-20T00:00:00Z",
        "asof": "2026-05-28T17:44:23Z",
        "verdict": {"state": "pass", "candidate": None},
        "copy": {"title": "t", "summary": "s", "blurb": "b", "drivers": []},
        "model": {"sims": 10000, "bootstrap_samples": 100, "seed": 42,
                  "overround_pp": 3.5},
        "ladder": [],
        "updated_at": "2026-05-28T17:44:38Z",
    }


# ── transform ─────────────────────────────────────────────────────────

def test_wire_adds_content_type(published_pick: dict) -> None:
    wire = outright_wire_payload(published_pick)
    assert wire["content_type"] == "outright"


def test_wire_lifts_hard_signals_to_top_level(published_pick: dict) -> None:
    wire = outright_wire_payload(published_pick)
    # Lifted to top level…
    assert isinstance(wire["hard_signal_adjustments"], list)
    assert wire["hard_signal_adjustments"][0]["team"] == "USA"
    # …and removed from the model block (one home, matches MatchOutput).
    assert "hard_signal_adjustments" not in wire["model"]


def test_wire_hard_signals_stay_structured_objects(published_pick: dict) -> None:
    """MTA relaxed the field to objects — we must NOT stringify them."""
    adj = outright_wire_payload(published_pick)["hard_signal_adjustments"][0]
    assert isinstance(adj, dict)
    # outright nudge keys on team, no a/b side like a match adjustment
    assert "side" not in adj
    assert adj["delta_elo"] == -8.0
    assert adj["signal_url"].startswith("https://")


def test_wire_empty_hard_signals_when_none(published_pass: dict) -> None:
    wire = outright_wire_payload(published_pass)
    # Always present for spine parity, even though the published dict had
    # no `model.hard_signal_adjustments` key.
    assert wire["hard_signal_adjustments"] == []


def test_wire_preserves_spine(published_pick: dict) -> None:
    wire = outright_wire_payload(published_pick)
    for field in ("outright_id", "sport", "competition", "copy", "verdict",
                  "ladder", "resolves_at", "updated_at", "market_venue",
                  "market_url", "candidate"):
        assert wire[field] == published_pick[field]


def test_wire_is_non_mutating(published_pick: dict) -> None:
    before = copy.deepcopy(published_pick)
    outright_wire_payload(published_pick)
    assert published_pick == before  # original untouched


def test_canonical_body_is_deterministic_and_minified(published_pick: dict) -> None:
    body = canonical_body_outright(published_pick)
    assert canonical_body_outright(published_pick) == body  # stable
    # minified: no space after JSON separators, no newlines/indentation
    # (string values may still contain spaces, so check the separators).
    assert b'": "' not in body and b'", "' not in body and b"\n" not in body
    parsed = json.loads(body)
    assert parsed["content_type"] == "outright"
    # byte-identical to encoding the wire dict directly through canonical_json
    assert body == canonical_json(outright_wire_payload(published_pick)).encode("utf-8")


def test_canonical_body_signs_and_verifies(published_pick: dict) -> None:
    """The signing path is payload-agnostic — same as matches."""
    body = canonical_body_outright(published_pick)
    sig = sign(1716988523, body, "shared-secret")
    assert verify(1716988523, body, "shared-secret", sig)


# ── enqueue ───────────────────────────────────────────────────────────

def test_enqueue_returns_none_when_push_disabled(published_pick: dict) -> None:
    cfg = _cfg(push=False)
    assert enqueue_outright(published_pick, config=cfg) is None


def test_enqueue_writes_row_keyed_on_outright_id(
    published_pick: dict, tmp_path: Path,
) -> None:
    cfg = _cfg(push=True, tmp_path=tmp_path)
    with Outbox(cfg.db_path) as box:
        rid = enqueue_outright(published_pick, config=cfg, outbox=box)
        assert rid is not None
        row = box.get(rid)
        assert row is not None
        assert row.match_id == "fb-wc26-winner"
        assert row.updated_at == "2026-05-28T17:44:38.157322Z"
        # body round-trips to the wire shape
        decoded = json.loads(row.body)
        assert decoded["content_type"] == "outright"
        assert decoded["hard_signal_adjustments"][0]["team"] == "USA"


def test_enqueue_collapses_to_one_pending_row(
    published_pick: dict, tmp_path: Path,
) -> None:
    cfg = _cfg(push=True, tmp_path=tmp_path)
    with Outbox(cfg.db_path) as box:
        enqueue_outright(published_pick, config=cfg, outbox=box)
        newer = copy.deepcopy(published_pick)
        newer["updated_at"] = "2026-05-29T00:00:00Z"
        enqueue_outright(newer, config=cfg, outbox=box)
        # collapse rule: one pending row per id, newer body wins
        assert box.pending_count() == 1


def test_oversized_body_raises(published_pick: dict, tmp_path: Path) -> None:
    cfg = _cfg(push=True, max_bytes=10, tmp_path=tmp_path)
    with Outbox(cfg.db_path) as box:
        with pytest.raises(BodyTooLarge):
            enqueue_outright(published_pick, config=cfg, outbox=box)
