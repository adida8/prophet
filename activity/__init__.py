"""Activity signals — anonymous views + reactions on every match page.

See ACTIVITY_SIGNALS_SPEC.md for the design.

Data lives in the Railway Postgres add-on (`DATABASE_URL`). Other domains
in this repo (ledger, signals, distribute) still use sqlite — this one
broke the pattern because the access pattern is many concurrent writers.
"""
