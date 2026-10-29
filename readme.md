# Whisper API Proxy

This project provides an (OpenAI-compatible) proxy API for audio transcriptions, allowing clients to transcribe audio files using either the great local [Whisper WebUI](https://github.com/jhj0517/Whisper-WebUI) service of @jhj0517 or the OpenAI Whisper API.

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

## Local Fallback Engines (CPU)

If the Whisper WebUI is unreachable or returns nothing, the proxy tries local
engines in the order defined by `config.fallback_order` — and only then OpenAI
(and only if `allow_openai` is enabled for the client):

```text
Whisper WebUI (GPU)  →  Parakeet (CPU)  →  Whistle (CPU)  →  OpenAI
```

```python
fallback_order = ["parakeet", "whistle"]

parakeet_enabled = True
parakeet_model = "nemo-parakeet-tdt-0.6b-v3"
parakeet_quantization = "int8"

whistle_enabled = True
whistle_language = None   # None = auto-detect, otherwise e.g. "de"

# Interval (seconds) at which the WebUI is checked (failover after an outage)
local_check_interval = 30
```

Installing the local engines:

```bash
pip install onnx-asr onnxruntime          # Parakeet (~640 MB int8)
pip install "cactus-needle[mic]"          # Whistle (~17 MB)
```

Both are optional: if a package is missing, that engine is skipped. The status
is available at `GET /v1/local_service_status` (`whistle`, `parakeet`).

### SRT / timestamps

Both engines return timestamps (Parakeet token times, Whistle word times). Set
`srt_format=true` in the request to get SRT — the same response format as the
Whisper WebUI path:

```srt
1
00:00:00,640 --> 00:00:04,000
1234 F.23.de23.de

2
00:00:11,040 --> 00:00:12,720
It doesn't really matter what I say here
```

Grouping: line breaks at `.`/`!`/`?`, after 42 characters or 3 s
(`srt_utils.words_to_srt(words, max_chars=…, max_secs=…)`).

### Where are the model weights stored?

| Engine | Path | Size |
|---|---|---|
| Parakeet (onnx-asr) | `~/.cache/huggingface/hub/models--istupakov--parakeet-tdt-0.6b-v3-onnx/` | ~640 MB (int8) |
| Whistle (cactus-needle) | `~/.cache/cactus-needle/whistle/2.0.0/whistle.cact` | 16.9 MB |

On first use, Whistle is downloaded via the HuggingFace Hub
(`Cactus-Compute/whistle`) and additionally copied into the cactus-needle cache.

Override:
- Parakeet: set `HF_HOME` or `HF_HUB_CACHE`
- Whistle: `NEEDLE_WHISTLE_WEIGHTS=/path/to/whistle.cact`

**Docker:** both caches live inside the container and are lost on a rebuild —
mount `~/.cache/huggingface` and `~/.cache/cactus-needle` as volumes (or set
`HF_HOME` to a volume).

Check:

```bash
du -sh ~/.cache/huggingface/hub/models--istupakov--parakeet-tdt-0.6b-v3-onnx        ~/.cache/cactus-needle/whistle/2.0.0/whistle.cact
huggingface-cli scan-cache | head
```

### Failover timings

- **WebUI goes down:** the next request that fails switches to the local engines
  immediately (no waiting for the poll tick).
- **WebUI comes back:** at most `local_check_interval` + 5 s health timeout
  (so ~35 s by default, about 15 s with `local_check_interval = 10`).

Whistle and Parakeet usage is counted as `local` in the usage statistics.

## Docker

The service can run in a container — including ffmpeg and both local engines.
A `config.py` does **not** need to be prepared: if it is missing, the container
creates a default configuration from [`config.example.py`](config.example.py)
on first start.

```bash
docker compose up -d --build
docker compose logs -f
```

On first start `./config/config.py` is created. Adjust the API keys and clients
there, then restart:

```bash
sudo nano config/config.py
docker compose restart whisper-proxy
```

The container runs as root, so `./config/` (including the generated file) is
owned by root. Edit it with `sudo` or set `user:` in the compose file first.

> **Note:** The default configuration contains demo clients and placeholder
> keys. Make sure to change them before running the service on a LAN or with a
> published port.

### Configuration: where does config.py come from?

The container looks in this order:

| # | Path | Purpose |
|---|---|---|
| 1 | `$CONFIG_PATH` (image default: `/app/config/config.py`) | Directory mount, created on demand |
| 2 | `/app/config.py` | Classic single-file mount |
| 3 | `/app/data/config.py` | Last fallback (not persistent) |

If no file is found, the entrypoint copies `config.example.py` to the first
writable target and starts anyway. A missing `config.py` is no longer a startup
error.

**Important for your own compose files:** A mount like

```yaml
- ./config.py:/app/config.py:ro
```

only works if `./config.py` **already exists** on the host. If the file is
missing, Docker creates a *directory* with that name; the container cannot write
to it and the app cannot import it. That is why the bundled compose file mounts
a directory instead:

```yaml
volumes:
  - ./config:/app/config
environment:
  CONFIG_PATH: /app/config/config.py
```

`docker compose up -d` then creates `./config/config.py` automatically. If you
already have the file as `./config.py`, simply move it to `./config/config.py`
(or keep mounting it read-only as a single file, see the comment in the compose
file). If an empty `./config.py` directory is left over from an earlier failed
attempt (for ei23: `volumes/whisper-proxy/config.py`), delete it first.

On first start the models are downloaded if needed (~660 MB). You can trigger
that beforehand:

```bash
docker compose exec whisper-proxy python warmup_models.py
```

### What is stored where

| Host | Container | Content |
|---|---|---|
| `./config/` | `/app/config` | `config.py` (created on first start) |
| `./recordings/` | `/app/recordings` | Recordings (Opus) + `.txt` — visible directly in the project folder |
| `./client_logs/` | `/app/client_logs` | Usage statistics per client |
| Volume `proxy_logs` | `/app/logs` | `error.log` |
| Volume `hf_cache` | `/root/.cache/huggingface` | Parakeet weights (~640 MB) |
| Volume `cactus_cache` | `/root/.cache/cactus-needle` | Whistle (`whistle.cact`, 16.9 MB) |

The two cache volumes survive `docker compose build` and `up --build`, so the
models are downloaded only once. If you prefer the weights as regular folders,
replace the last two entries in the compose file with the commented-out bind
mounts (`./models/hf`, `./models/cactus`).

Inspect/clean up volumes:

```bash
docker volume ls | grep -E "hf_cache|cactus_cache|proxy_logs"
docker compose exec whisper-proxy du -sh /root/.cache/*
docker compose down -v          # warning: also deletes the model caches
```

### Pulling the image from GHCR

The repo contains `.github/workflows/docker.yml`: on every push to `master`
(and for tags `v*`) the image is built and pushed to
`ghcr.io/ei23fxg/whisperapiproxy`. Tags are `master`, `latest`, `sha-<short>`
and, for Git tags, `1.2.3` and `1.2`.

After the first run: GitHub → **Packages** → `whisperapiproxy` → *Package
settings*. By default the package is **private** — either make it public there
or log in on the server with a token.

On the server (once, PAT with `read:packages`):

```bash
echo "$CR_PAT" | docker login ghcr.io -u ei23fxg --password-stdin
```

Then create a `.env` next to the compose file:

```dotenv
PROXY_IMAGE=ghcr.io/ei23fxg/whisperapiproxy:latest
```

and start:

```bash
docker compose pull
docker compose up -d
```

Updates later: `docker compose pull && docker compose up -d`.
Without `.env`, `docker compose up -d --build` keeps building locally.

The model caches live in the named volumes and survive an image update — only
the image is downloaded again.

### Operations

```bash
docker compose ps                    # status incl. healthcheck
docker compose restart whisper-proxy
docker compose build --pull && docker compose up -d   # update
docker compose down                  # stop (data is kept)
```

- Healthcheck: `GET /health` (no API key) — for Docker only, returns `{"status":"ok"}`.
- A single worker is hard-coded on purpose: models and state live in the process.
- Port `5431` is published on all interfaces; restrict it with a firewall if
  needed.
- The container runs as root; `./config`, `./recordings` and `./client_logs`
  are then owned by root. For a different user you would set `user:` in the
  compose file and prepare the folders accordingly.
- GPU: The image uses ONNX Runtime on the CPU. For CUDA you would install
  `onnxruntime-gpu`, enable the NVIDIA container toolkit and add
  `deploy.resources.reservations.devices` to the compose file — the CPU variant
  is sufficient for dictation.

### ei23 DIY Smart Home

The proxy fits directly into the [ei23 DIY Smart Home](https://github.com/ei23com/diy-smart-home)
and can run there as its own service. The template lives in the repo at
[`examples/diy-smart-home/whisper-proxy.yml`](examples/diy-smart-home/whisper-proxy.yml).

Add it under `services:` in `~/ei23-docker/docker-compose.yml` (the template is
already indented correctly):

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
      # Directory mount: the container creates config.py itself on first
      # start.
      CONFIG_PATH: /app/config/config.py
    volumes:
      - ./volumes/whisper-proxy/config:/app/config
      - ./volumes/whisper-proxy/recordings:/app/recordings
      - ./volumes/whisper-proxy/client_logs:/app/client_logs
      - ./volumes/whisper-proxy/proxy_logs:/app/logs
      - ./volumes/whisper-proxy/models/hf:/root/.cache/huggingface
      - ./volumes/whisper-proxy/models/cactus:/root/.cache/cactus-needle
```

Then start it in `~/ei23-docker`:

```bash
ei23 dc          # or: docker compose up -d
docker logs -f whisper-api-proxy
```

On first start the container creates
`./volumes/whisper-proxy/config/config.py` itself. Adjust keys and clients and
restart the container:

```bash
sudo nano ~/ei23-docker/volumes/whisper-proxy/config/config.py
docker restart whisper-api-proxy
```

- The paths are relative to `~/ei23-docker`; `volumes/whisper-proxy/` grows by
  the model weights (~660 MB) on first use.
- Port `5431` is published so Home Assistant and other LAN clients can connect.
- The GHCR package is private by default. If the pull fails, see
  [Pulling the image from GHCR](#pulling-the-image-from-ghcr) (`docker login ghcr.io`).
- Updates: `docker compose pull whisper-proxy && docker compose up -d` (in
  `~/ei23-docker`, or `ei23 du`). The model caches stay in the bind mounts.

### Using it as a Whisper server in Home Assistant

The proxy speaks the OpenAI API (`/v1/audio/transcriptions`) and can therefore
be used as a speech-to-text engine in Home Assistant. Audio is processed locally
by the Whisper WebUI or the CPU engines — provided `allow_openai` is disabled
for the client. The recommended integration is
[ha-openai-whisper-stt-api](https://github.com/fabio-garavini/ha-openai-whisper-stt-api)
("OpenAI Whisper Cloud", even though the server runs locally).

1. Install the integration via HACS (custom repository
   `https://github.com/fabio-garavini/ha-openai-whisper-stt-api`, category
   *Integration*) or copy it manually to `custom_components/`.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration →
   "OpenAI Whisper Cloud"**.
4. Choose **Custom** as the provider and enter:

   | Field | Value |
   |---|---|
   | URL | `http://<server-ip>:5431` |
   | API key | a key from `api_clients` in `config.py` |
   | Model | `whisper-1` (only forwarded to OpenAI; the local engines ignore it) |

   The URL without a path is correct: the integration appends
   `/v1/audio/transcriptions` automatically. A `/v1/models` endpoint is not
   required.
5. **Settings → Voice assistants → Pipeline → Speech-to-text** and select the
   new engine there.

Test without Home Assistant:

```bash
curl -s http://192.168.1.10:5431/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-..." \
  -F file=@test.wav \
  -F model=whisper-1
```

Notes:

- **Stay fully local:** set `allow_openai: False` for the client. Otherwise the
  paid OpenAI API is used after the Whisper WebUI and the local engines have
  failed.
- **Streaming upload:** The integration uploads audio while it is still being
  recorded. The proxy handles this normally; if you run into problems, disable
  the option in the integration settings.
- **Not evaluated:** The proxy currently only knows `file`, `model` and
  `srt_format`. `prompt`, `temperature`, `language` and `response_format` are
  ignored. The language is controlled via `whisper_predict_config` (Whisper
  WebUI) or `whistle_language` (Whistle); Parakeet detects it itself.
- **Healthcheck:** `curl http://<server-ip>:5431/health` returns
  `{"status":"ok"}` without an API key.

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
