"""Gemini 3.5 Transcribe → compact karaoke JSON (``w`` / ``s`` / ``e``).

Word timestamps and custom vocabulary cannot be combined on this model, so
karaoke runs verbatim with timings only. Brief ``asr_fix`` still applies at
compose time for any leftover homophones.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.modules_initialiser import get_module


def duration_to_seconds(value: Any) -> float:
    """Parse a Gemini offset (``1.600s``, ``5s``, milliseconds, or float).

    Args:
        value: SDK duration string or number.

    Returns:
        Time in seconds. ``None`` becomes ``0.0``.
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if text.endswith("ms"):
        return float(text[:-2]) / 1000.0
    if text.endswith("s"):
        return float(text[:-1])
    return float(text)


def _pack_word(token: str, start_seconds: float, end_seconds: float) -> dict[str, Any]:
    """One karaoke word in the on-disk compact shape.

    Args:
        token: Recognized text, punctuation attached as Gemini returns it.
        start_seconds: Word start.
        end_seconds: Word end. Swapped if the API inverts the pair.

    Returns:
        ``{"w", "s", "e"}`` with times rounded to hundredths.
    """
    if end_seconds < start_seconds:
        start_seconds, end_seconds = end_seconds, start_seconds
    return {
        "w": token.strip(),
        "s": round(start_seconds, 2),
        "e": round(end_seconds, 2),
    }


def _pack_segment(words: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a segment covering a run of packed words.

    Args:
        words: Compact word dicts.

    Returns:
        Segment with ``start``, ``end``, ``text``, ``words``.
    """
    return {
        "start": words[0]["s"],
        "end": words[-1]["e"],
        "text": " ".join(item["w"] for item in words),
        "words": words,
    }


def words_to_transcript_document(
    full_text: str, packed_words: list[dict[str, Any]]
) -> dict[str, Any]:
    """Group words into sentence segments (same shape captions already read).

    Args:
        full_text: Model transcript string.
        packed_words: Compact ``w`` / ``s`` / ``e`` list.

    Returns:
        ``{"text", "segments"}`` ready to dump as ``transcript.json``.
    """
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in packed_words:
        if not word["w"]:
            continue
        current.append(word)
        if word["w"].endswith((".", "?", "!", "…")):
            segments.append(_pack_segment(current))
            current = []
    if current:
        segments.append(_pack_segment(current))
    return {"text": full_text.strip(), "segments": segments}


def _audio_transcription_from_response(response: Any) -> tuple[str, list[Any]]:
    """Pull text + word list from a ``generate_content`` response.

    Args:
        response: ``google.genai`` ``GenerateContentResponse``.

    Returns:
        Transcript text and raw word objects.

    Raises:
        RuntimeError: The response has no audio transcription payload.
    """
    parts = list(getattr(response, "parts", None) or [])
    if not parts:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = list(getattr(content, "parts", None) or [])

    text = ""
    words: list[Any] = []
    for part in parts:
        transcription = getattr(part, "audio_transcription", None)
        if transcription is not None:
            text = str(getattr(transcription, "text", None) or text)
            words = list(getattr(transcription, "words", None) or [])
        if getattr(part, "text", None) and not text:
            text = str(part.text)

    if not words and not text:
        raise RuntimeError(
            "Gemini transcribe returned no audio_transcription words or text."
        )
    return text, words


def transcribe_wav(
    wav_path: Path,
    language_codes: list[str] | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Call Gemini 3.5 Transcribe with word timestamps.

    Custom vocabulary is omitted on purpose: this model rejects vocab +
    timestamps together, and karaoke needs the timestamps.

    Args:
        wav_path: 16 kHz mono WAV (ffmpeg extract).
        language_codes: BCP-47 hints (e.g. ``["es-419"]``). Empty = autodetect.
        model_name: Override ``config_store.gemini_transcribe_model``.

    Returns:
        Compact transcript document for ``source/transcript.json``.

    Raises:
        FileNotFoundError: WAV or auth config missing.
        RuntimeError: API returned no words/text.
    """
    from google.genai import types

    config_store = get_module("config_store")
    client = get_module("gemini_client")
    model = model_name or config_store.gemini_transcribe_model
    audio_bytes = wav_path.read_bytes()
    transcription_config = types.AudioTranscriptionConfig(
        language_codes=language_codes or None,
        word_timestamp=True,
    )
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
        ],
        config=types.GenerateContentConfig(
            audio_transcription_config=transcription_config,
        ),
    )
    text, raw_words = _audio_transcription_from_response(response)
    packed: list[dict[str, Any]] = []
    for item in raw_words:
        token = str(getattr(item, "word", None) or getattr(item, "text", "") or "")
        packed.append(
            _pack_word(
                token,
                duration_to_seconds(getattr(item, "start_offset", None)),
                duration_to_seconds(getattr(item, "end_offset", None)),
            )
        )
    if not packed and text:
        # Timestamp-less fallback so compose still has a full-line caption.
        packed = [_pack_word(text, 0.0, 0.0)]
    return words_to_transcript_document(text, packed)
