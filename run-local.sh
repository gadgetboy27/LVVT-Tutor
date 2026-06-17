#!/usr/bin/env bash
# Run LVV-PrepPal locally against a throwaway SQLite DB (no Postgres needed).
# Your real DATABASE_URL in .env is left untouched.
#
# Usage:
#   ./run-local.sh            # serve on http://127.0.0.1:8000
#   PORT=9000 ./run-local.sh  # pick a different port
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PYTHON="${PYTHON:-.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "error: $PYTHON not found. Create the venv first (python3.12 -m venv .venv)." >&2
  exit 1
fi

# Local SQLite file overrides whatever's in .env, only for this process.
export DATABASE_URL="${DATABASE_URL:-sqlite:///./local_dev.db}"

echo "Starting LVV-PrepPal on http://$HOST:$PORT  (DB: $DATABASE_URL)"
exec "$PYTHON" -m uvicorn main:app --host "$HOST" --port "$PORT" --reload "$@"
