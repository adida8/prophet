# Desk Stub

A **standalone, self-contained replica** of The Desk's MTAI-facing
surface. It serves *frozen* (stale) per-match and per-outright JSON to
Market Tips AI and never computes anything.

This folder is independent of the live Prophet/Desk app in the parent
repo — nothing here imports from `desk/`, and the live app does not
import from here. Deploy it as its **own Railway project**.

## What it does

MTAI touches the Desk in exactly two directions; this stub replicates
both, byte-for-byte:

```
                    ┌─────────────────────────────┐
   MTAI  ──GET────► │  external GET routes          │ ──reads──┐
 (pull, bearer)     │  /api/desk/external/match/…   │          │
                    │  /api/desk/external/outright/…│          ▼
                    └─────────────────────────────┘   ┌──────────────┐
                                                       │ FROZEN JSON  │
                    ┌─────────────────────────────┐   │ data/output/ │
   MTAI  ◄──POST─── │  push wire (outbox→drain)     │ ◄─│ (the only    │
 (HMAC webhook)     │  signed exactly like Desk     │   │  source of   │
                    └─────────────────────────────┘   │  truth)      │
                              ▲                        └──────────────┘
                              │ enqueues
                    ┌─────────────────────────────┐
                    │  STUB ENGINE (engine.py)      │  NO ingest / model /
                    │  walk frozen JSON → enqueue   │  Haiku / API keys
                    └─────────────────────────────┘
```

- **Inbound** — `GET /api/desk/external/match/{id}` and
  `/api/desk/external/outright/{id}`, gated by the same
  `DESK_API_BEARER_TOKEN`. Return the same wire shape the push delivers.
- **Outbound** — the stub engine re-enqueues the frozen JSON onto a
  SQLite outbox; the drain loop POSTs each payload to MTAI with the same
  `x-webhook-signature: v1=<HMAC-SHA256>` the live Desk uses. The signing
  code, outbox, client, and worker are copied verbatim from the live Desk
  so the same shared secret keeps verifying.

The frozen data was copied from the live Desk's output on the day this
folder was created (`data/output/football/*.json` + `outrights/*.json` +
their `index.json`). To refresh it, re-copy from the live `desk/data/output/`.

## Layout

```
desk_stub/
├── main.py                # entry: uvicorn + lifespan loops
├── railpack.json          # Railway build/start (Procfile is a fallback)
├── requirements.txt       # fastapi + uvicorn + httpx — that's all
├── .env.example
├── data/output/           # FROZEN JSON (committed — it's the product)
│   ├── football/*.json (+ index.json)
│   └── outrights/*.json (+ index.json)
└── stubdesk/
    ├── app.py             # FastAPI factory + lifespan
    ├── api.py             # internal + external GET routes
    ├── engine.py          # the stub "engine": walk frozen JSON → enqueue
    ├── loops.py           # refresh loop + drain loop
    ├── wire.py            # canonical body + enqueue (matches + outrights)
    ├── outbox.py          # SQLite durable queue   (verbatim from Desk)
    ├── client.py          # HMAC-signed webhook client (verbatim)
    ├── worker.py          # drain_once sweep        (verbatim)
    ├── signing.py         # HMAC-SHA256             (verbatim)
    ├── etag.py            # canonical_json          (verbatim)
    ├── config.py          # env → config
    └── cli.py             # python -m stubdesk run-once | drain | status
```

## Run locally

```bash
cd desk_stub
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/ on *nix
pip install -r requirements.txt
cp .env.example .env        # fill DESK_API_BEARER_TOKEN (+ push creds if testing push)

python main.py              # serves on :8000, loops armed

# in another shell:
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/desk/external/match/fb-wc26-arg-alg-20260617
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/desk/external/outright/fb-wc26-winner
```

CLI without the server:

```bash
python -m stubdesk status      # frozen inventory + outbox counts
python -m stubdesk run-once    # enqueue all frozen payloads (needs PUSH=1 to enqueue)
python -m stubdesk drain       # one drain sweep → MTAI
```

## Deploy to a new Railway project

1. **New project → Deploy from this repo.** In the service **Settings →
   Root Directory**, set `desk_stub`. Railpack then uses
   `desk_stub/railpack.json` and runs `python main.py --port $PORT`.
2. **Set env vars** (Settings → Variables) — see `.env.example`:
   - `DESK_API_BEARER_TOKEN` — same token MTAI already uses for pulls.
   - `DESK_DISTRIBUTE_PUSH=1` + `DESK_DISTRIBUTE_WEBHOOK_URL` +
     `DESK_DISTRIBUTE_WEBHOOK_SECRET` — same URL + secret the live Desk
     pushed with. (Leave `PUSH=0` to serve pulls only.)
   - Optional: `DESK_STUB_REFRESH_SEC`, `DESK_DISTRIBUTE_TICK_SEC`.
3. **(Optional) mounted volume** — if you want the outbox to survive
   redeploys mid-retry, add a Railway volume at `/data` and set
   `DESK_DISTRIBUTE_DB_PATH=/data/distribute.db`. The frozen JSON ships
   in the image, so `DESK_OUTPUT_DIR` only needs overriding if you host
   the frozen set on a volume instead.
4. **Point MTAI at the new host** — update MTAI's webhook source/refresh
   base URL to the new Railway domain when you're ready to cut over.

## Env vars

| Variable | Default | Purpose |
|---|---|---|
| `DESK_API_BEARER_TOKEN` | unset | Gates the external GETs. Unset ⇒ external routes not mounted. |
| `DESK_DISTRIBUTE_PUSH` | `0` | `1` enables the outbound push wire. |
| `DESK_DISTRIBUTE_WEBHOOK_URL` | unset | MTAI webhook. Required when `PUSH=1`. |
| `DESK_DISTRIBUTE_WEBHOOK_SECRET` | unset | HMAC secret. Required when `PUSH=1`. |
| `DESK_DISTRIBUTE_INCLUDE_CROSS_VENUE` | `1` | `0` strips `market_prices`/`consensus_fair`/`region` from the wire body. |
| `DESK_STUB_REFRESH_SEC` | `3600` | Re-enqueue cadence (the "engine ran" beat). |
| `DESK_DISTRIBUTE_TICK_SEC` | `30` | Outbox drain cadence. |
| `DESK_AUTORUN` | `1` | `0` disables both loops (GETs still served). |
| `DESK_OUTPUT_DIR` | `data/output` | Frozen JSON location. |
| `DESK_DISTRIBUTE_DB_PATH` | `data/distribute.db` | Outbox SQLite path. |
| `DESK_STUB_MOUNT_INTERNAL` | `1` | Mount the internal `/api/desk/*` reads too. |
| `DESK_DISTRIBUTE_RATE_PER_MIN` / `_MAX_IN_FLIGHT` / `_MAX_BYTES` | 50 / 8 / 60000 | Drain tuning. |

## Notes

- **No Postgres, no Anthropic, no api-football.** The activity-signals
  Postgres domain and all compute/data dependencies are intentionally absent.
- **Idempotent.** Re-running the engine refreshes the pending outbox rows
  (collapse rule: one pending row per id). The `updated_at` in the frozen
  JSON never changes — that's what makes the data "stale" by design.
- **Wire fidelity.** Match bodies are the canonical JSON of the on-disk
  dict; outright bodies add `content_type:"outright"` and lift
  `hard_signal_adjustments` to the top level — identical to the live Desk.
```
