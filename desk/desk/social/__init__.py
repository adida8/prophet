"""Social automation — drafts + approval queue + Phase 1 manual publish.

Spec: `THE_DESK_SOCIAL_AUTOMATION_SPEC.md`.

The public surface is intentionally small. The runner picks the
highest-conviction MatchOutput of the day (or builds a weekly roundup
payload), renders 4 slide PNGs (stub today, real renderer later),
writes IG + X captions, and persists a `Draft` row to sqlite. The
operator approves through `/desk/ops/social`. Phase 1 ships a bundle
download + Mark-as-posted. Phase 2 layers in IG Graph API + X v2.

Nothing in this package imports from a sport — we only consume
`MatchOutput` from `desk.publish.contract`, so a future tennis sport
gets social automation for free.
"""

from desk.social.config import SocialConfig, load_config
from desk.social.models import (
    DraftKind,
    DraftStatus,
    SlideAsset,
    WeeklyRoundupPayload,
)
from desk.social.queue import Draft, SocialQueue
from desk.social.renderer import Renderer, RendererError, StubRenderer

__all__ = (
    "SocialConfig",
    "load_config",
    "DraftKind",
    "DraftStatus",
    "SlideAsset",
    "WeeklyRoundupPayload",
    "Draft",
    "SocialQueue",
    "Renderer",
    "RendererError",
    "StubRenderer",
)
