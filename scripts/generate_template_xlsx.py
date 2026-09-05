"""
Build the Angélica-facing xlsx from the CSV template tabs.

One workbook is easier to File → Import into Google Sheets than four CSVs.
Run from repo root: python scripts/generate_template_xlsx.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))


def read_csv_matrix(path: Path) -> list[list[str]]:
    """Load a CSV as a list of rows (including the header).

    Args:
        path: UTF-8 CSV (BOM-safe).

    Returns:
        Rows of string cells.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [list(row) for row in csv.reader(handle)]


def generate_xlsx(destination: Path) -> Path:
    """Write the multi-tab workbook with dropdowns for ``tipo`` and ``lado``.

    Args:
        destination: ``plantilla_reel_angelica.xlsx``.

    Returns:
        Path written.

    Raises:
        ImportError: openpyxl is missing.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError as exc:
        raise ImportError("pip install openpyxl") from exc

    template_dir = REPOSITORY_ROOT / "templates" / "angelica_brief"
    instructions = (template_dir / "README.md").read_text(encoding="utf-8")
    header_fill = PatternFill("solid", fgColor="068A93")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(wrap_text=True, vertical="top")

    workbook = Workbook()

    instructions_sheet = workbook.active
    instructions_sheet.title = "Instrucciones"
    instructions_sheet["A1"] = instructions
    instructions_sheet["A1"].alignment = Alignment(wrap_text=True, vertical="top")
    instructions_sheet.column_dimensions["A"].width = 110
    instructions_sheet.row_dimensions[1].height = 420

    tabs = [
        ("Proyecto", "01_proyecto.csv", 18, 40, 55),
        ("Imagenes_y_tiempos", "02_imagenes_y_tiempos.csv", 16, 14, 18),
        ("Correcciones", "03_correcciones_transcripcion.csv", 24, 24, 50),
        ("Notas_edicion", "04_notas_edicion.csv", 18, 80),
    ]
    for title, filename, *widths in tabs:
        rows = read_csv_matrix(template_dir / filename)
        sheet = workbook.create_sheet(title)
        for row_index, row in enumerate(rows, start=1):
            for column_index, value in enumerate(row, start=1):
                cell = sheet.cell(row_index, column_index, value)
                cell.alignment = wrap
                if row_index == 1:
                    cell.fill = header_fill
                    cell.font = header_font
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column_index, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(column_index)].width = width
        # Remaining columns get a readable default so notes are not cramped.
        for column in range(len(widths) + 1, max(len(row) for row in rows) + 1):
            sheet.column_dimensions[get_column_letter(column)].width = 22

    images_sheet = workbook["Imagenes_y_tiempos"]
    kind_validation = DataValidation(
        type="list",
        formula1='"sticker,etiqueta,enfoque"',
        allow_blank=True,
    )
    kind_validation.error = "Usa sticker, etiqueta o enfoque"
    kind_validation.prompt = "sticker = PNG, etiqueta = pincel + texto, enfoque = lockup generado"
    images_sheet.add_data_validation(kind_validation)
    kind_validation.add("D2:D200")

    side_validation = DataValidation(
        type="list",
        formula1='"derecha,izquierda,gancho"',
        allow_blank=True,
    )
    side_validation.error = "Usa derecha, izquierda o gancho"
    side_validation.prompt = "derecha/izquierda = al lado de la cabeza; gancho = cielo"
    images_sheet.add_data_validation(side_validation)
    side_validation.add("G2:G200")

    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    return destination


def main() -> None:
    """Write ``templates/angelica_brief/plantilla_reel_angelica.xlsx``."""
    destination = (
        REPOSITORY_ROOT / "templates" / "angelica_brief" / "plantilla_reel_angelica.xlsx"
    )
    path = generate_xlsx(destination)
    print("wrote", path)


if __name__ == "__main__":
    main()
