# Migrations

Plain SQL files applied by hand against the Railway Postgres add-on. There is
no migration framework — this directory is the audit trail, not the runner.

## Convention

- One file per migration, named `YYYYMMDD_short_name.sql`.
- Each file wraps its DDL in `BEGIN; … COMMIT;` so a mid-flight failure
  leaves the database untouched.
- Each statement uses `IF NOT EXISTS` where possible so the file is safe to
  re-run if a prior apply was interrupted.
- Apply in filename order.

## Applying

1. In the Railway dashboard, open the **Postgres** service → **Variables** →
   reveal `DATABASE_PUBLIC_URL`. Copy it.
2. Connect with any SQL client (TablePlus, Postico, DBeaver, `psql …`).
3. Paste the file's contents into the SQL console and run.
4. Verify with `\d` (psql) or the client's schema browser.

The app itself never reads `DATABASE_PUBLIC_URL` — that's purely for the
operator's laptop. The running service uses `DATABASE_URL` (private network,
no egress fees), referenced from the Postgres service into the Prophet app
service.

## Why no framework

The historical pattern in this repo is sqlite databases created on first use
by the code that owns them (`ledger.db`, `signals.db`, `distribute.db`,
`prophet.db`). Activity signals broke the pattern because concurrent writes
under launch traffic call for Postgres. Rather than wire in Alembic for a
single domain, this directory is a flat append-only log of the schema
evolution. Add Alembic if a second Postgres-backed domain shows up.
