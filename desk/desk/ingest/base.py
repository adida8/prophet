"""Source ABC + registry.

Every external data source subclasses this. v1 implementations are
narrow (just enough for fixture ingest); the surface here is the contract
v2's admin backend will toggle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceState:
    """Mutable state carried per source. v1 reads on boot; v2 mutates live."""
    enabled: bool = True
    tier:    int  = 1                       # 1 = primary, 2/3 = supporting
    cadence_override_sec: int | None = None
    last_fetch_at: str | None = None
    last_error:    str | None = None


class Source(ABC):
    """Base class for every external data source."""

    id:    str = ""           # unique identifier — populated by subclass
    label: str = ""           # human-readable
    sport: str | None = None  # None for sport-agnostic sources (weather, news)

    def __init__(self) -> None:
        self.state = SourceState()

    @abstractmethod
    async def fetch(self) -> Any:
        """Pull whatever this source provides. Caller handles caching."""
        ...

    @property
    def cache_key(self) -> str:
        return f"{type(self).__module__}:{self.id}"


# Module-level registry; subclasses register on import.
source_registry: dict[str, Source] = {}


def register(src: Source) -> Source:
    if not src.id:
        raise ValueError(f"{type(src).__name__} must set a non-empty `id`")
    source_registry[src.id] = src
    return src
