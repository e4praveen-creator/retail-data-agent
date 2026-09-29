#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$APP_DIR")
cd "$PROJECT_DIR"
if [ -x "$PROJECT_DIR/.venv-runtime/bin/python" ]; then
  RETAIL_DEFAULT_PYTHON="$PROJECT_DIR/.venv-runtime/bin/python"
else
  RETAIL_DEFAULT_PYTHON="$PROJECT_DIR/.venv/bin/python"
fi
RETAIL_PYTHON=${RETAIL_PYTHON:-"$RETAIL_DEFAULT_PYTHON"}
if [ ! -x "$RETAIL_PYTHON" ]; then
  echo 'Python dependencies are missing. From the project directory, run:'
  echo 'python3.12 -m venv .venv-runtime'
  echo '.venv-runtime/bin/python -m pip install -r retail_app/requirements.lock.txt'
  exit 1
fi
"$RETAIL_PYTHON" -c 'import sys; sys.version_info >= (3,12) or sys.exit("Python 3.12 or newer is required. Create .venv-runtime as described in retail_app/README.md.")'
printf 'Summit Field is starting at http://127.0.0.1:8765\nKeep this terminal open. Press Control-C to stop.\n'
exec "$RETAIL_PYTHON" -m uvicorn retail_app.backend.main:app --host 127.0.0.1 --port 8765 --workers 1 --limit-concurrency 32 --timeout-keep-alive 5 --timeout-graceful-shutdown 15 --no-server-header --no-access-log
