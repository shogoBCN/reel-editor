"""
Load a project brief (YAML canonical) and resolve paths relative to the project folder.

A brief is the machine contract: source-clock timestamps, overlay schedule,
trim points, ASR fixes. Spreadsheet CSVs / xlsx are converted into this shape
by ``modules.brief.sheet_import`` before compose runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from modules.video.timing import parse_clock


@dataclass
class ProjectBrief:
    """Fully resolved reel brief ready for compose / transcribe / preview."""

    project_dir: Path
    slug: str
    title: str
    brand_id: str
    language: str
    video_path: Path
    transcript_path: Path | None
    overlay_dir: Path
    trim_start: float
    talk_end: float
    fade_white: float
    endcard_hold: float
    output_name: str
    captions_enabled: bool
    asr_fix: dict[str, str]
    overlays: list[dict[str, Any]]
    preview_shots: dict[str, float]
    notes: list[str] = field(default_factory=list)

    @property
    def talk_dur(self) -> float:
        return self.talk_end - self.trim_start

    @property
    def output_dir(self) -> Path:
        return self.project_dir / "output"

    @property
    def preview_dir(self) -> Path:
        return self.project_dir / "frames" / "compose_preview"


def _as_mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Brief field {name!r} must be a mapping")
    return value


def _resolve_path(project_dir: Path, value: Any, *, required: bool) -> Path | None:
    if not value:
        if required:
            raise ValueError("Missing required path in brief")
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = project_dir / path
    return path


def _normalise_overlay(row: dict[str, Any]) -> dict[str, Any]:
    overlay = dict(row)
    overlay["start"] = parse_clock(row.get("start") if "start" in row else row.get("tiempo_inicio"))
    overlay["end"] = parse_clock(row.get("end") if "end" in row else row.get("tiempo_fin"))
    if overlay["end"] <= overlay["start"]:
        raise ValueError(
            f"Overlay {row.get('id', '?')}: end ({overlay['end']}) must be after start ({overlay['start']})"
        )
    kind = str(overlay.get("kind") or overlay.get("tipo") or "sticker")
    overlay["kind"] = kind
    placement = overlay.get("placement") or overlay.get("lado") or "right"
    overlay["placement"] = str(placement)
    if "id" not in overlay:
        overlay["id"] = overlay.get("archivo") or overlay.get("file") or kind
    return overlay


def _default_preview_shots(overlays: list[dict[str, Any]], talk_end: float) -> dict[str, float]:
    shots: dict[str, float] = {}
    for row in overlays:
        mid = (float(row["start"]) + float(row["end"])) / 2.0
        shots[str(row["id"])] = mid
    shots["fade"] = max(0.0, talk_end - 0.3)
    return shots


def load_brief(project_dir: Path) -> ProjectBrief:
    """
    Load ``brief.yaml`` from a project folder.

    Args:
        project_dir: Folder that contains ``brief.yaml`` (and usually ``overlays/``, ``source/``).

    Raises:
        FileNotFoundError: brief.yaml or required media is missing.
        ValueError: timestamps or structure are invalid.
    """
    project_dir = project_dir.resolve()
    brief_path = project_dir / "brief.yaml"
    if not brief_path.is_file():
        raise FileNotFoundError(
            f"No brief.yaml in {project_dir}. "
            "Copy templates/angelica_brief/ or examples/ya_tienes/brief.yaml."
        )
    raw = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{brief_path} must be a YAML mapping")

    project = _as_mapping(raw.get("project"), "project")
    source = _as_mapping(raw.get("source"), "source")
    output = _as_mapping(raw.get("output"), "output")
    captions = _as_mapping(raw.get("captions"), "captions")

    slug = str(project.get("slug") or project_dir.name)
    brand_id = str(project.get("brand") or "dra_angelica")
    video_path = _resolve_path(project_dir, source.get("video"), required=True)
    assert video_path is not None
    if not video_path.is_file():
        raise FileNotFoundError(
            f"Source video not found: {video_path}. "
            "Drop the talking-head file there (mp4 is gitignored)."
        )
    transcript_path = _resolve_path(project_dir, source.get("transcript"), required=False)
    overlay_dir = _resolve_path(project_dir, source.get("overlays") or "overlays", required=False)
    assert overlay_dir is not None

    trim_start = parse_clock(source.get("trim_start", 0))
    talk_end = parse_clock(source.get("talk_end"))
    if talk_end <= trim_start:
        raise ValueError("source.talk_end must be after source.trim_start")

    overlays_raw = raw.get("overlays") or []
    if not isinstance(overlays_raw, list):
        raise ValueError("overlays must be a list")
    overlays = [_normalise_overlay(row) for row in overlays_raw]

    preview_raw = raw.get("preview") or {}
    if preview_raw:
        preview_shots = {str(k): parse_clock(v) for k, v in preview_raw.items()}
    else:
        preview_shots = _default_preview_shots(overlays, talk_end)

    asr_fix = captions.get("asr_fix") or {}
    asr_fix = {str(k): str(v) for k, v in asr_fix.items()}

    notes_raw = raw.get("notes") or []
    if isinstance(notes_raw, str):
        notes = [notes_raw]
    else:
        notes = [str(n) for n in notes_raw]

    return ProjectBrief(
        project_dir=project_dir,
        slug=slug,
        title=str(project.get("title") or slug),
        brand_id=brand_id,
        language=str(project.get("language") or "es"),
        video_path=video_path,
        transcript_path=transcript_path if transcript_path and transcript_path.is_file() else transcript_path,
        overlay_dir=overlay_dir,
        trim_start=trim_start,
        talk_end=talk_end,
        fade_white=float(output.get("fade_white", 0.70)),
        endcard_hold=float(output.get("endcard_hold", 2.00)),
        output_name=str(output.get("filename") or f"{slug}.mp4"),
        captions_enabled=bool(captions.get("enabled", True)),
        asr_fix=asr_fix,
        overlays=overlays,
        preview_shots=preview_shots,
        notes=notes,
    )


def dump_brief_yaml(brief: dict[str, Any], dest: Path) -> None:
    """Write a brief dict as UTF-8 YAML (used by sheet import)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.safe_dump(
            brief,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
