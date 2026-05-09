"""Sport-agnostic ingest infrastructure.

Each external data source subclasses `Source` and registers itself at
import time. v2's admin backend introspects this registry to toggle
sources on/off without code changes.
"""

from desk.ingest.base import Source, source_registry  # noqa: F401
