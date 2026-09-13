"""Gemini-fill CapCut watermark stills from original_.mp4 (no full encode).

Writes side-by-side comparisons under ``frames/wm_ai/`` so we can judge fill
quality before spending API calls on every frame.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.video.watermark_ai_fill import (  # noqa: E402
    LOGO_H,
    LOGO_W,
    LOGO_X,
    LOGO_Y,
    fill_frame,
    logo_crop,
)


def grab_frame(video_path: Path, seconds: float) -> np.ndarray:
    """Decode one frame at ``seconds``.

    Args:
        video_path: Source mp4.
        seconds: Timestamp.

    Returns:
        BGR frame.

    Raises:
        RuntimeError: Seek or decode failed.
    """
    capture = cv2.VideoCapture(str(video_path))
    capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError(f"Could not read {video_path} at {seconds}s")
    return frame


def zoom_logo(frame_bgr: np.ndarray, scale: int = 4) -> np.ndarray:
    """Nearest-neighbour zoom of the logo box for inspection.

    Args:
        frame_bgr: Full frame.
        scale: Integer upscale.

    Returns:
        Zoomed BGR crop.
    """
    pad = 8
    y0 = max(0, LOGO_Y - pad)
    x0 = max(0, LOGO_X - pad)
    crop = frame_bgr[y0 : y0 + LOGO_H + pad * 2, x0 : x0 + LOGO_W + pad * 2]
    return cv2.resize(
        crop,
        (crop.shape[1] * scale, crop.shape[0] * scale),
        interpolation=cv2.INTER_NEAREST,
    )


def hstack_labeled(images: list[np.ndarray], labels: list[str]) -> np.ndarray:
    """Pad to a common height and stack with a caption bar.

    Args:
        images: BGR images (any size).
        labels: One label per image.

    Returns:
        Single comparison image.
    """
    height = max(image.shape[0] for image in images)
    width = max(image.shape[1] for image in images)
    bar = 36
    panels = []
    for image, label in zip(images, labels):
        canvas = np.full((height + bar, width, 3), 24, np.uint8)
        canvas[bar : bar + image.shape[0], : image.shape[1]] = image
        cv2.putText(
            canvas,
            label,
            (8, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        panels.append(canvas)
    return np.hstack(panels)


def run_stills(
    video_path: Path,
    output_dir: Path,
    timestamps: list[float],
    model_name: str | None,
) -> None:
    """Fill listed timestamps and write comparison JPEGs.

    Args:
        video_path: CapCut original (not the smeared talking_head).
        output_dir: ``frames/wm_ai``.
        timestamps: Seconds to sample.
        model_name: Optional Gemini image model override.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for seconds in timestamps:
        tag = f"{seconds:.1f}"
        print(f"filling t={tag}s …", flush=True)
        original = grab_frame(video_path, seconds)
        result = fill_frame(original, model_name=model_name)
        composited = result["composited"]
        filled_crop = result["filled_crop"]
        cv2.imwrite(str(output_dir / f"ai_{tag}_frame.jpg"), composited)
        cv2.imwrite(str(output_dir / f"ai_{tag}_crop.jpg"), filled_crop)
        comparison = hstack_labeled(
            [
                zoom_logo(original),
                zoom_logo(composited),
                logo_crop(original),
                filled_crop,
            ],
            ["orig zoom", "AI paste zoom", "orig patch", "Gemini patch"],
        )
        cv2.imwrite(str(output_dir / f"ai_{tag}_compare.jpg"), comparison)
        print(f"  wrote ai_{tag}_compare.jpg", flush=True)


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Gemini-fill watermark stills.")
    parser.add_argument(
        "--project",
        default="projects/13-sept-26-cita-virtual-presencial",
        help="Project folder relative to repo root.",
    )
    parser.add_argument(
        "--times",
        default="1.0,3.5,8.0,30.0",
        help="Comma-separated timestamps in seconds.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini image model override.",
    )
    args = parser.parse_args()
    project_dir = REPOSITORY_ROOT / args.project
    timestamps = [float(item.strip()) for item in args.times.split(",") if item.strip()]
    run_stills(
        project_dir / "original_.mp4",
        project_dir / "frames" / "wm_ai",
        timestamps,
        args.model,
    )


if __name__ == "__main__":
    main()
