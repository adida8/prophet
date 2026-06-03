"""FastAPI app factory for the stub.

Mounts the read-only desk routes and, on lifespan startup, launches the
refresh + drain background loops. The external (bearer-gated) router is
mounted only when DESK_API_BEARER_TOKEN is set — exactly like the live
server, so an unconfigured deploy doesn't even acknowledge the surface.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from stubdesk import api, loops

log = logging.getLogger("stubdesk.app")

# Mount the internal /api/desk/* reads too? MTAI only needs the external
# pair, but these are handy for debugging + for fronting a public site.
_MOUNT_INTERNAL = os.getenv("DESK_STUB_MOUNT_INTERNAL", "1") == "1"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tasks: list[asyncio.Task] = [
        asyncio.create_task(loops.run_refresh_loop(), name="stub-refresh"),
        asyncio.create_task(loops.run_drain_loop(), name="stub-drain"),
    ]
    log.info("stub lifespan: %d background loop(s) started", len(tasks))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t


def create_app() -> FastAPI:
    app = FastAPI(title="Desk Stub", docs_url=None, redoc_url=None, lifespan=_lifespan)

    if _MOUNT_INTERNAL:
        app.include_router(api.router)

    # External (bearer-gated) routes — only when the token is configured.
    if os.getenv("DESK_API_BEARER_TOKEN"):
        app.include_router(api.external_router)
        log.info("external bearer-gated routes mounted")
    else:
        log.warning("DESK_API_BEARER_TOKEN unset — external routes NOT mounted")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
