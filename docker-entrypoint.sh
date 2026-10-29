#!/usr/bin/env bash
# Legt Datenverzeichnisse und – falls nötig – eine Standard-Konfiguration an
# und startet uvicorn.
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
CONFIG_EXAMPLE="$APP_DIR/config.example.py"
CONFIG_CLASSIC="$APP_DIR/config.py"
CONFIG_FALLBACK="$APP_DIR/data/config.py"

mkdir -p "$APP_DIR/recordings" "$APP_DIR/client_logs" "$APP_DIR/logs"

# Die App schreibt "error.log" relativ zum Arbeitsverzeichnis; wir zeigen auf
# das Log-Volume, damit es Neubauten überlebt.
ln -sfn "$APP_DIR/logs/error.log" "$APP_DIR/error.log"

# Docker legt bei einem Bind-Mount auf eine fehlende Host-Datei ein Verzeichnis
# an. Darin kann der Container nicht schreiben und die App kann es nicht als
# Modul importieren. Deshalb warnen und auf ein beschreibbares Ziel ausweichen.
warn_if_directory() {
  local path="$1"
  [[ -d "$path" ]] || return 1
  echo "WARNUNG: $path ist ein Verzeichnis, keine Datei." >&2
  echo "         Docker legt ein Verzeichnis an, wenn die Quelldatei eines" >&2
  echo "         Bind-Mounts auf dem Host fehlt. Bitte stattdessen das" >&2
  echo "         Verzeichnis mounten:" >&2
  echo "           ./config:/app/config" >&2
  echo "           CONFIG_PATH=/app/config/config.py" >&2
  return 0
}

if [[ -n "${CONFIG_PATH:-}" ]] && warn_if_directory "$CONFIG_PATH"; then
  # Nicht beschreibbar -> unten auf den Klassik-/Fallback-Pfad ausweichen.
  CONFIG_PATH=""
elif [[ -z "${CONFIG_PATH:-}" && ! -f "$CONFIG_CLASSIC" && -d "$APP_DIR/config" ]]; then
  # Verzeichnis gemountet, aber CONFIG_PATH (noch) nicht gesetzt.
  CONFIG_PATH="$APP_DIR/config/config.py"
elif [[ -z "${CONFIG_PATH:-}" && ! -f "$CONFIG_CLASSIC" ]]; then
  CONFIG_PATH="$CONFIG_FALLBACK"
fi

# Klassischer Einzeldatei-Mount (/app/config.py) hat Vorrang, wenn er als
# Datei vorhanden ist und CONFIG_PATH nicht schon auf eine Datei zeigt.
if [[ -z "${CONFIG_PATH:-}" || ! -f "$CONFIG_PATH" ]]; then
  if [[ -f "$CONFIG_CLASSIC" ]]; then
    CONFIG_PATH="$CONFIG_CLASSIC"
  else
    warn_if_directory "$CONFIG_CLASSIC" || true
  fi
fi

CONFIG_PATH="${CONFIG_PATH:-$CONFIG_FALLBACK}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "INFO: Keine config.py gefunden – erzeuge eine Standardkonfiguration" >&2
  echo "      aus config.example.py unter: $CONFIG_PATH" >&2
  if ! mkdir -p "$(dirname "$CONFIG_PATH")" \
     || ! cp "$CONFIG_EXAMPLE" "$CONFIG_PATH"; then
    echo "FEHLER: $CONFIG_PATH konnte nicht angelegt werden." >&2
    echo "        Bitte das Verzeichnis beschreibbar mounten, z. B.:" >&2
    echo "          ./config:/app/config" >&2
    echo "          CONFIG_PATH=/app/config/config.py" >&2
    exit 1
  fi
  chmod 600 "$CONFIG_PATH" 2>/dev/null || true
  echo "INFO: Die Datei enthält Demo-Clients und Platzhalter-Keys." >&2
  echo "      Bitte API-Keys/Clients anpassen und den Container neu starten." >&2
fi

echo "Config: $CONFIG_PATH"
export CONFIG_PATH

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "dry-run: uvicorn whisper_api_proxy:app --host 0.0.0.0 --port ${PORT:-5431}"
  exit 0
fi

exec uvicorn whisper_api_proxy:app \
     --host 0.0.0.0 --port "${PORT:-5431}" --workers 1 --proxy-headers
