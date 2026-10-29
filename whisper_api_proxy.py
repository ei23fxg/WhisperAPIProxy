from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydub import AudioSegment
from config_loader import config
import os
import requests
import threading
import time
from gradio_client import Client, handle_file
from typing import Optional
import parakeet_transcriber
import whistle_transcriber

ERROR_LOG_FILE = "error.log"

def log_error(client_id: str, error_message: str):
    """Logs an error message with timestamp and client ID to the error log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    error_message = error_message.replace("\n"," ")
    log_entry = f"[{timestamp}] - Client: {client_id} - Error: {error_message}\n"
    try:
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to error log: {e}")
app = FastAPI()


@app.get("/health")
async def health():
    """Unauthenticated liveness probe (Docker healthcheck)."""
    return JSONResponse(content={"status": "ok"})

# Script directory and fixed filename for the audio file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILE_NAME = os.path.join(SCRIPT_DIR, "api_tmp.wav")

# Global variable for the status of the local service
local_service_available = False

# Wie oft der Hintergrund-Thread die Whisper-WebUI prüft (Sekunden).
# Damit ist auch die Umschaltzeit nach einem Ausfall begrenzt.
LOCAL_CHECK_INTERVAL = int(getattr(config, "local_check_interval", 30))


# Function to periodically check the local service
def check_local_service():
    global local_service_available
    while True:
        try:
            response = requests.get(config.whisper_webui_host, timeout=5)
            local_service_available = response.status_code == 200
        except requests.RequestException:
            local_service_available = False
        time.sleep(LOCAL_CHECK_INTERVAL)

# Start the background thread for checking
threading.Thread(target=check_local_service, daemon=True).start()

@app.on_event("startup")
def warmup_local_engines():
    """Lokale Fallback-Modelle im Hintergrund laden, damit das erste Diktat nicht wartet."""
    if getattr(config, "whistle_enabled", True) and whistle_transcriber.available():
        threading.Thread(target=whistle_transcriber.warmup, daemon=True).start()
    if getattr(config, "parakeet_enabled", True) and parakeet_transcriber.available():
        threading.Thread(
            target=parakeet_transcriber.warmup,
            args=(getattr(config, "parakeet_model", parakeet_transcriber.DEFAULT_MODEL),
                  getattr(config, "parakeet_quantization", parakeet_transcriber.DEFAULT_QUANT)),
            daemon=True,
        ).start()


# Function for transcription with the local service
def get_transcript(audiofile, srt_format: bool):
    try:
        client = Client(config.whisper_webui_host)
        # Make a copy to avoid modifying the global config dict directly
        predict_config = config.whisper_predict_config.copy()
        predict_config["files"] = [handle_file(audiofile)]
        if srt_format:
            predict_config["file_format"] = "SRT"
        else:
            predict_config["file_format"] = "txt"
        result = client.predict(**predict_config)
        transcript_content = result[0]
        if len(transcript_content.split('\n')) > 5:
            transcript_content = '\n'.join(transcript_content.split('\n')[5:])
        return transcript_content.strip().replace("\n", " ").replace("\r", " ")
    except Exception as e:
        print(f"Error with local service: {e}")
        return None

# Function for transcription with the OpenAI API
def transcribe_with_openai(audio_file, model: str, client_id: str):
    url = config.openai_api_url
    headers = {"Authorization": f"Bearer {config.openai_api_key}"}
    files = {"file": ("audio.wav", open(audio_file, "rb"), "audio/wav")}
    data = {"model": model}

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        if response.status_code == 200:
            return response.json().get("text", "No transcription received.")
        else:
            print(f"OpenAI API Error: {response.status_code}, {response.text}")
            log_error(client_id, f"OpenAI API Error: {response.status_code}, {response.text}")
            return None
    except requests.RequestException as e:
        log_error(client_id, f"Error with OpenAI API: {e}")
        print(f"Error with OpenAI API: {e}")
        return None

def _run_local_engine(name: str, audio_file, srt: bool):
    """Eine lokale Engine ausführen (Text oder SRT); None, wenn sie nicht kann."""
    if name == "parakeet":
        model = getattr(config, "parakeet_model", parakeet_transcriber.DEFAULT_MODEL)
        quant = getattr(config, "parakeet_quantization", parakeet_transcriber.DEFAULT_QUANT)
        if srt:
            return parakeet_transcriber.transcribe_srt(audio_file, model, quant)
        return parakeet_transcriber.transcribe(audio_file, model, quant)

    if name == "whistle":
        lang = getattr(config, "whistle_language", None)
        if srt:
            return whistle_transcriber.transcribe_srt(audio_file, language=lang)
        return whistle_transcriber.transcribe(audio_file, language=lang)

    return None


def transcribe_with_local_fallback(audio_file, client_id: str, srt: bool = False):
    """Lokale Fallbacks in konfigurierter Reihenfolge, bevor OpenAI genutzt wird.

    `fallback_order` in config.py bestimmt die Reihenfolge, z. B.
    ["parakeet", "whistle"]. Jede Engine kann mit `<name>_enabled = False`
    abgeschaltet werden. Mit srt=True kommt SRT zurück (Wort-Zeitstempel).
    """
    order = getattr(config, "fallback_order", ["parakeet", "whistle"])
    for name in order:
        module = {"parakeet": parakeet_transcriber, "whistle": whistle_transcriber}.get(name)
        if module is None:
            log_error(client_id, f"Unbekannte Fallback-Engine: {name}")
            continue
        if not getattr(config, f"{name}_enabled", True):
            continue
        if not module.available():
            continue

        text = _run_local_engine(name, audio_file, srt)
        if text:
            print(f"{name}-Fallback für Client {client_id}")
            return text
        log_error(client_id, f"{name}-Fallback fehlgeschlagen: {module.load_error() or 'kein Text'}")

    return None


def save_transcript(save_recordings: bool, filename: str, transcription: str):
    """Transkript neben der Aufnahme ablegen (wenn für den Client aktiviert)."""
    if save_recordings:
        path = os.path.join("recordings", f"{filename}.txt")
        with open(path, "w") as text_file:
            text_file.write(transcription)


def get_audio_duration(file_path):
    audio = AudioSegment.from_file(file_path)
    duration_in_seconds = len(audio) / 1000.0
    return duration_in_seconds

# Security scheme
bearer_scheme = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    api_key = credentials.credentials
    # Iterate through api_clients to find a match for the provided api_key
    for c_id, client_config in config.api_clients.items():
        if client_config.get("api_key") == api_key:
            save_recordings = client_config.get("save_recordings", False)
            allow_openai = client_config.get("allow_openai", False)
            daily_quota = client_config.get("daily_quota")  # None means unlimited
            return c_id, save_recordings, allow_openai, daily_quota
    # If no match is found, log the error and raise HTTPException
    # Note: We don't have a client_id here if the key is invalid.
    # We could log the attempted key, but that might be a security risk.
    # For now, we'll log with a generic "UNKNOWN_CLIENT".
    log_error("UNKNOWN_CLIENT", f"Invalid API Key attempt: {api_key[:10]}...") # Log part of the key for tracing
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )

# API endpoint for audio transcriptions
@app.post('/v1/audio/transcriptions')
async def transcribe_audio(
    file: UploadFile = File(...),
    srt_format: bool = Form(False),
    model: str = Form("whisper-1"),
    client_data: tuple = Depends(verify_api_key)
):
    client_id, save_recordings, allow_openai, daily_quota = client_data

    # Check audio file
    if not file:
        log_error(client_id, "No file provided")
        raise HTTPException(status_code=400, detail="No file provided")
    if file.filename == '':
        log_error(client_id, "No selected file")
        raise HTTPException(status_code=400, detail="No selected file")

    # Save audio file
    with open(AUDIO_FILE_NAME, "wb") as f:
        f.write(await file.read())

    # Create the "recordings" folder if it doesn't exist
    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        os.makedirs(recordings_dir)

    # Generate the filename based on Client ID and timestamp
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    filename = f"{client_id}_{timestamp}"

    # Convert the audio file to Opus format and save the transcription (if enabled)
    if save_recordings:
        opus_file_path = os.path.join(recordings_dir, f"{filename}.opus")
        command = f"ffmpeg -y -i {AUDIO_FILE_NAME} -c:a libopus -b:a 20k -ac 1 {opus_file_path}"
        os.system(command)

    # Calculate the usage time
    audio_duration = get_audio_duration(AUDIO_FILE_NAME)

    # Check daily quota (None means unlimited, 0 means no quota)
    if daily_quota is not None and daily_quota == 0:
        # Convert the audio file to Opus format and save it (if enabled)
        if save_recordings:
            opus_file_path = os.path.join(recordings_dir, f"{filename}.opus")
            command = f"ffmpeg -y -i {AUDIO_FILE_NAME} -c:a libopus -b:a 20k -ac 1 {opus_file_path}"
            os.system(command)
        
        # Return the response directly without transcription
        # Return the filename instead of "Aufnahme gespeichert"
        if save_recordings:
            return JSONResponse({"text": f"{filename}.opus"})
        else:
            return JSONResponse({"text": f"{filename}.txt"})

    # Decide which service to use
    global local_service_available
    if local_service_available:
        transcription = get_transcript(AUDIO_FILE_NAME, srt_format)
        if transcription is None:
            # Dienst antwortet nicht mehr: sofort umschalten, nicht bis zum
            # naechsten Poll-Tick warten. Der Hintergrund-Thread schaltet ihn
            # wieder ein, sobald die WebUI zurueck ist.
            local_service_available = False
        if transcription:
            log_usage(client_id, audio_duration, "local")
            if save_recordings:
                # Save the transcription
                text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                with open(text_file_path, "w") as text_file:
                    text_file.write(transcription)
            return JSONResponse({"text": transcription})
        else:
            # Fallback: lokale Engines (Reihenfolge aus config.fallback_order)
            transcription = transcribe_with_local_fallback(AUDIO_FILE_NAME, client_id, srt_format)
            if transcription:
                log_usage(client_id, audio_duration, "local")
                save_transcript(save_recordings, filename, transcription)
                return JSONResponse({"text": transcription})

            # Fallback 2: OpenAI
            if allow_openai:
                transcription = transcribe_with_openai(AUDIO_FILE_NAME, model, client_id)
                log_usage(client_id, audio_duration, "openai")
                if transcription:
                    if save_recordings:
                        # Save the transcription
                        text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                        with open(text_file_path, "w") as text_file:
                            text_file.write(transcription)
                    return JSONResponse({"text": transcription})
                log_error(client_id, "Transcription failed with OpenAI after local fallback.")
                raise HTTPException(status_code=500, detail="Transcription failed")
            else:
                log_error(client_id, "OpenAI API usage is forbidden for this client after local fallback.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="OpenAI API usage is forbidden for this client",
                )
    else:
        # Fallback: lokale Engines (kein Netz, keine Kosten)
        transcription = transcribe_with_local_fallback(AUDIO_FILE_NAME, client_id, srt_format)
        if transcription:
            log_usage(client_id, audio_duration, "local")
            save_transcript(save_recordings, filename, transcription)
            return JSONResponse({"text": transcription})

        # Fallback 2: OpenAI
        if allow_openai:
            transcription = transcribe_with_openai(AUDIO_FILE_NAME, model, client_id)
            log_usage(client_id, audio_duration, "openai")
            if transcription:
                if save_recordings:
                    # Save the transcription
                    text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                    with open(text_file_path, "w") as text_file:
                        text_file.write(transcription)
                return JSONResponse({"text": transcription})
            log_error(client_id, "Transcription failed with OpenAI (local service unavailable).")
            raise HTTPException(status_code=500, detail="Transcription failed")
        else:
            log_error(client_id, "OpenAI API usage is forbidden for this client (local service unavailable).")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OpenAI API usage is forbidden for this client",
            )

# Function to log API usage
def log_usage(client_id, duration, api_type):
    log_dir = "client_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file_path = os.path.join(log_dir, f"{client_id}.log")
    today = time.strftime("%Y-%m-%d")

    # Check if the log file exists and write the header if necessary
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w") as log_file:
            log_file.write("Datum;LocalAPI;OpenAI\n")

    # Read the existing log data
    local_api_usage = 0
    openai_api_usage = 0
    existing_data = False

    try:
        with open(log_file_path, "r") as log_file:
            lines = log_file.readlines()
            if len(lines) > 1:
                last_line = lines[-1].strip().split(";")
                if last_line[0] == today:
                    local_api_usage = int(last_line[1])
                    openai_api_usage = int(last_line[2])
                    existing_data = True
    except FileNotFoundError:
        pass  # File was already created above, if it doesn't exist
    except Exception as e:
        print(f"Error reading the log file {log_file_path}: {e}")
        log_error(client_id, f"Error reading client log file {log_file_path}: {e}")

    # update user logs
    if api_type == "local":
        local_api_usage += int(duration)
    else:
        openai_api_usage += int(duration)

    # Write the updated log data
    with open(log_file_path, "a" if not existing_data else "w") as log_file:
        if not existing_data:
            log_file.write(f"{today};{local_api_usage};{openai_api_usage}\n")
        else:
            # change last line
            lines.pop()
            log_file.seek(0)
            log_file.truncate(0)
            log_file.writelines(lines)
            log_file.write(f"{today};{local_api_usage};{openai_api_usage}\n")

@app.get("/v1/local_service_status")
async def get_local_service_status(client_data: tuple = Depends(verify_api_key)):
    """
    Checks and returns the availability status of the local transcription service.
    Requires a valid API key.
    """
    # The verify_api_key dependency already handles authentication.
    # If the key is invalid, it will raise an HTTPException.
    # We just need to return the status of local_service_available.
    engines = {
        "whistle": whistle_transcriber.available(),
        "parakeet": parakeet_transcriber.available(),
    }
    if local_service_available:
        return JSONResponse(content={"status": "available", "message": "Local transcription service is available.", **engines})
    else:
        return JSONResponse(content={"status": "unavailable", "message": "Local transcription service is currently unavailable.", **engines})
    
@app.get("/usage")
async def get_usage_data():
    """
    Returns the API usage data for all clients for the current day.
    """
    today = time.strftime("%Y-%m-%d")
    usage_data = {}
    log_dir = "client_logs"

    if not os.path.exists(log_dir):
        return JSONResponse(content={"message": "No usage data available"}, status_code=404)

    for filename in os.listdir(log_dir):
        if filename.endswith(".log"):
            client_id = filename[:-4]  # Remove ".log" extension
            log_file_path = os.path.join(log_dir, filename)

            try:
                with open(log_file_path, "r") as log_file:
                    lines = log_file.readlines()
                    if len(lines) > 1:
                        last_line = lines[-1].strip().split(";")
                        if last_line[0] == today:
                            local_api_usage = int(last_line[1])
                            openai_api_usage = int(last_line[2])
                            usage_data[client_id] = {
                                "local_api_usage": local_api_usage,
                                "openai_api_usage": openai_api_usage
                            }
            except Exception as e:
                print(f"Error reading log file {filename}: {e}")
                log_error(client_id if 'client_id' in locals() else "SYSTEM", f"Error reading usage log file {filename}: {e}")

    if not usage_data:
        return JSONResponse(content={"message": "No usage data for today"}, status_code=404)

    return JSONResponse(content=usage_data)
