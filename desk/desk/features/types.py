"""FeatureRow — abstract base for any sport's feature vector.

Sports define a concrete dataclass that subclasses (or mimics) this. The
runner / replay never inspect sport-specific fields — they only know to
hand the row to `Sport.model(features)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FeatureRow:
    """Sport-agnostic envelope. The interesting fields are sport-specific
    and live on the subclass.
    """
    match_id: str
    sport:    str
    asof:     datetime
