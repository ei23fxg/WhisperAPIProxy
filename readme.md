# Whisper API Proxy

This project provides a (OpenAI compatible) proxy API for audio transcriptions, allowing clients to transcribe audio files using either the great local [Whisper WebUI](https://github.com/jhj0517/Whisper-WebUI) service of @jhj0517 or the OpenAI Whisper API.

## Features

*   **Audio Transcription:** Transcribes audio files using either a local Whisper WebUI or the OpenAI API.
*   **Local Service Check:** Periodically checks the availability of the local Whisper WebUI service.
*   **API Key Authentication:** Authenticates clients using API keys.
*   **Usage Logging:** Logs API usage by client, tracking usage of both the local API and the OpenAI API.
*   **Audio Recording:** Saves audio recordings to the `recordings` directory (if enabled in the client configuration).
*   **Opus Conversion:** Converts audio files to Opus format for storage.

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
