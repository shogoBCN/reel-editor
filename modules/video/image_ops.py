"""
Pillow / numpy primitives shared by overlays, captions, and the frame compositor.

Keep pixel math here so brand lockups and the compose loop stay readable.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def add_shadow(
    img: Image.Image,
    radius: int = 12,
    offset: tuple[int, int] = (4, 6),
    shadow_alpha: int = 140,
) -> Image.Image:
    """Drop shadow from the alpha channel so stickers lift off the talking head."""
    ox, oy = offset
    pad = radius * 2 + max(abs(ox), abs(oy)) + 4
    width, height = img.size
    canvas = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    alpha = img.split()[-1]
    shadow_mask = Image.new("L", canvas.size, 0)
    shadow_mask.paste(alpha, (pad + ox, pad + oy))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius))
    shadow_mask = shadow_mask.point(lambda p: int(p * shadow_alpha / 255))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.paste(img, (pad, pad), img)
    return canvas


def prepare_overlay(path, max_w: int, max_h: int) -> Image.Image:
    """Load a PNG, fit it in a max box, and add a sticker shadow."""
    image = Image.open(path).convert("RGBA")
    scale = min(max_w / image.width, max_h / image.height)
    new_w = max(1, int(image.width * scale))
    new_h = max(1, int(image.height * scale))
    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return add_shadow(image, radius=12, offset=(3, 6), shadow_alpha=140)


def clamp_overlay_width(img: Image.Image, max_w: int) -> Image.Image:
    """Shrink an overlay that would clip the side safe-zone."""
    if img.width <= max_w:
        return img
    scale = max_w / img.width
    return img.resize(
        (max_w, max(1, int(img.height * scale))),
        Image.Resampling.LANCZOS,
    )


def key_black(img: Image.Image, thresh: int = 28, feather: int = 1) -> Image.Image:
    """
    Cut a near-black background and crop to the remaining alpha bbox.

    Phone screenshots and emoji packs often arrive on black. Higher ``thresh``
    is more aggressive; keep a small ``feather`` so soft shadows survive.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.float32)
    mag = rgb.max(axis=2)
    if feather <= 0:
        alpha = np.where(mag <= thresh, 0, 255).astype(np.uint8)
    else:
        lo = max(0, thresh - feather * 8)
        hi = thresh + feather * 8
        alpha = np.clip((mag - lo) / max(1, hi - lo) * 255, 0, 255).astype(np.uint8)
    existing = arr[:, :, 3]
    arr[:, :, 3] = np.minimum(existing, alpha)
    ys, xs = np.where(arr[:, :, 3] > 16)
    if len(xs) == 0:
        return Image.fromarray(arr)
    pad = 4
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(arr.shape[1], int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(arr.shape[0], int(ys.max()) + pad + 1)
    return Image.fromarray(arr[y0:y1, x0:x1])


def blit(
    dst: np.ndarray,
    overlay: Image.Image,
    x: float,
    y: float,
    opacity: float,
    scale: float = 1.0,
    frame_w: int | None = None,
    frame_h: int | None = None,
) -> None:
    """Alpha-composite an RGBA overlay onto an RGB frame, in place."""
    if opacity <= 0.01 or scale <= 0.02:
        return
    height, width = dst.shape[:2]
    frame_w = width if frame_w is None else frame_w
    frame_h = height if frame_h is None else frame_h
    image = overlay
    if abs(scale - 1.0) > 0.01:
        new_w = max(1, int(image.width * scale))
        new_h = max(1, int(image.height * scale))
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        x = x - (new_w - overlay.width) / 2
        y = y - (new_h - overlay.height) / 2
    arr = np.array(image)
    oh, ow = arr.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(frame_w, x0 + ow), min(frame_h, y0 + oh)
    if xe <= xs or ye <= ys:
        return
    fx0, fy0 = xs - x0, ys - y0
    fg = arr[fy0 : fy0 + (ye - ys), fx0 : fx0 + (xe - xs)]
    alpha = fg[:, :, 3:4].astype(np.float32) * (opacity / 255.0)
    roi = dst[ys:ye, xs:xe].astype(np.float32)
    rgb = fg[:, :, :3].astype(np.float32)
    dst[ys:ye, xs:xe] = np.clip(rgb * alpha + roi * (1.0 - alpha), 0, 255).astype(
        np.uint8
    )
