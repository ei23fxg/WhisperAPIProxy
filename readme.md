# Whisper API Proxy

This project provides a (OpenAI compatible) proxy API for audio transcriptions, allowing clients to transcribe audio files using either a local Whisper WebUI service or the OpenAI Whisper API.

## Features

*   **Audio Transcription:** Transcribes audio files using either a local Whisper WebUI or the OpenAI API.
*   **Local Service Check:** Periodically checks the availability of the local Whisper WebUI service.
*   **API Key Authentication:** Authenticates clients using API keys.
*   **Usage Logging:** Logs API usage by client, tracking usage of both the local API and the OpenAI API.
*   **Audio Recording:** Saves audio recordings to the `recordings` directory (if enabled in the client configuration).
*   **Opus Conversion:** Converts audio files to Opus format for storage.

## Configuration

The project is configured using the `config.py` file. This file contains settings for:

*   `whisper_webui_host`: The host address of the local Whisper WebUI service.
*   `openai_api_key`: The API key for the OpenAI API.
*   `api_clients`: A dictionary of API clients, with each client identified by a unique ID and configured with an API key and a flag to enable/disable saving recordings.

## API Endpoint

`http://yourserver.local:5431/v1/audio/transcriptions`

*   **Method:** POST
*   **Headers:**
    *   `Authorization`: Bearer <API\_KEY>
*   **Body:**
    *   `file`: The audio file to transcribe.

## Usage

1.  Create a `config.py` file with the appropriate settings, see `config.example.py`
2.  Start the Flask application: `python whisper_api_proxy.py`
3.  Send a POST request to the `/v1/audio/transcriptions` endpoint with the audio file and API key.

## Dependencies

*   Flask
*   requests
*   gradio\_client
*   python-dotenv

Install dependencies using:

```bash
pip install -r requirements.txt
```

## Prerequisites

FFmpeg (with libopus) must be installed on the server.
