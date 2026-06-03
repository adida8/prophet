"""Stub Desk — a standalone replica of The Desk's MTAI-facing surface.

This package serves *frozen* (stale) per-match and per-outright JSON to
Market Tips AI through the two surfaces MTAI actually touches:

  1. Inbound  — bearer-gated external GET routes (MTAI pulls).
  2. Outbound — HMAC-signed push wire (the stub re-enqueues the frozen
                JSON; the drain loop POSTs it to MTAI).

There is NO compute here: no ingest, no model, no Haiku, no external API
keys. The "engine" (`engine.py`) walks the frozen JSON in `data/output/`
and re-enqueues it; everything downstream (signing, outbox, delivery) is
copied verbatim from the live Desk so the wire is byte-identical.

The live app in the parent repo is untouched — this folder is a separate
deployable for its own Railway project.
"""
