# Import brief

Convert Angélica's spreadsheet (CSV folder or xlsx) into canonical `brief.yaml`.

**Entry:** [`import_brief.py`](../import_brief.py)

Google Sheets is the human editor; YAML is the machine contract. See [angelica_brief](../../../templates/angelica_brief/README.md).

```bash
conda activate angelica-website
python pipelines/import_brief/import_brief.py --csv-dir examples/ya_tienes/brief_sheet --out examples/ya_tienes/brief.yaml
python pipelines/import_brief/import_brief.py --xlsx templates/angelica_brief/plantilla_reel_angelica.xlsx --out /tmp/brief.yaml
```

Spanish headers (`tiempo_inicio`, `lado`, `tipo`) map to `start` / `placement` / `kind`. Unknown `lado` or `tipo` values fail closed.
