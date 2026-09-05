"""
Karaoke captions from a word-timed Whisper transcript.

Groups stay short (≤4 words / 26 chars) so lines never overflow the 9:16
frame. Words share one baseline — per-word top offsets made accents like
``él`` / ``azúcar`` bounce. Speech-recognition corrections are brief-driven
(Spanish homophones: lacena→alacena).

On-disk ``transcript.json`` still uses compact keys ``w`` / ``s`` / ``e``
(Whisper export). In memory we use ``text`` / ``start_seconds`` / ``end_seconds``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from config.config_store import ConfigStore
from modules.video.brand_style import BrandPack, load_font
from modules.video.image_ops import (
    add_drop_shadow,
    composite_image_onto_frame,
    shrink_overlay_to_max_width,
)


def apply_speech_recognition_correction(
    token: str, corrections: dict[str, str]
) -> str:
    """Replace a known Whisper miss while keeping trailing punctuation.

    Args:
        token: One transcript word, possibly with comma/period attached.
        corrections: Brief map of wrong→right (``lacena`` → ``alacena``).

    Returns:
        Corrected token, or the original if it is not in the map.
    """
    stripped = token.strip()
    key = stripped.strip(".,;:¡!¿?")
    if key in corrections:
        suffix = stripped[len(key) :]
        return corrections[key] + suffix
    # Case-insensitive fallback so "Lacena" still maps if only "lacena" is listed.
    lower_map = {wrong.lower(): right for wrong, right in corrections.items()}
    if key.lower() in lower_map:
        replacement = lower_map[key.lower()]
        if key[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        suffix = stripped[len(key) :]
        return replacement + suffix
    return stripped


def _flush_caption_group(
    current: list[dict[str, Any]], groups: list[list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Move the in-progress word list onto ``groups`` and start a new line.

    Args:
        current: Words accumulated for the line being built.
        groups: Completed lines.

    Returns:
        A new empty current list (caller must rebind).
    """
    if current:
        groups.append(current)
    return []


def load_caption_groups(
    transcript_path: Path,
    trim_start_seconds: float,
    speech_recognition_corrections: dict[str, str],
    max_words: int = 4,
    max_characters: int = 26,
) -> list[dict[str, Any]]:
    """Group word timestamps into karaoke lines, dropping pre-trim audio.

    Four words / 26 characters is the largest line that still fits at caption
    size 56 with stroke, after the 92px side inset. Longer groups overflowed
    ("Entonces concertamos una cita e").

    Args:
        transcript_path: Whisper JSON (``segments[].words[].w/s/e``).
        trim_start_seconds: Discard groups that end entirely in the cut head.
        speech_recognition_corrections: Homophone map from the brief.
        max_words: Hard cap per karaoke line.
        max_characters: Hard cap including spaces.

    Returns:
        Groups with ``start_seconds``, ``end_seconds``, and ``words``.
    """
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    words: list[dict[str, Any]] = []
    for segment in data.get("segments") or []:
        for word in segment.get("words") or []:
            token = apply_speech_recognition_correction(
                str(word.get("w") or ""), speech_recognition_corrections
            )
            if not token:
                continue
            words.append(
                {
                    "text": token,
                    "start_seconds": float(word["s"]),
                    "end_seconds": float(word["e"]),
                }
            )

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for word in words:
        token = word["text"]
        trial = current + [word]
        text = " ".join(item["text"] for item in trial)
        ends_sentence = token.endswith((".", "?", "!", "…"))
        # Commas mid-breath are not breaks unless the line is already long.
        comma_break = token.endswith(",") and len(current) >= 3
        too_long = len(trial) > max_words or len(text) > max_characters
        if current and (too_long or comma_break):
            current = _flush_caption_group(current, groups)
            current = [word]
        else:
            current.append(word)
        if ends_sentence:
            current = _flush_caption_group(current, groups)
    current = _flush_caption_group(current, groups)

    timed_groups: list[dict[str, Any]] = []
    for group in groups:
        if group[-1]["end_seconds"] <= trim_start_seconds + 0.15:
            continue
        timed_groups.append(
            {
                "start_seconds": max(trim_start_seconds, group[0]["start_seconds"]),
                "end_seconds": group[-1]["end_seconds"] + 0.08,
                "words": group,
            }
        )
    # Hold each line until the next one starts so we never flash empty frames.
    for index, group in enumerate(timed_groups[:-1]):
        group["end_seconds"] = max(
            group["end_seconds"], timed_groups[index + 1]["start_seconds"] - 0.04
        )
    return timed_groups


def active_word_index(group: dict[str, Any], source_time_seconds: float) -> int:
    """Index of the karaoke word whose start has been reached.

    Args:
        group: Caption group with ``words``.
        source_time_seconds: Source clock.

    Returns:
        Index into ``group["words"]`` (0 if none have started yet).
    """
    active = 0
    for index, word in enumerate(group["words"]):
        # Tiny lead so the gold highlight is on the word as it is heard.
        if word["start_seconds"] - 0.04 <= source_time_seconds:
            active = index
    return active


def render_caption(
    group: dict[str, Any],
    source_time_seconds: float,
    brand: BrandPack,
) -> Image.Image:
    """Rasterise one karaoke line with the active word in gold.

    Args:
        group: Words sharing one line.
        source_time_seconds: Chooses which word is gold.
        brand: Font, gold, white, black.

    Returns:
        Shadowed RGBA caption strip.
    """
    font = load_font(brand, brand.font_black, brand.caption_size)
    dummy = Image.new("RGB", (8, 8))
    measure = ImageDraw.Draw(dummy)
    words = group["words"]
    active = active_word_index(group, source_time_seconds)
    stroke = 6
    gap = 16
    boxes = [
        measure.textbbox((0, 0), word["text"], font=font, stroke_width=stroke)
        for word in words
    ]
    # Shared layout origin so every word sits on the same baseline.
    # (Per-word top offsets made accents like "él" / "azúcar" bounce.)
    draw_y = 6 - min(box[1] for box in boxes)
    height = draw_y + max(box[3] for box in boxes) + 6
    total_width = sum(box[2] - box[0] for box in boxes) + gap * (len(boxes) - 1)
    image = Image.new("RGBA", (int(total_width) + 8, int(height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cursor_x = 4
    for index, word in enumerate(words):
        box = boxes[index]
        fill = brand.gold if index == active else brand.white
        draw.text(
            (cursor_x - box[0], draw_y),
            word["text"],
            font=font,
            fill=fill,
            stroke_width=stroke,
            stroke_fill=brand.black,
        )
        cursor_x += (box[2] - box[0]) + gap
    return add_drop_shadow(image, radius=8, offset=(0, 4), shadow_alpha=90)


_CAPTION_CACHE: dict[tuple, Image.Image] = {}


def get_cached_caption_image(
    group: dict[str, Any], source_time_seconds: float, brand: BrandPack
) -> Image.Image:
    """Cache by (group identity, active word) — karaoke colour is the only change.

    Args:
        group: Caption group (identity used as cache key).
        source_time_seconds: Current source clock.
        brand: Pack id is part of the key so two brands cannot collide.

    Returns:
        Raster for the current karaoke colouring.
    """
    active = active_word_index(group, source_time_seconds)
    cache_key = (id(group), active, brand.brand_id)
    if cache_key not in _CAPTION_CACHE:
        _CAPTION_CACHE[cache_key] = render_caption(group, source_time_seconds, brand)
    return _CAPTION_CACHE[cache_key]


def draw_captions(
    destination_frame,
    groups: list[dict[str, Any]],
    source_time_seconds: float,
    brand: BrandPack,
    config_store: ConfigStore,
) -> None:
    """Composite the active caption group; first match wins.

    Args:
        destination_frame: RGB frame mutated in place.
        groups: Timed karaoke lines.
        source_time_seconds: Source clock.
        brand: Caption Y and colours.
        config_store: Insets and floor so lines never clip Reels chrome.
    """
    for group in groups:
        if group["start_seconds"] <= source_time_seconds <= group["end_seconds"]:
            image = get_cached_caption_image(group, source_time_seconds, brand)
            image = shrink_overlay_to_max_width(
                image, config_store.caption_max_width_pixels
            )
            x = (config_store.frame_width - image.width) // 2
            x = max(
                config_store.caption_inset_pixels,
                min(
                    config_store.frame_width
                    - config_store.caption_inset_pixels
                    - image.width,
                    x,
                ),
            )
            y = min(
                brand.caption_baseline_y,
                config_store.caption_floor_pixels - image.height - 8,
            )
            composite_image_onto_frame(destination_frame, image, x, y, 1.0, 1.0)
            return
