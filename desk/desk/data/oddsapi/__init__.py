"""The Odds API — non-US sportsbook + exchange price adapter.

Locked launch venue set (per THE_DESK_NONUS_SPORTSBOOK_SCOPING.md §0):

  Pinnacle              `pinnacle`              eu   sharp anchor
  Betfair Exchange UK   `betfair_ex_uk`         uk   commission model
  Betfair Exchange EU   `betfair_ex_eu`         eu   commission model
  William Hill          `williamhill`           uk   consumer book
  Sky Bet               `skybet`                uk   consumer book

Bet365 is NOT available via The Odds API for UK/EU football — don't
add it. Only `bet365_au` exists, scoped to AFL/NRL.

Reads use `regions=uk,eu` and `oddsFormat=decimal`. Market `h2h` is
the 1X2 moneyline. Outrights are out of scope for v1.

The module mirrors `desk/desk/data/api_football/`:

    client.py  — async httpx wrapper + typed error buckets
    cache.py   — sqlite store for events + per-bookmaker prices
    status.py  — `/sports/?apiKey=…` quota probe
    venues.py  — locked launch venue set + venue-type classification
    refresh.py — fetch-once orchestrator (used by the CLI + refresh loop)

Live fetch is feature-flag-gated by DESK_ODDS_FETCH (default 0). The
adapter builds and tests cleanly against fixture JSON without a key.
"""

from desk.data.oddsapi.cache import (
    EventRow,
    OddsAPICache,
    PriceRow,
    default_cache_path,
)
from desk.data.oddsapi.client import (
    OddsAPIClient,
    OddsAPIError,
    OddsAPIResponse,
    OddsAPIRateLimit,
    ODDS_API_BASE_URL,
)
from desk.data.oddsapi.events import (
    DEFAULT_SPORT_KEY,
    DEFAULT_SPORT_KEYS,
    fetch_events_h2h,
    parse_event_payload,
    venue_ids_in_events,
)
from desk.data.oddsapi.refresh import (
    RefreshReport,
    refresh_all,
)
from desk.data.oddsapi.status import (
    QuotaStatus,
    fetch_quota_status,
)
from desk.data.oddsapi.venues import (
    LAUNCH_VENUE_IDS,
    VENUE_DISPLAY_NAMES,
    VENUE_TYPES,
    VENUE_REGIONS,
    venue_region,
    venue_type_for,
)

__all__ = [
    "EventRow",
    "OddsAPICache",
    "PriceRow",
    "default_cache_path",
    "OddsAPIClient",
    "OddsAPIError",
    "OddsAPIResponse",
    "OddsAPIRateLimit",
    "ODDS_API_BASE_URL",
    "DEFAULT_SPORT_KEY",
    "DEFAULT_SPORT_KEYS",
    "fetch_events_h2h",
    "parse_event_payload",
    "venue_ids_in_events",
    "RefreshReport",
    "refresh_all",
    "QuotaStatus",
    "fetch_quota_status",
    "LAUNCH_VENUE_IDS",
    "VENUE_DISPLAY_NAMES",
    "VENUE_TYPES",
    "VENUE_REGIONS",
    "venue_region",
    "venue_type_for",
]
