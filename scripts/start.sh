#!/usr/bin/env sh
# Container entrypoint for the production/embed profile (Railway, etc.).
# Applies migrations, then starts the API on the platform-provided $PORT.
# Local dev does not use this script — it uses .claude/launch.json / run_games.
set -e

# Ensure the schema exists / is up to date before serving. Safe to run every
# boot: Alembic is a no-op when already at head.
alembic upgrade head

# Railway (and most PaaS) inject $PORT; fall back to 8000 for plain `docker run`.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
