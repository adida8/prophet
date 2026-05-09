"""Historical data loaders for the backtest harness.

Every fetcher caches by date / competition. Anything time-travelled
through these loaders is guaranteed to not leak today's data into a
2022 fixture.
"""

from desk.backtest.historical.elo import (  # noqa: F401
    LookaheadError,
    load_intl_elo_snapshot,
)
from desk.backtest.historical.markets import (  # noqa: F401
    HistoricalMatch,
    load_tournament_matches,
)
from desk.backtest.historical.results import winner_from_score  # noqa: F401
