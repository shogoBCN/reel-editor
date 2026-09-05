"""
Cut near-black backgrounds from overlay PNGs (phone screenshots, emoji packs).

Angélica often sends stickers on black. This is a one-shot prep step before
compose; already-keyed assets in ``examples/`` do not need it again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
sys.path.insert(0, str(_repo_root))

from modules.video.image_ops import key_black


def prepare_overlays(
    input_dir: Path,
    output_dir: Path,
    thresh: int = 28,
    feather: int = 1,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in sorted(input_dir.glob("*.png")):
        image = Image.open(src)
        keyed = key_black(image, thresh=thresh, feather=feather)
        dest = output_dir / src.name
        keyed.save(dest, "PNG")
        written.append(dest)
        print(f"{src.name}: {image.size} -> {keyed.size}")
    if not written:
        raise FileNotFoundError(f"No PNG files in {input_dir}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Key black backgrounds on overlay PNGs")
    parser.add_argument("--input-dir", required=True, help="Folder of raw PNGs")
    parser.add_argument("--output-dir", required=True, help="Folder for keyed PNGs")
    parser.add_argument("--thresh", type=int, default=28)
    parser.add_argument("--feather", type=int, default=1)
    args = parser.parse_args()
    prepare_overlays(Path(args.input_dir), Path(args.output_dir), args.thresh, args.feather)


if __name__ == "__main__":
    main()
