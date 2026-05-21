"""FastAPI router for newsletter signup.

Mounted at /api/subscribe by server.py. Forwards opt-ins to SendX
(https://docs.sendx.io) using the server-side Team API Key, so the
secret never reaches the browser. New contacts are tagged so a SendX
visual workflow (the welcome automation) can trigger on the tag.

Both signup surfaces post here: the React op app (via
frontend/src/op/hooks) and the static site (site/generate.py).
"""

from __future__ import annotations

import logging
import re
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import config

log = logging.getLogger("signup.router")

router = APIRouter(prefix="/api", tags=["signup"])

SENDX_IDENTIFY_URL = "https://api.sendx.io/api/v1/rest/contact/identify"

# Pragmatic email shape check — avoids pulling in email-validator just for
# a public opt-in form. SendX does its own validation server-side too.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ── Per-IP rate limit ─────────────────────────────────────────────────
# The endpoint is unauthenticated and fans out to an upstream API, so a
# tight throttle keeps it from being used to hammer SendX. In-memory dict
# is fine for the single-instance Railway deploy (mirrors ledger.router).
SUBSCRIBE_MIN_INTERVAL_SEC = 3.0
_last_submit: dict[str, float] = {}


def _rate_gate(client_ip: str) -> None:
    now = time.monotonic()
    last = _last_submit.get(client_ip)
    if last is not None and (now - last) < SUBSCRIBE_MIN_INTERVAL_SEC:
        retry_after = int(SUBSCRIBE_MIN_INTERVAL_SEC - (now - last)) + 1
        raise HTTPException(
            status_code=429,
            detail="requests too frequent",
            headers={"Retry-After": str(retry_after)},
        )
    _last_submit[client_ip] = now
    # Cheap GC so the dict can't grow unbounded in a long-lived process.
    if len(_last_submit) > 10_000:
        cutoff = now - SUBSCRIBE_MIN_INTERVAL_SEC * 50
        for k, v in list(_last_submit.items()):
            if v < cutoff:
                _last_submit.pop(k, None)


class SubscribeRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    # Off-screen honeypot — real users leave it empty; bots fill it.
    hp: str = Field(default="", max_length=200)


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, request: Request):
    # Honeypot tripped → almost certainly a bot. Report success and do
    # nothing, so the bot can't tell it was filtered.
    if req.hp.strip():
        return {"ok": True}

    client_ip = request.client.host if request.client else "unknown"
    _rate_gate(client_ip)

    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    if not config.SENDX_API_KEY:
        log.error("SENDX_API_KEY is not configured — cannot accept signups")
        raise HTTPException(status_code=503, detail="The newsletter is not configured yet.")

    payload: dict = {"email": email}
    if config.SENDX_SIGNUP_TAGS:
        payload["tags"] = config.SENDX_SIGNUP_TAGS
    headers = {
        "Content-Type": "application/json",
        "X-Team-ApiKey": config.SENDX_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SENDX_IDENTIFY_URL, json=payload, headers=headers)
    except httpx.HTTPError:
        log.exception("SendX request failed for a signup")
        raise HTTPException(status_code=502, detail="The newsletter service is unavailable.")

    if resp.status_code >= 400:
        # Log upstream detail server-side; keep the reader-facing message generic.
        log.error("SendX identify failed: %s %s", resp.status_code, resp.text[:300])
        raise HTTPException(status_code=502, detail="Could not complete signup. Please try again.")

    return {"ok": True}
