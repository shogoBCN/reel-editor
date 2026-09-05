"""
Validate a project brief without encoding video.

Used as a fast smoke check after sheet import or YAML edits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.brief.brief_loader import load_brief
from modules.modules_initialiser import get_module
from modules.video.brand_style import load_brand_pack
from modules.video.overlays import build_overlay_layers
from modules.video.timing import (
    convert_source_time_to_final_time,
    format_seconds_as_timestamp,
)


def check_brief(project_dir: Path) -> None:
    """Print overlay schedule (source + final clocks) and fail if assets miss.

    Args:
        project_dir: Folder with ``brief.yaml``.
    """
    config_store = get_module("config_store")
    brief = load_brief(project_dir)
    brand = load_brand_pack(brief.brand_id, config_store)
    layers = build_overlay_layers(
        brief.overlays, brief.project_dir, brand, config_store
    )
    print(f"slug          {brief.slug}")
    print(f"title         {brief.title}")
    print(f"brand         {brief.brand_id}")
    print(
        f"video         {brief.video_path} "
        f"({'ok' if brief.video_path.is_file() else 'MISSING'})"
    )
    transcript = brief.transcript_path
    if transcript:
        print(
            f"transcript    {transcript} "
            f"({'ok' if transcript.is_file() else 'MISSING'})"
        )
    print(
        f"trim          {brief.trim_start_seconds:.2f}s → talk_end "
        f"{brief.talk_end_seconds:.2f}s (dur {brief.talk_duration_seconds:.2f}s)"
    )
    print(f"overlays      {len(layers)}")
    for layer in layers:
        final_start = convert_source_time_to_final_time(
            layer.start_seconds, brief.trim_start_seconds
        )
        final_end = convert_source_time_to_final_time(
            layer.end_seconds, brief.trim_start_seconds
        )
        print(
            f"  {layer.overlay_id:16} src "
            f"{format_seconds_as_timestamp(layer.start_seconds)}–"
            f"{format_seconds_as_timestamp(layer.end_seconds)}"
            f"  final {format_seconds_as_timestamp(final_start)}–"
            f"{format_seconds_as_timestamp(final_end)}"
            f"  {layer.image.size[0]}x{layer.image.size[1]}"
        )
    print(f"transitions   {len(brief.transitions)}")
    for transition in brief.transitions:
        print(
            f"  {transition.transition_id:16} {transition.style:12} "
            f"{format_seconds_as_timestamp(transition.start_seconds)}–"
            f"{format_seconds_as_timestamp(transition.end_seconds)} "
            f"cut {format_seconds_as_timestamp(transition.cut_seconds)}"
        )
    print(f"speech_fixes  {brief.speech_recognition_corrections}")
    print("ok")


def main() -> None:
    """CLI entry for ``--project``."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = REPOSITORY_ROOT / project_dir
    check_brief(project_dir)


if __name__ == "__main__":
    main()
