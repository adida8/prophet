"""Drafter — ties selector + renderer + captioner + queue together.

Two entry points:

  `draft_daily(...)`  → picks today's best Pick, renders 4 slides,
                        writes captions, persists a queue row. Returns
                        the new Draft or None when nothing qualifies.
  `draft_weekly(...)` → builds a roundup payload, renders 4 slides,
                        writes captions, persists. Returns the Draft or
                        None when the week's already been drafted.

Both are idempotent: the queue's partial-unique indexes guarantee
re-running won't create a second row for the same match_id (daily) or
same week (weekly). When the index would catch a clash, the runner
returns None silently — the caller saw a draft exists, no work needed.

Renderer + queue are injected so tests don't need to spin up sqlite
or write PNGs — pass a `FakeRenderer` and `:memory:` SocialQueue.

The runner uses `asyncio.run` internally so the CLI shim can call it
synchronously from a subprocess.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from desk.publish import Publisher
from desk.publish.contract import MatchOutput
from desk.social.caption import (
    GeneratedCaptions,
    generate_daily_captions,
    generate_weekly_captions,
)
from desk.social.models import (
    DraftKind,
    WeeklyRoundupPayload,
)
from desk.social.queue import Draft, SocialQueue
from desk.social.renderer import Renderer, StubRenderer
from desk.social.selector import (
    OutcomeLookup,
    daily_draft_id,
    select_daily_pick,
    weekly_draft_id,
    week_window_for,
    build_weekly_roundup,
)

log = logging.getLogger("desk.social.runner")


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _load_published_matches(pub: Publisher, sport: str = "football") -> list[MatchOutput]:
    """Read every published MatchOutput for the sport.

    The static-file publisher doesn't expose a "list everything" call;
    we scan `output_dir/{sport}/*.json` and skip the index file. Errors
    on a single file warn + skip, so a corrupted JSON doesn't shut the
    selector down.
    """
    sport_dir = pub.output_dir / sport
    if not sport_dir.is_dir():
        return []
    out: list[MatchOutput] = []
    for p in sport_dir.iterdir():
        if not p.is_file() or p.suffix != ".json":
            continue
        if p.name == "index.json":
            continue
        try:
            out.append(MatchOutput.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception as e:                  # noqa: BLE001
            log.warning("social runner: skipping %s: %s", p, e)
    return out


def _slides_dir(assets_dir: Path, draft_id: str) -> Path:
    return assets_dir / draft_id


def _source_json_from_match(m: MatchOutput) -> dict:
    return m.model_dump(mode="json", exclude_none=False)


def _source_json_from_payload(p: WeeklyRoundupPayload) -> dict:
    return p.model_dump(mode="json", exclude_none=False)


# ── Public API ────────────────────────────────────────────────────────


def draft_daily(
    *,
    queue: SocialQueue,
    assets_dir: Path,
    renderer: Optional[Renderer] = None,
    publisher: Optional[Publisher] = None,
    matches: Optional[Iterable[MatchOutput]] = None,
    min_edge_pp: float = 2.0,
    sport: str = "football",
    now: Optional[datetime] = None,
) -> Optional[Draft]:
    """Run the daily selector → render → caption → enqueue path.

    Returns the persisted Draft, or None when nothing qualifies or a
    draft for the chosen match already exists.
    """
    now = now or _now_utc()
    renderer = renderer or StubRenderer()

    if matches is None:
        if publisher is None:
            raise ValueError("either matches= or publisher= must be provided")
        matches = _load_published_matches(publisher, sport=sport)

    selected = select_daily_pick(
        matches,
        now=now,
        min_edge_pp=min_edge_pp,
    )
    if selected is None:
        log.info("draft_daily: nothing qualifies (now=%s, min_edge=%.2f)",
                 now.isoformat(), min_edge_pp)
        return None

    if queue.has_daily_for_match(selected.match_id):
        log.info("draft_daily: %s already drafted, skipping", selected.match_id)
        return None

    draft_id = daily_draft_id(selected, now=now)
    captions = generate_daily_captions(selected)
    if captions.fell_back:
        log.warning("draft_daily: %s fell back to minimal caption", selected.match_id)

    slides = asyncio.run(renderer.render_carousel(
        selected,
        output_dir=_slides_dir(assets_dir, draft_id),
    ))

    return queue.insert(
        draft_id      = draft_id,
        kind          = DraftKind.DAILY,
        match_id      = selected.match_id,
        week_starting = None,
        source_json   = _source_json_from_match(selected),
        slides        = slides,
        caption_ig    = captions.caption_ig,
        caption_x     = captions.caption_x,
    )


def draft_weekly(
    *,
    queue: SocialQueue,
    assets_dir: Path,
    outcome_lookup: OutcomeLookup,
    renderer: Optional[Renderer] = None,
    publisher: Optional[Publisher] = None,
    matches: Optional[Iterable[MatchOutput]] = None,
    sport: str = "football",
    now: Optional[datetime] = None,
) -> Optional[Draft]:
    """Run the weekly roundup selector + renderer + captioner + enqueue."""
    now = now or _now_utc()
    renderer = renderer or StubRenderer()

    if matches is None:
        if publisher is None:
            raise ValueError("either matches= or publisher= must be provided")
        matches = _load_published_matches(publisher, sport=sport)

    window = week_window_for(now)

    if queue.has_weekly_for(window.week_starting.isoformat()):
        log.info("draft_weekly: %s already drafted, skipping",
                 window.week_starting.isoformat())
        return None

    payload = build_weekly_roundup(
        matches,
        window=window,
        outcome_lookup=outcome_lookup,
    )

    if not payload.top_picks:
        log.info(
            "draft_weekly: no Picks in window [%s → %s], skipping",
            window.start.isoformat(), window.end.isoformat(),
        )
        return None

    draft_id = weekly_draft_id(window.week_starting)
    captions = generate_weekly_captions(payload)
    if captions.fell_back:
        log.warning("draft_weekly: fell back to minimal caption")

    slides = asyncio.run(renderer.render_carousel(
        payload,
        output_dir=_slides_dir(assets_dir, draft_id),
    ))

    return queue.insert(
        draft_id      = draft_id,
        kind          = DraftKind.WEEKLY_ROUNDUP,
        match_id      = None,
        week_starting = window.week_starting.isoformat(),
        source_json   = _source_json_from_payload(payload),
        slides        = slides,
        caption_ig    = captions.caption_ig,
        caption_x     = captions.caption_x,
    )


# ── No-op outcome lookup (used until results pipeline lands) ─────────


def stub_outcome_lookup(match_id: str) -> None:
    """Default outcome lookup: every match is unresolved.

    The roundup payload will simply ship without hit-rate / wrong rows.
    Swap this for a real lookup once results ingest is wired up.
    """
    _ = match_id
    return None
