"""
Word-timed Whisper transcription for a project talking-head clip.

Writes ``source/transcript.json`` in the compact ``w`` / ``s`` / ``e`` shape
``modules.video.captions`` reads. Language defaults to the brief (``es`` for
Dra. Angélica). Requires ``openai-whisper`` and ffmpeg. See ``pipelines/README.md``.
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
from modules.video.ffmpeg_io import extract_mono_wav_16k


def transcribe_project(project_dir: Path, model_name: str = "medium") -> Path:
    """Run Whisper with word timestamps and write ``transcript.json``.

    Corrections (lacena→alacena) are *not* applied here — they live in the
    brief so the raw transcript stays auditable.

    Args:
        project_dir: Folder with ``brief.yaml`` and a source video.
        model_name: Whisper size (``medium`` is the Spanish quality/speed trade).

    Returns:
        Path to the written JSON.

    Raises:
        ImportError: ``openai-whisper`` is not installed.
    """
    try:
        import whisper
    except ImportError as exc:
        raise ImportError(
            "openai-whisper is not installed in this environment. "
            "pip install openai-whisper  (conda env: angelica-website)"
        ) from exc

    brief = load_brief(project_dir)
    source_dir = brief.project_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    wav_path = source_dir / "audio_16k.wav"
    output_path = brief.transcript_path or (source_dir / "transcript.json")
    print(f"extracting 16 kHz wav → {wav_path}")
    extract_mono_wav_16k(brief.video_path, wav_path)
    print(f"loading Whisper {model_name}…")
    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(wav_path),
        language=brief.language,
        word_timestamps=True,
        verbose=True,
    )
    data = {"text": result.get("text", ""), "segments": []}
    for segment in result.get("segments", []):
        packed = {
            "start": round(segment["start"], 2),
            "end": round(segment["end"], 2),
            "text": str(segment["text"]).strip(),
            "words": [],
        }
        for word in segment.get("words") or []:
            packed["words"].append(
                {
                    "w": str(word.get("word", "")).strip(),
                    "s": round(float(word.get("start", 0)), 2),
                    "e": round(float(word.get("end", 0)), 2),
                }
            )
        data["segments"].append(packed)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== SEGMENTS ===")
    for packed in data["segments"]:
        print(f"{packed['start']:6.2f}-{packed['end']:6.2f}  {packed['text']}")
    print("Saved", output_path)
    return output_path


def main() -> None:
    """CLI entry: ``--project`` plus optional Whisper ``--model``."""
    parser = argparse.ArgumentParser(description="Whisper word timestamps for a reel project")
    parser.add_argument("--project", required=True, help="Project folder with brief.yaml")
    parser.add_argument("--model", default="medium", help="Whisper model size")
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = REPOSITORY_ROOT / project_dir
    transcribe_project(project_dir, args.model)


if __name__ == "__main__":
    main()
