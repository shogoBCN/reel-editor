"""
Turn Angélica's spreadsheet brief (CSV folder or xlsx) into ``brief.yaml``.

Google Sheets is the human format; YAML is what compose reads. Run this after
she sends a filled sheet, before ``reel_compose``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PIPELINE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = PIPELINE_DIRECTORY.parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.brief.sheet_import import write_brief_from_csv_dir, write_brief_from_xlsx


def main() -> None:
    """CLI entry: ``--csv-dir`` or ``--xlsx`` plus optional ``--out``."""
    parser = argparse.ArgumentParser(
        description="Convert CSV/xlsx brief tabs into brief.yaml"
    )
    parser.add_argument(
        "--csv-dir",
        help="Folder with 01_proyecto.csv, 02_imagenes_y_tiempos.csv, …",
    )
    parser.add_argument("--xlsx", help="Multi-sheet workbook matching the template")
    parser.add_argument(
        "--out",
        help="Destination brief.yaml (default: sibling of the sheet files)",
    )
    args = parser.parse_args()
    destination = Path(args.out) if args.out else None
    if args.xlsx:
        path = write_brief_from_xlsx(Path(args.xlsx), destination)
    elif args.csv_dir:
        path = write_brief_from_csv_dir(Path(args.csv_dir), destination)
    else:
        parser.error("Pass --csv-dir or --xlsx")
        return
    print("wrote", path)


if __name__ == "__main__":
    main()
