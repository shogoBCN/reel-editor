"""
Load a project brief (YAML canonical) and resolve paths relative to the project folder.

A brief is the machine contract: source-clock timestamps, overlay schedule,
trim points, speech-recognition corrections. Spreadsheet CSVs / xlsx are
converted into this shape by ``modules.brief.sheet_import`` before compose runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from modules.video.timing import parse_timestamp_to_seconds


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
    trim_start_seconds: float
    talk_end_seconds: float
    fade_to_white_seconds: float
    endcard_hold_seconds: float
    output_name: str
    captions_enabled: bool
    speech_recognition_corrections: dict[str, str]
    overlays: list[dict[str, Any]]
    preview_shots: dict[str, float]
    notes: list[str] = field(default_factory=list)

    @property
    def talk_duration_seconds(self) -> float:
        """Length of the talking-head segment after the opening trim.

        Returns:
            ``talk_end - trim_start`` in seconds.
        """
        return self.talk_end_seconds - self.trim_start_seconds

    @property
    def output_dir(self) -> Path:
        """Folder for the encoded mp4 and trimmed WAV.

        Returns:
            ``<project>/output``.
        """
        return self.project_dir / "output"

    @property
    def preview_dir(self) -> Path:
        """Folder for ``--preview`` JPEGs (gitignored).

        Returns:
            ``<project>/frames/compose_preview``.
        """
        return self.project_dir / "frames" / "compose_preview"


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    """Treat missing YAML sections as empty dicts; reject lists/scalars.

    Args:
        value: Raw YAML node.
        name: Field name for the error message.

    Returns:
        A dict (possibly empty).

    Raises:
        ValueError: The node exists but is not a mapping.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Brief field {name!r} must be a mapping")
    return value


def resolve_project_path(
    project_dir: Path, value: Any, *, required: bool
) -> Path | None:
    """Join a brief-relative path onto the project folder.

    Args:
        project_dir: Project root.
        value: Path string from YAML (or empty).
        required: If True, empty values raise.

    Returns:
        Absolute or project-relative ``Path``, or None when optional and empty.

    Raises:
        ValueError: Required path is missing.
    """
    if not value:
        if required:
            raise ValueError("Missing required path in brief")
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = project_dir / path
    return path


def normalise_overlay_row(row: dict[str, Any]) -> dict[str, Any]:
    """Parse overlay times and accept Spanish aliases from a raw sheet dump.

    Args:
        row: One overlay mapping from YAML.

    Returns:
        Copy with ``start`` / ``end`` as floats and ``kind`` / ``placement`` filled.

    Raises:
        ValueError: End is not after start, or timestamps cannot be parsed.
    """
    overlay = dict(row)
    overlay["start"] = parse_timestamp_to_seconds(
        row.get("start") if "start" in row else row.get("tiempo_inicio")
    )
    overlay["end"] = parse_timestamp_to_seconds(
        row.get("end") if "end" in row else row.get("tiempo_fin")
    )
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


def default_preview_shots(
    overlays: list[dict[str, Any]], talk_end_seconds: float
) -> dict[str, float]:
    """Build preview seek points from overlay midpoints plus the fade.

    Args:
        overlays: Normalised overlay rows.
        talk_end_seconds: Source-clock end of speech (for the fade still).

    Returns:
        Label → source-clock seconds.
    """
    shots: dict[str, float] = {}
    for row in overlays:
        midpoint = (float(row["start"]) + float(row["end"])) / 2.0
        shots[str(row["id"])] = midpoint
    shots["fade"] = max(0.0, talk_end_seconds - 0.3)
    return shots


def load_brief(project_dir: Path) -> ProjectBrief:
    """Load ``brief.yaml`` from a project folder.

    Args:
        project_dir: Folder that contains ``brief.yaml`` (and usually
            ``overlays/``, ``source/``).

    Returns:
        Resolved brief with absolute video path and parsed overlay times.

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
    parsed = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{brief_path} must be a YAML mapping")

    project = require_mapping(parsed.get("project"), "project")
    source = require_mapping(parsed.get("source"), "source")
    output = require_mapping(parsed.get("output"), "output")
    captions = require_mapping(parsed.get("captions"), "captions")

    slug = str(project.get("slug") or project_dir.name)
    brand_id = str(project.get("brand") or "dra_angelica")
    video_path = resolve_project_path(project_dir, source.get("video"), required=True)
    assert video_path is not None
    if not video_path.is_file():
        raise FileNotFoundError(
            f"Source video not found: {video_path}. "
            "Drop the talking-head file there (mp4 is gitignored)."
        )
    transcript_path = resolve_project_path(
        project_dir, source.get("transcript"), required=False
    )
    overlay_dir = resolve_project_path(
        project_dir, source.get("overlays") or "overlays", required=False
    )
    assert overlay_dir is not None

    trim_start_seconds = parse_timestamp_to_seconds(source.get("trim_start", 0))
    talk_end_seconds = parse_timestamp_to_seconds(source.get("talk_end"))
    if talk_end_seconds <= trim_start_seconds:
        raise ValueError("source.talk_end must be after source.trim_start")

    overlays_raw = parsed.get("overlays") or []
    if not isinstance(overlays_raw, list):
        raise ValueError("overlays must be a list")
    overlays = [normalise_overlay_row(row) for row in overlays_raw]

    preview_raw = parsed.get("preview") or {}
    if preview_raw:
        preview_shots = {
            str(label): parse_timestamp_to_seconds(timestamp)
            for label, timestamp in preview_raw.items()
        }
    else:
        preview_shots = default_preview_shots(overlays, talk_end_seconds)

    # On-disk key stays ``asr_fix`` so existing briefs/sheets keep working.
    corrections = captions.get("asr_fix") or {}
    corrections = {str(wrong): str(right) for wrong, right in corrections.items()}

    notes_raw = parsed.get("notes") or []
    if isinstance(notes_raw, str):
        notes = [notes_raw]
    else:
        notes = [str(item) for item in notes_raw]

    return ProjectBrief(
        project_dir=project_dir,
        slug=slug,
        title=str(project.get("title") or slug),
        brand_id=brand_id,
        language=str(project.get("language") or "es"),
        video_path=video_path,
        transcript_path=transcript_path,
        overlay_dir=overlay_dir,
        trim_start_seconds=trim_start_seconds,
        talk_end_seconds=talk_end_seconds,
        fade_to_white_seconds=float(output.get("fade_white", 0.70)),
        endcard_hold_seconds=float(output.get("endcard_hold", 2.00)),
        output_name=str(output.get("filename") or f"{slug}.mp4"),
        captions_enabled=bool(captions.get("enabled", True)),
        speech_recognition_corrections=corrections,
        overlays=overlays,
        preview_shots=preview_shots,
        notes=notes,
    )


def write_brief_yaml(brief: dict[str, Any], destination: Path) -> None:
    """Write a brief dict as UTF-8 YAML (used by sheet import).

    Args:
        brief: Mapping in the canonical schema.
        destination: ``brief.yaml`` path; parent dirs are created.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(
            brief,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
