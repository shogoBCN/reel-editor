"""
Compose a 9:16 talking-head reel from a project brief.

Reads ``brief.yaml`` (source-clock timestamps, overlays, trim, speech
corrections), composites stickers + karaoke captions onto scaled frames,
optionally mixes scene-cut transitions, fades to white, and holds the brand
endcard. Preview writes JPEGs; ``--full`` writes H.264.

See ``pipelines/README.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent
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
from modules.video.timing import smoothstep
from modules.video.transitions import (
    TRANSITION_STYLE_NAMES,
    apply_scene_transitions,
    parse_transition_style_list,
)


def output_path_for_style(base_path: Path, style: str | None) -> Path:
    """Append a transition style to the stem when encoding variants.

    Args:
        base_path: Brief ``output.filename`` path.
        style: Style name, or None to keep the base name.

    Returns:
        Path such as ``a-partir-40_final_slide_left.mp4``.
    """
    if not style:
        return base_path
    return base_path.with_name(f"{base_path.stem}_{style}{base_path.suffix}")


class ReelComposePipeline:
    """Trim + overlay + caption + transition + endcard compose for one project."""

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
                    f"{self.brief.transcript_path}. Run pipelines/transcribe.py first."
                )
            self.caption_groups = load_caption_groups(
                self.brief.transcript_path,
                self.brief.trim_start_seconds,
                self.brief.speech_recognition_corrections,
            )
        self.outgoing_holds: dict[str, np.ndarray] = {}
        self.incoming_holds: dict[str, np.ndarray] = {}
        if self.brief.transitions:
            self.preload_transition_holds()

    def composite_talk_frame(
        self, raw_rgb: bytes, source_time_seconds: float
    ) -> np.ndarray:
        """Overlays and karaoke only — no scene mix, no end fade.

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
        return frame

    def apply_end_fade(
        self, frame: np.ndarray, source_time_seconds: float
    ) -> np.ndarray:
        """Fade the talking-head to white in the last ``fade_white`` seconds.

        Args:
            frame: Composited RGB.
            source_time_seconds: Clock of the original recording.

        Returns:
            Frame mixed toward white when inside the fade window.
        """
        fade_start = self.brief.talk_end_seconds - self.brief.fade_to_white_seconds
        if source_time_seconds < fade_start:
            return frame
        amount = min(
            1.0,
            (source_time_seconds - fade_start) / self.brief.fade_to_white_seconds,
        )
        amount = smoothstep(amount)
        return (frame.astype(np.float32) * (1 - amount) + 255.0 * amount).astype(
            np.uint8
        )

    def preload_transition_holds(self) -> None:
        """Grab the last take-A and first take-B frame for each jump cut.

        Accurate seeks so we do not land on the wrong side of the cut. Sequential
        encode still refreshes the outgoing hold from live frames until ``cut``.
        """
        half_frame = 0.5 / self.config_store.frames_per_second
        for transition in self.brief.transitions:
            outgoing_time = transition.cut_seconds - half_frame
            incoming_time = transition.cut_seconds + half_frame
            outgoing_raw = grab_source_frame(
                self.brief.video_path,
                outgoing_time,
                self.config_store,
                accurate_seek=True,
            )
            incoming_raw = grab_source_frame(
                self.brief.video_path,
                incoming_time,
                self.config_store,
                accurate_seek=True,
            )
            self.outgoing_holds[transition.transition_id] = self.composite_talk_frame(
                outgoing_raw, outgoing_time
            )
            self.incoming_holds[transition.transition_id] = self.composite_talk_frame(
                incoming_raw, incoming_time
            )

    def finish_talk_frame(
        self,
        composited: np.ndarray,
        source_time_seconds: float,
        style_override: str | None = None,
    ) -> np.ndarray:
        """Scene-cut mix (if any) then the closing white fade.

        Args:
            composited: Overlays + captions at this timestamp.
            source_time_seconds: Clock of the original recording.
            style_override: Force every window to this style (variant encodes).

        Returns:
            Frame ready to write or save as a preview JPEG.
        """
        frame = apply_scene_transitions(
            composited,
            source_time_seconds,
            self.brief.transitions,
            self.outgoing_holds,
            self.incoming_holds,
            style_override=style_override,
        )
        return self.apply_end_fade(frame, source_time_seconds)

    def render_talk_frame(
        self,
        raw_rgb: bytes,
        source_time_seconds: float,
        style_override: str | None = None,
    ) -> np.ndarray:
        """Composite overlays, captions, scene mix, and the late white fade.

        Args:
            raw_rgb: Packed RGB24 from ffmpeg.
            source_time_seconds: Clock of the original recording.
            style_override: Optional transition style for variant previews.

        Returns:
            ``height × width × 3`` uint8 RGB.
        """
        composited = self.composite_talk_frame(raw_rgb, source_time_seconds)
        return self.finish_talk_frame(
            composited, source_time_seconds, style_override=style_override
        )

    def capture_outgoing_holds(
        self, composited: np.ndarray, source_time_seconds: float
    ) -> None:
        """Freeze take A while we are still before each cut.

        Args:
            composited: Live overlays + captions (no mix yet).
            source_time_seconds: Clock of the original recording.
        """
        for transition in self.brief.transitions:
            if transition.start_seconds <= source_time_seconds < transition.cut_seconds:
                self.outgoing_holds[transition.transition_id] = composited.copy()

    def run_preview(self, style_override: str | None = None) -> Path:
        """Seek-grab stills at brief preview times (or overlay midpoints).

        Args:
            style_override: Optional style for every jump-cut window.

        Returns:
            Directory of JPEG stills including ``endcard.jpg``.
        """
        preview_dir = self.brief.preview_dir
        preview_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"_{style_override}" if style_override else ""
        for label, source_time_seconds in self.brief.preview_shots.items():
            in_transition = any(
                transition.contains(source_time_seconds)
                for transition in self.brief.transitions
            )
            raw_rgb = grab_source_frame(
                self.brief.video_path,
                source_time_seconds,
                self.config_store,
                accurate_seek=in_transition,
            )
            frame = self.render_talk_frame(
                raw_rgb, source_time_seconds, style_override=style_override
            )
            Image.fromarray(frame).save(
                preview_dir / f"{label}{suffix}_{source_time_seconds:.2f}.jpg",
                quality=92,
            )
            print(f"preview {label}{suffix} source={source_time_seconds:.2f}s")
        Image.fromarray(
            make_endcard_frame(
                self.brand,
                self.config_store.frame_width,
                self.config_store.frame_height,
            )
        ).save(preview_dir / "endcard.jpg", quality=92)
        print("previews in", preview_dir)
        return preview_dir

    def run_preview_styles(self, styles: list[str]) -> Path:
        """Write preview stills once per transition style.

        Args:
            styles: Mix names (``fade_white``, ``slide_left``, …).

        Returns:
            Preview directory.
        """
        preview_dir = self.brief.preview_dir
        if not styles:
            return self.run_preview()
        for style in styles:
            self.run_preview(style_override=style)
        return preview_dir

    def run_full(
        self,
        output_path: Path | None = None,
        style_variants: list[str] | None = None,
    ) -> list[Path]:
        """Encode the talking-head window plus endcard hold to H.264.

        One decode pass can feed several writers when ``style_variants`` has
        more than one name — only the jump-cut windows differ.

        Args:
            output_path: Optional mp4 path; default is ``output/<filename>``.
            style_variants: Transition styles to encode. Empty/None uses the
                styles already on the brief (one file).

        Returns:
            Paths written.

        Raises:
            SystemExit: An ffmpeg writer returned non-zero.
        """
        output_dir = self.brief.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        base_path = output_path or (output_dir / self.brief.output_name)
        variants = list(style_variants or [])
        if len(variants) > 1:
            output_paths = [output_path_for_style(base_path, style) for style in variants]
        elif len(variants) == 1:
            output_paths = [output_path_for_style(base_path, variants[0])]
        else:
            output_paths = [base_path]
            variants = [None]

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
            f"overlays={len(self.layers)} caption groups={len(self.caption_groups)} "
            f"transitions={len(self.brief.transitions)} variants={len(output_paths)}"
        )

        reader = open_frame_reader(
            self.brief.video_path,
            self.brief.trim_start_seconds,
            self.brief.talk_duration_seconds,
            self.config_store,
        )
        writers = [
            open_frame_writer(path, audio_path, self.config_store)
            for path in output_paths
        ]
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
                composited = self.composite_talk_frame(raw_rgb, source_time_seconds)
                self.capture_outgoing_holds(composited, source_time_seconds)
                for writer, style in zip(writers, variants):
                    frame = self.finish_talk_frame(
                        composited, source_time_seconds, style_override=style
                    )
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
                payload = frame.tobytes()
                for writer in writers:
                    writer.stdin.write(payload)
            for writer in writers:
                writer.stdin.close()
            for writer, path in zip(writers, output_paths):
                writer_return_code = writer.wait()
                if writer_return_code != 0:
                    raise SystemExit(
                        f"ffmpeg writer failed for {path}: {writer_return_code}"
                    )
                print("wrote", path)
        finally:
            if reader.poll() is None:
                reader.kill()
            for writer in writers:
                if writer.poll() is None:
                    writer.kill()
        return output_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags for preview vs full encode.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Namespace with ``project``, ``preview``, ``full``, transition flags.
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
    parser.add_argument(
        "--output",
        default=None,
        help="mp4 destination (default: projects/<slug>/output/<filename>)",
    )
    parser.add_argument(
        "--transition-style",
        default=None,
        choices=TRANSITION_STYLE_NAMES,
        help="Override brief transition style for preview or a single encode",
    )
    parser.add_argument(
        "--transition-variants",
        default=None,
        help=(
            "Comma-separated styles to encode in one pass "
            f"(e.g. {','.join(TRANSITION_STYLE_NAMES)})"
        ),
    )
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
    variants = parse_transition_style_list(args.transition_variants)
    if args.transition_style and not variants:
        variants = [args.transition_style]
    pipeline = ReelComposePipeline(project_dir)
    print(
        f"{pipeline.brief.slug}: {len(pipeline.layers)} overlay layers, "
        f"{len(pipeline.caption_groups)} caption groups, "
        f"{len(pipeline.brief.transitions)} transitions"
    )
    if args.preview or not args.full:
        if variants:
            pipeline.run_preview_styles(variants)
        else:
            pipeline.run_preview()
    if args.full:
        output_path = Path(args.output) if args.output else None
        pipeline.run_full(output_path=output_path, style_variants=variants or None)


if __name__ == "__main__":
    main()
