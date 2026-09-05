# How to add a reel

One project folder per talking-head clip. The engine is brand-agnostic; Dra. Angélica is `brands/dra_angelica/`.

## 1. Folder

```text
projects/<slug>/
  brief.yaml          # or brief_sheet/*.csv → import_brief
  source/talking_head.mp4
  source/transcript.json   # from transcribe pipeline
  overlays/*.png
```

Copy `examples/ya_tienes/` as a starting point. Source `.mp4` is gitignored — drop it locally.

## 2. Brief

Prefer Angélica filling the [Google Sheet template](../../templates/angelica_brief/README.md), then:

```bash
conda activate angelica-website
python pipelines/import_brief.py \
  --csv-dir projects/<slug>/brief_sheet \
  --out projects/<slug>/brief.yaml
python scripts/check_brief.py --project projects/<slug>
```

Or edit `brief.yaml` directly (source-clock times).

## 3. Overlays

If PNGs have a black background:

```bash
python pipelines/prepare_overlays.py \
  --input-dir projects/<slug>/overlays_raw \
  --output-dir projects/<slug>/overlays
```

Filenames in the brief must match (`overlays/frutero_alto.png`).

## 4. Transcript

```bash
python pipelines/transcribe.py --project projects/<slug>
```

Add Whisper mistakes to `captions.asr_fix` (or the Correcciones tab).

## 5. Preview, then encode

```bash
python pipelines/reel_compose.py --project projects/<slug> --preview
python pipelines/reel_compose.py --project projects/<slug> --full
```

Preview JPEGs land in `projects/<slug>/frames/compose_preview/`. Adjust times in the brief and re-preview before `--full`.

## New brand

Copy `brands/dra_angelica/` to `brands/<id>/`, point `project.brand` at the new id, replace brush + endcard + colours.
