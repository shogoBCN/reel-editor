"""
Karaoke captions from a word-timed Whisper transcript.

Groups stay short (≤4 words / 26 chars) so lines never overflow the 9:16
frame. Words share one baseline — per-word top offsets made accents like
``él`` / ``azúcar`` bounce. ASR fixes are brief-driven (Spanish homophones).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from config.config_store import ConfigStore
from modules.video.brand_style import BrandPack, load_font
from modules.video.image_ops import add_shadow, blit, clamp_overlay_width


def apply_asr_fix(token: str, asr_fix: dict[str, str]) -> str:
    """Replace a known Whisper miss while keeping trailing punctuation."""
    stripped = token.strip()
    key = stripped.strip(".,;:¡!¿?")
    if key in asr_fix:
        suffix = stripped[len(key) :]
        return asr_fix[key] + suffix
    ## Case-insensitive fallback so "Lacena" still maps if only "lacena" is listed.
    lower_map = {k.lower(): v for k, v in asr_fix.items()}
    if key.lower() in lower_map:
        replacement = lower_map[key.lower()]
        if key[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        suffix = stripped[len(key) :]
        return replacement + suffix
    return stripped


def load_caption_groups(
    transcript_path: Path,
    trim_start: float,
    asr_fix: dict[str, str],
    max_words: int = 4,
    max_chars: int = 26,
) -> list[dict[str, Any]]:
    """Group word timestamps into karaoke lines, dropping pre-trim audio."""
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    words: list[dict[str, Any]] = []
    for segment in data.get("segments") or []:
        for word in segment.get("words") or []:
            token = apply_asr_fix(str(word.get("w") or ""), asr_fix)
            if not token:
                continue
            words.append(
                {
                    "w": token,
                    "s": float(word["s"]),
                    "e": float(word["e"]),
                }
            )

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if current:
            groups.append(current)
            current = []

    for word in words:
        token = word["w"]
        trial = current + [word]
        text = " ".join(item["w"] for item in trial)
        punct_end = token.endswith((".", "?", "!", "…"))
        comma_break = token.endswith(",") and len(current) >= 3
        too_long = len(trial) > max_words or len(text) > max_chars
        if current and (too_long or comma_break):
            flush()
            current = [word]
        else:
            current.append(word)
        if punct_end:
            flush()
    flush()

    out: list[dict[str, Any]] = []
    for group in groups:
        if group[-1]["e"] <= trim_start + 0.15:
            continue
        out.append(
            {
                "s": max(trim_start, group[0]["s"]),
                "e": group[-1]["e"] + 0.08,
                "words": group,
            }
        )
    for i, group in enumerate(out[:-1]):
        group["e"] = max(group["e"], out[i + 1]["s"] - 0.04)
    return out


def render_caption(
    group: dict[str, Any],
    source_t: float,
    brand: BrandPack,
) -> Image.Image:
    font = load_font(brand, brand.font_black, brand.caption_size)
    dummy = Image.new("RGB", (8, 8))
    draw0 = ImageDraw.Draw(dummy)
    words = group["words"]
    active = 0
    for i, word in enumerate(words):
        if word["s"] - 0.04 <= source_t:
            active = i
    stroke = 6
    gap = 16
    boxes = [
        draw0.textbbox((0, 0), word["w"], font=font, stroke_width=stroke)
        for word in words
    ]
    ## Shared layout origin so every word sits on the same baseline.
    y_draw = 6 - min(box[1] for box in boxes)
    height = y_draw + max(box[3] for box in boxes) + 6
    total_w = sum(box[2] - box[0] for box in boxes) + gap * (len(boxes) - 1)
    img = Image.new("RGBA", (int(total_w) + 8, int(height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = 4
    for i, word in enumerate(words):
        bbox = boxes[i]
        fill = brand.gold if i == active else brand.white
        draw.text(
            (x - bbox[0], y_draw),
            word["w"],
            font=font,
            fill=fill,
            stroke_width=stroke,
            stroke_fill=brand.black,
        )
        x += (bbox[2] - bbox[0]) + gap
    return add_shadow(img, radius=8, offset=(0, 4), shadow_alpha=90)


_CAPTION_CACHE: dict[tuple, Image.Image] = {}


def caption_image(
    group: dict[str, Any], source_t: float, brand: BrandPack
) -> Image.Image:
    """Cache by (group identity, active word) — karaoke colour is the only change."""
    active = 0
    for i, word in enumerate(group["words"]):
        if word["s"] - 0.04 <= source_t:
            active = i
    key = (id(group), active, brand.brand_id)
    if key not in _CAPTION_CACHE:
        _CAPTION_CACHE[key] = render_caption(group, source_t, brand)
    return _CAPTION_CACHE[key]


def draw_captions(
    dst,
    groups: list[dict[str, Any]],
    source_t: float,
    brand: BrandPack,
    config_store: ConfigStore,
) -> None:
    """Composite the active caption group; first match wins."""
    for group in groups:
        if group["s"] <= source_t <= group["e"]:
            image = caption_image(group, source_t, brand)
            image = clamp_overlay_width(image, config_store.caption_max_width_px)
            x = (config_store.frame_width - image.width) // 2
            x = max(
                config_store.caption_inset_px,
                min(
                    config_store.frame_width - config_store.caption_inset_px - image.width,
                    x,
                ),
            )
            y = min(
                brand.caption_y,
                config_store.caption_floor_px - image.height - 8,
            )
            blit(dst, image, x, y, 1.0, 1.0)
            return
