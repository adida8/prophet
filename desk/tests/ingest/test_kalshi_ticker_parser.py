"""Ticker parsers for Kalshi WC 2026 events and child markets."""

from __future__ import annotations

from datetime import date

import pytest

from desk.ingest.kalshi import (
    KalshiEventKey,
    parse_event_ticker,
    parse_market_ticker,
)


class TestParseEventTicker:
    def test_wc26_event_parses(self) -> None:
        got = parse_event_ticker("KXWCGAME-26JUN11MEXRSA")
        assert got == KalshiEventKey(
            series="KXWCGAME",
            kickoff=date(2026, 6, 11),
            team_codes=frozenset({"mex", "rsa"}),
        )

    def test_three_letter_team_codes_lowercased(self) -> None:
        got = parse_event_ticker("KXWCGAME-26JUN27COLPOR")
        assert got is not None
        assert got.team_codes == frozenset({"col", "por"})

    def test_team_pair_is_order_independent(self) -> None:
        """Kalshi's ordering is its own choice; we treat it as a set."""
        a = parse_event_ticker("KXWCGAME-26JUN11MEXRSA")
        b = parse_event_ticker("KXWCGAME-26JUN11RSAMEX")
        assert a is not None and b is not None
        assert a.team_codes == b.team_codes

    @pytest.mark.parametrize(
        "ticker",
        [
            "",
            "KXWCGAME",                       # no body
            "KXWCGAME-26JUN11MEXRSA-MEX",     # market ticker, not event
            "KXWCGAME-26FOO11MEXRSA",         # bogus month
            "KXWCGAME-26JUN32MEXRSA",         # bogus day
            "KXWCGAME-26JUN11MEX",            # only one team code
            "polymarket-event-slug",          # totally wrong
        ],
    )
    def test_unparseable_returns_none(self, ticker: str) -> None:
        assert parse_event_ticker(ticker) is None

    def test_year_century_prefix(self) -> None:
        """2-digit YY in tickers maps to 20YY — we don't expect 1900s WCs."""
        got = parse_event_ticker("KXWCGAME-26JUN11MEXRSA")
        assert got is not None
        assert got.kickoff.year == 2026


class TestParseMarketTicker:
    def test_team_suffix(self) -> None:
        assert parse_market_ticker("KXWCGAME-26JUN11MEXRSA-MEX") == (
            "KXWCGAME-26JUN11MEXRSA", "mex",
        )

    def test_other_team_suffix(self) -> None:
        assert parse_market_ticker("KXWCGAME-26JUN11MEXRSA-RSA") == (
            "KXWCGAME-26JUN11MEXRSA", "rsa",
        )

    def test_tie_suffix(self) -> None:
        assert parse_market_ticker("KXWCGAME-26JUN11MEXRSA-TIE") == (
            "KXWCGAME-26JUN11MEXRSA", "tie",
        )

    @pytest.mark.parametrize(
        "ticker",
        [
            "",
            "KXWCGAME-26JUN11MEXRSA",         # event ticker, not a market
            "KXWCGAME-26JUN11MEXRSA-MEXICO",  # 6-char suffix
            "garbage",
        ],
    )
    def test_unparseable_returns_none(self, ticker: str) -> None:
        assert parse_market_ticker(ticker) is None
