"""Lokaler CPU-Fallback für den Whisper-API-Proxy: Cactus Whistle.

Whistle ist ein 16,9-MB-Modell (7 Sprachen inkl. Deutsch), das über
`cactus-needle` läuft. Es kommt zum Einsatz, wenn die lokale Whisper-WebUI
nicht erreichbar ist oder keine Transkription liefert — vor dem (kosten-
pflichtigen) OpenAI-Fallback.

Whistle liefert auf Wunsch **Wort-Zeitstempel** (`word_timestamps=True`);
daraus baut dieses Modul SRT.

Installation auf dem Proxy-Rechner:

    pip install "cactus-needle[mic]"

Das `[mic]`-Extra bringt `soxr` mit. Trotzdem normalisiert dieses Modul jedes
Audio vorher per ffmpeg auf 16 kHz mono WAV — damit funktionieren auch
Opus/MP3/48 kHz zuverlässig.
"""

from __future__ import annotations

import os
import threading

import audio_utils
import srt_utils

_lock = threading.Lock()          # Transkription (needle ist nicht threadsicher)
_load_lock = threading.Lock()     # Modellgewichte laden
_model = None
_load_error: str | None = None
_import_checked = False
_import_ok = False


def available() -> bool:
    """Ist `cactus-needle` mit Whistle-API installiert? (ohne das Modell zu laden)"""
    global _import_checked, _import_ok
    if not _import_checked:
        _import_checked = True
        try:
            import needle
            if not (hasattr(needle, "Whistle") or hasattr(needle, "transcribe")):
                raise RuntimeError(
                    "cactus-needle ist zu alt; bitte aktualisieren: "
                    "pip install -U 'cactus-needle[mic]'"
                )
            _import_ok = True
        except Exception as exc:  # ImportError oder kaputte Installation
            _import_ok = False
            print(f"Whistle nicht verfügbar ({exc}). Install: pip install 'cactus-needle[mic]'")
    return _import_ok


def load_error() -> str | None:
    return _load_error


def warmup() -> bool:
    """Modellgewichte jetzt laden, damit das erste Diktat nicht wartet.

    Gibt ``True`` zurück, wenn das Modell geladen werden konnte.
    """
    global _load_error
    try:
        _get_model()
        return True
    except Exception as exc:  # noqa: BLE001 - Proxy darf daran nicht sterben
        _load_error = str(exc)
        print(f"Whistle-Warmup fehlgeschlagen: {exc}", flush=True)
        return False


def _get_model():
    global _model, _load_error
    if _model is not None:
        return _model
    with _load_lock:
        if _model is not None:
            return _model
        import needle
        whistle_cls = getattr(needle, "Whistle", None)
        if whistle_cls is not None:
            # Whistle() lädt die .cact-Gewichte in den Speicher (needle >= 3).
            _model = whistle_cls()
        else:
            # Ältere Builds laden das Modell beim ersten transcribe().
            _model = needle
        _load_error = None
        return _model


def _run(path: str, language: str | None, with_words: bool):
    """Gemeinsamer Pfad für Text und SRT; gibt das Ergebnis-Dict zurück oder None."""
    global _load_error
    if not available():
        return None
    try:
        model = _get_model()
    except Exception as exc:  # noqa: BLE001
        _load_error = str(exc)
        return None

    wav = None
    try:
        wav = audio_utils.to_wav16k(path)
        kwargs = {}
        if language:
            kwargs["language"] = language
        if with_words:
            kwargs["word_timestamps"] = True
        with _lock:  # needle ist nicht threadsicher
            try:
                return model.transcribe(wav, **kwargs)
            except TypeError:
                # Ältere needle-Version ohne einzelne kwargs
                return model.transcribe(wav)
    except Exception as exc:  # noqa: BLE001
        _load_error = str(exc)
        print(f"Whistle-Transkription fehlgeschlagen: {exc}")
        return None
    finally:
        if wav and os.path.exists(wav):
            try:
                os.unlink(wav)
            except OSError:
                pass


def transcribe(path: str, language: str | None = None) -> str | None:
    """Transkribiert `path`; gibt None zurück, wenn Whistle nicht kann."""
    result = _run(path, language, with_words=False)
    if not isinstance(result, dict):
        return None
    text = result.get("text", "") or ""
    return text.strip() or None


def transcribe_srt(path: str, language: str | None = None) -> str | None:
    """Wie transcribe(), aber als SRT mit Wort-Zeitstempeln."""
    result = _run(path, language, with_words=True)
    if not isinstance(result, dict):
        return None
    words = result.get("words") or []
    if words:
        return srt_utils.words_to_srt(words)
    # Fallback: keine Wortzeiten geliefert → ein Block über die ganze Aufnahme
    text = (result.get("text") or "").strip()
    if not text:
        return None
    return f"1\n00:00:00,000 --> 99:59:59,000\n{text}\n"
