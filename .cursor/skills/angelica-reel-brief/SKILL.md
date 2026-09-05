---
name: angelica-reel-brief
description: >-
  Turns Dra. Angélica's informal brief (Excel, Spanish notes, or a messy
  script) into engine-ready brief.yaml, then transcribes, previews, and
  composes the reel. Use when she sends a filled xlsx, a plantilla, BRIEF_Angelica,
  times plus photos, or asks to make / import / amend a reel from her notes.
---

# Angélica brief → reel

She writes **natural language**. You produce `brief.yaml` and run the pipelines. Do not send engine fields back to her (`kind`, `placement`, `max_w`, `tipo`, filenames).

## Two layers

| Who | File | What |
|-----|------|------|
| Angélica | `BRIEF_Angelica_*.xlsx` (Brief + Instrucciones; Desde / Hasta / Foto / Qué quieres) | Times on **her original video** as `1:29,5` (not frames), photos pasted in cells, Spanish as she talks |
| Engine | `projects/<slug>/brief.yaml` | `kind`, `placement`, overlay paths, sizes, trim, captions, `preview` |

`import_brief.py` is a **sketch** (times + extracted PNGs + notes). You **amend** YAML to match `examples/ya_tienes/brief.yaml` before compose.

If she sends a Doc, voice-note transcript, or paragraph script instead of the xlsx, still build the same YAML. Prefer the Excel when it exists.

## Environment

Run every pipeline inside conda env **`angelica-website`**. Activate before the first `python` call:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate angelica-website
```

`./runner.sh pipelines/<script>.py …` does the same activate. `ffmpeg` must be on `PATH`.

### Auth (you must remind the user)

The agent cannot finish a browser login. Before **transcribe** (and any later Gemini/Vertex call), check:

1. `auth/auth-config.json` exists with a real `gemini.api_key` (copy `auth/auth-config.example.json`; never commit the key).
2. Google Cloud user credentials are valid.

If auth is missing, expired, or a Google call returns 401/403/unauthenticated, **stop** and tell the user to run these in **their** terminal (interactive):

```bash
gcloud auth login
gcloud auth application-default login
```

Do not retry in a loop waiting for them. After they confirm login, continue.

## New reel

1. Activate `angelica-website` (and remind the user about `gcloud auth login` if transcribe will run).
2. `projects/<slug>/` with `source/talking_head.mp4` **uncut** (her file as recorded) and `overlays/`.
3. Save her workbook as `projects/<slug>/BRIEF_Angelica.xlsx`.
4. First pass:
   ```bash
   python pipelines/import_brief.py --xlsx projects/<slug>/BRIEF_Angelica.xlsx --out projects/<slug>/brief.yaml
   ```
5. Read every «Qué quieres» cell (also in overlay `notes`). Rewrite overlays: kinds, placements, `file` names, `font_size`, `preview` midpoints. Keep inferred `max_w`/`max_h` unless a sticker looks wrong in preview.
6. `python pipelines/transcribe.py --project projects/<slug>`
7. `python scripts/check_brief.py --project projects/<slug>`
8. `python pipelines/reel_compose.py --project projects/<slug> --preview`
9. `--full` only after previews look right.

## Reading «Qué quieres»

Messy Spanish is expected. Map it; do not make her rewrite.

- Photo in the row → `kind: sticker`, `file: overlays/<name>.png`. Rename `foto_7.png` to a Spanish stem (`frutero_alto.png`) from the note. She may paste a JPEG or a huge Google image; import saves a PNG and compose fits it in the box.
- Size words in «Qué quieres»: **grande** → 480×340, **mediano** (default, or «no tan grande») → 400×340, **chico** / pequeño / chiquito / más chica → 320×260. Do not ask her for `max_w`. Override in YAML only if preview looks wrong.
- No photo + her name / “Dra. Angélica” → `brush_label`, `hook_center`, `font_size: 72`.
- No photo + “Medicina Familiar” → `brush_label`, `hook_center`, `font_size: 66`, right after the name.
- No photo + “enfoque integral” / bio-psico-social → `enfoque_lockup`, `hook_center`. No PNG.
- “derecha” / “a la derecha” → `right`. “izquierda” → `left`. “arriba” / “cielo” / “gancho” → `hook_center`.
- “se suma” / “también” / two things at once = two overlays that overlap (frutero right + susto left). Same PNG may appear twice (susto).
- Endcard / WhatsApp card: never in her table; brand pack adds it after `talk_end`.

Times are **source clock** (her original file, including pre-roll). She writes ``0:04``, ``1:29,5``, ``10:25,5`` (minutes:seconds, tenths with a comma). Not frames — captions come from Gemini.

**Do not cut the source mp4.** She usually hits record 1–5s before speaking and leaves 1–5s after. Copy `talking_head.mp4` as she sent it. “El reel empieza en” → `source.trim_start`. “Terminas de hablar” → `source.talk_end`. Overlay Desde/Hasta stay on that same clock. If you trim the file first, every time she wrote is wrong.

Final reel time = source − trim_start. Do not retune against the published Instagram file.

## Locked compose (do not regress)

- Stickers **beside** the head, never on the hat.
- Captions on the coat, shared baseline. Keep `captions.asr_fix` even if Gemini is clean.
- Brand `dra_angelica`. Canvas from `get_module("config_store")`.
- Gold: `examples/ya_tienes/brief.yaml`.

## Blank template

`templates/angelica_brief/plantilla_reel_angelica.xlsx` — one tab, four columns. Rebuild with `python scripts/generate_template_xlsx.py`.
