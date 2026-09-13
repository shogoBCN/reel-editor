"""Gemini-fill CapCut watermark, rebuild talking_head.mp4.

Dense Gemini for the fade-in wordmark (every frame through 4s), then 3 fills
per second with a 2-frame blend at each hold so the invented bark does not pop.
Trims the CapCut sting and muxes original audio.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.video.watermark_ai_fill import (  # noqa: E402
    composite_filled_crop,
    gemini_fill_crop,
    logo_crop,
)

TALK_END_SECONDS = 85.55
FRAMES_PER_SECOND = 30
DENSE_UNTIL_SECONDS = 4.0
SPARSE_FILLS_PER_SECOND = 3
BLEND_FRAMES = 0
HOLD_FILLS_PER_SECOND = 1.0
JPEG_QUALITY = 95


def extract_original_frames(video_path: Path, frames_dir: Path) -> list[Path]:
    """Decode talk frames once (skips if the folder is already populated).

    Args:
        video_path: CapCut original.
        frames_dir: Destination ``%06d.jpg``.

    Returns:
        Sorted frame paths.
    """
    frames_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(frames_dir.glob("*.jpg"))
    if existing:
        print(f"reusing {len(existing)} extracted frames", flush=True)
        return existing
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-t",
        f"{TALK_END_SECONDS:.3f}",
        "-q:v",
        "2",
        str(frames_dir / "%06d.jpg"),
    ]
    subprocess.check_call(command)
    return sorted(frames_dir.glob("*.jpg"))


def keyframe_indices(
    frame_count: int,
    dense_until_seconds: float = DENSE_UNTIL_SECONDS,
    sparse_fills_per_second: float = SPARSE_FILLS_PER_SECOND,
) -> list[int]:
    """Every frame through the wordmark fade, then 3/s, plus the last frame.

    Args:
        frame_count: Number of extracted talk frames.
        dense_until_seconds: Inclusive end of 30fps Gemini.
        sparse_fills_per_second: Gemini rate after the fade.

    Returns:
        Sorted 0-based frame indices to send to Gemini.
    """
    dense_last = min(frame_count - 1, int(round(dense_until_seconds * FRAMES_PER_SECOND)))
    keys = set(range(dense_last + 1))
    stride = max(1, int(round(FRAMES_PER_SECOND / sparse_fills_per_second)))
    index = dense_last
    while index < frame_count:
        keys.add(index)
        index += stride
    keys.add(frame_count - 1)
    return sorted(keys)


def hold_indices(frame_count: int, crops_dir: Path, holds_per_second: float) -> list[int]:
    """Reuse saved crops at 1/s (or ``holds_per_second``): first fill of each second, held.

    Snaps each second-boundary to the last existing crop at or before that frame
    so we never call Gemini again.

    Args:
        frame_count: Number of talk frames.
        crops_dir: Already-written crop PNGs.
        holds_per_second: How often to switch to the next saved fill.

    Returns:
        Sorted 0-based indices of crops to hold.
    """
    stride = max(1, int(round(FRAMES_PER_SECOND / holds_per_second)))
    wanted = list(range(0, frame_count, stride))
    if wanted[-1] != frame_count - 1:
        wanted.append(frame_count - 1)
    existing = [
        index
        for index in range(frame_count)
        if crop_path_for(crops_dir, index).is_file()
    ]
    keys: list[int] = []
    for target in wanted:
        before = [index for index in existing if index <= target]
        pick = before[-1] if before else None
        if pick is None:
            after = [index for index in existing if index >= target]
            pick = after[0] if after else None
        if pick is not None and (not keys or keys[-1] != pick):
            keys.append(pick)
    return keys


def crop_path_for(crops_dir: Path, frame_index: int) -> Path:
    """PNG path for a Gemini-filled 1:1 crop.

    Args:
        crops_dir: Crop folder.
        frame_index: 0-based frame number.

    Returns:
        ``%06d.png`` (ffmpeg frame numbers are 1-based, so +1).
    """
    return crops_dir / f"{frame_index + 1:06d}.png"


def _gemini_one_crop(
    source_path: Path,
    dest_path: Path,
    model_name: str | None,
) -> str:
    """Fill one keyframe crop. Resume-safe.

    Args:
        source_path: Original JPEG.
        dest_path: Filled crop PNG.
        model_name: Optional Gemini image model.

    Returns:
        ``ok``, ``skip``, or ``fail``.
    """
    if dest_path.exists():
        return "skip"
    frame = cv2.imread(str(source_path))
    if frame is None:
        raise RuntimeError(f"could not read {source_path}")
    try:
        filled = gemini_fill_crop(logo_crop(frame), model_name=model_name)
        cv2.imwrite(str(dest_path), filled)
        return "ok"
    except Exception as exc:
        print(f"  FAIL {source_path.name}: {exc}", flush=True)
        return "fail"


def fill_keyframes(
    source_paths: list[Path],
    keys: list[int],
    crops_dir: Path,
    workers: int,
    model_name: str | None,
) -> None:
    """Gemini-fill only the keyframe crops, in parallel.

    Args:
        source_paths: Extracted original frames.
        keys: 0-based indices to fill.
        crops_dir: Where to write crop PNGs.
        workers: Concurrent Gemini calls.
        model_name: Optional model override.
    """
    crops_dir.mkdir(parents=True, exist_ok=True)
    total = len(keys)
    done = 0
    skipped = 0
    failed = 0
    lock = threading.Lock()
    print(
        f"Gemini keyframes {total} "
        f"(dense 0–{DENSE_UNTIL_SECONDS:.1f}s, then {SPARSE_FILLS_PER_SECOND}/s) "
        f"workers={workers}",
        flush=True,
    )

    def work(frame_index: int) -> str:
        return _gemini_one_crop(
            source_paths[frame_index],
            crop_path_for(crops_dir, frame_index),
            model_name,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, index) for index in keys]
        for future in as_completed(futures):
            status = future.result()
            with lock:
                done += 1
                if status == "skip":
                    skipped += 1
                elif status == "fail":
                    failed += 1
                if done % 10 == 0 or done == total:
                    print(
                        f"progress {done}/{total} (skip={skipped} fail={failed})",
                        flush=True,
                    )


def _load_crop(crops_dir: Path, frame_index: int) -> np.ndarray | None:
    """Read a filled crop if Gemini succeeded for that keyframe.

    Args:
        crops_dir: Crop folder.
        frame_index: 0-based index.

    Returns:
        BGR crop, or None if missing.
    """
    image = cv2.imread(str(crop_path_for(crops_dir, frame_index)))
    return image


def _lerp_crops(first: np.ndarray, second: np.ndarray, alpha: float) -> np.ndarray:
    """Linear blend of two filled crops.

    Args:
        first: Hold crop.
        second: Next keyframe crop.
        alpha: 0 = first, 1 = second.

    Returns:
        BGR uint8 crop.
    """
    alpha = float(np.clip(alpha, 0.0, 1.0))
    mixed = first.astype(np.float32) * (1.0 - alpha) + second.astype(np.float32) * alpha
    return np.clip(mixed, 0, 255).astype(np.uint8)


def crop_for_frame(
    frame_index: int,
    keys: list[int],
    crops_dir: Path,
    crop_cache: dict[int, np.ndarray],
    blend_frames: int = BLEND_FRAMES,
) -> np.ndarray | None:
    """Hold the last chosen crop until the next hold key (no blend by default).

    Args:
        frame_index: 0-based output frame.
        keys: Sorted hold indices.
        crops_dir: Filled crops.
        crop_cache: Loaded BGR crops by index.
        blend_frames: Crossfade length; 0 = hard hold.

    Returns:
        Crop to paste, or None to leave the original pixels.
    """
    previous = [key for key in keys if key <= frame_index]
    if not previous:
        return None
    key_before = previous[-1]
    if key_before not in crop_cache:
        loaded = _load_crop(crops_dir, key_before)
        if loaded is None:
            return None
        crop_cache[key_before] = loaded
    crop_before = crop_cache[key_before]
    if blend_frames <= 0:
        return crop_before
    upcoming = [key for key in keys if key > frame_index]
    if not upcoming:
        return crop_before
    key_after = upcoming[0]
    frames_to_next = key_after - frame_index
    if frames_to_next > blend_frames:
        return crop_before
    if key_after not in crop_cache:
        loaded = _load_crop(crops_dir, key_after)
        if loaded is None:
            return crop_before
        crop_cache[key_after] = loaded
    alpha = 1.0 - (frames_to_next / (blend_frames + 1))
    return _lerp_crops(crop_before, crop_cache[key_after], alpha)


def composite_all_frames(
    source_paths: list[Path],
    keys: list[int],
    crops_dir: Path,
    dest_dir: Path,
) -> None:
    """Paste held/blended crops onto every original frame.

    Args:
        source_paths: Original JPEGs.
        keys: Gemini keyframes.
        crops_dir: Filled crops.
        dest_dir: Composited JPEGs for ffmpeg.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = len(source_paths)
    crop_cache: dict[int, np.ndarray] = {}
    print(f"compositing {total} frames with {len(keys)} held fills …", flush=True)
    for index, source_path in enumerate(source_paths):
        dest_path = dest_dir / source_path.name
        frame = cv2.imread(str(source_path))
        if frame is None:
            raise RuntimeError(f"could not read {source_path}")
        filled_crop = crop_for_frame(index, keys, crops_dir, crop_cache)
        if filled_crop is None:
            composited = frame
        else:
            composited = composite_filled_crop(frame, filled_crop)
        cv2.imwrite(str(dest_path), composited, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if (index + 1) % 200 == 0 or index + 1 == total:
            print(f"composite {index + 1}/{total}", flush=True)


def encode_talking_head(
    filled_dir: Path,
    original_video: Path,
    output_path: Path,
) -> None:
    """Encode filled JPEGs + original audio, trimmed to talk_end.

    Args:
        filled_dir: Sequential ``%06d.jpg``.
        original_video: Audio source.
        output_path: ``source/talking_head.mp4``.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(FRAMES_PER_SECOND),
        "-i",
        str(filled_dir / "%06d.jpg"),
        "-i",
        str(original_video),
        "-t",
        f"{TALK_END_SECONDS:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "16",
        "-preset",
        "medium",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_path),
    ]
    subprocess.check_call(command)
    print(f"talking_head written {output_path}", flush=True)


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Rebuild talking_head with Gemini fill.")
    parser.add_argument(
        "--project",
        default="projects/13-sept-26-cita-virtual-presencial",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--composite-only",
        action="store_true",
        help="Reuse saved crops; do not call Gemini.",
    )
    parser.add_argument(
        "--hold-fps",
        type=float,
        default=HOLD_FILLS_PER_SECOND,
        help="Switch to the next saved fill this many times per second (0 = every crop).",
    )
    args = parser.parse_args()
    project_dir = REPOSITORY_ROOT / args.project
    original = project_dir / "original_.mp4"
    work_dir = project_dir / "frames" / "wm_fill"
    source_paths = extract_original_frames(original, work_dir / "orig")
    gemini_keys = keyframe_indices(len(source_paths))
    if not args.composite_only:
        fill_keyframes(
            source_paths, gemini_keys, work_dir / "crops", args.workers, args.model
        )
    if args.hold_fps > 0:
        keys = hold_indices(len(source_paths), work_dir / "crops", args.hold_fps)
        print(
            f"holding {len(keys)} saved fills at {args.hold_fps:g}/s (no Gemini)",
            flush=True,
        )
    else:
        keys = gemini_keys
    composite_all_frames(source_paths, keys, work_dir / "crops", work_dir / "filled")
    encode_talking_head(
        work_dir / "filled",
        original,
        project_dir / "source" / "talking_head.mp4",
    )


if __name__ == "__main__":
    main()
