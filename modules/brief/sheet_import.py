"""
Convert Angélica's spreadsheet (CSV folder or xlsx) into canonical ``brief.yaml``.

Google Sheets is the human editor: File → Download → CSV (or xlsx). Spanish
column names map onto the YAML schema so she never has to touch YAML.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from modules.brief.brief_loader import write_brief_yaml
from modules.video.timing import parse_timestamp_to_seconds


# Spanish sheet values → engine placement names.
PLACEMENT_BY_ALIAS = {
    "derecha": "right",
    "right": "right",
    "izquierda": "left",
    "left": "left",
    "centro": "hook_center",
    "center": "hook_center",
    "gancho": "hook_center",
    "hook": "hook_center",
    "hook_center": "hook_center",
}

KIND_BY_ALIAS = {
    "sticker": "sticker",
    "imagen": "sticker",
    "png": "sticker",
    "etiqueta": "brush_label",
    "brush_label": "brush_label",
    "texto": "brush_label",
    "enfoque": "enfoque_lockup",
    "enfoque_lockup": "enfoque_lockup",
}


def normalise_column_header(name: str) -> str:
    """Lowercase, unaccent, and snake_case a spreadsheet header.

    Args:
        name: Raw CSV/xlsx header (may include ``á`` / spaces).

    Returns:
        Stable key such as ``tiempo_inicio``.
    """
    return (
        str(name or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV (BOM-safe) into dicts keyed by normalised headers.

    Args:
        path: CSV file.

    Returns:
        Non-empty rows only (blank spreadsheet lines are skipped).
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {normalise_column_header(key): (value or "").strip() for key, value in raw.items() if key}
            if not any(row.values()):
                continue
            rows.append(row)
        return rows


def read_key_value_csv(path: Path) -> dict[str, str]:
    """Read the Proyecto tab (``clave`` / ``valor`` columns).

    Args:
        path: ``01_proyecto.csv``.

    Returns:
        Normalised key → value.
    """
    mapping: dict[str, str] = {}
    for row in read_csv_rows(path):
        key = row.get("clave") or row.get("key") or row.get("campo")
        value = row.get("valor") or row.get("value") or row.get("dato")
        if key:
            mapping[normalise_column_header(key)] = value or ""
    return mapping


def find_first_existing_file(folder: Path, names: list[str]) -> Path | None:
    """Return the first filename that exists in ``folder``.

    Args:
        folder: Directory to search.
        names: Candidate filenames in preference order.

    Returns:
        Path if found, else None.
    """
    for name in names:
        path = folder / name
        if path.is_file():
            return path
    return None


def map_placement_name(raw: str) -> str:
    """Translate Spanish ``lado`` values to engine placement names.

    Args:
        raw: Cell value (``derecha``, ``izquierda``, ``gancho``, …).

    Returns:
        ``right``, ``left``, or ``hook_center``.

    Raises:
        ValueError: Unknown value — fail closed so a typo does not silently
            default to the right slot.
    """
    key = normalise_column_header(raw)
    if key not in PLACEMENT_BY_ALIAS:
        raise ValueError(
            f"Unknown lado/placement {raw!r}. Use derecha, izquierda, or gancho."
        )
    return PLACEMENT_BY_ALIAS[key]


def map_overlay_kind(raw: str) -> str:
    """Translate Spanish ``tipo`` values to engine kind names.

    Args:
        raw: Cell value (``sticker``, ``etiqueta``, ``enfoque``, …).

    Returns:
        ``sticker``, ``brush_label``, or ``enfoque_lockup``.

    Raises:
        ValueError: Unknown value.
    """
    key = normalise_column_header(raw) or "sticker"
    if key not in KIND_BY_ALIAS:
        raise ValueError(
            f"Unknown tipo {raw!r}. Use sticker, etiqueta, or enfoque."
        )
    return KIND_BY_ALIAS[key]


def overlays_from_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert Imágenes_y_tiempos rows into YAML overlay mappings.

    Args:
        rows: Dicts from ``02_imagenes_y_tiempos.csv``.

    Returns:
        Overlay list for ``brief.yaml``.

    Raises:
        ValueError: Missing start/end, or unknown tipo/lado.
    """
    overlays: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        overlay_id = row.get("id") or row.get("nombre") or f"overlay_{index}"
        start_raw = row.get("tiempo_inicio") or row.get("start") or row.get("desde")
        end_raw = row.get("tiempo_fin") or row.get("end") or row.get("hasta")
        if not start_raw or not end_raw:
            raise ValueError(f"Row {overlay_id}: missing tiempo_inicio / tiempo_fin")
        kind = map_overlay_kind(row.get("tipo") or row.get("kind") or "sticker")
        overlay: dict[str, Any] = {
            "id": overlay_id,
            "kind": kind,
            "start": parse_timestamp_to_seconds(start_raw),
            "end": parse_timestamp_to_seconds(end_raw),
            "placement": map_placement_name(
                row.get("lado") or row.get("placement") or "derecha"
            ),
        }
        file_name = row.get("archivo_imagen") or row.get("archivo") or row.get("file")
        if file_name:
            overlay["file"] = f"overlays/{Path(file_name).name}"
        text = row.get("texto") or row.get("text")
        if text:
            overlay["text"] = text
        if row.get("ancho_max"):
            overlay["max_w"] = int(float(row["ancho_max"]))
        if row.get("alto_max"):
            overlay["max_h"] = int(float(row["alto_max"]))
        if row.get("tamano_fuente") or row.get("font_size"):
            overlay["font_size"] = int(
                float(row.get("tamano_fuente") or row["font_size"])
            )
        notes = row.get("notas_edicion") or row.get("notas") or row.get("que_es")
        if notes:
            overlay["notes"] = notes
        overlays.append(overlay)
    return overlays


def speech_corrections_from_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    """Convert the Correcciones tab into the ``asr_fix`` YAML map.

    Args:
        rows: Dicts from ``03_correcciones_transcripcion.csv``.

    Returns:
        Wrong word → correct word.
    """
    corrections: dict[str, str] = {}
    for row in rows:
        wrong = row.get("palabra_incorrecta") or row.get("whisper") or row.get("from")
        right = row.get("palabra_correcta") or row.get("correcto") or row.get("to")
        if wrong and right:
            corrections[wrong] = right
    return corrections


def brief_dict_from_csv_dir(csv_dir: Path) -> dict[str, Any]:
    """Build a brief mapping from a folder of Spanish CSV tabs.

    Args:
        csv_dir: Directory with ``01_proyecto.csv`` and ``02_imagenes_y_tiempos.csv``.

    Returns:
        Canonical brief dict (not yet written to disk).

    Raises:
        FileNotFoundError: Required tabs are missing.
    """
    csv_dir = csv_dir.resolve()
    project_path = find_first_existing_file(
        csv_dir, ["01_proyecto.csv", "proyecto.csv", "project.csv"]
    )
    images_path = find_first_existing_file(
        csv_dir,
        ["02_imagenes_y_tiempos.csv", "imagenes_y_tiempos.csv", "overlays.csv"],
    )
    corrections_path = find_first_existing_file(
        csv_dir,
        ["03_correcciones_transcripcion.csv", "correcciones.csv", "asr_fix.csv"],
    )
    notes_path = find_first_existing_file(
        csv_dir, ["04_notas_edicion.csv", "notas.csv"]
    )
    if project_path is None or images_path is None:
        raise FileNotFoundError(
            f"{csv_dir} needs 01_proyecto.csv and 02_imagenes_y_tiempos.csv"
        )

    project_fields = read_key_value_csv(project_path)
    overlays = overlays_from_rows(read_csv_rows(images_path))
    corrections = (
        speech_corrections_from_rows(read_csv_rows(corrections_path))
        if corrections_path
        else {}
    )
    notes_rows = read_csv_rows(notes_path) if notes_path else []
    notes = [
        f"{row.get('seccion') or 'general'}: {row.get('nota') or row.get('texto') or ''}".strip()
        for row in notes_rows
        if (row.get("nota") or row.get("texto"))
    ]

    slug = project_fields.get("slug") or csv_dir.parent.name
    return {
        "project": {
            "slug": slug,
            "title": project_fields.get("titulo") or project_fields.get("title") or slug,
            "brand": project_fields.get("marca") or project_fields.get("brand") or "dra_angelica",
            "language": project_fields.get("idioma") or "es",
        },
        "source": {
            "video": project_fields.get("video") or "source/talking_head.mp4",
            "transcript": project_fields.get("transcripcion") or "source/transcript.json",
            "overlays": "overlays",
            "trim_start": parse_timestamp_to_seconds(
                project_fields.get("cortar_inicio") or project_fields.get("trim_start") or 0
            ),
            "talk_end": parse_timestamp_to_seconds(
                project_fields.get("fin_de_habla") or project_fields.get("talk_end")
            ),
        },
        "output": {
            "filename": project_fields.get("archivo_salida") or f"{slug}.mp4",
            "fade_white": float(project_fields.get("fundido_blanco") or 0.70),
            "endcard_hold": float(project_fields.get("tarjeta_final") or 2.00),
        },
        "captions": {
            "enabled": (project_fields.get("subtitulos") or "si").lower()
            not in ("no", "false", "0"),
            "asr_fix": corrections,
        },
        "overlays": overlays,
        "notes": notes,
    }


def write_brief_from_csv_dir(csv_dir: Path, destination: Path | None = None) -> Path:
    """Convert a CSV folder to brief.yaml next to it (or at ``destination``).

    Args:
        csv_dir: Folder of Spanish CSV tabs.
        destination: Optional ``brief.yaml`` path.

    Returns:
        Path written.
    """
    brief = brief_dict_from_csv_dir(csv_dir)
    if destination is None:
        destination = csv_dir.parent / "brief.yaml"
    write_brief_yaml(brief, destination)
    return destination


def write_brief_from_xlsx(xlsx_path: Path, destination: Path | None = None) -> Path:
    """Convert a multi-sheet xlsx (same tabs as the CSV template) to brief.yaml.

    Requires openpyxl. Prefer CSV download from Google Sheets when openpyxl
    is not installed.

    Args:
        xlsx_path: Workbook matching the Angélica template.
        destination: Optional ``brief.yaml`` path.

    Returns:
        Path written.

    Raises:
        ImportError: openpyxl is missing.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required to read .xlsx. "
            "Download each Google Sheet tab as CSV instead, or pip install openpyxl."
        ) from exc

    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    # Reuse the CSV importer: dump each known tab, then parse as usual.
    export_dir = xlsx_path.parent / ".sheet_csv_export"
    export_dir.mkdir(parents=True, exist_ok=True)

    name_map = {
        "proyecto": "01_proyecto.csv",
        "project": "01_proyecto.csv",
        "imagenes_y_tiempos": "02_imagenes_y_tiempos.csv",
        "imagenes": "02_imagenes_y_tiempos.csv",
        "overlays": "02_imagenes_y_tiempos.csv",
        "correcciones_transcripcion": "03_correcciones_transcripcion.csv",
        "correcciones": "03_correcciones_transcripcion.csv",
        "notas_edicion": "04_notas_edicion.csv",
        "notas": "04_notas_edicion.csv",
    }
    for sheet in workbook.worksheets:
        key = normalise_column_header(sheet.title)
        if key in ("instrucciones", "como_usar", "readme"):
            continue
        filename = name_map.get(key)
        if filename is None:
            continue
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [normalise_column_header(str(header or "")) for header in rows[0]]
        out_path = export_dir / filename
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows[1:]:
                if row is None or all(
                    cell is None or str(cell).strip() == "" for cell in row
                ):
                    continue
                writer.writerow(["" if cell is None else str(cell) for cell in row])
    written = write_brief_from_csv_dir(
        export_dir, destination or xlsx_path.parent / "brief.yaml"
    )
    return written
