"""Tests for the loop registry + schedules.json read/write helpers.

These tests pin the contract every loop relies on:
  * `is_enabled(loop_id)` returns the per-loop default on a fresh deploy.
  * `set_loop_enabled` round-trips through disk.
  * Unknown loop_ids never raise (defensive — a typo at boot should not
    take a loop down; warning logged, returns False).
  * On-disk schema preserves unknown rows written by a newer deploy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import loop_registry as lr


@pytest.fixture
def isolated_ops_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the registry at a tmp dir so each test is hermetic."""
    monkeypatch.setenv("DESK_OPS_DIR", str(tmp_path))
    # Resolve once so the env var actually wins; loop_registry reads on demand.
    assert lr._ops_root() == tmp_path
    return tmp_path


def test_defaults_when_file_absent(isolated_ops_dir: Path) -> None:
    doc = lr.read_schedules()
    assert doc["version"] == 1
    assert doc["updated_at"] is None
    loops = doc["loops"]
    # Every registered loop has a row.
    for ld in lr.loop_defs():
        assert ld.id in loops
        assert loops[ld.id]["enabled"] is ld.default_enabled


def test_ledger_default_is_off(isolated_ops_dir: Path) -> None:
    """Pinned: ledger refresh ships disabled on a fresh install."""
    assert lr.is_enabled("ledger_refresh") is False


def test_lineups_default_is_off(isolated_ops_dir: Path) -> None:
    """Pinned: lineups loop is opt-in via the admin + DESK_LINEUP_LOOP_ENABLED env."""
    assert lr.is_enabled("lineups_refresh") is False


def test_set_loop_enabled_round_trip(isolated_ops_dir: Path) -> None:
    # Default state: ledger off.
    assert lr.is_enabled("ledger_refresh") is False
    # Flip on, persist, re-read.
    lr.set_loop_enabled("ledger_refresh", True)
    assert lr.is_enabled("ledger_refresh") is True
    # Flip off again.
    lr.set_loop_enabled("ledger_refresh", False)
    assert lr.is_enabled("ledger_refresh") is False


def test_unknown_loop_id_returns_false(isolated_ops_dir: Path) -> None:
    """Defensive — a typo in a loop's LOOP_ID must not raise."""
    assert lr.is_enabled("not_a_real_loop") is False


def test_set_unknown_loop_id_raises(isolated_ops_dir: Path) -> None:
    with pytest.raises(KeyError):
        lr.set_loop_enabled("not_a_real_loop", True)


def test_preserves_unknown_rows(isolated_ops_dir: Path, tmp_path: Path) -> None:
    """A newer deploy may write a row for a loop this build doesn't know.

    Old code must preserve it round-trip — read includes it (as merged),
    write keeps it.
    """
    path = tmp_path / "schedules.json"
    raw = {
        "version": 1,
        "loops": {
            "ledger_refresh":     {"enabled": True, "tick_sec": 1800},
            "future_loop_v2":     {"enabled": True, "tick_sec": 999},
        },
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    doc = lr.read_schedules()
    assert doc["loops"]["ledger_refresh"]["enabled"] is True
    assert doc["loops"]["future_loop_v2"]["tick_sec"] == 999
    # Round-trip: writing should preserve future_loop_v2.
    lr.set_loop_enabled("ledger_refresh", False)
    after = json.loads(path.read_text(encoding="utf-8"))
    assert "future_loop_v2" in after["loops"]
    assert after["loops"]["future_loop_v2"]["tick_sec"] == 999


def test_corrupt_file_falls_back_to_defaults(isolated_ops_dir: Path, tmp_path: Path) -> None:
    (tmp_path / "schedules.json").write_text("not json", encoding="utf-8")
    doc = lr.read_schedules()
    # Falls back cleanly without raising.
    assert "loops" in doc
    assert lr.is_enabled("ledger_refresh") is False


def test_enabled_coerced_to_bool(isolated_ops_dir: Path, tmp_path: Path) -> None:
    """Truthy non-bool values from disk are coerced — defends against
    a hand-edited file that wrote 1 / "yes" / etc."""
    path = tmp_path / "schedules.json"
    raw = {
        "version": 1,
        "loops": {"ledger_refresh": {"enabled": 1}},
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    doc = lr.read_schedules()
    assert doc["loops"]["ledger_refresh"]["enabled"] is True
