"""Outright backtest harness.

Read-only side workflow that replays the outright MC sim against a
frozen historical tournament (groups + Elo + true winner) and reports
calibration metrics. Complements `desk/backtest/` (match-shaped).
"""
