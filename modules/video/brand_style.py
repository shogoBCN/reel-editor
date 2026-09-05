"""
Brand pack loader and generated lockups (teal brush labels, enfoque banner, endcard).

Per-client look lives in ``brands/<id>/brand.yaml`` plus that folder's ``assets/``.
The compose pipeline never hardcodes Dra. Angélica colours — swap the pack to
reuse the same renderer for another talking-head brand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from config.config_store import ConfigStore
from modules.brief.sticker_size import DEFAULT_STICKER_SIZE_BOXES
from modules.video.image_ops import add_drop_shadow, shrink_overlay_to_max_width


@dataclass
class BrandPack:
    """Resolved brand assets and visual constants for one client."""

    brand_id: str
    root: Path
    teal: tuple[int, int, int]
    gold: tuple[int, int, int]
    white: tuple[int, int, int]
    black: tuple[int, int, int]
    bio: tuple[int, int, int]
    psico: tuple[int, int, int]
    social: tuple[int, int, int]
    font_round: str
    font_black: str
    font_bold: str
    brush_path: Path
    endcard_path: Path
    sticker_inset: int
    sticker_y_from_top_safe: int
    sticker_size_boxes: dict[str, tuple[int, int]]
    caption_size: int
    caption_baseline_y: int
    enfoque_title: str
    enfoque_parts: list[tuple[str, str]]


def parse_rgb_tuple(
    colours: dict[str, Any], key: str, default: tuple[int, int, int]
) -> tuple[int, int, int]:
    """Read an RGB triple from brand YAML, falling back to the engine default.

    Args:
        colours: ``colours:`` mapping from ``brand.yaml``.
        key: Colour name (``teal``, ``gold``, ``bio``, …).
        default: Used when the pack omits the key.

    Returns:
        ``(red, green, blue)`` each 0–255.
    """
    value = colours.get(key, list(default))
    return (int(value[0]), int(value[1]), int(value[2]))


def resolve_brand_asset(
    brand_directory: Path, assets: dict[str, Any], name: str, default_relative: str
) -> Path:
    """Resolve a brand PNG path and fail if the file is missing.

    Args:
        brand_directory: ``brands/<id>/``.
        assets: ``assets:`` mapping from ``brand.yaml``.
        name: Key such as ``brush`` or ``endcard``.
        default_relative: Fallback relative path inside the brand folder.

    Returns:
        Absolute path to the asset.

    Raises:
        FileNotFoundError: The PNG is not on disk.
    """
    relative = assets.get(name, default_relative)
    path = brand_directory / relative
    if not path.is_file():
        raise FileNotFoundError(f"Brand asset {name} not found: {path}")
    return path


def load_brand_pack(brand_id: str, config_store: ConfigStore) -> BrandPack:
    """Load ``brands/<id>/brand.yaml`` and resolve asset paths against that folder.

    Args:
        brand_id: Folder name under ``brands/``.
        config_store: Supplies default macOS font paths when YAML omits them.

    Returns:
        Fully resolved ``BrandPack``.

    Raises:
        FileNotFoundError: ``brand.yaml`` or a listed asset is missing.
    """
    brand_directory = config_store.resolve_brand_directory(brand_id)
    yaml_path = brand_directory / "brand.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Missing brand.yaml at {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    colours = data.get("colours") or {}
    fonts = data.get("fonts") or {}
    assets = data.get("assets") or {}
    sticker = data.get("sticker") or {}
    captions = data.get("captions") or {}
    enfoque = data.get("enfoque") or {}

    # Default Bio/Psico/Social split matches Dra. Angélica's lockup; other
    # brands override ``enfoque.parts`` rather than forking the renderer.
    parts_raw = enfoque.get("parts") or [
        {"text": "Bio", "colour": "bio"},
        {"text": "  -  ", "colour": "white"},
        {"text": "Psico", "colour": "psico"},
        {"text": "  -  ", "colour": "white"},
        {"text": "Social", "colour": "social"},
    ]
    parts = [(str(item["text"]), str(item.get("colour", "white"))) for item in parts_raw]

    size_boxes = dict(DEFAULT_STICKER_SIZE_BOXES)
    for size_name, spec in (sticker.get("sizes") or {}).items():
        if not isinstance(spec, dict):
            continue
        fallback_width, fallback_height = size_boxes.get(
            str(size_name), DEFAULT_STICKER_SIZE_BOXES["mediano"]
        )
        size_boxes[str(size_name)] = (
            int(spec.get("max_w", fallback_width)),
            int(spec.get("max_h", fallback_height)),
        )

    return BrandPack(
        brand_id=brand_id,
        root=brand_directory,
        teal=parse_rgb_tuple(colours, "teal", (6, 138, 147)),
        gold=parse_rgb_tuple(colours, "gold", (245, 196, 48)),
        white=parse_rgb_tuple(colours, "white", (255, 255, 255)),
        black=parse_rgb_tuple(colours, "black", (0, 0, 0)),
        # Lime / periwinkle / peach: dark green and blue vanished on teal.
        bio=parse_rgb_tuple(colours, "bio", (210, 255, 90)),
        psico=parse_rgb_tuple(colours, "psico", (196, 176, 255)),
        social=parse_rgb_tuple(colours, "social", (255, 176, 70)),
        font_round=str(fonts.get("round") or config_store.mac_font_round),
        font_black=str(fonts.get("black") or config_store.mac_font_black),
        font_bold=str(fonts.get("bold") or config_store.mac_font_bold),
        brush_path=resolve_brand_asset(brand_directory, assets, "brush", "assets/brush.png"),
        endcard_path=resolve_brand_asset(
            brand_directory, assets, "endcard", "assets/endcard.png"
        ),
        sticker_inset=int(sticker.get("inset", 18)),
        # Same Y as the dual fruit-bowl slot — never centre on her head (hat).
        sticker_y_from_top_safe=int(sticker.get("y_from_top_safe", 8)),
        sticker_size_boxes=size_boxes,
        caption_size=int(captions.get("size", 56)),
        # Coat V / cleavage: below the chin, above organic Reels UI (~Y 1528).
        caption_baseline_y=int(captions.get("y", 1528)),
        enfoque_title=str(enfoque.get("title") or "ENFOQUE INTEGRAL"),
        enfoque_parts=parts,
    )


def load_font(brand: BrandPack, path: str, size: int) -> ImageFont.FreeTypeFont:
    """Try the requested face, then brand fallbacks, then PIL default.

    Missing fonts on CI/Linux must not crash compose; Arial Rounded is macOS
    Supplemental-only.

    Args:
        brand: Pack whose fallback faces we try next.
        path: Preferred ``.ttf`` path.
        size: Point size.

    Returns:
        A FreeType font, or PIL's bitmap default as last resort.
    """
    for candidate in (path, brand.font_black, brand.font_bold):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


_BRUSH_CACHE: dict[str, Image.Image] = {}


def load_brush(brand: BrandPack) -> Image.Image:
    """Knock out the white paper of the scanned brush and cache the crop.

    The source scan sits on white paper. Treating near-white as transparent
    lets us 9-slice a painterly stroke without a rectangular card.

    Args:
        brand: Pack whose ``brush_path`` we load.

    Returns:
        Tight RGBA crop of the teal stroke, cached per path.
    """
    cache_key = str(brand.brush_path)
    if cache_key not in _BRUSH_CACHE:
        image = Image.open(brand.brush_path).convert("RGBA")
        pixels = np.array(image)
        rgb = pixels[:, :, :3].astype(np.int16)
        white_paper = rgb.min(axis=2) >= 238
        pixels[:, :, 3] = np.where(white_paper, 0, 255).astype(np.uint8)
        rows, columns = np.where(pixels[:, :, 3] > 20)
        padding = 2
        top = max(0, int(rows.min()) - padding)
        bottom = min(pixels.shape[0], int(rows.max()) + padding + 1)
        left = max(0, int(columns.min()) - padding)
        right = min(pixels.shape[1], int(columns.max()) + padding + 1)
        _BRUSH_CACHE[cache_key] = Image.fromarray(pixels[top:bottom, left:right])
    return _BRUSH_CACHE[cache_key]


def slice_brush_to_size(brand: BrandPack, width: int, height: int) -> Image.Image:
    """9-slice the brush so labels of any width keep the same stroke ends.

    Stretching the whole scan would smear the ragged tips. We pin the left
    and right caps (~13% of source width) and only stretch the middle.

    Args:
        brand: Pack that owns the brush scan.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        RGBA brush banner at ``width × height``.
    """
    source = load_brush(brand)
    source_width, source_height = source.size
    cap_source = max(28, int(source_width * 0.13))
    cap_width = max(16, int(round(cap_source * height / source_height)))
    left = source.crop((0, 0, cap_source, source_height)).resize(
        (cap_width, height), Image.Resampling.LANCZOS
    )
    right = source.crop((source_width - cap_source, 0, source_width, source_height)).resize(
        (cap_width, height), Image.Resampling.LANCZOS
    )
    middle_width = max(1, width - left.width - right.width)
    middle = source.crop((cap_source, 0, source_width - cap_source, source_height)).resize(
        (middle_width, height), Image.Resampling.LANCZOS
    )
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    output.paste(left, (0, 0), left)
    output.paste(middle, (left.width, 0), middle)
    output.paste(right, (left.width + middle.width, 0), right)
    return output


def make_brush_label(brand: BrandPack, text: str, font_size: int) -> Image.Image:
    """White rounded type on a teal brush — used for name / specialty hooks.

    Args:
        brand: Colours and fonts.
        text: Line to paint (e.g. ``Dra. Angélica``).
        font_size: Point size; 72 for the name, 66 for the specialty.

    Returns:
        Shadowed RGBA lockup. Caller should still clamp to side gutters.
    """
    font = load_font(brand, brand.font_round, font_size)
    dummy = Image.new("RGB", (8, 8))
    measure = ImageDraw.Draw(dummy)
    bounding_box = measure.textbbox((0, 0), text, font=font)
    text_width = bounding_box[2] - bounding_box[0]
    text_height = bounding_box[3] - bounding_box[1]
    pad_x, pad_y = 58, 32
    width, height = text_width + pad_x * 2, text_height + pad_y * 2
    image = slice_brush_to_size(brand, width, height)
    draw = ImageDraw.Draw(image)
    # Subtract bbox origin so glyph bearings do not shift the visual centre.
    draw.text(
        ((width - text_width) // 2 - bounding_box[0], (height - text_height) // 2 - bounding_box[1]),
        text,
        font=font,
        fill=brand.white,
    )
    return add_drop_shadow(image, radius=10, offset=(0, 5), shadow_alpha=120)


def colour_for_lockup_part(brand: BrandPack, name: str) -> tuple[int, int, int]:
    """Map a YAML colour token (``bio``, ``white``, …) to an RGB triple.

    Args:
        brand: Pack whose palette we read.
        name: Token from ``enfoque.parts[].colour``.

    Returns:
        RGB tuple; unknown tokens fall back to white so a typo stays readable.
    """
    lookup = {
        "teal": brand.teal,
        "gold": brand.gold,
        "white": brand.white,
        "black": brand.black,
        "bio": brand.bio,
        "psico": brand.psico,
        "social": brand.social,
    }
    return lookup.get(name, brand.white)


def make_enfoque_lockup(brand: BrandPack) -> Image.Image:
    """Teal brush banner: title + coloured Bio / Psico / Social.

    Dark greens and blues vanished on this teal; lime / periwinkle / peach
    plus a black stroke is the pairing that survives the sky behind her.

    Args:
        brand: Title string, part list, and palette.

    Returns:
        Shadowed RGBA lockup for the hook/sky slot.
    """
    title_font = load_font(brand, brand.font_round, 58)
    word_font = load_font(brand, brand.font_round, 50)
    dummy = Image.new("RGB", (8, 8))
    measure = ImageDraw.Draw(dummy)
    title = brand.enfoque_title
    parts = [
        (text, colour_for_lockup_part(brand, colour))
        for text, colour in brand.enfoque_parts
    ]
    title_box = measure.textbbox((0, 0), title, font=title_font)
    title_width = title_box[2] - title_box[0]
    title_height = title_box[3] - title_box[1]
    stroke = 3
    part_boxes = [
        measure.textbbox((0, 0), text, font=word_font, stroke_width=stroke)
        for text, _ in parts
    ]
    parts_width = sum(box[2] - box[0] for box in part_boxes)
    parts_height = max(box[3] - box[1] for box in part_boxes)
    pad_x, pad_y = 56, 34
    gap_y = 10
    width = max(title_width, parts_width) + pad_x * 2
    height = title_height + gap_y + parts_height + pad_y * 2
    image = slice_brush_to_size(brand, width, height)
    draw = ImageDraw.Draw(image)
    title_x = (width - title_width) // 2 - title_box[0]
    title_y = pad_y - title_box[1]
    draw.text((title_x, title_y), title, font=title_font, fill=brand.white)
    line_y = pad_y + title_height + gap_y
    # Shared baseline so "Bio" and "Psico" do not bounce on glyph bearings.
    min_top = min(box[1] for box in part_boxes)
    draw_y = line_y - min_top
    cursor_x = (width - parts_width) // 2
    for (text, colour), box in zip(parts, part_boxes):
        draw.text(
            (cursor_x - box[0], draw_y),
            text,
            font=word_font,
            fill=colour,
            stroke_width=stroke,
            stroke_fill=brand.black,
        )
        cursor_x += box[2] - box[0]
    return add_drop_shadow(image, radius=12, offset=(0, 6), shadow_alpha=110)


def make_endcard_frame(
    brand: BrandPack, frame_width: int, frame_height: int, pad: int = 20
) -> np.ndarray:
    """Near-full-frame contact card on white.

    The card is 2:3, the reel is 9:16 — letterbox rather than stretch so
    WhatsApp at the bottom of the card stays readable. Do not squash into the
    15–68% safe band; Angélica asked for the card to fill the frame.

    Args:
        brand: Pack whose ``endcard_path`` we load.
        frame_width: Output width (1080).
        frame_height: Output height (1920).
        pad: Minimum margin so the card does not clip the encoder edge.

    Returns:
        ``height × width × 3`` uint8 RGB frame.
    """
    source = Image.open(brand.endcard_path).convert("RGBA")
    canvas = Image.new("RGB", (frame_width, frame_height), brand.white)
    scale = min(
        (frame_width - 2 * pad) / source.width,
        (frame_height - 2 * pad) / source.height,
    )
    new_width, new_height = int(source.width * scale), int(source.height * scale)
    source = source.resize((new_width, new_height), Image.Resampling.LANCZOS)
    x = (frame_width - new_width) // 2
    y = (frame_height - new_height) // 2
    canvas.paste(source, (x, y), source)
    return np.array(canvas, dtype=np.uint8)


def clamp_to_side_safe(overlay: Image.Image, config_store: ConfigStore) -> Image.Image:
    """Keep generated banners inside the 6% side gutters.

    Args:
        overlay: Brush label or enfoque lockup.
        config_store: Canvas width and side-safe ratio.

    Returns:
        Overlay scaled down if it would clip the rails.
    """
    max_width = config_store.frame_width - 2 * config_store.side_safe_pixels
    return shrink_overlay_to_max_width(overlay, max_width)
