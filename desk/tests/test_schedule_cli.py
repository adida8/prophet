"""`desk schedule` — CLI wrapper around desk_refresh_loop.py.

The wrapper must:
  * locate the project-root loop script
  * report a clean error when it's missing
  * import + call the right entry-point for `--once`
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from desk.cli import _cmd_schedule, build_parser


def test_parser_accepts_schedule_with_once():
    parser = build_parser()
    args = parser.parse_args(["schedule", "--once"])
    assert args.cmd == "schedule"
    assert args.once is True


def test_parser_accepts_schedule_without_once():
    parser = build_parser()
    args = parser.parse_args(["schedule"])
    assert args.cmd == "schedule"
    assert args.once is False


def test_missing_loop_script_returns_nonzero(tmp_path, capsys, monkeypatch):
    """Point the cli.__file__ search at a temp tree with no loop file."""
    fake_module = type(sys)("desk.cli")
    fake_path = tmp_path / "desk" / "desk" / "cli.py"
    fake_path.parent.mkdir(parents=True)
    fake_path.write_text("")
    # `_cmd_schedule` uses `Path(__file__).resolve().parents[2]` to find
    # the project root. Patch the resolved `__file__` lookup.
    with patch("desk.cli.__file__", str(fake_path)):
        from argparse import Namespace
        rc = _cmd_schedule(Namespace(once=True))
    assert rc == 2
    err = capsys.readouterr().err
    assert "desk_refresh_loop.py not found" in err


def test_once_path_invokes_tick(monkeypatch):
    """Verify --once calls the loop module's _tick exactly once."""
    calls: list[None] = []

    def fake_tick():
        calls.append(None)

    # Build a fake module that mimics desk_refresh_loop.
    fake_loop = type(sys)("desk_refresh_loop")
    fake_loop._tick = fake_tick

    real_spec_from_file = __import__("importlib").util.spec_from_file_location
    real_module_from_spec = __import__("importlib").util.module_from_spec

    def patched_spec(name, path):
        # Return a real spec but with a loader that yields our fake module.
        class _Loader:
            def exec_module(self, mod):
                mod._tick = fake_tick

        class _Spec:
            loader = _Loader()
            name = "desk_refresh_loop"

        return _Spec()

    def patched_module_from_spec(_spec):
        return type(sys)("desk_refresh_loop")

    monkeypatch.setattr(
        "importlib.util.spec_from_file_location", patched_spec,
    )
    monkeypatch.setattr(
        "importlib.util.module_from_spec", patched_module_from_spec,
    )

    # `_cmd_schedule` first asserts the loop file exists; we let it
    # point at the real path (which does exist in the working tree).
    from argparse import Namespace
    rc = _cmd_schedule(Namespace(once=True))
    assert rc == 0
    assert len(calls) == 1
