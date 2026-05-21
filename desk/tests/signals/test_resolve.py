"""Tag-intersection resolver."""

from __future__ import annotations

from desk.signals.models import Source
from desk.signals.registry import Registry
from desk.signals.resolve import sources_for


def _src(id: str, tags: str, reliability: float = 0.9, enabled: bool = True,
         tier: str = "trusted_core", bias_flag: str = "none") -> Source:
    return Source.model_validate(dict(
        id=id, name=id, feed_type="rss", feed_ref=f"https://{id}",
        language="en", coverage_tags=tags, reliability=reliability,
        bias_flag=bias_flag, parent_org=None, tier=tier, enabled=enabled,
    ))


def _registry(*sources: Source) -> Registry:
    return Registry(sources)


def test_returns_sources_whose_tags_intersect():
    reg = _registry(
        _src("bbc",     "global|sport:football"),
        _src("ole",     "country:ar|sport:football"),
        _src("clarin",  "country:ar"),
        _src("la-times","country:us"),
    )
    want = {"global", "sport:football", "country:ar", "league:wc26"}
    ids = [s.id for s in sources_for(want, reg)]
    assert set(ids) == {"bbc", "ole", "clarin"}


def test_no_match_returns_empty_list():
    reg = _registry(_src("only-cricket", "sport:cricket"))
    assert sources_for({"sport:football"}, reg) == []


def test_sorts_by_reliability_descending():
    reg = _registry(
        _src("low",  "global", reliability=0.55),
        _src("high", "global", reliability=0.95),
        _src("mid",  "global", reliability=0.80),
    )
    ids = [s.id for s in sources_for({"global"}, reg)]
    assert ids == ["high", "mid", "low"]


def test_tiebreaks_deterministically_by_id():
    reg = _registry(
        _src("zzz", "global", reliability=0.9),
        _src("aaa", "global", reliability=0.9),
        _src("mmm", "global", reliability=0.9),
    )
    ids = [s.id for s in sources_for({"global"}, reg)]
    assert ids == ["aaa", "mmm", "zzz"]


def test_disabled_sources_are_skipped():
    reg = _registry(
        _src("on",  "global", reliability=0.9, enabled=True),
        _src("off", "global", reliability=0.95, enabled=False),
    )
    ids = [s.id for s in sources_for({"global"}, reg)]
    assert ids == ["on"]


def test_resolver_returns_mix_of_can_feed_model_and_editorial_only():
    # The resolver doesn't enforce the trust gate — that's a downstream
    # decision when routing each signal. Both kinds must surface so the
    # editorial track can still quote biased outlets.
    reg = _registry(
        _src("bbc", "global", reliability=0.95, bias_flag="none"),
        _src("ole", "global", reliability=0.85, bias_flag="national"),
    )
    out = sources_for({"global"}, reg)
    assert {s.id for s in out} == {"bbc", "ole"}
    assert any(s.can_feed_model for s in out)
    assert any(s.editorial_only for s in out)


def test_realistic_national_team_fixture_tag_set():
    # Argentina v France (WC26 final, say). The football glue would
    # build this tag set from the FixtureRef.
    reg = Registry.from_csv()
    tags = {"global", "sport:football", "country:ar", "country:fr", "league:wc26"}
    ids = {s.id for s in sources_for(tags, reg)}
    # tier-1 globals always in (matched on `global` or `sport:football`)
    assert "bbc-sport-football" in ids
    assert "reuters-sport" in ids
    # home-country outlets pulled by their country tag
    assert "ole-ar" in ids
    assert "lequipe-football" in ids
    # ranked highest-reliability first
    ordered = [s.id for s in sources_for(tags, reg)]
    rels = [s.reliability for s in sources_for(tags, reg)]
    assert rels == sorted(rels, reverse=True), ordered


def test_country_only_tag_excludes_outlets_lacking_that_country():
    # A purely country-scoped intent (no sport:football) should only
    # match outlets carrying that country tag.
    reg = Registry.from_csv()
    ids = {s.id for s in sources_for({"country:ar"}, reg)}
    assert "ole-ar" in ids
    assert "lequipe-football" not in ids
    assert "ge-futebol" not in ids
