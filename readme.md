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
Engines. Voraussetzung: eine `config.py` im Projektordner (wird read-only
eingebunden).

```bash
docker compose up -d --build
docker compose logs -f
```

Beim ersten Start werden die Modelle bei Bedarf geladen (~660 MB). Das lässt
sich vorher anstoßen:

```bash
docker compose exec whisper-proxy python warmup_models.py
```

### Was wo liegt

| Host | Container | Inhalt |
|---|---|---|
| `./config.py` | `/app/config.py` (read-only) | API-Keys, Clients, Fallback-Konfiguration |
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
- Der Container läuft als root; `./data` gehört danach root. Für einen anderen
  Benutzer müsste man `user:` in der Compose-Datei setzen und `./data`
  entsprechend vorbereiten.
- GPU: Das Image nutzt ONNX Runtime für die CPU. Für CUDA müsste man
  `onnxruntime-gpu` installieren, das NVIDIA-Container-Toolkit aktivieren und
  `deploy.resources.reservations.devices` in der Compose-Datei ergänzen — für
  Diktat ist die CPU-Variante ausreichend.

## Configuration

The project is configured using the `config.py` file. This file contains settings for:

*   `whisper_webui_host`: The host address of the local [Whisper WebUI](https://github.com/jhj0517/Whisper-WebUI) service.
*   `openai_api_key`: The API key for the OpenAI API.
*   `api_clients`: A dictionary of API clients, with each client identified by a unique ID and configured with an API key and a flag to enable/disable saving recordings.

## API Endpoint

`http://yourserver.local:5431/v1/audio/transcriptions`

*   **Method:** POST
*   **Headers:**
    *   `Authorization`: Bearer <API_KEY>
*   **Body:**
    *   `file`: The audio file to transcribe (as a file upload).

## Usage

1.  Create a `config.py` file with the appropriate settings, see `config.example.py`
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
