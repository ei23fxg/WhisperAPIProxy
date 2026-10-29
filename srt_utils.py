"""SRT-Erzeugung aus Wort-Zeitstempeln (gemeinsam für Whistle und Parakeet)."""

from __future__ import annotations


def fmt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def words_to_srt(words: list[dict], max_chars: int = 42, max_secs: float = 3.0) -> str:
    """Wort-Zeitstempel zu SRT gruppieren (Satzende, Länge oder Dauer als Trenner)."""
    cues: list[list[dict]] = []
    current: list[dict] = []

    def flush():
        nonlocal current
        if current:
            cues.append(current)
            current = []

    for word in words:
        if current:
            candidate = " ".join([w.get("word", "") for w in current] + [word.get("word", "")])
            cand_duration = float(word.get("end", 0)) - float(current[0].get("start", 0))
            if len(candidate) > max_chars or cand_duration > max_secs:
                flush()
        current.append(word)
        ends_sentence = word.get("word", "").rstrip().endswith((".", "!", "?"))
        text = " ".join(w.get("word", "") for w in current)
        if ends_sentence or len(text) >= max_chars:
            flush()
    flush()

    blocks = []
    for i, cue in enumerate(cues, 1):
        start = fmt_timestamp(float(cue[0].get("start", 0)))
        end = fmt_timestamp(float(cue[-1].get("end", 0)))
        text = " ".join(w.get("word", "") for w in cue).strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)
