"""Publish — Pydantic contract, static-file writer, ETag helper.

The output contract is the only thing Faktor sees. Treat it as a public API.
"""

from desk.publish.contract import (  # noqa: F401
    Competition,
    Copy,
    MatchOutput,
    MatchOutputIndexEntry,
    OutputIndex,
    Venue,
    Verdict,
    VerdictState,
)
from desk.publish.etag import content_etag  # noqa: F401
from desk.publish.writer import Publisher  # noqa: F401
