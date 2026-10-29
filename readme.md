# Whisper API Proxy

This project provides a (OpenAI compatible) proxy API for audio transcriptions, allowing clients to transcribe audio files using either the great local [Whisper WebUI](https://github.com/jhj0517/Whisper-WebUI) service of @jhj0517 or the OpenAI Whisper API.

## Features

*   **Audio Transcription:** Transcribes audio files using either a local Whisper WebUI or the OpenAI API.
*   **Local Service Check:** Periodically checks the availability of the local Whisper WebUI service.
*   **Whistle-Fallback (CPU):** If the Whisper WebUI is down or returns nothing, transcription falls back to Cactus Whistle (16.9 MB, runs on the CPU, 7 languages) before any paid API is used.
*   **Fallback chain:** local Whisper WebUI → Whistle (CPU) → OpenAI (only if `allow_openai` is set for the client).
*   **API Key Authentication:** Authenticates clients using API keys.
*   **Usage Logging:** Logs API usage by client, tracking usage of both the local API and the OpenAI API.
*   **Client-specific OpenAI API Usage Control:** Allows disabling OpenAI API usage for individual clients.
*   **Usage Endpoint:** Provides a `/usage` endpoint to query daily API usage for each client.
*   **Audio Recording:** Saves audio recordings to the `recordings` directory (if enabled in the client configuration).
*   **Opus Conversion:** Converts audio files to Opus format for storage.
*   **Zero-config Docker start:** If no `config.py` exists, a default one is created automatically on first start.
*   **Ready for Home Assistant:** Works as a local STT backend via the OpenAI-compatible API, e.g. with [ha-openai-whisper-stt-api](https://github.com/fabio-garavini/ha-openai-whisper-stt-api).
*   **ei23 DIY Smart Home:** A ready-to-use compose template is included in [`examples/diy-smart-home/`](examples/diy-smart-home/whisper-proxy.yml).

## Lokale Fallback-Engines (CPU)

Wenn die Whisper-WebUI nicht erreichbar ist oder nichts liefert, probiert der
Proxy lokale Engines in der Reihenfolge aus `config.fallback_order` — erst
danach OpenAI (nur wenn `allow_openai` für den Client gesetzt ist):

```text
Whisper-WebUI (GPU)  →  Parakeet (CPU)  →  Whistle (CPU)  →  OpenAI
```

```python
fallback_order = ["parakeet", "whistle"]

parakeet_enabled = True
parakeet_model = "nemo-parakeet-tdt-0.6b-v3"
parakeet_quantization = "int8"

whistle_enabled = True
whistle_language = None   # None = automatisch, sonst z.B. "de"

# Prüfintervall der WebUI in Sekunden (Umschaltzeit nach einem Ausfall)
local_check_interval = 30
```

Installation der lokalen Engines:

```bash
pip install onnx-asr onnxruntime          # Parakeet (~640 MB int8)
pip install "cactus-needle[mic]"          # Whistle (~17 MB)
```

Beide sind optional: fehlt ein Paket, wird die Engine übersprungen. Der Status
steht unter `GET /v1/local_service_status` (`whistle`, `parakeet`).

### SRT / Zeitstempel

Beide Engines liefern Zeitstempel (Parakeet Token-, Whistle Wortzeiten). Mit
`srt_format=true` im Request kommt SRT zurück — gleiches Antwortformat wie beim
Whisper-WebUI-Pfad:

```srt
1
00:00:00,640 --> 00:00:04,000
1234 F.23.de23.de

2
00:00:11,040 --> 00:00:12,720
Es ist eigentlich egal, was ich hier so
```

Gruppierung: Umbruch bei `.`/`!`/`?`, nach 42 Zeichen oder 3 s
(`srt_utils.words_to_srt(words, max_chars=…, max_secs=…)`).

### Wo liegen die Modellgewichte?

| Engine | Pfad | Größe |
|---|---|---|
| Parakeet (onnx-asr) | `~/.cache/huggingface/hub/models--istupakov--parakeet-tdt-0.6b-v3-onnx/` | ~640 MB (int8) |
| Whistle (cactus-needle) | `~/.cache/cactus-needle/whistle/2.0.0/whistle.cact` | 16,9 MB |

Whistle wird beim ersten Aufruf über den HuggingFace-Hub (`Cactus-Compute/whistle`)
geladen und zusätzlich in den cactus-needle-Cache kopiert.

Überschreiben:
- Parakeet: `HF_HOME` bzw. `HF_HUB_CACHE` setzen
- Whistle: `NEEDLE_WHISTLE_WEIGHTS=/pfad/whistle.cact`

**Docker:** beide Caches liegen im Container und sind nach einem Rebuild weg —
`~/.cache/huggingface` und `~/.cache/cactus-needle` als Volume mounten (oder
`HF_HOME` auf ein Volume setzen).

Prüfen:

```bash
du -sh ~/.cache/huggingface/hub/models--istupakov--parakeet-tdt-0.6b-v3-onnx        ~/.cache/cactus-needle/whistle/2.0.0/whistle.cact
huggingface-cli scan-cache | head
```

### Umschaltzeiten

- **WebUI fällt aus:** der nächste Request, der scheitert, schaltet sofort auf
  die lokalen Engines um (kein Warten auf den Poll-Tick).
- **WebUI kommt zurück:** maximal `local_check_interval` + 5 s Health-Timeout
  (Default also ~35 s, mit `local_check_interval = 10` etwa 15 s).

Whistle- und Parakeet-Nutzung wird in der Usage-Statistik als `local` gezählt.

## Docker

Der Dienst lässt sich gekapselt betreiben — inklusive ffmpeg und beider lokaler
Engines. Eine `config.py` muss **nicht** vorbereitet werden: Fehlt sie, legt der
Container beim ersten Start automatisch eine Standardkonfiguration aus
[`config.example.py`](config.example.py) an.

```bash
docker compose up -d --build
docker compose logs -f
```

Beim ersten Start entsteht `./config/config.py`. Dort API-Keys und Clients
anpassen, danach neu starten:

```bash
sudo nano config/config.py
docker compose restart whisper-proxy
```

Der Container läuft als root, daher gehören `./config/` (und die generierte
Datei) root. Mit `sudo` bearbeiten oder vorher `user:` in der Compose-Datei
setzen.

> **Hinweis:** Die Standardkonfiguration enthält Demo-Clients und
> Platzhalter-Keys. Vor dem Betrieb im LAN oder mit Portfreigabe unbedingt
> ändern.

### Konfiguration: woher kommt die config.py?

Der Container sucht in dieser Reihenfolge:

| # | Pfad | Zweck |
|---|---|---|
| 1 | `$CONFIG_PATH` (Image-Default: `/app/config/config.py`) | Verzeichnis-Mount, wird bei Bedarf erzeugt |
| 2 | `/app/config.py` | klassischer Einzeldatei-Mount |
| 3 | `/app/data/config.py` | letzter Fallback (nicht persistent) |

Findet er keine Datei, kopiert der Entrypoint `config.example.py` an das erste
beschreibbare Ziel und startet trotzdem. Ein fehlendes `config.py` ist also kein
Startfehler mehr.

**Wichtig für eigene Compose-Dateien:** Ein Mount wie

```yaml
- ./config.py:/app/config.py:ro
```

funktioniert nur, wenn `./config.py` auf dem Host **schon existiert**. Fehlt die
Datei, legt Docker ein *Verzeichnis* dieses Namens an; der Container kann dort
nicht schreiben und die App kann es nicht importieren. Deshalb nutzt die
mitgelieferte Compose-Datei ein Verzeichnis:

```yaml
volumes:
  - ./config:/app/config
environment:
  CONFIG_PATH: /app/config/config.py
```

Mit `docker compose up -d` wird `./config/config.py` dann automatisch erzeugt.
Wer die Datei bereits als `./config.py` liegen hat, verschiebt sie einfach nach
`./config/config.py` (oder mountet sie weiter read-only als Einzeldatei, siehe
Kommentar in der Compose-Datei). Ein durch einen früheren Fehlversuch
entstandenes leeres Verzeichnis `./config.py` (bei ei23:
`volumes/whisper-proxy/config.py`) vorher löschen.

Beim ersten Start werden die Modelle bei Bedarf geladen (~660 MB). Das lässt
sich vorher anstoßen:

```bash
docker compose exec whisper-proxy python warmup_models.py
```

### Was wo liegt

| Host | Container | Inhalt |
|---|---|---|
| `./config/` | `/app/config` | `config.py` (wird beim ersten Start erzeugt) |
| `./recordings/` | `/app/recordings` | Aufnahmen (Opus) + `.txt` — direkt im Projektordner sichtbar |
| `./client_logs/` | `/app/client_logs` | Usage-Statistik je Client |
| Volume `proxy_logs` | `/app/logs` | `error.log` |
| Volume `hf_cache` | `/root/.cache/huggingface` | Parakeet-Gewichte (~640 MB) |
| Volume `cactus_cache` | `/root/.cache/cactus-needle` | Whistle (`whistle.cact`, 16,9 MB) |

Die beiden Cache-Volumes überleben `docker compose build` und `up --build` —
die Modelle werden also nur einmal geladen. Wer die Gewichte lieber als
normale Ordner sehen will, ersetzt in der Compose-Datei die letzten beiden
Einträge durch die auskommentierten Bind-Mounts (`./models/hf`, `./models/cactus`).

Volumes ansehen/aufräumen:

```bash
docker volume ls | grep -E "hf_cache|cactus_cache|proxy_logs"
docker compose exec whisper-proxy du -sh /root/.cache/*
docker compose down -v          # Achtung: löscht auch die Modell-Caches
```

### Image über GHCR beziehen

Das Repo enthält `.github/workflows/docker.yml`: Bei jedem Push auf `master`
(und bei Tags `v*`) wird das Image gebaut und nach
`ghcr.io/ei23fxg/whisperapiproxy` gepusht. Tags sind `master`, `latest`,
`sha-<kurz>` sowie bei Git-Tags `1.2.3` und `1.2`.

Nach dem ersten Lauf: GitHub → **Packages** → `whisperapiproxy` → *Package
settings*. Standardmäßig ist das Paket **privat** — entweder dort auf *public*
stellen, oder auf dem Server mit Token anmelden.

Auf dem Server (einmalig, PAT mit `read:packages`):

```bash
echo "$CR_PAT" | docker login ghcr.io -u ei23fxg --password-stdin
```

Dann neben der Compose-Datei eine `.env`:

```dotenv
PROXY_IMAGE=ghcr.io/ei23fxg/whisperapiproxy:latest
```

und starten:

```bash
docker compose pull
docker compose up -d
```

Updates später: `docker compose pull && docker compose up -d`.
Ohne `.env` baut `docker compose up -d --build` weiter lokal.

Die Modell-Caches liegen in den benannten Volumes und bleiben beim
Image-Wechsel erhalten — es wird also nur das Image neu geladen.

### Betrieb

```bash
docker compose ps                    # Status inkl. Healthcheck
docker compose restart whisper-proxy
docker compose build --pull && docker compose up -d   # Update
docker compose down                  # stoppen (Daten bleiben)
```

- Healthcheck: `GET /health` (ohne API-Key) — nur für Docker, liefert `{"status":"ok"}`.
- Ein Worker ist bewusst fest verdrahtet: Modelle und Status liegen im Prozess.
- Port `5431` wird auf alle Interfaces veröffentlicht; im LAN ggf. per Firewall
  einschränken.
- Der Container läuft als root; `./config`, `./recordings` und `./client_logs`
  gehören danach root. Für einen anderen Benutzer müsste man `user:` in der
  Compose-Datei setzen und die Ordner entsprechend vorbereiten.
- GPU: Das Image nutzt ONNX Runtime für die CPU. Für CUDA müsste man
  `onnxruntime-gpu` installieren, das NVIDIA-Container-Toolkit aktivieren und
  `deploy.resources.reservations.devices` in der Compose-Datei ergänzen — für
  Diktat ist die CPU-Variante ausreichend.

### ei23 DIY Smart Home

Der Proxy passt direkt in das [ei23 DIY Smart Home](https://github.com/ei23com/diy-smart-home)
und lässt sich dort als eigener Dienst betreiben. Die Vorlage liegt im Repo
unter [`examples/diy-smart-home/whisper-proxy.yml`](examples/diy-smart-home/whisper-proxy.yml).

In `~/ei23-docker/docker-compose.yml` unter `services:` einfügen (die Vorlage
ist bereits passend eingerückt):

```yaml
  whisper-proxy:
    image: ghcr.io/ei23fxg/whisperapiproxy
    container_name: whisper-api-proxy
    restart: unless-stopped
    ports:
      - "5431:5431"
    environment:
      NEEDLE_TELEMETRY: "0"
      TZ: Europe/Berlin
      # Verzeichnis-Mount: der Container schreibt die config.py beim ersten
      # Start selbst.
      CONFIG_PATH: /app/config/config.py
    volumes:
      - ./volumes/whisper-proxy/config:/app/config
      - ./volumes/whisper-proxy/recordings:/app/recordings
      - ./volumes/whisper-proxy/client_logs:/app/client_logs
      - ./volumes/whisper-proxy/proxy_logs:/app/logs
      - ./volumes/whisper-proxy/models/hf:/root/.cache/huggingface
      - ./volumes/whisper-proxy/models/cactus:/root/.cache/cactus-needle
```

Dann im `~/ei23-docker` starten:

```bash
ei23 dc          # oder: docker compose up -d
docker logs -f whisper-api-proxy
```

Beim ersten Start legt der Container
`./volumes/whisper-proxy/config/config.py` selbst an. Keys und Clients anpassen
und den Container neu starten:

```bash
sudo nano ~/ei23-docker/volumes/whisper-proxy/config/config.py
docker restart whisper-api-proxy
```

- Die Pfade sind relativ zu `~/ei23-docker`; `volumes/whisper-proxy/` wächst
  beim ersten Betrieb um die Modellgewichte (~660 MB).
- Der Port `5431` wird veröffentlicht, damit Home Assistant und andere
  LAN-Clients zugreifen können.
- Das GHCR-Paket ist standardmäßig privat. Falls der Pull fehlschlägt, siehe
  [Image über GHCR beziehen](#image-über-ghcr-beziehen) (`docker login ghcr.io`).
- Updates: `docker compose pull whisper-proxy && docker compose up -d` (im
  `~/ei23-docker`, oder `ei23 du`). Die Modell-Caches bleiben in den
  Bind-Mounts erhalten.

### Als Whisper-Server in Home Assistant

Der Proxy spricht die OpenAI-API (`/v1/audio/transcriptions`) und lässt sich
damit als Sprache-zu-Text-Engine in Home Assistant nutzen. Die Aufnahmen werden
lokal von Whisper-WebUI bzw. den CPU-Engines verarbeitet — vorausgesetzt,
`allow_openai` ist für den Client deaktiviert. Empfohlen ist die Integration
[ha-openai-whisper-stt-api](https://github.com/fabio-garavini/ha-openai-whisper-stt-api)
(„OpenAI Whisper Cloud“, obwohl der Server lokal läuft).

1. Integration über HACS installieren (Custom Repository
   `https://github.com/fabio-garavini/ha-openai-whisper-stt-api`, Kategorie
   *Integration*) oder manuell nach `custom_components/` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen →
   „OpenAI Whisper Cloud“**.
4. Als Provider **Custom** wählen und eintragen:

   | Feld | Wert |
   |---|---|
   | URL | `http://<IP-des-Servers>:5431` |
   | API-Key | ein Key aus `api_clients` in der `config.py` |
   | Modell | `whisper-1` (wird nur an OpenAI weitergereicht, die lokalen Engines ignorieren ihn) |

   Die URL ohne Pfad ist richtig: die Integration hängt
   `/v1/audio/transcriptions` automatisch an. Ein `/v1/models`-Endpoint ist
   nicht nötig.
5. **Einstellungen → Sprachassistenten → Pipeline → Sprache-zu-Text** und dort
   die neue Engine auswählen.

Funktionstest ohne Home Assistant:

```bash
curl -s http://192.168.1.10:5431/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-..." \
  -F file=@test.wav \
  -F model=whisper-1
```

Hinweise:

- **Rein lokal bleiben:** Beim Client `allow_openai: False` setzen. Sonst wird
  nach dem Ausfall von Whisper-WebUI und lokalen Engines doch die
  kostenpflichtige OpenAI-API genutzt.
- **Streaming-Upload:** Die Integration lädt Audio standardmäßig schon während
  der Aufnahme hoch. Der Proxy verarbeitet das normal; falls es Probleme gibt,
  die Option in den Integrationsoptionen abschalten.
- **Nicht ausgewertet:** Der Proxy kennt derzeit nur `file`, `model` und
  `srt_format`. `prompt`, `temperature`, `language` und `response_format` werden
  ignoriert. Die Sprache steuert man über `whisper_predict_config` (Whisper-WebUI)
  bzw. `whistle_language` (Whistle); Parakeet erkennt sie selbst.
- **Healthcheck:** `curl http://<IP-des-Servers>:5431/health` liefert
  `{"status":"ok"}` ohne API-Key.

## Configuration

The project is configured using the `config.py` file. This file contains settings for:

*   `whisper_webui_host`: The host address of the local [Whisper WebUI](https://github.com/jhj0517/Whisper-WebUI) service.
*   `openai_api_key`: The API key for the OpenAI API.
*   `api_clients`: A dictionary of API clients, with each client identified by a unique ID and configured with an API key and a flag to enable/disable saving recordings.

In Docker, no manual setup is needed: if the file is missing, it is created from
`config.example.py` on first start. Its location is `$CONFIG_PATH` (default
`/app/config/config.py`, mounted from `./config/` in the bundled compose file).
A legacy single-file mount at `/app/config.py` is still detected. Outside Docker
the loader looks for `config.py` next to the source files (or in `data/`).

## API Endpoint

`http://yourserver.local:5431/v1/audio/transcriptions`

*   **Method:** POST
*   **Headers:**
    *   `Authorization`: Bearer <API_KEY>
*   **Body:**
    *   `file`: The audio file to transcribe (as a file upload).

## Usage

1.  Create a `config.py` file with the appropriate settings, see `config.example.py` (Docker creates it automatically on first start)
2.  Start the FastAPI application: `uvicorn whisper_api_proxy:app --host 0.0.0.0 --port 5431` (`.venv/bin/uvicorn` with venv)
3.  Send a POST request to the `http://yourserver.local:5431/v1/audio/transcriptions` endpoint with the audio file and API key (same as OpenAI Whisper API)

## Dependencies

*   FastAPI
*   gradio_client
*   pydub
*   python-multipart
*   requests
*   Uvicorn


Install dependencies using:

```bash
python3 -m venv .venv; source .venv/bin/activate # optional venv
pip install -r requirements.txt
```

## Prerequisites

FFmpeg (with libopus) must be installed on the server.
