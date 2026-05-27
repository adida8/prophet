"""The Desk · external data layer.

Each external provider gets its own subpackage with a narrow client +
cache. v1 ships api-football (Phase 2: rank + form for B.1; Phase 4:
injuries + lineups for B.3) and openweathermap (Phase 3: weather for
B.2). When data-layer Phase 1a's full Source ABC lands, these are
refactored onto the typed-Source layer — keep the public surface narrow
so that refactor is mechanical.
"""
