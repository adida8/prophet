"""Anonymous identity + IP-hash helpers.

`op_anon` cookie — UUIDv4, 1-year lifetime, SameSite=Lax, HttpOnly=false so
the frontend can read it for the "your chip is on" state.

IP hash uses a daily-rotated salt so the same IP produces the same hash
within a UTC day (for rate-limiting) but is unlinkable across days.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Request, Response

ANON_COOKIE = "op_anon"
_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60

# Per-deployment IP-hash secret. Falls back to a process-local random value
# if the env var is unset — that means a redeploy resets the salt, but the
# hash is only used for same-day rate limiting so the worst case is a brief
# bucket reshuffle.
_RUNTIME_IP_SECRET = secrets.token_hex(16)


def _ip_secret() -> str:
    return os.getenv("ACTIVITY_IP_SALT") or _RUNTIME_IP_SECRET


def ensure_anon_id(request: Request, response: Response) -> str:
    """Read `op_anon` from the request, generating + setting it on first hit."""
    existing = request.cookies.get(ANON_COOKIE)
    if existing:
        return existing
    new_id = str(uuid.uuid4())
    response.set_cookie(
        key=ANON_COOKIE,
        value=new_id,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=False,
        samesite="lax",
        secure=False,  # the site runs on http during local dev; Railway terminates TLS
        path="/",
    )
    return new_id


def client_ip(request: Request) -> str:
    """Best-effort client IP. Railway puts the real IP in X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # First entry is the original client; subsequent are proxies.
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"


def hash_ip(ip: str, *, today: Optional[date] = None) -> str:
    """Daily-salted SHA-256 of an IP. Truncated to 32 hex chars (128 bits) —
    plenty for rate-limit bucket cardinality."""
    if today is None:
        today = datetime.now(timezone.utc).date()
    salt = f"{_ip_secret()}:{today.isoformat()}"
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()[:32]
