"""Lädt die lokalen Fallback-Modelle vor (z. B. nach dem ersten Start).

    docker compose exec whisper-proxy python warmup_models.py
"""

import config
import parakeet_transcriber
import whistle_transcriber


def main() -> None:
    if getattr(config, "parakeet_enabled", True):
        if parakeet_transcriber.available():
            print("lade Parakeet (int8, CPU) …", flush=True)
            parakeet_transcriber.warmup(
                getattr(config, "parakeet_model", parakeet_transcriber.DEFAULT_MODEL),
                getattr(config, "parakeet_quantization", parakeet_transcriber.DEFAULT_QUANT),
            )
            print("Parakeet bereit", flush=True)
        else:
            print("Parakeet übersprungen (onnx-asr fehlt)", flush=True)

    if getattr(config, "whistle_enabled", True):
        if whistle_transcriber.available():
            print("lade Whistle …", flush=True)
            whistle_transcriber.warmup()
            print("Whistle bereit", flush=True)
        else:
            print("Whistle übersprungen (cactus-needle fehlt)", flush=True)


if __name__ == "__main__":
    main()
