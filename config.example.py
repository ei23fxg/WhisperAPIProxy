# Vorlage für config.py.
#
# Fehlt beim Containerstart eine config.py, kopiert docker-entrypoint.sh diese
# Datei automatisch nach $CONFIG_PATH (Default: /app/config/config.py). Danach
# die Keys/Clients anpassen und den Container neu starten
# (docker compose restart whisper-proxy).

whisper_webui_host = "http://localhost:7860/"

# --- Lokale Fallback-Engines (CPU) -------------------------------------
# Reihenfolge, in der lokale Engines probiert werden, bevor OpenAI genutzt
# wird. Jede Engine lässt sich mit <name>_enabled = False abschalten.
fallback_order = ["parakeet", "whistle"]

# Parakeet TDT 0.6B v3: genauer bei Zahlen/Domains, ~640 MB int8.
#   pip install onnx-asr onnxruntime
parakeet_enabled = True
parakeet_model = "nemo-parakeet-tdt-0.6b-v3"
parakeet_quantization = "int8"

# Whistle: 16,9 MB, sehr schnell, 7 Sprachen.
#   pip install "cactus-needle[mic]"
whistle_enabled = True
whistle_language = None   # None = Spracherkennung automatisch, sonst z.B. "de"

# Wie oft (Sekunden) die Whisper-WebUI im Hintergrund geprüft wird.
# Bestimmt, wie lange die Rückkehr zu Whisper nach einem Ausfall dauert.
local_check_interval = 30

# Lokale Modellgewichte beim Containerstart laden (blockierend), nicht erst
# beim ersten Diktat. False = sofort starten und erst bei Bedarf laden.
warmup_on_startup = True

# Uploads unter dieser Dauer (Sekunden) werden mit HTTP 400 abgelehnt, statt
# sie an die Engines zu geben. 0.2 s filtert leere/Test-Aufnahmen; 0 = aus.
min_audio_duration = 0.2

# OpenAI API key (hardcoded)
openai_api_key = "sk-proj-XXXXXXXXXXXXXXXXXXx"  # Place your API KEY here
# OpenAI WHISPER API URL
openai_api_url = "https://api.openai.com/v1/audio/transcriptions"

# API Clients - you can disable
api_clients = {
    "felix_test": {"api_key": "sk-1234felix", "save_recordings": True, "allow_openai": True},
    "alice456": {"api_key": "sk-client-alice456", "save_recordings": True, "allow_openai": False},
    "charlie789": {"api_key": "sk-client-charlie789", "save_recordings": False, "allow_openai": True},
}

# Whisper predict configuration - you may need to change something for yourself here
whisper_predict_config = {
    "files": "[handle_file(audiofile)]",
    "input_folder_path": "",
    "include_subdirectory": False,
    "save_same_dir": True,
    "file_format": "txt",
    "add_timestamp": False,
    "progress": "large-v3-turbo",
    "param_7": "Automatic Detection",
    "param_8": False,
    "param_9": 5,
    "param_10": -1,
    "param_11": 0.6,
    "param_12": "float16",
    "param_13": 5,
    "param_14": 1,
    "param_15": True,
    "param_16": 0.5,
    "param_17": "",
    "param_18": 0,
    "param_19": 2.4,
    "param_20": 1,
    "param_21": 1,
    "param_22": 0,
    "param_23": "",
    "param_24": True,
    "param_25": "[-1]",
    "param_26": 1,
    "param_27": False,
    "param_28": '“¿([{-"',
    "param_29": '.。,，!！?？:：”)]}、',
    "param_30": 0,
    "param_31": 30,
    "param_32": 0,
    "param_33": "",
    "param_34": 0,
    "param_35": 1,
    "param_36": 24,
    "param_37": True,
    "param_38": True,
    "param_39": 0.5,
    "param_40": 250,
    "param_41": 9999,
    "param_42": 1000,
    "param_43": 2000,
    "param_44": False,
    "param_45": "cuda",
    "param_46": "",
    "param_47": True,
    "param_48": False,
    "param_49": "UVR-MDX-NET-Inst_HQ_4",
    "param_50": "cuda",
    "param_51": 256,
    "param_52": False,
    "param_53": True,
    "api_name": "/transcribe_file"
}
