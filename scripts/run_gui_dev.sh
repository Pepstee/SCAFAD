#!/usr/bin/env bash
# scripts/run_gui_dev.sh — bring up the SCAFAD GUI backend and frontend
# in a single terminal.  Backend on :8088, frontend on :5173.
#
# Usage:
#   ./scripts/run_gui_dev.sh
#   ./scripts/run_gui_dev.sh --no-seed     # skip the demo seed step
#
# Requirements:
#   - Python 3.11 with `fastapi`, `uvicorn`, `sse-starlette` installed
#   - Node 20 LTS + npm available on PATH (frontend stage only)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEED=1
for arg in "$@"; do
  case "$arg" in
    --no-seed) SEED=0 ;;
    --help|-h)
      sed -n '2,12p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
  esac
done

export PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scafad:${PYTHONPATH:-}"

if [[ "$SEED" == "1" ]]; then
  echo "[gui-dev] seeding demo detections via the real runtime..."
  python -m scafad.gui.backend.seed
fi

# Start backend in background; frontend in foreground so Ctrl+C tears down both.
echo "[gui-dev] backend  -> http://127.0.0.1:8088 (uvicorn)"
python -m uvicorn scafad.gui.backend.main:app \
  --host 127.0.0.1 --port 8088 --reload &
BACKEND_PID=$!

cleanup() {
  echo "[gui-dev] stopping backend pid=$BACKEND_PID"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$REPO_ROOT/scafad/gui/frontend"
if [[ ! -d node_modules ]]; then
  echo "[gui-dev] installing frontend dependencies (one-time, ~60s)..."
  npm install --no-audit --no-fund
fi
echo "[gui-dev] frontend -> http://127.0.0.1:5173 (vite)"
npm run dev
