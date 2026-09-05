"""
Compose a 9:16 talking-head reel from a project brief.

Reads ``brief.yaml`` (source-clock timestamps, overlays, trim, ASR fixes),
composites stickers + karaoke captions onto scaled frames, fades to white,
and holds the brand endcard. Preview writes JPEGs; ``--full`` writes H.264.

See ``pipelines/reel_compose/pipeline_docu/README.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
sys.path.insert(0, str(_repo_root))

from modules.brief.brief_loader import ProjectBrief, load_brief
from modules.modules_initialiser import get_module
from modules.video.brand_style import load_brand_pack, make_endcard_frame
from modules.video.captions import draw_captions, load_caption_groups
from modules.video.ffmpeg_io import (
    grab_frame,
    open_frame_reader,
    open_frame_writer,
    prepare_audio,
)
from modules.video.overlays import OverlayLayer, build_overlay_layers, composite_overlay


class ReelComposePipeline:
    """Trim + overlay + caption + endcard compose for one project folder."""

    def __init__(self, project_dir: Path) -> None:
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
                self.brief.trim_start,
                self.brief.asr_fix,
            )

    def render_talk_frame(self, raw: bytes, source_t: float) -> np.ndarray:
        width = self.config_store.frame_width
        height = self.config_store.frame_height
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).copy()
        for layer in self.layers:
            composite_overlay(frame, layer, source_t)
        if self.caption_groups:
            draw_captions(
                frame,
                self.caption_groups,
                source_t,
                self.brand,
                self.config_store,
            )
        fade_start = self.brief.talk_end - self.brief.fade_white
        if source_t >= fade_start:
            u = min(1.0, (source_t - fade_start) / self.brief.fade_white)
            u = u * u * (3 - 2 * u)
            frame = (frame.astype(np.float32) * (1 - u) + 255.0 * u).astype(np.uint8)
        return frame

    def run_preview(self) -> Path:
        preview_dir = self.brief.preview_dir
        preview_dir.mkdir(parents=True, exist_ok=True)
        for label, source_t in self.brief.preview_shots.items():
            raw = grab_frame(self.brief.video_path, source_t, self.config_store)
            frame = self.render_talk_frame(raw, source_t)
            Image.fromarray(frame).save(
                preview_dir / f"{label}_{source_t:.2f}.jpg", quality=92
            )
            print(f"preview {label} source={source_t:.2f}s")
        Image.fromarray(
            make_endcard_frame(
                self.brand,
                self.config_store.frame_width,
                self.config_store.frame_height,
            )
        ).save(preview_dir / "endcard.jpg", quality=92)
        print("previews in", preview_dir)
        return preview_dir

    def run_full(self, out_path: Path | None = None) -> Path:
        out_dir = self.brief.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_path or (out_dir / self.brief.output_name)
        audio_path = out_dir / "audio_trim.wav"
        print("preparing audio…")
        prepare_audio(
            self.brief.video_path,
            audio_path,
            self.brief.trim_start,
            self.brief.talk_dur,
            self.brief.fade_white,
            self.brief.endcard_hold,
        )

        n_talk = int(round(self.brief.talk_dur * self.config_store.fps))
        n_end = int(round(self.brief.endcard_hold * self.config_store.fps))
        print(
            f"talk frames={n_talk} endcard frames={n_end} "
            f"overlays={len(self.layers)} caption groups={len(self.caption_groups)}"
        )

        reader = open_frame_reader(
            self.brief.video_path,
            self.brief.trim_start,
            self.brief.talk_dur,
            self.config_store,
        )
        writer = open_frame_writer(out_path, audio_path, self.config_store)
        endcard = make_endcard_frame(
            self.brand,
            self.config_store.frame_width,
            self.config_store.frame_height,
        )
        bytes_per = self.config_store.frame_width * self.config_store.frame_height * 3
        try:
            for i in range(n_talk):
                raw = reader.stdout.read(bytes_per)
                if len(raw) < bytes_per:
                    print(f"reader ended early at frame {i}")
                    break
                source_t = self.brief.trim_start + i / self.config_store.fps
                frame = self.render_talk_frame(raw, source_t)
                writer.stdin.write(frame.tobytes())
                if i % 90 == 0:
                    print(f"  talk {i}/{n_talk} orig={source_t:.2f}s")
            reader.stdout.close()
            reader.wait()

            for j in range(n_end):
                t = j / self.config_store.fps
                u = min(1.0, t / 0.35)
                u = u * u * (3 - 2 * u)
                frame = (
                    255.0 * (1 - u) + endcard.astype(np.float32) * u
                ).astype(np.uint8)
                writer.stdin.write(frame.tobytes())
            writer.stdin.close()
            rc = writer.wait()
            if rc != 0:
                raise SystemExit(f"ffmpeg writer failed: {rc}")
        finally:
            if reader.poll() is None:
                reader.kill()
            if writer.poll() is None:
                writer.kill()
        print("wrote", out_path)
        return out_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    args = parse_args(argv)
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = _repo_root / project_dir
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
