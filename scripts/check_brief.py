"""
Validate a project brief without encoding video.

Used as a fast smoke check after sheet import or YAML edits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from modules.brief.brief_loader import load_brief
from modules.modules_initialiser import get_module
from modules.video.brand_style import load_brand_pack
from modules.video.overlays import build_overlay_layers
from modules.video.timing import format_clock, source_to_final


def check_brief(project_dir: Path) -> None:
    config_store = get_module("config_store")
    brief = load_brief(project_dir)
    brand = load_brand_pack(brief.brand_id, config_store)
    layers = build_overlay_layers(
        brief.overlays, brief.project_dir, brand, config_store
    )
    print(f"slug          {brief.slug}")
    print(f"title         {brief.title}")
    print(f"brand         {brief.brand_id}")
    print(f"video         {brief.video_path} ({'ok' if brief.video_path.is_file() else 'MISSING'})")
    transcript = brief.transcript_path
    if transcript:
        print(f"transcript    {transcript} ({'ok' if transcript.is_file() else 'MISSING'})")
    print(
        f"trim          {brief.trim_start:.2f}s → talk_end {brief.talk_end:.2f}s "
        f"(dur {brief.talk_dur:.2f}s)"
    )
    print(f"overlays      {len(layers)}")
    for layer in layers:
        final0 = source_to_final(layer.start, brief.trim_start)
        final1 = source_to_final(layer.end, brief.trim_start)
        print(
            f"  {layer.overlay_id:16} src {format_clock(layer.start)}–{format_clock(layer.end)}"
            f"  final {format_clock(final0)}–{format_clock(final1)}"
            f"  {layer.image.size[0]}x{layer.image.size[1]}"
        )
    print(f"asr_fix       {brief.asr_fix}")
    print("ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = _repo_root / project_dir
    check_brief(project_dir)


if __name__ == "__main__":
    main()
