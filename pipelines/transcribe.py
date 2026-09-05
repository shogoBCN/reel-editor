"""Gemini 3.5 Transcribe for a project talking-head clip.

Writes ``source/transcript.json`` in the compact ``w`` / ``s`` / ``e`` shape
``modules.video.captions`` reads. Language comes from the brief (``es`` →
``es-419`` for Dra. Angélica). Requires ``google-genai``, ffmpeg, and
``auth/auth-config.json``. See ``pipelines/README.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.brief.brief_loader import load_brief
from modules.gemini.transcribe import transcribe_wav
from modules.modules_initialiser import get_module
from modules.video.ffmpeg_io import extract_mono_wav_16k


def transcribe_project(project_dir: Path, model_name: str | None = None) -> Path:
    """Extract 16 kHz audio and run Gemini with word timestamps.

    Corrections (lacena→alacena) are *not* applied here — they live in the
    brief so the raw transcript stays auditable.

    Args:
        project_dir: Folder with ``brief.yaml`` and a source video.
        model_name: Optional Gemini model override (default from config_store).

    Returns:
        Path to the written JSON.

    Raises:
        FileNotFoundError: Source video or ``auth/auth-config.json`` missing.
        ImportError: ``google-genai`` is not installed.
    """
    config_store = get_module("config_store")
    brief = load_brief(project_dir)
    source_dir = brief.project_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    wav_path = source_dir / "audio_16k.wav"
    output_path = brief.transcript_path or (source_dir / "transcript.json")
    language_codes = config_store.gemini_transcribe_language_codes(brief.language)
    model = model_name or config_store.gemini_transcribe_model
    print(f"extracting 16 kHz wav → {wav_path}")
    extract_mono_wav_16k(brief.video_path, wav_path)
    print(f"Gemini transcribe model={model} language={language_codes}")
    data = transcribe_wav(
        wav_path,
        language_codes=language_codes,
        model_name=model,
    )
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== SEGMENTS ===")
    for packed in data["segments"]:
        print(f"{packed['start']:6.2f}-{packed['end']:6.2f}  {packed['text']}")
    print("Saved", output_path)
    return output_path


def main() -> None:
    """CLI entry: ``--project`` plus optional Gemini ``--model``."""
    parser = argparse.ArgumentParser(
        description="Gemini 3.5 Transcribe word timestamps for a reel project"
    )
    parser.add_argument("--project", required=True, help="Project folder with brief.yaml")
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini transcribe model (default: config_store.gemini_transcribe_model)",
    )
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = REPOSITORY_ROOT / project_dir
    transcribe_project(project_dir, args.model)


if __name__ == "__main__":
    main()
