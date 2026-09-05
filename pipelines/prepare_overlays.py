"""
Cut near-black backgrounds from overlay PNGs (phone screenshots, emoji packs).

Angélica often sends stickers on black. This is a one-shot prep step before
compose; already-keyed assets in ``examples/`` do not need it again. See ``pipelines/README.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.video.image_ops import cut_black_background


def prepare_overlays(
    input_dir: Path,
    output_dir: Path,
    threshold: int = 28,
    feather: int = 1,
) -> list[Path]:
    """Key every PNG in ``input_dir`` and write cropped RGBA files.

    Args:
        input_dir: Folder of raw PNGs.
        output_dir: Destination (created if missing).
        threshold: Black-cut aggressiveness (see ``cut_black_background``).
        feather: Soft-edge width.

    Returns:
        Paths written.

    Raises:
        FileNotFoundError: No PNGs in the input folder.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in sorted(input_dir.glob("*.png")):
        image = Image.open(source)
        keyed = cut_black_background(image, threshold=threshold, feather=feather)
        destination = output_dir / source.name
        keyed.save(destination, "PNG")
        written.append(destination)
        print(f"{source.name}: {image.size} -> {keyed.size}")
    if not written:
        raise FileNotFoundError(f"No PNG files in {input_dir}")
    return written


def main() -> None:
    """CLI entry for black-keying a folder of overlay PNGs."""
    parser = argparse.ArgumentParser(description="Key black backgrounds on overlay PNGs")
    parser.add_argument("--input-dir", required=True, help="Folder of raw PNGs")
    parser.add_argument("--output-dir", required=True, help="Folder for keyed PNGs")
    parser.add_argument("--thresh", type=int, default=28)
    parser.add_argument("--feather", type=int, default=1)
    args = parser.parse_args()
    prepare_overlays(
        Path(args.input_dir),
        Path(args.output_dir),
        args.thresh,
        args.feather,
    )


if __name__ == "__main__":
    main()
