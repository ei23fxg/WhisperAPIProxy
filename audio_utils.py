"""Kleine Audio-Helfer für die lokalen Fallback-Engines."""

from __future__ import annotations

import os
import subprocess
import tempfile


def to_wav16k(path: str, ffmpeg: str | None = None) -> str:
    """Beliebiges Audio → 16 kHz mono PCM-WAV (temporäre Datei, Aufrufer löscht)."""
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="asr-")
    os.close(fd)
    cmd = [
        ffmpeg or os.environ.get("ASR_FFMPEG", "ffmpeg"),
        "-hide_banner", "-loglevel", "error", "-y",
        "-i", path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
