"""Registry CSV loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk.signals.registry import DEFAULT_SEED_PATH, Registry


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    header = (
        "id,name,feed_type,feed_ref,language,coverage_tags,"
        "reliability,bias_flag,parent_org,tier,enabled"
    )
    lines = [header]
    for r in rows:
        lines.append(",".join(r.get(c, "") for c in header.split(",")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_loads_shipped_seed():
    reg = Registry.from_csv()
    assert len(reg) >= 5
    assert any(s.id == "bbc-sport-football" for s in reg)


def test_shipped_seed_has_at_least_one_model_eligible_source():
    reg = Registry.from_csv()
    assert any(s.can_feed_model for s in reg), (
        "seed must contain at least one trusted-core, unbiased source "
        "or the hard-signal track has nothing to feed it"
    )


def test_shipped_seed_has_long_tail_aggregator_editorial_only():
    reg = Registry.from_csv()
    gdelt = [s for s in reg if s.tier == "long_tail"]
    assert gdelt, "expected at least one long-tail aggregator"
    assert all(s.editorial_only for s in gdelt)


def test_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "dupes.csv"
    _write_csv(path, [
        dict(id="dup", name="A", feed_type="rss", feed_ref="https://a", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             parent_org="", tier="trusted_core", enabled="true"),
        dict(id="dup", name="B", feed_type="rss", feed_ref="https://b", language="en",
             coverage_tags="global", reliability="0.9", bias_flag="none",
             parent_org="", tier="trusted_core", enabled="true"),
    ])
    with pytest.raises(ValueError, match="duplicate"):
        Registry.from_csv(path)


def test_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "short.csv"
    path.write_text("id,name\nfoo,Foo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        Registry.from_csv(path)


def test_parent_org_empty_becomes_none(tmp_path: Path):
    path = tmp_path / "noparent.csv"
    _write_csv(path, [
        dict(id="orphan", name="Orphan", feed_type="rss", feed_ref="https://o",
             language="en", coverage_tags="global", reliability="0.9",
             bias_flag="none", parent_org="", tier="trusted_core", enabled="true"),
    ])
    reg = Registry.from_csv(path)
    assert reg.get("orphan").parent_org is None


def test_enabled_false_filtered_from_enabled():
    reg = Registry.from_csv()
    all_count = len(reg.all())
    enabled_count = len(reg.enabled())
    assert all_count >= enabled_count


def test_default_seed_path_resolves():
    assert DEFAULT_SEED_PATH.exists()
