# Video editor

Reusable **9:16 talking-head reel** toolkit: trim, overlays, karaoke captions, white fade, brand endcard. Briefs are data (YAML or a Google Sheet); the engine does not hardcode a client schedule.

Dra. Angélica is the first brand pack (`brands/dra_angelica/`). The locked example is `examples/ya_tienes/`.

**Layout** follows Locaria conventions ([`adaptria_pulls`](https://github.com/Locaria/adaptria_pulls): `config/`, `modules/`, `pipelines/<name>/`, `documentation/`, `CHANGELOG.md`).

**Environment:** conda env `angelica-website` (Pillow, numpy, PyYAML, ffmpeg on PATH).

---

## Pipelines

| Area | Entry | Role |
|------|-------|------|
| Compose | [`reel_compose.py`](pipelines/reel_compose/reel_compose.py) | Brief → preview JPEGs or H.264 reel |
| Brief | [`import_brief.py`](pipelines/import_brief/import_brief.py) | Google Sheet CSV/xlsx → `brief.yaml` |
| Speech | [`transcribe.py`](pipelines/transcribe/transcribe.py) | Whisper word timestamps → `transcript.json` |
| Assets | [`prepare_overlays.py`](pipelines/prepare_overlays/prepare_overlays.py) | Key black backgrounds on PNG stickers |

## Quick start

```bash
conda activate angelica-website
python scripts/check_brief.py --project examples/ya_tienes
python pipelines/reel_compose/reel_compose.py --project examples/ya_tienes --preview
python pipelines/reel_compose/reel_compose.py --project examples/ya_tienes --full
```

Drop `examples/ya_tienes/source/talking_head.mp4` locally if it is missing (mp4 files are gitignored).

## Angélica's brief

She fills a **Google Sheet** (timestamps, image filenames, left/right, notes) — not a Word doc. Template and how-to: [`templates/angelica_brief/`](templates/angelica_brief/README.md). Workbook: [`plantilla_reel_angelica.xlsx`](templates/angelica_brief/plantilla_reel_angelica.xlsx).

Every time is the clock of **her original recording**. Opening silence is `cortar_inicio`. Images live in Drive/WhatsApp with filenames that match the sheet.

## Repository structure

```
video-editor/
├── config/config_store.py          # canvas, safe zones, paths
├── modules/modules_initialiser.py  # get_module("config_store")
├── modules/video/                  # timing, ffmpeg, overlays, captions, brand
├── modules/brief/                  # YAML loader + sheet → YAML
├── pipelines/reel_compose/
├── pipelines/import_brief/
├── pipelines/transcribe/
├── pipelines/prepare_overlays/
├── brands/dra_angelica/            # colours, brush, endcard
├── templates/angelica_brief/       # Spanish sheet template
├── examples/ya_tienes/             # locked production example
├── projects/                       # local reels (gitignored outputs)
├── documentation/
├── CHANGELOG.md
├── requirements.txt
└── runner.sh
```

## Documentation Links

| Category | Documentation | Description |
|----------|---------------|-------------|
| Getting started | [How to add a reel](documentation/guides/how_to_add_a_reel.md) | New project folder, brief, preview, encode |
| Brief | [Angélica brief](documentation/guides/angelica_brief.md) | Sheet vs YAML; clock rule |
| | [Plantilla (ES)](templates/angelica_brief/README.md) | Tabs, `tipo` / `lado`, what to send |
| Config | [config_store](documentation/config/config_store.md) | Canvas, safe zones, paths |
| Modules | [module_initialiser](documentation/modules/module_initialiser.md) | Singleton `get_module` |
| Pipelines | [reel_compose](pipelines/reel_compose/pipeline_docu/README.md) | Overlay + caption + endcard |
| | [import_brief](pipelines/import_brief/pipeline_docu/README.md) | CSV/xlsx → YAML |
| | [transcribe](pipelines/transcribe/pipeline_docu/README.md) | Whisper word timestamps |
| | [prepare_overlays](pipelines/prepare_overlays/pipeline_docu/README.md) | Key black PNG backgrounds |
| Example | [ya_tienes](examples/ya_tienes/README.md) | Locked Dra. Angélica reel |

**Change log:** [CHANGELOG.md](CHANGELOG.md)
