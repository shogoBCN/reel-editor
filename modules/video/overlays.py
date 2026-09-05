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
from modules.video.image_ops import blit, prepare_overlay
from modules.video.timing import ease_out_back, fade_opacity


@dataclass
class OverlayLayer:
    """One composited layer with source-clock in/out points."""

    overlay_id: str
    image: Image.Image
    start: float
    end: float
    x: int
    y: int
    motion: str  # "sticker" pops harder than "text"


def side_x(
    overlay: Image.Image,
    side: str,
    frame_w: int,
    inset: int,
) -> int:
    if side == "left":
        return inset
    return frame_w - inset - overlay.width


def resolve_placement(
    overlay: Image.Image,
    placement: str,
    brand: BrandPack,
    config_store: ConfigStore,
) -> tuple[int, int]:
    """Map brief placement names to pixel coordinates."""
    frame_w = config_store.frame_width
    top_safe = config_store.top_safe_px
    sticker_y = top_safe + brand.sticker_y_from_top_safe
    if placement in ("hook_center", "gancho", "center", "centro"):
        return (frame_w - overlay.width) // 2, top_safe + 10
    if placement in ("left", "izquierda"):
        return side_x(overlay, "left", frame_w, brand.sticker_inset), sticker_y
    ## Default: right of head, same height as the fruit-bowl slot.
    return side_x(overlay, "right", frame_w, brand.sticker_inset), sticker_y


def _motion_for_kind(kind: str) -> str:
    if kind in ("sticker", "sticker_png"):
        return "sticker"
    return "text"


def build_overlay_layers(
    overlays: list[dict[str, Any]],
    project_dir: Path,
    brand: BrandPack,
    config_store: ConfigStore,
) -> list[OverlayLayer]:
    """Rasterise brief overlay rows into positioned PIL images."""
    layers: list[OverlayLayer] = []
    for row in overlays:
        kind = str(row.get("kind") or "sticker")
        overlay_id = str(row.get("id") or kind)
        start = float(row["start"])
        end = float(row["end"])
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
            rel = row.get("file")
            if not rel:
                raise ValueError(f"Overlay {overlay_id}: sticker needs file")
            path = Path(rel)
            if not path.is_absolute():
                path = project_dir / path
            if not path.is_file():
                raise FileNotFoundError(f"Overlay {overlay_id}: missing file {path}")
            max_w = int(row.get("max_w") or 400)
            max_h = int(row.get("max_h") or 340)
            image = prepare_overlay(path, max_w, max_h)
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
                start=start,
                end=end,
                x=x,
                y=y,
                motion=_motion_for_kind(kind),
            )
        )
    return layers


def composite_overlay(dst: np.ndarray, layer: OverlayLayer, source_t: float) -> None:
    """Draw one layer if ``source_t`` is inside its window."""
    if source_t < layer.start or source_t > layer.end:
        return
    local = source_t - layer.start
    duration = layer.end - layer.start
    opacity = fade_opacity(local, duration)
    if opacity <= 0:
        return
    pop_t = 0.38 if layer.motion == "sticker" else 0.28
    scale = ease_out_back(local / pop_t) if local < pop_t else 1.0
    bob = math.sin(local * 2.4) * (5.0 if layer.motion == "sticker" else 2.0)
    blit(dst, layer.image, layer.x, layer.y + bob, opacity, scale)
