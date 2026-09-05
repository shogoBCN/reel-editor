"""
Build the Angélica-facing xlsx from the CSV template tabs.

One workbook is easier to File → Import into Google Sheets than four CSVs.
Run from repo root: python scripts/generate_template_xlsx.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [list(row) for row in csv.reader(handle)]


def generate_xlsx(dest: Path) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError as exc:
        raise ImportError("pip install openpyxl") from exc

    template_dir = _repo_root / "templates" / "angelica_brief"
    instructions = (template_dir / "README.md").read_text(encoding="utf-8")
    header_fill = PatternFill("solid", fgColor="068A93")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(wrap_text=True, vertical="top")

    workbook = Workbook()

    instr = workbook.active
    instr.title = "Instrucciones"
    instr["A1"] = instructions
    instr["A1"].alignment = Alignment(wrap_text=True, vertical="top")
    instr.column_dimensions["A"].width = 110
    instr.row_dimensions[1].height = 420

    tabs = [
        ("Proyecto", "01_proyecto.csv", 18, 40, 55),
        ("Imagenes_y_tiempos", "02_imagenes_y_tiempos.csv", 16, 14, 18),
        ("Correcciones", "03_correcciones_transcripcion.csv", 24, 24, 50),
        ("Notas_edicion", "04_notas_edicion.csv", 18, 80),
    ]
    for title, filename, *widths in tabs:
        rows = _read_csv(template_dir / filename)
        sheet = workbook.create_sheet(title)
        for r_i, row in enumerate(rows, start=1):
            for c_i, value in enumerate(row, start=1):
                cell = sheet.cell(r_i, c_i, value)
                cell.alignment = wrap
                if r_i == 1:
                    cell.fill = header_fill
                    cell.font = header_font
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for i, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(i)].width = width
        ## Remaining columns get a readable default.
        for col in range(len(widths) + 1, max(len(row) for row in rows) + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 22

    imagenes = workbook["Imagenes_y_tiempos"]
    tipo = DataValidation(
        type="list",
        formula1='"sticker,etiqueta,enfoque"',
        allow_blank=True,
    )
    tipo.error = "Usa sticker, etiqueta o enfoque"
    tipo.prompt = "sticker = PNG, etiqueta = pincel + texto, enfoque = lockup generado"
    imagenes.add_data_validation(tipo)
    tipo.add("D2:D200")

    lado = DataValidation(
        type="list",
        formula1='"derecha,izquierda,gancho"',
        allow_blank=True,
    )
    lado.error = "Usa derecha, izquierda o gancho"
    lado.prompt = "derecha/izquierda = al lado de la cabeza; gancho = cielo"
    imagenes.add_data_validation(lado)
    lado.add("G2:G200")

    dest.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(dest)
    return dest


def main() -> None:
    dest = _repo_root / "templates" / "angelica_brief" / "plantilla_reel_angelica.xlsx"
    path = generate_xlsx(dest)
    print("wrote", path)


if __name__ == "__main__":
    main()
