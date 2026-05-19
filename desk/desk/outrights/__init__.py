"""Outright (tournament-winner) verdict engine.

v1 ships the WC 2026 winner market only. Architecture is sport-tagged
so club outrights plug in later. This is the local-Prophet build —
no Supabase, no waist refactor; outrights run as a parallel pipeline
that writes the same shape of JSON the static site already reads.
"""
