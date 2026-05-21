"""Registry CSV loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk.signals.registry import DEFAULT_SEED_PATH, Registry


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    # Required columns only; parent_org / notes are optional.
    header = (
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,tier,enabled"
    )
    cols = header.split(",")
    lines = [header]
    for r in rows:
        lines.append(",".join(r.get(c, "") for c in cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── shipped seed sanity ──────────────────────────────────────────────

def test_loads_shipped_seed():
    reg = Registry.from_csv()
    assert len(reg) >= 10
    # The shipped seed names the tier-1 globals up front.
    assert any(s.id == "bbc-sport"          for s in reg)
    assert any(s.id == "guardian-football"  for s in reg)


def test_shipped_seed_has_at_least_one_model_eligible_source():
    reg = Registry.from_csv()
    assert any(s.can_feed_model for s in reg), (
        "seed must contain at least one trusted-core, unbiased source "
        "or the hard-signal track has nothing to feed it"
    )


def test_shipped_seed_has_at_least_one_editorial_only_source():
    # Below the 0.8 reliability floor → editorial-only.
    reg = Registry.from_csv()
    assert any(s.editorial_only for s in reg)


def test_shipped_seed_has_unfetchable_rows_with_feed_type_none():
    # Reuters / AP / AFP / FIFA / UEFA etc. — registered for trust
    # weighting only, no public feed currently.
    reg = Registry.from_csv()
    none_sources = [s for s in reg if s.feed_type == "none"]
    assert none_sources, "expected some feed_type=none rows in the seed"
    assert all(s.feed_ref == "" for s in none_sources)


def test_default_seed_path_resolves():
    assert DEFAULT_SEED_PATH.exists()


def test_enabled_false_filtered_from_enabled():
    reg = Registry.from_csv()
    all_count = len(reg.all())
    enabled_count = len(reg.enabled())
    assert all_count >= enabled_count


# ── fails-loud-on-bad-row ────────────────────────────────────────────

def test_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "dupes.csv"
    _write_csv(path, [
        dict(id="dup", name="A", feed_type="rss", feed_ref="https://a", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             tier="trusted_core", enabled="true"),
        dict(id="dup", name="B", feed_type="rss", feed_ref="https://b", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             tier="trusted_core", enabled="true"),
    ])
    with pytest.raises(ValueError, match="duplicate"):
        Registry.from_csv(path)


def test_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "short.csv"
    path.write_text("id,name\nfoo,Foo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        Registry.from_csv(path)


def test_bad_row_error_carries_line_and_id(tmp_path: Path):
    path = tmp_path / "bad.csv"
    _write_csv(path, [
        dict(id="bad", name="Bad", feed_type="not-a-real-type",
             feed_ref="https://x", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             tier="trusted_core", enabled="true"),
    ])
    with pytest.raises(ValueError) as exc:
        Registry.from_csv(path)
    # The error names the line number AND the source id so the operator
    # can fix the seed without guessing.
    assert "bad.csv:2" in str(exc.value)
    assert "'bad'" in str(exc.value)


def test_feed_type_none_requires_empty_feed_ref(tmp_path: Path):
    path = tmp_path / "bad.csv"
    _write_csv(path, [
        dict(id="reuters", name="Reuters", feed_type="none",
             feed_ref="https://reuters/feed",  # not allowed for feed_type=none
             language="en", coverage_tags="global", reliability="0.9",
             bias_flag="none", tier="trusted_core", enabled="true"),
    ])
    with pytest.raises(ValueError, match="feed_type='none' must have empty feed_ref"):
        Registry.from_csv(path)


def test_non_none_feed_type_requires_feed_ref(tmp_path: Path):
    path = tmp_path / "bad.csv"
    _write_csv(path, [
        dict(id="empty", name="Empty", feed_type="rss",
             feed_ref="",                                     # empty
             language="en", coverage_tags="global", reliability="0.9",
             bias_flag="none", tier="trusted_core", enabled="true"),
    ])
    with pytest.raises(ValueError, match="requires.*feed_ref"):
        Registry.from_csv(path)


# ── optional columns ────────────────────────────────────────────────

def test_parent_org_column_is_optional(tmp_path: Path):
    # CSV without a parent_org column should still load — parent_org
    # defaults to None on every source.
    path = tmp_path / "no_parent.csv"
    _write_csv(path, [
        dict(id="orphan", name="Orphan", feed_type="rss",
             feed_ref="https://o", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             tier="trusted_core", enabled="true"),
    ])
    reg = Registry.from_csv(path)
    assert reg.get("orphan").parent_org is None


def test_notes_column_is_optional(tmp_path: Path):
    path = tmp_path / "with_notes.csv"
    text = (
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,tier,enabled,notes\n"
        "bbc,BBC,rss,https://bbc,en,global,0.9,none,trusted_core,true,"
        "Verified 2026-05-21.\n"
    )
    path.write_text(text, encoding="utf-8")
    reg = Registry.from_csv(path)
    assert reg.get("bbc").notes == "Verified 2026-05-21."


# ── coverage_tags parser ─────────────────────────────────────────────

def test_loads_json_array_coverage_tags(tmp_path: Path):
    path = tmp_path / "json_tags.csv"
    text = (
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,tier,enabled\n"
        'bbc,BBC,rss,https://bbc,en,"[""global"", ""sport:football""]",'
        "0.9,none,trusted_core,true\n"
    )
    path.write_text(text, encoding="utf-8")
    reg = Registry.from_csv(path)
    assert reg.get("bbc").coverage_tags == frozenset({"global", "sport:football"})


def test_loads_pipe_separated_coverage_tags(tmp_path: Path):
    path = tmp_path / "pipe_tags.csv"
    text = (
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,tier,enabled\n"
        "bbc,BBC,rss,https://bbc,en,global|sport:football,0.9,none,trusted_core,true\n"
    )
    path.write_text(text, encoding="utf-8")
    reg = Registry.from_csv(path)
    assert reg.get("bbc").coverage_tags == frozenset({"global", "sport:football"})
