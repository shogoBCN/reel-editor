"""German ceremony → English burned-in subtitles, volume, start/end card.

Transcribes 16 kHz WAV in chunks (Gemini timeout cannot swallow 27 min in
one call), translates to English with speaker labels, writes an ASS file,
then muxes: white→card intro, ceremony with subs + loudnorm, card outro.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.gemini.transcribe import merge_transcripts, offset_transcript, transcribe_wav
from modules.modules_initialiser import get_module

SPEAKERS = ("Clerk", "Selina", "Marcin", "Clerk2")
CHUNK_SECONDS = 120.0
TRANSLATE_BATCH = 55
INTRO_FADE_IN = 1.2
INTRO_HOLD = 3.5
INTRO_FADE_OUT = 0.8
OUTRO_FADE_IN = 1.2
OUTRO_HOLD = 4.0
OUTRO_FADE_OUT = 1.5
VIDEO_FADE_TO_WHITE = 1.0
CANVAS_W = 1080
CANVAS_H = 1920


def _wav_duration_seconds(wav_path: Path) -> float:
    """Return duration of a WAV via ffprobe."""
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(wav_path),
        ],
        text=True,
    ).strip()
    return float(raw)


def _extract_chunk(src: Path, dest: Path, start: float, duration: float) -> None:
    """Cut a PCM window for one transcribe call."""
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(dest),
        ]
    )


def _retry_seconds_from_error(exc: BaseException) -> float:
    """Read Gemini's ``Please retry in Ns`` hint; default one minute."""
    match = re.search(r"retry in ([0-9.]+)s", str(exc), flags=re.IGNORECASE)
    if match:
        return max(15.0, float(match.group(1)) + 2.0)
    return 60.0


def _transcribe_wav_with_retry(
    wav_path: Path,
    language_codes: list[str],
    attempts: int = 8,
) -> dict[str, Any]:
    """Call Gemini transcribe; wait out 429 quota and retry."""
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return transcribe_wav(wav_path, language_codes=language_codes)
        except Exception as exc:
            last_error = exc
            name = type(exc).__name__
            quota = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            network = name in {
                "ReadError",
                "ConnectError",
                "RemoteProtocolError",
                "TimeoutException",
            } or "Broken pipe" in str(exc)
            if not (quota or network) or attempt == attempts:
                raise
            wait = _retry_seconds_from_error(exc) if quota else min(20.0 * attempt, 60.0)
            print(f"  {name} attempt {attempt}/{attempts}; sleep {wait:.0f}s")
            time.sleep(wait)
    raise last_error  # pragma: no cover


def transcribe_wav_chunked(
    wav_path: Path,
    language_codes: list[str],
    chunk_seconds: float = CHUNK_SECONDS,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Gemini-transcribe a long WAV as successive windows.

    Each window is written to ``cache_dir`` so a 429 can resume. The
    transcribe model is capped at 10k input tokens/min — we wait and retry.

    Args:
        wav_path: Full 16 kHz mono file.
        language_codes: BCP-47 hints (``de-DE`` for this ceremony).
        chunk_seconds: Window length; keep under the HTTP timeout.
        cache_dir: Optional folder for ``chunk_000.json`` resume files.

    Returns:
        Merged compact transcript on the source clock.
    """
    duration = _wav_duration_seconds(wav_path)
    parts: list[dict[str, Any]] = []
    start = 0.0
    index = 0
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="subs_chunks_") as tmp:
        tmp_dir = Path(tmp)
        while start < duration - 0.05:
            window = min(chunk_seconds, duration - start)
            cache_path = (
                cache_dir / f"chunk_{index:03d}.json" if cache_dir is not None else None
            )
            print(
                f"transcribe chunk {index + 1} "
                f"{start:.1f}–{start + window:.1f}s / {duration:.1f}s"
            )
            if cache_path is not None and cache_path.is_file():
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                print(f"  resume {cache_path.name}")
            else:
                chunk_path = tmp_dir / f"chunk_{index:03d}.wav"
                _extract_chunk(wav_path, chunk_path, start, window)
                data = offset_transcript(
                    _transcribe_wav_with_retry(
                        chunk_path, language_codes=language_codes
                    ),
                    start,
                )
                if cache_path is not None:
                    cache_path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                # Stay under ~4 two-minute windows per minute on this model.
                time.sleep(20)
            parts.append(data)
            start += window
            index += 1
    return merge_transcripts(parts)


def _seconds_to_ass(value: float) -> str:
    """ASS clock ``H:MM:SS.cc`` (centiseconds)."""
    if value < 0:
        value = 0.0
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    centis = int(round((value - math.floor(value)) * 100))
    if centis == 100:
        seconds += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def _ass_escape(text: str) -> str:
    """Escape ASS special characters."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def cues_to_ass(cues: list[dict[str, Any]], play_res: tuple[int, int]) -> str:
    """Build a bottom-centered ASS with a coloured speaker name.

    Args:
        cues: ``start``, ``end``, ``speaker``, ``text``.
        play_res: Output pixel size (portrait 1080×1920 here).

    Returns:
        Full ``.ass`` file text.
    """
    width, height = play_res
    header = f"""[Script Info]
Title: English ceremony subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,46,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3.2,0,2,70,70,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    colours = {
        "Clerk": "H7AA2D6",
        "Selina": "HD8A0B8",
        "Marcin": "H78C8A8",
        "Clerk2": "H6EC8FF",
    }
    lines = [header]
    for cue in cues:
        speaker = str(cue.get("speaker") or "Clerk").strip()
        if speaker not in SPEAKERS:
            speaker = "Clerk"
        body = _ass_escape(str(cue.get("text") or "").strip())
        if not body:
            continue
        body = body.replace("\n", "\\N")
        colour = colours.get(speaker, colours["Clerk"])
        text = f"{{\\b1\\c&{colour}&}}{speaker}{{\\b0\\c&H00FFFFFF&}}\\N{body}"
        lines.append(
            "Dialogue: 0,"
            f"{_seconds_to_ass(float(cue['start']))},"
            f"{_seconds_to_ass(float(cue['end']))},"
            f"Default,{speaker},0,0,0,,{text}\n"
        )
    return "".join(lines)


def _strip_json_fence(raw: str) -> str:
    """Pull a JSON array/object out of a model reply."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    start_obj = text.find("{")
    start_arr = text.find("[")
    if start_obj == -1 and start_arr == -1:
        raise ValueError("No JSON in model reply")
    if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
        return text[start_arr:]
    return text[start_obj:]


def _translate_batch(
    segments: list[dict[str, Any]],
    clerk_notes: str,
    batch_index: int,
    batch_count: int,
) -> list[dict[str, Any]]:
    """One Gemini pass: German timed lines → English speaker cues."""
    from google.genai import types

    config_store = get_module("config_store")
    client = get_module("gemini_client")
    payload = [
        {
            "start": round(float(seg["start"]), 2),
            "end": round(float(seg["end"]), 2),
            "de": str(seg.get("text") or "").strip(),
        }
        for seg in segments
        if str(seg.get("text") or "").strip()
    ]
    prompt = f"""You are subtitling a German civil wedding ceremony for English viewers.

Speakers (only these three names):
- Clerk — the registrar (Standesbeamter). Most of the talking.
- Selina — the bride.
- Marcin — the groom.

Return JSON only:
{{"cues":[{{"start":12.4,"end":16.1,"speaker":"Clerk","text":"Dear Selina, dear Marcin,"}}]}}

Rules:
- Translate what was actually SAID. The clerk notes below are a sense-check for the registrar's prepared speech only (already translated, incomplete, not 100% accurate). Prefer the German transcript when they disagree.
- English subtitles, natural spoken English, not stiff.
- speaker must be Clerk, Selina, or Marcin.
- Keep the given start/end times. You may merge 2 short German segments into one cue if they are the same speaker and under ~7s, or split a long segment into two cues.
- Max two lines per cue, about 42 characters per line. Use \\n between lines.
- Skip coughs, laughter without words, and off-mic chatter that is not one of the three speakers.
- German "Ja" as a vow answer → "I do."
- Batch {batch_index} of {batch_count}.

CLERK NOTES (partial, English):
{clerk_notes}

GERMAN SEGMENTS:
{json.dumps(payload, ensure_ascii=False)}
"""
    response = client.models.generate_content(
        model=config_store.gemini_text_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    raw = getattr(response, "text", None) or ""
    if not raw and getattr(response, "candidates", None):
        parts = getattr(response.candidates[0].content, "parts", None) or []
        raw = "".join(str(getattr(part, "text", "") or "") for part in parts)
    parsed = json.loads(_strip_json_fence(raw))
    cues = parsed.get("cues") if isinstance(parsed, dict) else parsed
    if not isinstance(cues, list):
        raise ValueError("Model did not return a cues list")
    cleaned: list[dict[str, Any]] = []
    for cue in cues:
        speaker = str(cue.get("speaker") or "Clerk").strip()
        if speaker not in SPEAKERS:
            speaker = "Clerk"
        text = str(cue.get("text") or "").replace("\\n", "\n").strip()
        if not text:
            continue
        cleaned.append(
            {
                "start": float(cue["start"]),
                "end": float(cue["end"]),
                "speaker": speaker,
                "text": text,
            }
        )
    return cleaned


def translate_transcript(
    transcript: dict[str, Any], clerk_notes: str
) -> list[dict[str, Any]]:
    """Translate every German segment in batches."""
    segments = [
        seg
        for seg in transcript.get("segments") or []
        if str(seg.get("text") or "").strip()
    ]
    cues: list[dict[str, Any]] = []
    batch_count = max(1, math.ceil(len(segments) / TRANSLATE_BATCH))
    for batch_index, offset in enumerate(range(0, len(segments), TRANSLATE_BATCH), start=1):
        batch = segments[offset : offset + TRANSLATE_BATCH]
        print(f"translate batch {batch_index}/{batch_count} ({len(batch)} segments)")
        cues.extend(
            _translate_batch(batch, clerk_notes, batch_index, batch_count)
        )
    cues.sort(key=lambda item: item["start"])
    return cues


def _probe_duration(path: Path) -> float:
    """Media duration in seconds."""
    return _wav_duration_seconds(path)


def mux_ceremony(
    video_path: Path,
    ass_path: Path,
    endcard_path: Path,
    output_path: Path,
    heart_path: Path | None = None,
) -> None:
    """Burn ASS, raise speech loudness, bookend with the same card.

    Intro: fade in from white onto the card, hold, fade to white.
    Then the ceremony (subs + loudnorm, last second fades to white).
    Outro: fade in the same card from white, hold, fade out.
    """
    duration = _probe_duration(video_path)
    intro = INTRO_FADE_IN + INTRO_HOLD + INTRO_FADE_OUT
    outro = OUTRO_FADE_IN + OUTRO_HOLD + OUTRO_FADE_OUT
    fade_start = max(0.0, duration - VIDEO_FADE_TO_WHITE)
    intro_fade_out_at = INTRO_FADE_IN + INTRO_HOLD
    outro_fade_out_at = OUTRO_FADE_IN + OUTRO_HOLD
    scale = (
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=decrease,"
        f"pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2:white,setsar=1"
    )
    # Escape ASS path for the subtitles filter (colons on macOS paths).
    ass_escaped = str(ass_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
    # Vow "I do" windows on the ceremony (source) clock — held long enough to read.
    marcin_do = (1075.8, 1080.8)
    selina_do = (1101.4, 1104.8)
    lived = "[main]"
    heart_filters = ""
    extra_inputs: list[str] = []
    if heart_path is not None and heart_path.is_file():
        extra_inputs = [
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(heart_path),
        ]
        # PNG already has alpha (hot-pink plate keyed out). One heart in the
        # ceiling gap above the couple — not over faces.
        heart_filters = (
            "[2:v]fps=30,format=rgba,scale=420:-1[ha];"
            f"[main][ha]overlay=150:60:enable='"
            f"between(t,{marcin_do[0]},{marcin_do[1]})+"
            f"between(t,{selina_do[0]},{selina_do[1]})'[lived];"
        )
        lived = "[lived]"
    filter_complex = (
        f"[1:v]{scale},split=2[carda][cardb];"
        f"[carda]loop=loop=-1:size=1:start=0,fps=30,trim=duration={intro:.3f},"
        f"setpts=PTS-STARTPTS,"
        f"fade=t=in:st=0:d={INTRO_FADE_IN:.3f}:color=white,"
        f"fade=t=out:st={intro_fade_out_at:.3f}:d={INTRO_FADE_OUT:.3f}:color=white[intro];"
        f"[0:v]{scale},fps=30,subtitles='{ass_escaped}',"
        f"fade=t=out:st={fade_start:.3f}:d={VIDEO_FADE_TO_WHITE:.3f}:color=white[main];"
        f"{heart_filters}"
        f"[cardb]loop=loop=-1:size=1:start=0,fps=30,trim=duration={outro:.3f},"
        f"setpts=PTS-STARTPTS,"
        f"fade=t=in:st=0:d={OUTRO_FADE_IN:.3f}:color=white,"
        f"fade=t=out:st={outro_fade_out_at:.3f}:d={OUTRO_FADE_OUT:.3f}[outro];"
        f"[intro]{lived}[outro]concat=n=3:v=1:a=0[v];"
        f"anullsrc=r=48000:cl=stereo,atrim=0:{intro:.3f},asetpts=PTS-STARTPTS[aintro];"
        f"[0:a]loudnorm=I=-16:TP=-1.5:LRA=11,"
        f"afade=t=out:st={fade_start:.3f}:d={VIDEO_FADE_TO_WHITE:.3f}[a0];"
        f"anullsrc=r=48000:cl=stereo,atrim=0:{outro:.3f},asetpts=PTS-STARTPTS[aoutro];"
        f"[aintro][a0][aoutro]concat=n=3:v=0:a=1[a]"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stats",
        "-i",
        str(video_path),
        "-loop",
        "1",
        "-framerate",
        "30",
        "-t",
        "20",
        "-i",
        str(endcard_path),
        *extra_inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    print("mux →", output_path)
    subprocess.check_call(command)


def _default_project_paths(project_dir: Path) -> dict[str, Path]:
    """Layout under ``projects/<slug>/``."""
    source = project_dir / "source"
    return {
        "wav": source / "audio_16k.wav",
        "video": source / "ceremony.mp4",
        "transcript": source / "transcript_de.json",
        "chunks": source / "transcribe_chunks",
        "cues": source / "cues_en.json",
        "notes": source / "clerk_notes_en.txt",
        "ass": project_dir / "subtitles" / "english.ass",
        "endcard": project_dir / "overlays" / "endcard.png",
        "heart": project_dir / "overlays" / "vow-heart.png",
        "output": project_dir / "output" / "selina-marcin-ceremony.mp4",
    }


def main() -> None:
    """CLI: ``--transcribe`` / ``--translate`` / ``--mux`` (default: all)."""
    parser = argparse.ArgumentParser(
        description="English ceremony subtitles + start/end card mux"
    )
    parser.add_argument("--project", required=True, help="Project folder")
    parser.add_argument("--transcribe", action="store_true")
    parser.add_argument("--translate", action="store_true")
    parser.add_argument("--mux", action="store_true")
    args = parser.parse_args()
    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = REPOSITORY_ROOT / project_dir
    run_all = not (args.transcribe or args.translate or args.mux)
    paths = _default_project_paths(project_dir)
    config_store = get_module("config_store")

    if run_all or args.transcribe:
        if not paths["wav"].is_file():
            raise FileNotFoundError(paths["wav"])
        data = transcribe_wav_chunked(
            paths["wav"],
            language_codes=config_store.gemini_transcribe_language_codes("de"),
            cache_dir=paths["chunks"],
        )
        paths["transcript"].write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("Saved", paths["transcript"], "segments", len(data.get("segments") or []))

    if run_all or args.translate:
        transcript = json.loads(paths["transcript"].read_text(encoding="utf-8"))
        notes = ""
        if paths["notes"].is_file():
            notes = paths["notes"].read_text(encoding="utf-8")
        cues = translate_transcript(transcript, notes)
        paths["cues"].write_text(
            json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        paths["ass"].parent.mkdir(parents=True, exist_ok=True)
        paths["ass"].write_text(
            cues_to_ass(cues, (CANVAS_W, CANVAS_H)), encoding="utf-8"
        )
        print("Saved", paths["ass"], "cues", len(cues))

    if run_all or args.mux:
        if not paths["video"].is_file():
            raise FileNotFoundError(paths["video"])
        mux_ceremony(
            paths["video"],
            paths["ass"],
            paths["endcard"],
            paths["output"],
            heart_path=paths["heart"],
        )


if __name__ == "__main__":
    main()
