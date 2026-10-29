"""Lokaler CPU-Fallback: NVIDIA Parakeet TDT 0.6B v3 über onnx-asr.

Deutlich genauer als Whistle bei Zahlen/Domains, aber etwas schwergewichtiger
(Modell ~640 MB int8). Liefert Token-Zeitstempel, aus denen hier Wortzeiten
und SRT gebaut werden.

    pip install onnx-asr onnxruntime
"""

from __future__ import annotations

import os
import threading

import audio_utils
import srt_utils

_lock = threading.Lock()          # Transkription (onnxruntime-Session nicht parallel füttern)
_load_lock = threading.Lock()     # Modellgewichte laden
_model = None
_load_error: str | None = None
_import_checked = False
_import_ok = False

DEFAULT_MODEL = "nemo-parakeet-tdt-0.6b-v3"
DEFAULT_QUANT = "int8"


def available() -> bool:
    global _import_checked, _import_ok
    if not _import_checked:
        _import_checked = True
        try:
            import onnx_asr  # noqa: F401
            _import_ok = True
        except Exception as exc:  # noqa: BLE001
            _import_ok = False
            print(f"Parakeet nicht verfügbar ({exc}). Install: pip install onnx-asr onnxruntime")
    return _import_ok


def load_error() -> str | None:
    return _load_error


def _get_model(model_name: str, quant: str | None):
    global _model, _load_error
    if _model is not None:
        return _model
    with _load_lock:
        if _model is not None:
            return _model
        import onnx_asr
        _model = onnx_asr.load_model(
            model_name,
            quantization=None if quant in (None, "", "fp32", "none") else quant,
            providers=["CPUExecutionProvider"],
        )
        _load_error = None
        return _model


def warmup(model_name: str = DEFAULT_MODEL, quant: str = DEFAULT_QUANT) -> bool:
    """Modellgewichte jetzt laden, damit das erste Diktat nicht wartet.

    Gibt ``True`` zurück, wenn das Modell geladen werden konnte.
    """
    global _load_error
    try:
        _get_model(model_name, quant)
        return True
    except Exception as exc:  # noqa: BLE001 - Proxy darf daran nicht sterben
        _load_error = str(exc)
        print(f"Parakeet-Warmup fehlgeschlagen: {exc}", flush=True)
        return False


def _recognize(path: str, model_name: str, quant: str, with_timestamps: bool):
    global _load_error
    if not available():
        return None
    try:
        model = _get_model(model_name, quant)
    except Exception as exc:  # noqa: BLE001
        _load_error = str(exc)
        return None

    wav = None
    try:
        wav = audio_utils.to_wav16k(path)
        with _lock:  # onnxruntime-Session nicht parallel füttern
            if with_timestamps:
                return model.with_timestamps().recognize(wav)
            return model.recognize(wav)
    except Exception as exc:  # noqa: BLE001
        _load_error = str(exc)
        print(f"Parakeet-Transkription fehlgeschlagen: {exc}")
        return None
    finally:
        if wav and os.path.exists(wav):
            try:
                os.unlink(wav)
            except OSError:
                pass


def transcribe(path: str, model_name: str = DEFAULT_MODEL, quant: str = DEFAULT_QUANT) -> str | None:
    result = _recognize(path, model_name, quant, with_timestamps=False)
    text = getattr(result, "text", None)
    if text is None and isinstance(result, str):
        text = result
    text = (text or "").strip()
    return text or None


def tokens_to_words(tokens: list[str], timestamps: list[float]) -> list[dict]:
    """Token-Zeiten zu Wortzeiten zusammenfassen (Wort beginnt nach Leerzeichen)."""
    words: list[dict] = []
    current: dict | None = None

    for token, ts in zip(tokens, timestamps):
        if not token.strip():
            continue
        if token.startswith(" ") and current is not None:
            words.append(current)
            current = None
        if current is None:
            current = {"word": token.strip(), "start": float(ts), "end": float(ts)}
        else:
            current["word"] += token
            current["end"] = float(ts)

    if current is not None:
        words.append(current)

    for i, word in enumerate(words):
        next_start = words[i + 1]["start"] if i + 1 < len(words) else word["end"] + 0.4
        word["end"] = max(word["start"] + 0.05, min(next_start, word["end"] + 0.4))
    return words


def transcribe_srt(path: str, model_name: str = DEFAULT_MODEL, quant: str = DEFAULT_QUANT) -> str | None:
    result = _recognize(path, model_name, quant, with_timestamps=True)
    if result is None:
        return None
    tokens = getattr(result, "tokens", None)
    timestamps = getattr(result, "timestamps", None)
    if tokens and timestamps:
        return srt_utils.words_to_srt(tokens_to_words(list(tokens), list(timestamps)))
    text = (getattr(result, "text", "") or "").strip()
    if not text:
        return None
    return f"1\n00:00:00,000 --> 99:59:59,000\n{text}\n"
