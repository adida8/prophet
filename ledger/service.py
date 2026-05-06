"""Ledger service — orchestrates refresh, persistence, and view-model build.

Refresh policy: a refresh writes a new snapshot, upserts open positions, and
closes positions that have disappeared from the API response. The closed
positions retain whatever realizedPnl and last value Polymarket reported the
last time we saw them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ledger import db
from ledger.polymarket import get_client, is_valid_address

log = logging.getLogger("ledger.service")

REFRESH_AGE_SEC = 5 * 60  # 5 minutes — implicit refresh threshold


class InvalidAddressError(ValueError):
    pass


def _normalise_position(p: dict[str, Any]) -> dict[str, Any]:
    """Translate one /positions row into our internal shape."""
    return {
        "condition_id":       p.get("conditionId", ""),
        "asset":              p.get("asset", ""),
        "market_question":    p.get("title", ""),
        "event_slug":         p.get("eventSlug"),
        "icon_url":           p.get("icon"),
        "outcome":            p.get("outcome", ""),
        "shares":             float(p.get("size", 0) or 0),
        "avg_entry_price":    float(p.get("avgPrice", 0) or 0),
        "current_price":      float(p.get("curPrice", 0) or 0),
        "initial_value_usd":  float(p.get("initialValue", 0) or 0),
        "value_usd":          float(p.get("currentValue", 0) or 0),
        "unrealized_pnl_usd": float(p.get("cashPnl", 0) or 0),
        "realized_pnl_usd":   float(p.get("realizedPnl", 0) or 0),
        "end_date":           p.get("endDate"),
    }


def _row_to_position_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "condition_id":       row["condition_id"],
        "asset":              row["asset"],
        "market_question":    row["market_question"],
        "event_slug":         row["event_slug"],
        "icon_url":           row["icon_url"],
        "outcome":            row["outcome"],
        "shares":             row["shares"],
        "avg_entry_price":    row["avg_entry_price"],
        "current_price":      row["current_price"],
        "initial_value_usd":  row["initial_value_usd"],
        "value_usd":          row["value_usd"],
        "unrealized_pnl_usd": row["unrealized_pnl_usd"],
        "realized_pnl_usd":   row["realized_pnl_usd"],
        "end_date":           row["end_date"],
        "opened_at":          row["opened_at"],
        "closed_at":          row["closed_at"],
    }


async def _build_view_model(address: str) -> dict[str, Any]:
    address = address.lower()
    wallet = await db.get_wallet(address)
    snap   = await db.get_latest_snapshot(address)
    open_p = await db.get_positions(address, only_open=True)
    all_p  = await db.get_positions(address)

    closed_p = [r for r in all_p if r["closed_at"] is not None]

    decisive_closes = [r for r in closed_p if abs(r["realized_pnl_usd"]) > 0.01]
    wins = [r for r in decisive_closes if r["realized_pnl_usd"] > 0]
    win_rate = (len(wins) / len(decisive_closes)) if decisive_closes else None

    return {
        "address":      address,
        "label":        wallet.get("label") if wallet else None,
        "first_seen_at":     wallet.get("first_seen_at") if wallet else None,
        "last_refreshed_at": wallet.get("last_refreshed_at") if wallet else None,
        "snapshot_at":  snap["snapshot_at"] if snap else None,
        "totals": {
            "total_value_usd":    snap["total_value_usd"] if snap else 0.0,
            "realized_pnl_usd":   snap["realized_pnl_usd"] if snap else 0.0,
            "unrealized_pnl_usd": snap["unrealized_pnl_usd"] if snap else 0.0,
            "open_position_count":   len(open_p),
            "closed_position_count": len(closed_p),
            "win_rate":           win_rate,
        },
        "open_positions":   [_row_to_position_view(r) for r in open_p],
        "closed_positions": [_row_to_position_view(r) for r in closed_p],
    }


async def refresh_wallet(address: str) -> dict[str, Any]:
    if not is_valid_address(address):
        raise InvalidAddressError(f"not a valid 0x… address: {address!r}")
    address = address.lower()

    client = get_client()
    raw_positions = await client.positions(address)
    raw_value     = await client.value(address)
    raw_activity  = await client.activity(address, limit=200)

    normalised = [_normalise_position(p) for p in raw_positions]

    realized = sum(p["realized_pnl_usd"] for p in normalised)
    unrealized = sum(p["unrealized_pnl_usd"] for p in normalised)

    await db.upsert_wallet(address, viewed=True)
    snapshot_at = await db.insert_snapshot(
        address=address,
        total_value_usd=raw_value,
        realized_pnl_usd=realized,
        unrealized_pnl_usd=unrealized,
        raw_positions=raw_positions,
        raw_activity=raw_activity,
    )
    await db.upsert_positions(
        address=address, positions=normalised, seen_at=snapshot_at
    )
    current_assets = {p["asset"] for p in normalised if p["asset"]}
    await db.close_missing_positions(
        address=address, current_assets=current_assets, closed_at=snapshot_at
    )
    await db.mark_refreshed(address)

    return await _build_view_model(address)


async def get_wallet_view(address: str, *, mark_viewed: bool = True) -> dict[str, Any]:
    if not is_valid_address(address):
        raise InvalidAddressError(f"not a valid 0x… address: {address!r}")
    address = address.lower()

    wallet = await db.get_wallet(address)
    if mark_viewed and wallet is not None:
        await db.upsert_wallet(address, viewed=True)

    return await _build_view_model(address)


async def get_history(address: str) -> list[dict[str, Any]]:
    if not is_valid_address(address):
        raise InvalidAddressError(f"not a valid 0x… address: {address!r}")
    rows = await db.get_snapshot_history(address.lower())
    return [
        {
            "snapshot_at":         r["snapshot_at"],
            "total_value_usd":     r["total_value_usd"],
            "realized_pnl_usd":    r["realized_pnl_usd"],
            "unrealized_pnl_usd":  r["unrealized_pnl_usd"],
            "total_pnl_usd":       r["realized_pnl_usd"] + r["unrealized_pnl_usd"],
        }
        for r in rows
    ]


def is_stale(last_refreshed_at: str | None, max_age_sec: int = REFRESH_AGE_SEC) -> bool:
    if not last_refreshed_at:
        return True
    try:
        last = datetime.fromisoformat(last_refreshed_at)
    except ValueError:
        return True
    age = (datetime.now(timezone.utc) - last).total_seconds()
    return age > max_age_sec
