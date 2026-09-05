"""
Pillow / numpy pixel helpers shared by overlays, captions, and the compositor.

Keep blending math here so brand lockups and the compose loop stay readable.
Nothing in this module knows about briefs or brands — it only paints pixels.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def add_drop_shadow(
    image: Image.Image,
    radius: int = 12,
    offset: tuple[int, int] = (4, 6),
    shadow_alpha: int = 140,
) -> Image.Image:
    """Drop shadow from the alpha channel so stickers lift off the talking head.

    A hard-edged PNG on a sky background looks pasted. The shadow uses the
    overlay's own alpha (not a rectangle) so irregular fruit bowls still read.

    Args:
        image: RGBA overlay.
        radius: Gaussian blur of the shadow matte.
        offset: Shadow shift in pixels (x, y). Positive y = downward.
        shadow_alpha: Peak shadow opacity (0–255).

    Returns:
        Larger RGBA image with padding for the blur halo.
    """
    offset_x, offset_y = offset
    padding = radius * 2 + max(abs(offset_x), abs(offset_y)) + 4
    width, height = image.size
    canvas = Image.new(
        "RGBA", (width + padding * 2, height + padding * 2), (0, 0, 0, 0)
    )
    alpha = image.split()[-1]
    shadow_mask = Image.new("L", canvas.size, 0)
    shadow_mask.paste(alpha, (padding + offset_x, padding + offset_y))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius))
    shadow_mask = shadow_mask.point(lambda pixel: int(pixel * shadow_alpha / 255))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.paste(image, (padding, padding), image)
    return canvas


def load_fitted_sticker(
    path: Path | str, max_width: int, max_height: int
) -> Image.Image:
    """Load a PNG, fit it in a max box, and add a sticker shadow.

    Args:
        path: Overlay file (already keyed if the source had a black background).
        max_width: Box width in pixels, including later shadow padding.
        max_height: Box height in pixels. Keep ≤ ~340 so stickers stay in the
            crown slot above her eyes and below the IG crop.

    Returns:
        RGBA sticker ready to composite.
    """
    image = Image.open(path).convert("RGBA")
    scale = min(max_width / image.width, max_height / image.height)
    new_width = max(1, int(image.width * scale))
    new_height = max(1, int(image.height * scale))
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return add_drop_shadow(image, radius=12, offset=(3, 6), shadow_alpha=140)


def shrink_overlay_to_max_width(image: Image.Image, max_width: int) -> Image.Image:
    """Shrink an overlay that would clip the side safe-zone.

    Generated brush labels can exceed 1080 minus gutters; we scale rather than
    clip so the teal stroke ends stay intact.

    Args:
        image: RGBA overlay.
        max_width: Inclusive maximum width in pixels.

    Returns:
        The original image if it already fits, otherwise a Lanczos-scaled copy.
    """
    if image.width <= max_width:
        return image
    scale = max_width / image.width
    return image.resize(
        (max_width, max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )


def cut_black_background(
    image: Image.Image, threshold: int = 28, feather: int = 1
) -> Image.Image:
    """Cut a near-black background and crop to the remaining alpha bbox.

    Phone screenshots and emoji packs often arrive on black. Higher
    ``threshold`` is more aggressive; keep a small ``feather`` so soft
    shadows on fruit bowls survive.

    Args:
        image: Source PNG (RGB or RGBA).
        threshold: Channel-max below this is treated as background.
        feather: Softness of the cutoff. Zero is a hard matte (use for
            already-crisp type).

    Returns:
        RGBA crop with a few pixels of padding around the opaque region.
    """
    rgba = image.convert("RGBA")
    pixels = np.array(rgba)
    rgb = pixels[:, :, :3].astype(np.float32)
    # Max channel = distance from black; using luminance would keep dark-red
    # chocolates which we want, but would also keep navy that should go.
    brightness = rgb.max(axis=2)
    if feather <= 0:
        alpha = np.where(brightness <= threshold, 0, 255).astype(np.uint8)
    else:
        low = max(0, threshold - feather * 8)
        high = threshold + feather * 8
        alpha = np.clip(
            (brightness - low) / max(1, high - low) * 255, 0, 255
        ).astype(np.uint8)
    existing_alpha = pixels[:, :, 3]
    pixels[:, :, 3] = np.minimum(existing_alpha, alpha)
    rows, columns = np.where(pixels[:, :, 3] > 16)
    if len(columns) == 0:
        return Image.fromarray(pixels)
    padding = 4
    left = max(0, int(columns.min()) - padding)
    right = min(pixels.shape[1], int(columns.max()) + padding + 1)
    top = max(0, int(rows.min()) - padding)
    bottom = min(pixels.shape[0], int(rows.max()) + padding + 1)
    return Image.fromarray(pixels[top:bottom, left:right])


def composite_image_onto_frame(
    destination_frame: np.ndarray,
    overlay: Image.Image,
    x: float,
    y: float,
    opacity: float,
    scale: float = 1.0,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> None:
    """Alpha-composite an RGBA overlay onto an RGB frame, in place.

    Scaling is centred on the overlay so a pop-in does not slide toward the
    top-left. Out-of-frame pixels are clipped; a fully off-screen overlay is
    a no-op.

    Args:
        destination_frame: ``height × width × 3`` uint8 RGB, mutated in place.
        overlay: RGBA source.
        x: Left of the unscaled overlay in frame pixels.
        y: Top of the unscaled overlay in frame pixels.
        opacity: 0–1 extra multiplier on the PNG alpha.
        scale: Uniform scale around the overlay centre (pop-in animation).
        frame_width: Optional clip width; defaults to the array width.
        frame_height: Optional clip height; defaults to the array height.
    """
    if opacity <= 0.01 or scale <= 0.02:
        return
    height, width = destination_frame.shape[:2]
    frame_width = width if frame_width is None else frame_width
    frame_height = height if frame_height is None else frame_height
    drawn = overlay
    if abs(scale - 1.0) > 0.01:
        new_width = max(1, int(drawn.width * scale))
        new_height = max(1, int(drawn.height * scale))
        drawn = drawn.resize((new_width, new_height), Image.Resampling.BILINEAR)
        # Keep the visual centre fixed while the stamp grows.
        x = x - (new_width - overlay.width) / 2
        y = y - (new_height - overlay.height) / 2
    overlay_pixels = np.array(drawn)
    overlay_height, overlay_width = overlay_pixels.shape[:2]
    origin_x, origin_y = int(round(x)), int(round(y))
    clip_left, clip_top = max(0, origin_x), max(0, origin_y)
    clip_right = min(frame_width, origin_x + overlay_width)
    clip_bottom = min(frame_height, origin_y + overlay_height)
    if clip_right <= clip_left or clip_bottom <= clip_top:
        return
    source_left = clip_left - origin_x
    source_top = clip_top - origin_y
    foreground = overlay_pixels[
        source_top : source_top + (clip_bottom - clip_top),
        source_left : source_left + (clip_right - clip_left),
    ]
    alpha = foreground[:, :, 3:4].astype(np.float32) * (opacity / 255.0)
    region = destination_frame[clip_top:clip_bottom, clip_left:clip_right].astype(
        np.float32
    )
    rgb = foreground[:, :, :3].astype(np.float32)
    destination_frame[clip_top:clip_bottom, clip_left:clip_right] = np.clip(
        rgb * alpha + region * (1.0 - alpha), 0, 255
    ).astype(np.uint8)
