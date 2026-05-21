"""FastAPI router for the Ledger.

Mounted at /api/ledger/* by server.py.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ledger import service
from ledger.service import InvalidAddressError

log = logging.getLogger("ledger.router")

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


# ── Refresh rate limit ────────────────────────────────────────────────
# Each call to `/wallet/refresh` fans out to ~3 Polymarket fetches; the
# endpoint is unauthenticated, so a tight per-(IP, address) throttle
# keeps it from being used to amplify traffic or burn upstream quota.
# In-memory dict is fine for the single-instance Railway deploy; if we
# ever scale horizontally this needs a shared store (Redis) and a real
# token bucket.
REFRESH_MIN_INTERVAL_SEC = 10.0
_last_refresh: dict[tuple[str, str], float] = {}


def _refresh_gate(client_ip: str, address: str) -> None:
    """Raise HTTP 429 if (ip, address) tried to refresh within the
    cooldown window. Otherwise stamp `now` and let the caller through."""
    key = (client_ip, address.lower())
    now = time.monotonic()
    last = _last_refresh.get(key)
    if last is not None and (now - last) < REFRESH_MIN_INTERVAL_SEC:
        retry_after = int(REFRESH_MIN_INTERVAL_SEC - (now - last)) + 1
        raise HTTPException(
            status_code=429,
            detail="refresh requested too frequently",
            headers={"Retry-After": str(retry_after)},
        )
    _last_refresh[key] = now
    # Cheap GC: keep the dict from growing forever in a long-lived
    # process. 10 000 entries ≈ a few hundred KB, plenty of headroom.
    if len(_last_refresh) > 10_000:
        cutoff = now - REFRESH_MIN_INTERVAL_SEC * 10
        for k, v in list(_last_refresh.items()):
            if v < cutoff:
                _last_refresh.pop(k, None)


class WalletRefreshRequest(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)


@router.post("/wallet/refresh")
async def refresh(req: WalletRefreshRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _refresh_gate(client_ip, req.address)
    try:
        return await service.refresh_wallet(req.address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        log.exception("refresh failed for %s", req.address)
        raise HTTPException(status_code=502, detail="upstream fetch failed")


@router.get("/wallet/{address}")
async def view_wallet(address: str):
    try:
        view = await service.get_wallet_view(address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if view["snapshot_at"] is None or service.is_stale(view["last_refreshed_at"]):
        try:
            view = await service.refresh_wallet(address)
        except Exception:
            log.exception("auto-refresh failed for %s", address)
            if view["snapshot_at"] is None:
                raise HTTPException(
                    status_code=502, detail="upstream fetch failed"
                )
    return view


@router.get("/wallet/{address}/history")
async def history(address: str):
    try:
        return await service.get_history(address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))
