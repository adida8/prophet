# Moved to /desk_api.py at project root (Python import path concerns —
# the desk/ directory is a separate package with its own pyproject and
# isn't pip-installed in the deploy). This file is intentionally empty
# so old imports surface a clear error rather than a stale router.

raise ImportError(
    "desk.router has moved to the project-root module `desk_api`. "
    "Update imports to `from desk_api import router`."
)
