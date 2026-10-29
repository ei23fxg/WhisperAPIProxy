#!/usr/bin/env bash
# Bereitet Verzeichnisse/Symlinks vor und startet uvicorn.
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

mkdir -p "$APP_DIR/recordings" "$APP_DIR/client_logs" "$APP_DIR/logs"

# Die App schreibt "error.log" relativ zum Arbeitsverzeichnis; wir zeigen auf
# das Log-Volume, damit es Neubauten überlebt.
ln -sfn "$APP_DIR/logs/error.log" "$APP_DIR/error.log"

if [[ ! -f "$APP_DIR/config.py" ]]; then
  echo "FEHLER: $APP_DIR/config.py fehlt — bitte per Volume einbinden." >&2
  exit 1
fi

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "dry-run: uvicorn whisper_api_proxy:app --host 0.0.0.0 --port ${PORT:-5431}"
  exit 0
fi

exec uvicorn whisper_api_proxy:app \
     --host 0.0.0.0 --port "${PORT:-5431}" --workers 1 --proxy-headers
