# reel-editor

Reusable **9:16 talking-head reel** toolkit: trim, overlays, karaoke captions, white fade, brand endcard.

**New here?** Read [Start here](documentation/guides/start_here.md) first (two clocks, where files live, one command to preview).

Briefs are data. Angélica fills a one-tab Excel in her own words; Cursor turns that into `brief.yaml`. The engine does not hardcode a client schedule. Dra. Angélica is `brands/dra_angelica/`. The locked example is `examples/ya_tienes/`.

**Layout** follows Locaria conventions ([`adaptria_pulls`](https://github.com/Locaria/adaptria_pulls): `config/`, `modules/`, `pipelines/`, `documentation/`, `CHANGELOG.md`). Pipeline scripts sit flat in `pipelines/` with one combined [README](pipelines/README.md).

**Environment:** conda env `angelica-website`. Install: `pip install -r requirements.txt`. ffmpeg must be on `PATH`. Copy `auth/auth-config.example.json` to `auth/auth-config.json` and set `gemini.api_key` (needed for transcribe).

---

## Pipelines

| Area | Entry | Role |
|------|-------|------|
| Compose | [`reel_compose.py`](pipelines/reel_compose.py) | Brief → preview JPEGs or H.264 reel |
| Brief | [`import_brief.py`](pipelines/import_brief.py) | Her Excel (or legacy CSV) → first-pass `brief.yaml` |
| Speech | [`transcribe.py`](pipelines/transcribe.py) | Gemini 3.5 Transcribe → `transcript.json` |
| Assets | [`prepare_overlays.py`](pipelines/prepare_overlays.py) | Key black backgrounds on PNG stickers |

## Quick start

```bash
conda activate angelica-website
pip install -r requirements.txt
python scripts/check_brief.py --project examples/ya_tienes
python pipelines/reel_compose.py --project examples/ya_tienes --preview
python pipelines/reel_compose.py --project examples/ya_tienes --full
```

Drop `examples/ya_tienes/source/talking_head.mp4` locally if it is missing (mp4 files are gitignored).

## Angélica's brief

She fills a **one-tab Excel** (`Desde` / `Hasta` / `Foto` / `Qué quieres`) — photos pasted in cells, notes in Spanish. Template: [`templates/angelica_brief/`](templates/angelica_brief/README.md). Workbook: [`plantilla_reel_angelica.xlsx`](templates/angelica_brief/plantilla_reel_angelica.xlsx). Cursor maps that onto `brief.yaml` (skill: `.cursor/skills/angelica-reel-brief`).

Every time is the clock of **her original recording**. Opening silence is `cortar_inicio`.

## Repository structure

```
reel-editor/
├── config/config_store.py          # canvas, safe zones, paths, Gemini models
├── auth/auth-config.example.json   # copy to auth-config.json (API key)
├── modules/modules_initialiser.py  # get_module("config_store")
├── modules/gemini/                 # transcribe client (image/music later)
├── modules/video/                  # timing, ffmpeg, overlays, captions, brand
├── modules/brief/                  # YAML loader + sheet → YAML
├── pipelines/                    # entry scripts + README.md
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
| Getting started | [Start here](documentation/guides/start_here.md) | Two clocks, map of the repo, first commands |
| | [How to add a reel](documentation/guides/how_to_add_a_reel.md) | New project folder, brief, preview, encode |
| Brief | [Angélica brief](documentation/guides/angelica_brief.md) | Sheet vs YAML; clock rule |
| | [Plantilla (ES)](templates/angelica_brief/README.md) | One tab: times, photo, qué quieres |
| Config | [config_store](documentation/config/config_store.md) | Canvas, safe zones, paths |
| Modules | [module_initialiser](documentation/modules/module_initialiser.md) | Singleton `get_module` |
| Pipelines | [pipelines/README.md](pipelines/README.md) | import_brief, prepare_overlays, transcribe, reel_compose |
| Example | [ya_tienes](examples/ya_tienes/README.md) | Locked Dra. Angélica reel |

**Change log:** [CHANGELOG.md](CHANGELOG.md)

**Source:** [github.com/shogoBCN/reel-editor](https://github.com/shogoBCN/reel-editor)
