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


def grab_frame(
    source_path: Path,
    source_t: float,
    config_store: ConfigStore,
) -> bytes:
    """Seek-and-grab one RGB24 frame at the source clock."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{source_t:.3f}",
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
    return subprocess.check_output(cmd)


def open_frame_reader(
    source_path: Path,
    trim_start: float,
    talk_dur: float,
    config_store: ConfigStore,
) -> subprocess.Popen:
    """Stream trimmed, scaled RGB frames for the full-encode path."""
    vf = f"scale={config_store.frame_width}:{config_store.frame_height}:flags=lanczos,fps={config_store.fps}"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{trim_start:.3f}",
        "-t",
        f"{talk_dur:.3f}",
        "-i",
        str(source_path),
        "-vf",
        vf,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)


def open_frame_writer(
    out_path: Path,
    audio_path: Path,
    config_store: ConfigStore,
) -> subprocess.Popen:
    """H.264 + AAC muxer reading RGB24 on stdin."""
    cmd = [
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
        str(config_store.fps),
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
        str(config_store.video_crf),
        "-preset",
        "medium",
        "-c:a",
        "aac",
        "-b:a",
        config_store.audio_bitrate,
        "-movflags",
        "+faststart",
        "-shortest",
        str(out_path),
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def prepare_audio(
    source_path: Path,
    out_wav: Path,
    trim_start: float,
    talk_dur: float,
    fade_white: float,
    endcard_hold: float,
) -> None:
    """Trim, fade out under the white flash, and pad silence for the endcard hold."""
    fade_st = max(0.0, talk_dur - fade_white)
    af = (
        f"afade=t=out:st={fade_st:.3f}:d={fade_white:.3f},"
        f"apad=pad_dur={endcard_hold:.3f}"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{trim_start:.3f}",
        "-t",
        f"{talk_dur:.3f}",
        "-i",
        str(source_path),
        "-af",
        af,
        "-ar",
        "48000",
        "-ac",
        "2",
        str(out_wav),
    ]
    subprocess.check_call(cmd)


def extract_wav_16k(source_path: Path, out_wav: Path) -> None:
    """Mono 16 kHz WAV for Whisper."""
    cmd = [
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
        str(out_wav),
    ]
    subprocess.check_call(cmd)
