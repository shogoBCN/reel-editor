"""
Word-timed Whisper transcription for a project talking-head clip.

Writes ``source/transcript.json`` in the shape ``modules.video.captions`` expects.
Language defaults to the brief (``es`` for Dra. Angélica). Requires the
``openai-whisper`` extra and ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
sys.path.insert(0, str(_repo_root))

from modules.brief.brief_loader import load_brief
from modules.video.ffmpeg_io import extract_wav_16k


def transcribe_project(project_dir: Path, model_name: str = "medium") -> Path:
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
    out_path = brief.transcript_path or (source_dir / "transcript.json")
    print(f"extracting 16 kHz wav → {wav_path}")
    extract_wav_16k(brief.video_path, wav_path)
    print(f"loading Whisper {model_name}…")
    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(wav_path),
        language=brief.language,
        word_timestamps=True,
        verbose=True,
    )
    data = {"text": result.get("text", ""), "segments": []}
    for seg in result.get("segments", []):
        segment = {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": str(seg["text"]).strip(),
            "words": [],
        }
        for word in seg.get("words") or []:
            segment["words"].append(
                {
                    "w": str(word.get("word", "")).strip(),
                    "s": round(float(word.get("start", 0)), 2),
                    "e": round(float(word.get("end", 0)), 2),
                }
            )
        data["segments"].append(segment)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SEGMENTS ===")
    for segment in data["segments"]:
        print(f"{segment['start']:6.2f}-{segment['end']:6.2f}  {segment['text']}")
    print("Saved", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Whisper word timestamps for a reel project")
    parser.add_argument("--project", required=True, help="Project folder with brief.yaml")
    parser.add_argument("--model", default="medium", help="Whisper model size")
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = _repo_root / project_dir
    transcribe_project(project_dir, args.model)


if __name__ == "__main__":
    main()
