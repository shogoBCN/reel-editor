# How to add a reel

One project folder per talking-head clip. The engine is brand-agnostic; Dra. Angélica is `brands/dra_angelica/`.

## 1. Folder

```text
projects/<slug>/
  BRIEF_Angelica.xlsx # what she fills (times, pasted photos, Spanish notes)
  brief.yaml          # engine brief (Cursor amends after import)
  source/talking_head.mp4
  source/transcript.json   # from transcribe pipeline
  overlays/*.png      # extracted from the sheet, then renamed
```

Copy `examples/ya_tienes/` as a starting point. Source `.mp4` is gitignored — drop it locally.

## 2. Brief

She fills the [one-tab Excel](../../templates/angelica_brief/README.md) (`Desde` / `Hasta` / `Foto` / `Qué quieres`). Photos can be any pixel size; she describes **grande / mediano / chico**. Import is a sketch; amend YAML to match `examples/ya_tienes/brief.yaml` (skill `.cursor/skills/angelica-reel-brief`):

```bash
conda activate angelica-website
python pipelines/import_brief.py \
  --xlsx projects/<slug>/BRIEF_Angelica.xlsx \
  --out projects/<slug>/brief.yaml
python scripts/check_brief.py --project projects/<slug>
```

Times in YAML are source clock.

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

Copy `auth/auth-config.example.json` to `auth/auth-config.json` first. Add leftover ASR mistakes to `captions.asr_fix` if Gemini still misses a homophone.

## 5. Preview, then encode

```bash
python pipelines/reel_compose.py --project projects/<slug> --preview
python pipelines/reel_compose.py --project projects/<slug> --full
```

Preview JPEGs land in `projects/<slug>/frames/compose_preview/`. Adjust times in the brief and re-preview before `--full`.

## New brand

Copy `brands/dra_angelica/` to `brands/<id>/`, point `project.brand` at the new id, replace brush + endcard + colours.
