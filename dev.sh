#!/usr/bin/env bash
# One command for local dev: starts Postgres (bundled via the `pgserver`
# Python package — no system Postgres/Docker needed), the FastAPI backend,
# and the static frontend server, then opens the game catalog.
#
# Safe to re-run any time (e.g. after a reboot, or if a server crashed) —
# each piece is skipped if it's already up.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PGDATA="/private/tmp/demo_slot_pgdata"
BACKEND_PORT=8000
FRONT_PORT="${PORT:-4175}"

# app/core/config.py loads .env via a path relative to the process's cwd,
# not this script's location — when launched from elsewhere (double-clicked
# app, cron, another shell's cwd, ...) uvicorn would silently miss .env and
# fall back to its default localhost:5432 DB URL instead of the pgserver
# socket below, which then fails with a bare "connection refused" that looks
# exactly like a Postgres-not-ready race (cost real time to track down).
cd "$ROOT"

is_up() { curl -fsS -o /dev/null --max-time 1 "$1" 2>/dev/null; }

echo "==> Postgres"
# scripts/dev_db.py starts the cluster, waits for it to actually serve queries
# (pg_ctl -w only waits for the socket, not readiness — the backend used to
# race this), auto-rebuilds a /private/tmp-corrupted cluster, and bootstraps
# the demo_slot role + database. It prints the server URI.
PG_URI="$("$ROOT/.venv/bin/python" "$ROOT/scripts/dev_db.py" "$PGDATA")"
echo "   $PG_URI"
# pg_ctl daemonizes the actual postgres process, so it keeps running after
# that short python process exits — no need to keep anything alive here.

echo "==> Schema (alembic upgrade head)"
# Idempotent: creates every table on a fresh cluster, no-op once up to date.
"$ROOT/.venv/bin/alembic" upgrade head

echo "==> Backend (uvicorn :$BACKEND_PORT)"
if is_up "http://127.0.0.1:$BACKEND_PORT/health"; then
  echo "   already running"
else
  started=0
  for attempt in 1 2 3; do
    nohup "$ROOT/.venv/bin/uvicorn" app.main:app --port "$BACKEND_PORT" \
      > /tmp/demo_slot_backend.log 2>&1 &
    disown
    for _ in $(seq 1 10); do
      is_up "http://127.0.0.1:$BACKEND_PORT/health" && { started=1; break; }
      sleep 1
    done
    [ "$started" = 1 ] && break
    echo "   attempt $attempt failed, retrying..." >&2
  done
  if [ "$started" != 1 ]; then
    echo "   FAILED to start — see /tmp/demo_slot_backend.log" >&2
    tail -20 /tmp/demo_slot_backend.log >&2
    exit 1
  fi
fi

echo "==> Frontend (static :$FRONT_PORT)"
if is_up "http://localhost:$FRONT_PORT/games.html"; then
  echo "   already running"
else
  nohup python3 -m http.server "$FRONT_PORT" --directory "$ROOT/front" \
    > /tmp/demo_slot_frontend.log 2>&1 &
  disown
  sleep 1
fi

URL="http://localhost:$FRONT_PORT/games.html"
echo "==> Ready: $URL"
open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || echo "Open $URL in your browser"
