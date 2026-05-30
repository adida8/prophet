"""Outbound venue links for football fixtures.

For each fixture we link out to the prediction-market / sportsbook
venues a reader can trade on. The published `market_sources` list
(see `desk/publish/contract.py:MarketSource`) carries one row per venue:
its deep link (or nearest landing page when no per-event deep link
exists yet), whether the verdict's Pick rode on that venue's price, and
which market sides the venue actually quoted into the calculation.

Today only Polymarket feeds the model — Kalshi ingest is still a stub,
so its row carries the WC landing page and an empty `priced_sides`.
When Kalshi ingest lands its prices flow into the `MarketSnapshot` and
`priced_sides` fills in automatically; upgrading the Kalshi link from
the landing page to a per-event deep link is a follow-on (the
build-time event-ticker resolution lives in `site/generate.py` today).

This module is football-specific by design — the URL patterns are. The
`MarketSource` shape it returns is sport-agnostic; the sport-agnostic
runner only ever sees the finished list.
"""

from __future__ import annotations

from desk.publish.contract import MarketSource, MarketVenue, Verdict, VerdictState
from desk.sport import FixtureRef
from desk.verdict.compare import MarketSnapshot, Side

# Venues we surface a trade CTA for on football fixtures, in render
# order. Polymarket is the fixture-of-record; Kalshi is linked for
# parity even though its live ingest is still a stub.
_POLYMARKET_LANDING = "https://polymarket.com/"
_KALSHI_WC_LANDING = "https://kalshi.com/category/sports/soccer/fifa-world-cup"

_VENUE_NAME = {
    MarketVenue.POLYMARKET.value: "Polymarket",
    MarketVenue.KALSHI.value:     "Kalshi",
}

# Stable display order for the per-side list.
_SIDE_ORDER = {"a": 0, "draw": 1, "b": 2}


def market_url_for_fixture(fx: FixtureRef) -> str | None:
    """Build the Polymarket-side deep link from the source slug.

    Polymarket WC 2026 match events resolve at
    `https://polymarket.com/sports/world-cup/{slug}` (slug e.g.
    `fifwc-fra-mex-2026-06-12`). Other events still live under
    `/event/{slug}`. We strip the optional `-more-markets` suffix
    Polymarket sometimes appends, then front it with the right path.

    Returns None when we can't construct a clean URL — caller decides
    whether that downgrades a Pick to a Pass (see `verdict.decide`), and
    `build_market_sources` falls back to the Polymarket landing page.
    """
    slug = (fx.source_event_slug or "").strip().lower()
    if not slug:
        return None
    if slug.endswith("-more-markets"):
        slug = slug[: -len("-more-markets")]
    if (fx.source_venue or "").lower() == "polymarket":
        if slug.startswith("fifwc-"):
            return f"https://polymarket.com/sports/world-cup/{slug}"
        return f"https://polymarket.com/event/{slug}"
    # Kalshi (and future venues) plug in here when their slug + URL
    # pattern is known. Until then we don't fabricate a URL.
    return None


def _kalshi_url_for_fixture(fx: FixtureRef) -> str:
    """Kalshi link for the fixture.

    Kalshi has no per-event deep link inside the engine yet (ingest is a
    stub), so we land the reader on the World Cup category page. The
    richer build-time event-ticker resolution lives in `site/generate.py`
    and can override this when step 5 wires the site to consume
    `market_sources`.
    """
    return _KALSHI_WC_LANDING


def _priced_sides_by_venue(snapshot: MarketSnapshot) -> dict[str, list[Side]]:
    """Group a snapshot's per-side prices by venue → ordered side list."""
    by_venue: dict[str, set[Side]] = {}
    for p in snapshot.prices:
        by_venue.setdefault(p.venue, set()).add(p.side)
    return {
        venue: sorted(sides, key=lambda s: _SIDE_ORDER.get(s, 99))
        for venue, sides in by_venue.items()
    }


def build_market_sources(
    fx: FixtureRef,
    snapshot: MarketSnapshot,
    verdict: Verdict,
) -> list[MarketSource]:
    """Assemble the per-fixture `market_sources` list.

    Lists every venue we link a CTA for (Polymarket + Kalshi today), each
    with its deep link, whether the Pick rode on it, and which sides it
    priced into the calculation. `priced_sides` comes straight off the
    `MarketSnapshot`, so a venue that didn't feed the model surfaces with
    an empty list — the honest "linked but not used" signal.
    """
    priced = _priced_sides_by_venue(snapshot)

    # `verdict.market_venue` is stored as its string value (the Verdict
    # model sets `use_enum_values=True`) and is only populated on a Pick.
    picked_venue: str | None = None
    is_pick = verdict.state in (VerdictState.PICK, VerdictState.PICK.value)
    if is_pick and verdict.market_venue:
        picked_venue = verdict.market_venue

    sources: list[MarketSource] = []
    for venue, url in (
        (MarketVenue.POLYMARKET.value, market_url_for_fixture(fx) or _POLYMARKET_LANDING),
        (MarketVenue.KALSHI.value,     _kalshi_url_for_fixture(fx)),
    ):
        sources.append(
            MarketSource(
                venue=venue,
                name=_VENUE_NAME[venue],
                url=url,
                picked=(venue == picked_venue),
                priced_sides=list(priced.get(venue, [])),
            )
        )
    return sources
