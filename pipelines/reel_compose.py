"""
Compose a 9:16 talking-head reel from a project brief.

Reads ``brief.yaml`` (source-clock timestamps, overlays, trim, speech
corrections), composites stickers + karaoke captions onto scaled frames,
fades to white, and holds the brand endcard. Preview writes JPEGs; ``--full``
writes H.264.

See ``pipelines/reel_compose/pipeline_docu/README.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.brief.brief_loader import ProjectBrief, load_brief
from modules.modules_initialiser import get_module
from modules.video.brand_style import load_brand_pack, make_endcard_frame
from modules.video.captions import draw_captions, load_caption_groups
from modules.video.ffmpeg_io import (
    grab_source_frame,
    open_frame_reader,
    open_frame_writer,
    prepare_talk_audio,
)
from modules.video.overlays import OverlayLayer, build_overlay_layers, draw_scheduled_overlay


def smoothstep(amount: float) -> float:
    """Cubic Hermite smoothstep so fades ease in and out instead of linear cuts.

    Args:
        amount: 0–1 (clamped by the caller).

    Returns:
        Smoothed 0–1.
    """
    return amount * amount * (3 - 2 * amount)


class ReelComposePipeline:
    """Trim + overlay + caption + endcard compose for one project folder."""

    def __init__(self, project_dir: Path) -> None:
        """Load brief, brand, overlay rasters, and caption groups.

        Args:
            project_dir: Folder containing ``brief.yaml``.

        Raises:
            FileNotFoundError: Captions are on but ``transcript.json`` is missing.
        """
        self.config_store = get_module("config_store")
        self.brief: ProjectBrief = load_brief(project_dir)
        self.brand = load_brand_pack(self.brief.brand_id, self.config_store)
        self.layers: list[OverlayLayer] = build_overlay_layers(
            self.brief.overlays,
            self.brief.project_dir,
            self.brand,
            self.config_store,
        )
        self.caption_groups: list[dict] = []
        if self.brief.captions_enabled:
            if self.brief.transcript_path is None or not self.brief.transcript_path.is_file():
                raise FileNotFoundError(
                    f"Captions are enabled but transcript is missing: "
                    f"{self.brief.transcript_path}. Run pipelines/transcribe/transcribe.py first."
                )
            self.caption_groups = load_caption_groups(
                self.brief.transcript_path,
                self.brief.trim_start_seconds,
                self.brief.speech_recognition_corrections,
            )

    def render_talk_frame(
        self, raw_rgb: bytes, source_time_seconds: float
    ) -> np.ndarray:
        """Composite overlays, captions, and the late white fade onto one frame.

        Args:
            raw_rgb: Packed RGB24 from ffmpeg (``width * height * 3`` bytes).
            source_time_seconds: Clock of the original recording.

        Returns:
            ``height × width × 3`` uint8 RGB.
        """
        width = self.config_store.frame_width
        height = self.config_store.frame_height
        frame = np.frombuffer(raw_rgb, dtype=np.uint8).reshape(height, width, 3).copy()
        for layer in self.layers:
            draw_scheduled_overlay(frame, layer, source_time_seconds)
        if self.caption_groups:
            draw_captions(
                frame,
                self.caption_groups,
                source_time_seconds,
                self.brand,
                self.config_store,
            )
        fade_start = self.brief.talk_end_seconds - self.brief.fade_to_white_seconds
        if source_time_seconds >= fade_start:
            amount = min(
                1.0,
                (source_time_seconds - fade_start) / self.brief.fade_to_white_seconds,
            )
            amount = smoothstep(amount)
            frame = (frame.astype(np.float32) * (1 - amount) + 255.0 * amount).astype(
                np.uint8
            )
        return frame

    def run_preview(self) -> Path:
        """Seek-grab stills at brief preview times (or overlay midpoints).

        Returns:
            Directory of JPEG stills including ``endcard.jpg``.
        """
        preview_dir = self.brief.preview_dir
        preview_dir.mkdir(parents=True, exist_ok=True)
        for label, source_time_seconds in self.brief.preview_shots.items():
            raw_rgb = grab_source_frame(
                self.brief.video_path, source_time_seconds, self.config_store
            )
            frame = self.render_talk_frame(raw_rgb, source_time_seconds)
            Image.fromarray(frame).save(
                preview_dir / f"{label}_{source_time_seconds:.2f}.jpg", quality=92
            )
            print(f"preview {label} source={source_time_seconds:.2f}s")
        Image.fromarray(
            make_endcard_frame(
                self.brand,
                self.config_store.frame_width,
                self.config_store.frame_height,
            )
        ).save(preview_dir / "endcard.jpg", quality=92)
        print("previews in", preview_dir)
        return preview_dir

    def run_full(self, output_path: Path | None = None) -> Path:
        """Encode the talking-head window plus endcard hold to H.264.

        Args:
            output_path: Optional mp4 path; default is ``output/<filename>``.

        Returns:
            Path written.

        Raises:
            SystemExit: ffmpeg writer returned non-zero.
        """
        output_dir = self.brief.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path or (output_dir / self.brief.output_name)
        audio_path = output_dir / "audio_trim.wav"
        print("preparing audio…")
        prepare_talk_audio(
            self.brief.video_path,
            audio_path,
            self.brief.trim_start_seconds,
            self.brief.talk_duration_seconds,
            self.brief.fade_to_white_seconds,
            self.brief.endcard_hold_seconds,
        )

        talk_frame_count = int(
            round(self.brief.talk_duration_seconds * self.config_store.frames_per_second)
        )
        endcard_frame_count = int(
            round(self.brief.endcard_hold_seconds * self.config_store.frames_per_second)
        )
        print(
            f"talk frames={talk_frame_count} endcard frames={endcard_frame_count} "
            f"overlays={len(self.layers)} caption groups={len(self.caption_groups)}"
        )

        reader = open_frame_reader(
            self.brief.video_path,
            self.brief.trim_start_seconds,
            self.brief.talk_duration_seconds,
            self.config_store,
        )
        writer = open_frame_writer(output_path, audio_path, self.config_store)
        endcard = make_endcard_frame(
            self.brand,
            self.config_store.frame_width,
            self.config_store.frame_height,
        )
        bytes_per_frame = (
            self.config_store.frame_width * self.config_store.frame_height * 3
        )
        try:
            for frame_index in range(talk_frame_count):
                raw_rgb = reader.stdout.read(bytes_per_frame)
                if len(raw_rgb) < bytes_per_frame:
                    print(f"reader ended early at frame {frame_index}")
                    break
                source_time_seconds = (
                    self.brief.trim_start_seconds
                    + frame_index / self.config_store.frames_per_second
                )
                frame = self.render_talk_frame(raw_rgb, source_time_seconds)
                writer.stdin.write(frame.tobytes())
                if frame_index % 90 == 0:
                    print(
                        f"  talk {frame_index}/{talk_frame_count} orig={source_time_seconds:.2f}s"
                    )
            reader.stdout.close()
            reader.wait()

            for hold_index in range(endcard_frame_count):
                hold_time = hold_index / self.config_store.frames_per_second
                # 0.35s dissolve from white into the contact card.
                amount = min(1.0, hold_time / 0.35)
                amount = smoothstep(amount)
                frame = (
                    255.0 * (1 - amount) + endcard.astype(np.float32) * amount
                ).astype(np.uint8)
                writer.stdin.write(frame.tobytes())
            writer.stdin.close()
            writer_return_code = writer.wait()
            if writer_return_code != 0:
                raise SystemExit(f"ffmpeg writer failed: {writer_return_code}")
        finally:
            if reader.poll() is None:
                reader.kill()
            if writer.poll() is None:
                writer.kill()
        print("wrote", output_path)
        return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags for preview vs full encode.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Namespace with ``project``, ``preview``, ``full``.
    """
    parser = argparse.ArgumentParser(
        description="Compose a 9:16 reel from a project brief."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project folder containing brief.yaml (e.g. examples/ya_tienes)",
    )
    parser.add_argument("--preview", action="store_true", help="Write JPEG stills")
    parser.add_argument("--full", action="store_true", help="Encode the H.264 reel")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point: preview by default, encode when ``--full`` is set.

    Args:
        argv: Optional argument list.
    """
    args = parse_args(argv)
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = REPOSITORY_ROOT / project_dir
    pipeline = ReelComposePipeline(project_dir)
    print(
        f"{pipeline.brief.slug}: {len(pipeline.layers)} overlay layers, "
        f"{len(pipeline.caption_groups)} caption groups"
    )
    if args.preview or not args.full:
        pipeline.run_preview()
    if args.full:
        pipeline.run_full()


if __name__ == "__main__":
    main()
