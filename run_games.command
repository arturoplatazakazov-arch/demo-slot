#!/usr/bin/env bash
# Double-click entry point (Finder runs .command files in Terminal).
# Starts a local static server for front/ and opens the game catalog in Safari.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-4175}"
URL="http://localhost:$PORT/games.html"

python3 -m http.server "$PORT" --directory "$DIR/front" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

sleep 1
open -a Safari "$URL"

echo "Server running at $URL — close this window (or Ctrl+C) to stop it."
wait "$SERVER_PID"
