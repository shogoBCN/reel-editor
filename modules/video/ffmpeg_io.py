"""
FFmpeg pipes for talking-head frames, AAC/WAV audio, and H.264 output.

The compose loop is CPU-bound in Python (overlays + captions). FFmpeg only
does scale/fps decode, encode, and the audio fade/pad. Paths and CRF come
from ConfigStore so pipelines do not hardcode codec flags.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from config.config_store import ConfigStore


def grab_source_frame(
    source_path: Path,
    source_time_seconds: float,
    config_store: ConfigStore,
) -> bytes:
    """Seek-and-grab one RGB24 frame at the source clock.

    Used by ``--preview`` so we do not decode the whole clip for a dozen
    stills. ``-ss`` before ``-i`` is a fast (keyframe) seek — good enough
    for review JPEGs.

    Args:
        source_path: Talking-head file.
        source_time_seconds: Timestamp on that file.
        config_store: Target canvas size.

    Returns:
        Raw ``width * height * 3`` RGB bytes.

    Raises:
        subprocess.CalledProcessError: ffmpeg failed (missing file, no decoder).
    """
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{source_time_seconds:.3f}",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={config_store.frame_width}:{config_store.frame_height}:flags=lanczos",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    return subprocess.check_output(command)


def open_frame_reader(
    source_path: Path,
    trim_start_seconds: float,
    talk_duration_seconds: float,
    config_store: ConfigStore,
) -> subprocess.Popen:
    """Stream trimmed, scaled RGB frames for the full-encode path.

    Args:
        source_path: Talking-head file.
        trim_start_seconds: Drop this many seconds from the start.
        talk_duration_seconds: How long to keep after the trim.
        config_store: Canvas size and frame rate.

    Returns:
        Popen with RGB24 on ``stdout``. Caller must drain and ``wait()``.
    """
    video_filter = (
        f"scale={config_store.frame_width}:{config_store.frame_height}:flags=lanczos,"
        f"fps={config_store.frames_per_second}"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{trim_start_seconds:.3f}",
        "-t",
        f"{talk_duration_seconds:.3f}",
        "-i",
        str(source_path),
        "-vf",
        video_filter,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    return subprocess.Popen(command, stdout=subprocess.PIPE)


def open_frame_writer(
    output_path: Path,
    audio_path: Path,
    config_store: ConfigStore,
) -> subprocess.Popen:
    """H.264 + AAC muxer reading RGB24 on stdin.

    ``+faststart`` moves the moov atom to the front so Instagram can stream
    the upload. ``-shortest`` stops when video or audio ends — audio is
    padded to cover the endcard hold.

    Args:
        output_path: Destination ``.mp4``.
        audio_path: Trimmed/faded WAV from ``prepare_talk_audio``.
        config_store: Size, frame rate, CRF, audio bitrate.

    Returns:
        Popen with stdin expecting raw frames.
    """
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{config_store.frame_width}x{config_store.frame_height}",
        "-r",
        str(config_store.frames_per_second),
        "-i",
        "pipe:0",
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(config_store.video_constant_rate_factor),
        "-preset",
        "medium",
        "-c:a",
        "aac",
        "-b:a",
        config_store.audio_bitrate,
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_path),
    ]
    return subprocess.Popen(command, stdin=subprocess.PIPE)


def prepare_talk_audio(
    source_path: Path,
    output_wav: Path,
    trim_start_seconds: float,
    talk_duration_seconds: float,
    fade_to_white_seconds: float,
    endcard_hold_seconds: float,
) -> None:
    """Trim, fade out under the white flash, and pad silence for the endcard hold.

    Args:
        source_path: Talking-head file (audio track).
        output_wav: Destination WAV (48 kHz stereo).
        trim_start_seconds: Match the video trim.
        talk_duration_seconds: Match the video talk window.
        fade_to_white_seconds: Audio fade aligned with the picture fade.
        endcard_hold_seconds: Silence so the muxer has audio for the card.

    Raises:
        subprocess.CalledProcessError: ffmpeg failed.
    """
    fade_start = max(0.0, talk_duration_seconds - fade_to_white_seconds)
    audio_filter = (
        f"afade=t=out:st={fade_start:.3f}:d={fade_to_white_seconds:.3f},"
        f"apad=pad_dur={endcard_hold_seconds:.3f}"
    )
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{trim_start_seconds:.3f}",
        "-t",
        f"{talk_duration_seconds:.3f}",
        "-i",
        str(source_path),
        "-af",
        audio_filter,
        "-ar",
        "48000",
        "-ac",
        "2",
        str(output_wav),
    ]
    subprocess.check_call(command)


def extract_mono_wav_16k(source_path: Path, output_wav: Path) -> None:
    """Mono 16 kHz WAV for Gemini 3.5 Transcribe.

    The speech model accepts this PCM shape; we mix stereo talking-head
    files down here so we do not resample inside Python.

    Args:
        source_path: Talking-head file.
        output_wav: Destination WAV.

    Raises:
        subprocess.CalledProcessError: ffmpeg failed.
    """
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_wav),
    ]
    subprocess.check_call(command)
