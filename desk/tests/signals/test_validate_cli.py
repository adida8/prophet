"""`desk signals validate` CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk.cli import build_parser


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    out = capsys.readouterr()
    return code, out.out, out.err


# ── happy path ───────────────────────────────────────────────────────

def test_validate_loads_shipped_seed(capsys):
    code, out, _err = _run(["signals", "validate"], capsys)
    assert code == 0
    assert "can_feed_model:" in out
    assert "editorial_only:" in out
    # We name at least the first row in the shipped seed.
    assert "bbc-sport" in out


def test_validate_reports_feed_type_breakdown(capsys):
    _, out, _ = _run(["signals", "validate"], capsys)
    assert "by feed_type:" in out
    assert "rss=" in out
    # Shipped seed today has feed_type=none rows (Reuters, AP, …).
    assert "none=" in out


def test_validate_resolve_smoke(capsys):
    _, out, _ = _run(["signals", "validate", "--resolve", "global,sport:football"], capsys)
    assert "resolve" in out
    assert "match" in out


# ── failure path ─────────────────────────────────────────────────────

def test_validate_returns_nonzero_on_bad_seed(tmp_path: Path, capsys):
    path = tmp_path / "bad.csv"
    # Missing several required columns.
    path.write_text("id,name\nfoo,Foo\n", encoding="utf-8")
    code, _out, err = _run(["signals", "validate", "--seed", str(path)], capsys)
    assert code == 2
    assert "missing required columns" in err


def test_validate_surfaces_per_row_error(tmp_path: Path, capsys):
    """The loader's per-row error wrapping is the load-bearing piece for
    `validate` — without it the operator sees a stack of Pydantic
    spew without knowing which row to fix."""
    path = tmp_path / "bad.csv"
    path.write_text(
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,tier,enabled\n"
        # Two valid rows, then a bad feed_type to trigger the error
        # mid-file so the line number is something other than 2.
        "bbc,BBC,rss,https://bbc/r,en,global,0.9,none,trusted_core,true\n"
        "guardian,Guardian,rss,https://g/r,en,global,0.9,none,trusted_core,true\n"
        "broken,Broken,carrier-pigeon,https://x,en,global,0.9,none,trusted_core,true\n",
        encoding="utf-8",
    )
    code, _out, err = _run(["signals", "validate", "--seed", str(path)], capsys)
    assert code == 2
    # The error names the line number and the source id.
    assert ":4" in err
    assert "broken" in err
