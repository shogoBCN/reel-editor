"""
Convert Angélica's spreadsheet (CSV folder or xlsx) into canonical ``brief.yaml``.

Google Sheets is the human editor: File → Download → CSV (or xlsx). Spanish
column names map onto the YAML schema so she never has to touch YAML.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from modules.brief.brief_loader import dump_brief_yaml
from modules.video.timing import parse_clock


PLACEMENT_MAP = {
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

KIND_MAP = {
    "sticker": "sticker",
    "imagen": "sticker",
    "png": "sticker",
    "etiqueta": "brush_label",
    "brush_label": "brush_label",
    "texto": "brush_label",
    "enfoque": "enfoque_lockup",
    "enfoque_lockup": "enfoque_lockup",
}


def _norm_header(name: str) -> str:
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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue
            rows.append(row)
        return rows


def _read_kv_csv(path: Path) -> dict[str, str]:
    """Two-column clave/valor sheet (proyecto tab)."""
    mapping: dict[str, str] = {}
    for row in _read_csv_rows(path):
        key = row.get("clave") or row.get("key") or row.get("campo")
        value = row.get("valor") or row.get("value") or row.get("dato")
        if key:
            mapping[_norm_header(key)] = value or ""
    return mapping


def _first_existing(folder: Path, names: list[str]) -> Path | None:
    for name in names:
        path = folder / name
        if path.is_file():
            return path
    return None


def _map_placement(raw: str) -> str:
    key = _norm_header(raw)
    if key not in PLACEMENT_MAP:
        raise ValueError(
            f"Unknown lado/placement {raw!r}. Use derecha, izquierda, or gancho."
        )
    return PLACEMENT_MAP[key]


def _map_kind(raw: str) -> str:
    key = _norm_header(raw) or "sticker"
    if key not in KIND_MAP:
        raise ValueError(
            f"Unknown tipo {raw!r}. Use sticker, etiqueta, or enfoque."
        )
    return KIND_MAP[key]


def overlays_from_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    overlays: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        overlay_id = row.get("id") or row.get("nombre") or f"overlay_{index}"
        start_raw = row.get("tiempo_inicio") or row.get("start") or row.get("desde")
        end_raw = row.get("tiempo_fin") or row.get("end") or row.get("hasta")
        if not start_raw or not end_raw:
            raise ValueError(f"Row {overlay_id}: missing tiempo_inicio / tiempo_fin")
        kind = _map_kind(row.get("tipo") or row.get("kind") or "sticker")
        overlay: dict[str, Any] = {
            "id": overlay_id,
            "kind": kind,
            "start": parse_clock(start_raw),
            "end": parse_clock(end_raw),
            "placement": _map_placement(row.get("lado") or row.get("placement") or "derecha"),
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
            overlay["font_size"] = int(float(row.get("tamano_fuente") or row["font_size"]))
        notes = row.get("notas_edicion") or row.get("notas") or row.get("que_es")
        if notes:
            overlay["notes"] = notes
        overlays.append(overlay)
    return overlays


def asr_fix_from_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    fixes: dict[str, str] = {}
    for row in rows:
        wrong = row.get("palabra_incorrecta") or row.get("whisper") or row.get("from")
        right = row.get("palabra_correcta") or row.get("correcto") or row.get("to")
        if wrong and right:
            fixes[wrong] = right
    return fixes


def brief_dict_from_csv_dir(csv_dir: Path) -> dict[str, Any]:
    """Build a brief mapping from a folder of Spanish CSV tabs."""
    csv_dir = csv_dir.resolve()
    proyecto_path = _first_existing(
        csv_dir,
        ["01_proyecto.csv", "proyecto.csv", "project.csv"],
    )
    imagenes_path = _first_existing(
        csv_dir,
        ["02_imagenes_y_tiempos.csv", "imagenes_y_tiempos.csv", "overlays.csv"],
    )
    correcciones_path = _first_existing(
        csv_dir,
        ["03_correcciones_transcripcion.csv", "correcciones.csv", "asr_fix.csv"],
    )
    notas_path = _first_existing(
        csv_dir,
        ["04_notas_edicion.csv", "notas.csv"],
    )
    if proyecto_path is None or imagenes_path is None:
        raise FileNotFoundError(
            f"{csv_dir} needs 01_proyecto.csv and 02_imagenes_y_tiempos.csv"
        )

    project_kv = _read_kv_csv(proyecto_path)
    overlays = overlays_from_rows(_read_csv_rows(imagenes_path))
    asr_fix = asr_fix_from_rows(_read_csv_rows(correcciones_path)) if correcciones_path else {}
    notes_rows = _read_csv_rows(notas_path) if notas_path else []
    notes = [
        f"{row.get('seccion') or 'general'}: {row.get('nota') or row.get('texto') or ''}".strip()
        for row in notes_rows
        if (row.get("nota") or row.get("texto"))
    ]

    slug = project_kv.get("slug") or csv_dir.parent.name
    return {
        "project": {
            "slug": slug,
            "title": project_kv.get("titulo") or project_kv.get("title") or slug,
            "brand": project_kv.get("marca") or project_kv.get("brand") or "dra_angelica",
            "language": project_kv.get("idioma") or "es",
        },
        "source": {
            "video": project_kv.get("video") or "source/talking_head.mp4",
            "transcript": project_kv.get("transcripcion") or "source/transcript.json",
            "overlays": "overlays",
            "trim_start": parse_clock(project_kv.get("cortar_inicio") or project_kv.get("trim_start") or 0),
            "talk_end": parse_clock(project_kv.get("fin_de_habla") or project_kv.get("talk_end")),
        },
        "output": {
            "filename": project_kv.get("archivo_salida") or f"{slug}.mp4",
            "fade_white": float(project_kv.get("fundido_blanco") or 0.70),
            "endcard_hold": float(project_kv.get("tarjeta_final") or 2.00),
        },
        "captions": {
            "enabled": (project_kv.get("subtitulos") or "si").lower() not in ("no", "false", "0"),
            "asr_fix": asr_fix,
        },
        "overlays": overlays,
        "notes": notes,
    }


def write_brief_from_csv_dir(csv_dir: Path, dest: Path | None = None) -> Path:
    """Convert a CSV folder to brief.yaml next to it (or at ``dest``)."""
    brief = brief_dict_from_csv_dir(csv_dir)
    if dest is None:
        dest = csv_dir.parent / "brief.yaml"
    dump_brief_yaml(brief, dest)
    return dest


def write_brief_from_xlsx(xlsx_path: Path, dest: Path | None = None) -> Path:
    """
    Convert a multi-sheet xlsx (same tabs as the CSV template) to brief.yaml.

    Requires openpyxl. Prefer CSV download from Google Sheets when openpyxl
    is not installed.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required to read .xlsx. "
            "Download each Google Sheet tab as CSV instead, or pip install openpyxl."
        ) from exc

    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    tmp_dir = xlsx_path.parent / ".sheet_csv_export"
    tmp_dir.mkdir(parents=True, exist_ok=True)

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
        key = _norm_header(sheet.title)
        if key in ("instrucciones", "como_usar", "readme"):
            continue
        filename = name_map.get(key)
        if filename is None:
            continue
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [_norm_header(str(h or "")) for h in rows[0]]
        out_path = tmp_dir / filename
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows[1:]:
                if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
                    continue
                writer.writerow(["" if cell is None else str(cell) for cell in row])
    dest = write_brief_from_csv_dir(tmp_dir, dest or xlsx_path.parent / "brief.yaml")
    return dest
