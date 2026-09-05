"""
Place and schedule overlay layers from a loaded brief.

Sticker Y is the original dual fruit-bowl slot (top-safe + a few pixels), not
centred on the head — putting art on her hat reads as a costume. Generated
brush labels sit in the sky (hook), below the IG crop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from config.config_store import ConfigStore
from modules.video.brand_style import (
    BrandPack,
    clamp_to_side_safe,
    make_brush_label,
    make_enfoque_lockup,
)
from modules.video.image_ops import composite_image_onto_frame, load_fitted_sticker
from modules.video.timing import compute_edge_fade_opacity, compute_pop_in_scale


@dataclass
class OverlayLayer:
    """One composited layer with source-clock in/out points."""

    overlay_id: str
    image: Image.Image
    start_seconds: float
    end_seconds: float
    x: int
    y: int
    # "sticker" pops harder and bobs more than generated "text" banners.
    motion: str


def left_or_right_x(
    overlay: Image.Image,
    side: str,
    frame_width: int,
    inset: int,
) -> int:
    """X origin for a side-mounted sticker.

    Args:
        overlay: Already-sized RGBA image.
        side: ``left`` or anything else (treated as right).
        frame_width: Canvas width.
        inset: Distance from the vertical edge. Brand ``sticker_inset`` is
            tighter than Meta's 6% so fruit bowls sit next to her cheek, not
            in the far gutter.

    Returns:
        Integer X of the overlay's left edge.
    """
    if side == "left":
        return inset
    return frame_width - inset - overlay.width


def resolve_placement(
    overlay: Image.Image,
    placement: str,
    brand: BrandPack,
    config_store: ConfigStore,
) -> tuple[int, int]:
    """Map brief placement names to pixel coordinates.

    Args:
        overlay: Rasterised layer (size needed for centering).
        placement: ``right`` / ``left`` / ``hook_center`` (Spanish aliases
            accepted: ``derecha``, ``izquierda``, ``gancho``).
        brand: Sticker inset and Y offset.
        config_store: Frame size and top-safe band.

    Returns:
        ``(x, y)`` of the overlay's top-left, before pop-in recentring.
    """
    frame_width = config_store.frame_width
    top_safe = config_store.top_safe_pixels
    sticker_y = top_safe + brand.sticker_y_from_top_safe
    if placement in ("hook_center", "gancho", "center", "centro"):
        # +10px so the brush sits in the sky, not under the IG top crop.
        return (frame_width - overlay.width) // 2, top_safe + 10
    if placement in ("left", "izquierda"):
        return left_or_right_x(overlay, "left", frame_width, brand.sticker_inset), sticker_y
    # Default: right of head, same height as the fruit-bowl slot.
    return left_or_right_x(overlay, "right", frame_width, brand.sticker_inset), sticker_y


def motion_style_for_kind(kind: str) -> str:
    """Choose pop/bob intensity from the brief kind.

    Args:
        kind: ``sticker``, ``brush_label``, or ``enfoque_lockup``.

    Returns:
        ``sticker`` (punchier) or ``text`` (gentler, for generated banners).
    """
    if kind in ("sticker", "sticker_png"):
        return "sticker"
    return "text"


def build_overlay_layers(
    overlays: list[dict[str, Any]],
    project_dir: Path,
    brand: BrandPack,
    config_store: ConfigStore,
) -> list[OverlayLayer]:
    """Rasterise brief overlay rows into positioned PIL images.

    Args:
        overlays: Normalised brief rows (``kind``, ``start``, ``end``, …).
        project_dir: Root for relative ``file:`` paths.
        brand: Fonts and generated lockups.
        config_store: Canvas for side-gutter clamping.

    Returns:
        Layers in brief order (later rows draw on top).

    Raises:
        ValueError: Unknown kind, or a sticker/label missing its payload.
        FileNotFoundError: Sticker PNG is not on disk.
    """
    layers: list[OverlayLayer] = []
    for row in overlays:
        kind = str(row.get("kind") or "sticker")
        overlay_id = str(row.get("id") or kind)
        start_seconds = float(row["start"])
        end_seconds = float(row["end"])
        placement = str(row.get("placement") or "right")
        if kind in ("brush_label", "etiqueta"):
            text = str(row.get("text") or "").strip()
            if not text:
                raise ValueError(f"Overlay {overlay_id}: brush_label needs text")
            font_size = int(row.get("font_size") or 66)
            image = clamp_to_side_safe(
                make_brush_label(brand, text, font_size), config_store
            )
        elif kind in ("enfoque_lockup", "enfoque"):
            image = clamp_to_side_safe(make_enfoque_lockup(brand), config_store)
        elif kind in ("sticker", "sticker_png"):
            relative = row.get("file")
            if not relative:
                raise ValueError(f"Overlay {overlay_id}: sticker needs file")
            path = Path(relative)
            if not path.is_absolute():
                path = project_dir / path
            if not path.is_file():
                raise FileNotFoundError(f"Overlay {overlay_id}: missing file {path}")
            max_width = int(row.get("max_w") or 400)
            max_height = int(row.get("max_h") or 340)
            image = load_fitted_sticker(path, max_width, max_height)
        else:
            raise ValueError(
                f"Overlay {overlay_id}: unknown kind {kind!r}. "
                "Use sticker, brush_label, or enfoque_lockup."
            )
        x, y = resolve_placement(image, placement, brand, config_store)
        layers.append(
            OverlayLayer(
                overlay_id=overlay_id,
                image=image,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                x=x,
                y=y,
                motion=motion_style_for_kind(kind),
            )
        )
    return layers


def draw_scheduled_overlay(
    destination_frame: np.ndarray, layer: OverlayLayer, source_time_seconds: float
) -> None:
    """Draw one layer if the source clock is inside its window.

    Args:
        destination_frame: RGB frame mutated in place.
        layer: Raster + schedule.
        source_time_seconds: Clock of the original recording (not the trim).
    """
    if source_time_seconds < layer.start_seconds or source_time_seconds > layer.end_seconds:
        return
    local_time = source_time_seconds - layer.start_seconds
    duration = layer.end_seconds - layer.start_seconds
    opacity = compute_edge_fade_opacity(local_time, duration)
    if opacity <= 0:
        return
    # Stickers get a longer pop so they feel like stamps; type is quicker.
    pop_duration = 0.38 if layer.motion == "sticker" else 0.28
    scale = (
        compute_pop_in_scale(local_time / pop_duration)
        if local_time < pop_duration
        else 1.0
    )
    # Slow sine so the sticker breathes without looking drunk.
    bob = math.sin(local_time * 2.4) * (5.0 if layer.motion == "sticker" else 2.0)
    composite_image_onto_frame(
        destination_frame, layer.image, layer.x, layer.y + bob, opacity, scale
    )
