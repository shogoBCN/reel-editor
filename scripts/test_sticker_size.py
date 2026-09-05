"""Smoke tests for Angélica's sticker size words and paste-any-size fit."""

from __future__ import annotations

import sys
import tempfile
from io import BytesIO
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from PIL import Image

from modules.brief.sticker_size import (
    DEFAULT_STICKER_SIZE_BOXES,
    infer_sticker_size_name,
    sticker_box_for_notes,
)
from modules.video.image_ops import load_fitted_sticker, save_pasted_overlay_png


def expect(notes: str, name: str) -> None:
    """Assert size-word inference.

    Args:
        notes: Fake «Qué quieres».
        name: Expected grande / mediano / chico.

    Raises:
        SystemExit: Mismatch.
    """
    got = infer_sticker_size_name(notes)
    if got != name:
        raise SystemExit(f"{notes!r} -> {got!r}, expected {name!r}")


def main() -> None:
    """Run size-word and fit checks."""
    expect("", "mediano")
    expect("a la derecha de la cabeza", "mediano")
    expect("Tamaño grande.", "grande")
    expect("el frutero grande con mango", "grande")
    expect("bien grande, a la derecha", "grande")
    expect("más grande que el susto", "grande")
    expect("Tamaño mediano.", "mediano")
    expect("no tan grande", "mediano")
    expect("Tamaño chico.", "chico")
    expect("más chica que el frutero", "chico")
    expect("una carita chiquita", "chico")
    expect("pequeñito a la izquierda", "chico")
    width, height, name = sticker_box_for_notes("tamaño grande")
    if (width, height, name) != (*DEFAULT_STICKER_SIZE_BOXES["grande"], "grande"):
        raise SystemExit("sticker_box_for_notes grande failed")

    huge = Image.new("RGB", (2400, 1800), (10, 200, 40))
    jpeg_buffer = BytesIO()
    huge.save(jpeg_buffer, "JPEG", quality=85)
    tiny = Image.new("RGB", (48, 48), (200, 30, 30))
    with tempfile.TemporaryDirectory() as temp_dir:
        jpeg_png = Path(temp_dir) / "from_jpeg.png"
        save_pasted_overlay_png(jpeg_buffer.getvalue(), jpeg_png)
        stored = Image.open(jpeg_png)
        if stored.size != (2400, 1800):
            raise SystemExit(f"import must keep source pixels, got {stored.size}")
        fitted_huge = load_fitted_sticker(jpeg_png, 480, 340)
        if fitted_huge.width >= 2400 or fitted_huge.height >= 1800:
            raise SystemExit(f"huge paste was not scaled down: {fitted_huge.size}")
        tiny_path = Path(temp_dir) / "tiny.png"
        tiny.save(tiny_path)
        fitted_tiny = load_fitted_sticker(tiny_path, 320, 260)
        if fitted_tiny.width <= 48 or fitted_tiny.height <= 48:
            raise SystemExit(f"tiny paste was not scaled up: {fitted_tiny.size}")
    print("sticker size words ok")


if __name__ == "__main__":
    main()
