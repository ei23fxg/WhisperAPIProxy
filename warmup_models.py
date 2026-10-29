"""Loads the local fallback model weights ahead of time.

The proxy already does this during startup (see ``warmup_on_startup`` in
config.py). This script is useful to pre-download the weights into the cache
volumes without starting the service, e.g.:

    docker compose run --rm whisper-proxy python warmup_models.py
"""

from config_loader import config
import parakeet_transcriber
import whistle_transcriber


def main() -> int:
    ok = True

    if getattr(config, "parakeet_enabled", True):
        if parakeet_transcriber.available():
            print("Loading Parakeet (int8, CPU) …", flush=True)
            if parakeet_transcriber.warmup(
                getattr(config, "parakeet_model", parakeet_transcriber.DEFAULT_MODEL),
                getattr(config, "parakeet_quantization", parakeet_transcriber.DEFAULT_QUANT),
            ):
                print("Parakeet ready", flush=True)
            else:
                ok = False
                print("Parakeet failed to load", flush=True)
        else:
            print("Parakeet skipped (onnx-asr not installed)", flush=True)

    if getattr(config, "whistle_enabled", True):
        if whistle_transcriber.available():
            print("Loading Whistle …", flush=True)
            if whistle_transcriber.warmup():
                print("Whistle ready", flush=True)
            else:
                ok = False
                print("Whistle failed to load", flush=True)
        else:
            print("Whistle skipped (cactus-needle not installed)", flush=True)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
