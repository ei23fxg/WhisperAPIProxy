whisper_webui_host = "http://localhost:7860/"

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
