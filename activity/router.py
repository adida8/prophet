"""FastAPI router mounted at `/api/activity/*`.

Three endpoints:
  POST /api/activity/view             body {match_id}              → 204
  POST /api/activity/vote             body {match_id, reaction}    → {your_vote, locked_at}
  GET  /api/activity/{match_id}                                    → aggregate view-model

Rate limits enforced server-side via SQL on the existing tables — no
Redis, no in-memory token bucket. Activity tables are small enough that
COUNT queries against a recent-time window are cheap.

Per-IP vote rate limiting (10/min/ip_hash from the spec) is deferred:
it requires storing ip_hash on match_reactions, which the v1 migration
doesn't include. Per-anon limits are sufficient until traffic shows it
matters. Tracked as TODO at the top of this module.
"""

# TODO: per-IP vote rate limit (10/min/ip_hash). Requires alter table
# match_reactions add column ip_hash text; then a COUNT query against the
# last 60s windowed by ip_hash. Skipped in v1 — per-anon limits + the
# one-vote-per-match constraint give meaningful baseline anti-abuse.

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .anon import client_ip, ensure_anon_id, hash_ip
from .db import get_pool

router = APIRouter(prefix="/api/activity", tags=["activity"])

REACTIONS = ("sharp_call", "fair_call", "off_mark", "wait_see")
ReactionLiteral = Literal["sharp_call", "fair_call", "off_mark", "wait_see"]

# Display thresholds — see ACTIVITY_SIGNALS_SPEC.md §"Display rules".
# Frontend respects these too; server returns the raw counts regardless,
# and clients hide the UI below threshold. Mirroring the rule here lets
# the GET response also report `display_*` flags for paranoid clients.
VIEWS_DISPLAY_MIN = 10
VOTES_DISPLAY_MIN = 5

# Rate limits — see spec §API.
VOTE_CHANGE_COOLDOWN_SEC = 30
VOTE_PER_ANON_DAILY_MAX = 500


# --- request / response shapes ----------------------------------------------


class ViewBody(BaseModel):
    match_id: str = Field(min_length=3, max_length=128)


class VoteBody(BaseModel):
    match_id: str = Field(min_length=3, max_length=128)
    reaction: ReactionLiteral


class VoteResponse(BaseModel):
    your_vote: ReactionLiteral
    locked_at: Optional[str] = None  # ISO 8601 or null


class AggregateResponse(BaseModel):
    match_id: str
    views_24h: int
    votes_total: int
    by_reaction: dict[str, int]
    aligned_pct: Optional[int] = None
    your_vote: Optional[ReactionLiteral] = None
    refreshed_at: Optional[str] = None  # ISO 8601 or null when no row yet
    display_views: bool
    display_votes: bool


# --- helpers ----------------------------------------------------------------


def _empty_aggregate(match_id: str) -> AggregateResponse:
    return AggregateResponse(
        match_id=match_id,
        views_24h=0,
        votes_total=0,
        by_reaction={r: 0 for r in REACTIONS},
        aligned_pct=None,
        your_vote=None,
        refreshed_at=None,
        display_views=False,
        display_votes=False,
    )


# --- routes -----------------------------------------------------------------


@router.post("/view", status_code=204)
async def post_view(body: ViewBody, request: Request, response: Response) -> None:
    # NOTE: must mutate the injected `response` (cookie + status) instead of
    # returning a fresh Response, otherwise the Set-Cookie header is dropped.
    anon_id = ensure_anon_id(request, response)
    ip = hash_ip(client_ip(request))
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO match_views (match_id, anon_id, ip_hash, seeded) "
            "VALUES ($1, $2, $3, false)",
            body.match_id, anon_id, ip,
        )
    return None


@router.post("/vote", response_model=VoteResponse)
async def post_vote(body: VoteBody, request: Request, response: Response):
    anon_id = ensure_anon_id(request, response)
    pool = get_pool()
    async with pool.acquire() as conn:
        # Daily ceiling per anon — guards a single browser from flipping
        # votes across many matches.
        daily_count = await conn.fetchval(
            "SELECT count(*) FROM match_reactions "
            "WHERE anon_id = $1 AND voted_at > now() - interval '1 day'",
            anon_id,
        )
        if daily_count and daily_count >= VOTE_PER_ANON_DAILY_MAX:
            raise HTTPException(status_code=429, detail="vote_daily_limit")

        # Look up existing vote on this match.
        row = await conn.fetchrow(
            "SELECT reaction, voted_at, locked_at FROM match_reactions "
            "WHERE match_id = $1 AND anon_id = $2",
            body.match_id, anon_id,
        )

        if row is None:
            # First vote on this match for this anon.
            await conn.execute(
                "INSERT INTO match_reactions "
                "  (match_id, anon_id, reaction, seeded, voted_at) "
                "VALUES ($1, $2, $3, false, now())",
                body.match_id, anon_id, body.reaction,
            )
            return VoteResponse(your_vote=body.reaction, locked_at=None)

        # Existing row.
        if row["locked_at"] is not None:
            raise HTTPException(status_code=409, detail="vote_locked")

        # Lazy-lock: if the original vote is more than 24h old, set
        # locked_at = now() and reject the change. The spec's intent: the
        # voter's first 24h is mutable, after that the row is frozen.
        delta = await conn.fetchval(
            "SELECT now() - $1::timestamptz", row["voted_at"]
        )
        if delta is not None and delta.total_seconds() > 24 * 3600:
            await conn.execute(
                "UPDATE match_reactions SET locked_at = now() "
                "WHERE match_id = $1 AND anon_id = $2",
                body.match_id, anon_id,
            )
            raise HTTPException(status_code=409, detail="vote_locked")

        # 30-second cooldown between flips.
        if delta is not None and delta.total_seconds() < VOTE_CHANGE_COOLDOWN_SEC:
            raise HTTPException(status_code=429, detail="vote_change_cooldown")

        # In-window change.
        await conn.execute(
            "UPDATE match_reactions "
            "SET reaction = $3, voted_at = now() "
            "WHERE match_id = $1 AND anon_id = $2",
            body.match_id, anon_id, body.reaction,
        )
        return VoteResponse(your_vote=body.reaction, locked_at=None)


@router.get("/{match_id}", response_model=AggregateResponse)
async def get_match_activity(match_id: str, request: Request, response: Response):
    anon_id = ensure_anon_id(request, response)
    pool = get_pool()
    async with pool.acquire() as conn:
        agg = await conn.fetchrow(
            "SELECT views_24h, votes_total, sharp_call, fair_call, off_mark, "
            "       wait_see, aligned_pct, refreshed_at "
            "FROM match_aggregates WHERE match_id = $1",
            match_id,
        )
        your_vote_row = await conn.fetchrow(
            "SELECT reaction FROM match_reactions "
            "WHERE match_id = $1 AND anon_id = $2",
            match_id, anon_id,
        )

    if agg is None:
        out = _empty_aggregate(match_id)
        out.your_vote = your_vote_row["reaction"] if your_vote_row else None
        return out

    views_24h = int(agg["views_24h"])
    votes_total = int(agg["votes_total"])
    return AggregateResponse(
        match_id=match_id,
        views_24h=views_24h,
        votes_total=votes_total,
        by_reaction={
            "sharp_call": int(agg["sharp_call"]),
            "fair_call": int(agg["fair_call"]),
            "off_mark":  int(agg["off_mark"]),
            "wait_see":  int(agg["wait_see"]),
        },
        aligned_pct=int(agg["aligned_pct"]) if agg["aligned_pct"] is not None else None,
        your_vote=your_vote_row["reaction"] if your_vote_row else None,
        refreshed_at=agg["refreshed_at"].isoformat() if agg["refreshed_at"] else None,
        display_views=views_24h >= VIEWS_DISPLAY_MIN,
        display_votes=votes_total >= VOTES_DISPLAY_MIN,
    )
