"""Phase 1b live-Elo bridge for the outright winner sim."""

from __future__ import annotations

from desk.data.elo.cache import EloCache
from desk.data.elo.runtime import EloRuntime
from desk.outrights.live_elo import (
    live_elo_overrides_for_field, merge_elo_overrides,
)
from desk.outrights.wc26_data import elo as outright_seed_elo


def test_empty_cache_yields_no_overrides(tmp_path):
    """No live cache file ⇒ runtime falls through to seed ⇒
    `national_elo_source` returns 'wiki'/'stub' ⇒ no overrides.
    This is the byte-identical-when-cache-absent guarantee."""
    rt = EloRuntime(tmp_path / "nope.db")
    overrides = live_elo_overrides_for_field(
        ["France", "Brazil", "Mexico"], runtime=rt,
    )
    assert overrides == {}
    rt.close()


def test_live_value_produces_delta(tmp_path):
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_national(
            "fra", 2100.0,
            source_id="eloratings", source_url="x",
        )
    rt = EloRuntime(db)
    overrides = live_elo_overrides_for_field(["France"], runtime=rt)
    expected_delta = 2100.0 - outright_seed_elo("France")
    assert "France" in overrides
    assert overrides["France"] == expected_delta
    rt.close()


def test_only_eloratings_source_triggers_override(tmp_path):
    """Even if a row exists in the cache with a non-eloratings
    source_id, we skip it — that's reserved for if/when other
    providers land."""
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_national(
            "fra", 2100.0,
            source_id="some_other_source", source_url="x",
        )
    rt = EloRuntime(db)
    overrides = live_elo_overrides_for_field(["France"], runtime=rt)
    assert overrides == {}
    rt.close()


def test_tiny_delta_dropped(tmp_path):
    """Live within 0.5 Elo of the outright seed → no override, keeps
    the dict tight."""
    db = tmp_path / "elo.db"
    seed = outright_seed_elo("Brazil")
    with EloCache(db) as cache:
        cache.upsert_national(
            "bra", seed + 0.2,           # delta < 0.5
            source_id="eloratings", source_url="x",
        )
    rt = EloRuntime(db)
    overrides = live_elo_overrides_for_field(["Brazil"], runtime=rt)
    assert overrides == {}
    rt.close()


def test_unknown_display_name_skipped(tmp_path):
    """A team name not in `iso3_for_name` is silently skipped."""
    rt = EloRuntime(tmp_path / "nope.db")
    overrides = live_elo_overrides_for_field(
        ["Not A Real Country"], runtime=rt,
    )
    assert overrides == {}
    rt.close()


# ── merge_elo_overrides ────────────────────────────────────────────

def test_merge_sums_deltas_across_sources():
    live = {"France": +30.0, "Brazil": -10.0}
    hard = {"France": -8.0,  "Mexico": -20.0}
    merged = merge_elo_overrides(live, hard)
    assert merged == {
        "France": +22.0,
        "Brazil": -10.0,
        "Mexico": -20.0,
    }


def test_merge_with_empty_sources():
    assert merge_elo_overrides({}, {}) == {}
    assert merge_elo_overrides() == {}
    assert merge_elo_overrides({"X": 1.0}) == {"X": 1.0}


def test_live_overrides_do_not_collide_with_hard_signals(tmp_path):
    """End-to-end: live + hard for the same team sum cleanly."""
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_national(
            "fra", outright_seed_elo("France") + 25.0,
            source_id="eloratings", source_url="x",
        )
    rt = EloRuntime(db)
    live = live_elo_overrides_for_field(["France"], runtime=rt)
    hard = {"France": -8.0}    # mocked injury nudge
    merged = merge_elo_overrides(live, hard)
    assert merged["France"] == 25.0 - 8.0
    rt.close()
