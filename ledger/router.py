"""FastAPI router for the Ledger.

Mounted at /api/ledger/* by server.py.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ledger import service
from ledger.service import InvalidAddressError

log = logging.getLogger("ledger.router")

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


class WalletRefreshRequest(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)


@router.post("/wallet/refresh")
async def refresh(req: WalletRefreshRequest):
    try:
        return await service.refresh_wallet(req.address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("refresh failed for %s", req.address)
        raise HTTPException(status_code=502, detail=f"upstream fetch failed: {e}")


@router.get("/wallet/{address}")
async def view_wallet(address: str):
    try:
        view = await service.get_wallet_view(address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if view["snapshot_at"] is None or service.is_stale(view["last_refreshed_at"]):
        try:
            view = await service.refresh_wallet(address)
        except Exception as e:
            log.warning("auto-refresh failed for %s: %s", address, e)
            if view["snapshot_at"] is None:
                raise HTTPException(
                    status_code=502, detail=f"no cached data and upstream failed: {e}"
                )
    return view


@router.get("/wallet/{address}/history")
async def history(address: str):
    try:
        return await service.get_history(address)
    except InvalidAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))
