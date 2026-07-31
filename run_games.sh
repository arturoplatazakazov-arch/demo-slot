#!/usr/bin/env bash
# Starts a local static server for front/ and opens the game catalog page.
set -euo pipefail

PORT="${PORT:-4175}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/front"
URL="http://localhost:$PORT/games.html"

python3 -m http.server "$PORT" --directory "$DIR" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

sleep 1
open -a Safari "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || echo "Open $URL in your browser"

wait "$SERVER_PID"
