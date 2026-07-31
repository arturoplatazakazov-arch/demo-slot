#!/usr/bin/env bash
# Double-click launcher for the WHOLE local stack (Finder runs .command files
# in Terminal, unlike .sh which just opens in an editor).
#
# It hands off to dev.sh, which starts Postgres (self-healing — it rebuilds the
# dev DB automatically if macOS has purged /private/tmp), applies migrations,
# starts the FastAPI backend and the static frontend, then opens the catalog.
#
# First run only: if macOS blocks it with "unidentified developer", right-click
# the file in Finder → Open → Open. After that a normal double-click works.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
./dev.sh

echo
echo "✅ Everything is running. You can close this window — the servers keep"
echo "   running in the background. Re-run this launcher any time to restart."
