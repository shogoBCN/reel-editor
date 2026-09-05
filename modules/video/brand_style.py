"""
Brand pack loader and generated lockups (teal brush labels, enfoque banner, endcard).

Per-client look lives in ``brands/<id>/brand.yaml`` plus that folder's ``assets/``.
The compose pipeline never hardcodes Dra. Angélica colours — swap the pack to
reuse the same renderer for another talking-head brand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from config.config_store import ConfigStore
from modules.video.image_ops import add_shadow, clamp_overlay_width


@dataclass
class BrandPack:
    """Resolved brand assets and visual constants."""

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
    caption_size: int
    caption_y: int
    enfoque_title: str
    enfoque_parts: list[tuple[str, str]]


def load_brand_pack(brand_id: str, config_store: ConfigStore) -> BrandPack:
    """Load ``brands/<id>/brand.yaml`` and resolve asset paths against that folder."""
    brand_dir = config_store.resolve_brand_dir(brand_id)
    yaml_path = brand_dir / "brand.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Missing brand.yaml at {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    colours = data.get("colours") or {}
    fonts = data.get("fonts") or {}
    assets = data.get("assets") or {}
    sticker = data.get("sticker") or {}
    captions = data.get("captions") or {}
    enfoque = data.get("enfoque") or {}

    def _rgb(key: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
        value = colours.get(key, list(default))
        return (int(value[0]), int(value[1]), int(value[2]))

    def _asset(name: str, default_rel: str) -> Path:
        rel = assets.get(name, default_rel)
        path = brand_dir / rel
        if not path.is_file():
            raise FileNotFoundError(f"Brand asset {name} not found: {path}")
        return path

    parts_raw = enfoque.get("parts") or [
        {"text": "Bio", "colour": "bio"},
        {"text": "  -  ", "colour": "white"},
        {"text": "Psico", "colour": "psico"},
        {"text": "  -  ", "colour": "white"},
        {"text": "Social", "colour": "social"},
    ]
    parts = [(str(p["text"]), str(p.get("colour", "white"))) for p in parts_raw]

    return BrandPack(
        brand_id=brand_id,
        root=brand_dir,
        teal=_rgb("teal", (6, 138, 147)),
        gold=_rgb("gold", (245, 196, 48)),
        white=_rgb("white", (255, 255, 255)),
        black=_rgb("black", (0, 0, 0)),
        bio=_rgb("bio", (210, 255, 90)),
        psico=_rgb("psico", (196, 176, 255)),
        social=_rgb("social", (255, 176, 70)),
        font_round=str(fonts.get("round") or config_store.mac_font_round),
        font_black=str(fonts.get("black") or config_store.mac_font_black),
        font_bold=str(fonts.get("bold") or config_store.mac_font_bold),
        brush_path=_asset("brush", "assets/brush.png"),
        endcard_path=_asset("endcard", "assets/endcard.png"),
        sticker_inset=int(sticker.get("inset", 18)),
        sticker_y_from_top_safe=int(sticker.get("y_from_top_safe", 8)),
        caption_size=int(captions.get("size", 56)),
        caption_y=int(captions.get("y", 1528)),
        enfoque_title=str(enfoque.get("title") or "ENFOQUE INTEGRAL"),
        enfoque_parts=parts,
    )


def load_font(brand: BrandPack, path: str, size: int) -> ImageFont.FreeTypeFont:
    """Try the requested face, then brand fallbacks, then PIL default."""
    for candidate in (path, brand.font_black, brand.font_bold):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


_brush_cache: dict[str, Image.Image] = {}


def load_brush(brand: BrandPack) -> Image.Image:
    """Knock out the white paper of the scanned brush and cache the crop."""
    cache_key = str(brand.brush_path)
    if cache_key not in _brush_cache:
        image = Image.open(brand.brush_path).convert("RGBA")
        arr = np.array(image)
        rgb = arr[:, :, :3].astype(np.int16)
        white = rgb.min(axis=2) >= 238
        arr[:, :, 3] = np.where(white, 0, 255).astype(np.uint8)
        ys, xs = np.where(arr[:, :, 3] > 20)
        pad = 2
        y0 = max(0, int(ys.min()) - pad)
        y1 = min(arr.shape[0], int(ys.max()) + pad + 1)
        x0 = max(0, int(xs.min()) - pad)
        x1 = min(arr.shape[1], int(xs.max()) + pad + 1)
        _brush_cache[cache_key] = Image.fromarray(arr[y0:y1, x0:x1])
    return _brush_cache[cache_key]


def sized_brush(brand: BrandPack, width: int, height: int) -> Image.Image:
    """9-slice the brush so labels of any width keep the same stroke ends."""
    src = load_brush(brand)
    sw, sh = src.size
    cap = max(28, int(sw * 0.13))
    cap_w = max(16, int(round(cap * height / sh)))
    left = src.crop((0, 0, cap, sh)).resize((cap_w, height), Image.Resampling.LANCZOS)
    right = src.crop((sw - cap, 0, sw, sh)).resize((cap_w, height), Image.Resampling.LANCZOS)
    mid_w = max(1, width - left.width - right.width)
    mid = src.crop((cap, 0, sw - cap, sh)).resize((mid_w, height), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.paste(left, (0, 0), left)
    out.paste(mid, (left.width, 0), mid)
    out.paste(right, (left.width + mid.width, 0), right)
    return out


def make_brush_label(brand: BrandPack, text: str, font_size: int) -> Image.Image:
    """White rounded type on a teal brush — used for name / specialty hooks."""
    font = load_font(brand, brand.font_round, font_size)
    dummy = Image.new("RGB", (8, 8))
    draw0 = ImageDraw.Draw(dummy)
    bbox = draw0.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 58, 32
    width, height = tw + pad_x * 2, th + pad_y * 2
    img = sized_brush(brand, width, height)
    draw = ImageDraw.Draw(img)
    draw.text(
        ((width - tw) // 2 - bbox[0], (height - th) // 2 - bbox[1]),
        text,
        font=font,
        fill=brand.white,
    )
    return add_shadow(img, radius=10, offset=(0, 5), shadow_alpha=120)


def _colour_for_part(brand: BrandPack, name: str) -> tuple[int, int, int]:
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
    """
    Teal brush banner: title + coloured Bio / Psico / Social.

    Dark greens and blues vanish on this teal; lime / periwinkle / peach
    plus a black stroke is the readable pairing.
    """
    title_font = load_font(brand, brand.font_round, 58)
    word_font = load_font(brand, brand.font_round, 50)
    dummy = Image.new("RGB", (8, 8))
    draw0 = ImageDraw.Draw(dummy)
    title = brand.enfoque_title
    parts = [(text, _colour_for_part(brand, colour)) for text, colour in brand.enfoque_parts]
    title_bbox = draw0.textbbox((0, 0), title, font=title_font)
    tw, th = title_bbox[2] - title_bbox[0], title_bbox[3] - title_bbox[1]
    stroke = 3
    part_boxes = [
        draw0.textbbox((0, 0), text, font=word_font, stroke_width=stroke)
        for text, _ in parts
    ]
    pw = sum(box[2] - box[0] for box in part_boxes)
    ph = max(box[3] - box[1] for box in part_boxes)
    pad_x, pad_y = 56, 34
    gap_y = 10
    width = max(tw, pw) + pad_x * 2
    height = th + gap_y + ph + pad_y * 2
    img = sized_brush(brand, width, height)
    draw = ImageDraw.Draw(img)
    tx = (width - tw) // 2 - title_bbox[0]
    ty = pad_y - title_bbox[1]
    draw.text((tx, ty), title, font=title_font, fill=brand.white)
    y_line = pad_y + th + gap_y
    min_top = min(box[1] for box in part_boxes)
    y_draw = y_line - min_top
    x = (width - pw) // 2
    for (text, colour), bbox in zip(parts, part_boxes):
        draw.text(
            (x - bbox[0], y_draw),
            text,
            font=word_font,
            fill=colour,
            stroke_width=stroke,
            stroke_fill=brand.black,
        )
        x += bbox[2] - bbox[0]
    return add_shadow(img, radius=12, offset=(0, 6), shadow_alpha=110)


def make_endcard_frame(
    brand: BrandPack, frame_w: int, frame_h: int, pad: int = 20
) -> np.ndarray:
    """
    Near-full-frame contact card on white.

    The card is 2:3, the reel is 9:16 — letterbox rather than stretch so
    WhatsApp at the bottom of the card stays readable.
    """
    src = Image.open(brand.endcard_path).convert("RGBA")
    canvas = Image.new("RGB", (frame_w, frame_h), brand.white)
    scale = min((frame_w - 2 * pad) / src.width, (frame_h - 2 * pad) / src.height)
    new_w, new_h = int(src.width * scale), int(src.height * scale)
    src = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x = (frame_w - new_w) // 2
    y = (frame_h - new_h) // 2
    canvas.paste(src, (x, y), src)
    return np.array(canvas, dtype=np.uint8)


def clamp_to_side_safe(
    overlay: Image.Image, config_store: ConfigStore
) -> Image.Image:
    """Keep generated banners inside the 6% side gutters."""
    max_w = config_store.frame_width - 2 * config_store.side_safe_px
    return clamp_overlay_width(overlay, max_w)
