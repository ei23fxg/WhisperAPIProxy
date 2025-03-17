from flask import Flask, request, jsonify
import config
import os
import requests
import threading
import time
from gradio_client import Client, handle_file

app = Flask(__name__)

# Script directory and fixed filename for the audio file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILE_NAME = os.path.join(SCRIPT_DIR, "api_tmp.wav")

# Global variable for the status of the local service
local_service_available = False

# Function to periodically check the local service
def check_local_service():
    global local_service_available
    while True:
        try:
            response = requests.get(config.whisper_webui_host, timeout=5)
            local_service_available = response.status_code == 200
        except requests.RequestException:
            local_service_available = False
        time.sleep(30)  # Check every 30 seconds

# Start the background thread for checking
threading.Thread(target=check_local_service, daemon=True).start()

# Function for transcription with the local service
def get_transcript(audiofile):
    try:
        client = Client(config.whisper_webui_host)
        predict_config = config.whisper_predict_config
        predict_config["files"] = [handle_file(audiofile)]
        result = client.predict(**predict_config)
        transcript_content = result[0]
        if len(transcript_content.split('\n')) > 5:
            transcript_content = '\n'.join(transcript_content.split('\n')[5:])
        return transcript_content.strip().replace("\n", " ").replace("\r", " ")
    except Exception as e:
        print(f"Error with local service: {e}")
        return None

# Function for transcription with the OpenAI API
def transcribe_with_openai(audio_file):
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config.openai_api_key}"}
    files = {"file": ("audio.wav", open(audio_file, "rb"), "audio/wav")}
    data = {"model": "whisper-1"}

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        if response.status_code == 200:
            return response.json().get("text", "No transcription received.")
        else:
            print(f"OpenAI API Error: {response.status_code}, {response.text}")
            return None
    except requests.RequestException as e:
        print(f"Error with OpenAI API: {e}")
        return None

# API endpoint for audio transcriptions
@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe_audio():
    # Check authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    api_key = auth_header[7:]  # Entferne "Bearer "
    client_id = None
    for client_id, client_config in config.api_clients.items():
        if client_config["api_key"] == api_key:
            save_recordings = client_config["save_recordings"]
            break
    else:
        return jsonify({"error": "Unauthorized"}), 401

    # Check audio file
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save audio file
    file.save(AUDIO_FILE_NAME)

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
    audio_duration = 0
    # Here the actual duration of the audio file should be calculated.
    # Since I don't have access to a library for audio analysis,
    # I use a dummy calculation based on the file size.
    file_size_kb = os.path.getsize(AUDIO_FILE_NAME) / 1024
    audio_duration = file_size_kb * 0.1  # Dummy calculation: 100ms per KB

    # Log the usage
    log_usage(client_id, audio_duration, "openai" if not local_service_available else "local")

    # Decide which service to use

    if local_service_available:
        transcription = get_transcript(AUDIO_FILE_NAME)
        if transcription:
            if save_recordings:
                # Save the transcription
                text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                with open(text_file_path, "w") as text_file:
                    text_file.write(transcription)
            return jsonify({"text": transcription})
        else:
            # Fallback zu OpenAI
            transcription = transcribe_with_openai(AUDIO_FILE_NAME)
            if transcription:
                if save_recordings:
                    # Save the transcription
                    text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                    with open(text_file_path, "w") as text_file:
                        text_file.write(transcription)
                return jsonify({"text": transcription})
            return jsonify({"error": "Transcription failed"}), 500
    else:
        # Local service not available, use OpenAI
        transcription = transcribe_with_openai(AUDIO_FILE_NAME)
        if transcription:
            if save_recordings:
                # Save the transcription
                text_file_path = os.path.join(recordings_dir, f"{filename}.txt")
                with open(text_file_path, "w") as text_file:
                    text_file.write(transcription)
            return jsonify({"text": transcription})
        return jsonify({"error": "Transcription failed"}), 500

    # Calculate the usage time
    audio_duration = 0
    # Here the actual duration of the audio file should be calculated.
    # Since I don't have access to a library for audio analysis,
    # I use a dummy calculation based on the file size.
    file_size_kb = os.path.getsize(AUDIO_FILE_NAME) / 1024
    audio_duration = file_size_kb * 0.1  # Dummy-Berechnung: 100ms pro KB

    # Log the usage
    log_usage(client_id, audio_duration, "openai" if not local_service_available else "local")

    # Decice which service to use
    if local_service_available:
        transcription = get_transcript(AUDIO_FILE_NAME)
        if transcription:
            return jsonify({"text": transcription})
        else:
            # Fallback to OpenAI
            transcription = transcribe_with_openai(AUDIO_FILE_NAME)
            if transcription:
                return jsonify({"text": transcription})
            return jsonify({"error": "Transcription failed"}), 500
    else:
        # Local service not available, use OpenAI
        transcription = transcribe_with_openai(AUDIO_FILE_NAME)
        if transcription:
            return jsonify({"text": transcription})
        return jsonify({"error": "Transcription failed"}), 500

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
        print(f"Error reading the log file: {e}")

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5431)