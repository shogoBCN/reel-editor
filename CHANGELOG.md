# Video editor change log

This change log records notable updates to the `video-editor` repository. Its purpose is to capture changes as we implement them so we can:

- Keep the team up to date in real time
- Consolidate updates into the main documentation in one pass
- Maintain a clear history for auditing and troubleshooting

### Scope

- Compose / transcribe / overlay-prep pipelines
- Brief schema (YAML) and Angélica sheet template
- Brand packs and canvas/safe-zone config
- Documentation updates

### How to record changes

Add an entry for every meaningful change as soon as it lands (or when opening the PR). Prefer small, frequent entries over large batched summaries.

- **Date**: YYYY-MM-DD
- **Author**: your name/handle
- **Area**: file(s) or module(s) touched
- **Type**: Add | Change | Fix | Remove | Docs | Infra
- **Description**: concise but specific
- **Rationale**: why this change was needed (if non-obvious)
- **Impact**: behavior, coverage, performance, or developer workflow implications
- **Links**: PR, or related docs

### Format

- Keep entries in reverse chronological order.
- Group under a version heading if applicable; otherwise use an "Unreleased" section at the top.
- Use short, scannable bullets; include links for traceability.

#### Entry template

```text
#### YYYY-MM-DD — Type — Short title
- Author: <name>
- Area: <path/to/file_or_module.py>
- Description: <what changed>
- Rationale: <why> (optional)
- Impact: <behavior/coverage/infra effects>
- Links: PR #<id> or doc link
```

---

### Logs

#### 2026-09-05 — Add — Jump-cut scene transitions (four styles)

- **Author:** Thorsten
- **Area:** `modules/video/transitions.py`, `pipelines/reel_compose.py`, `modules/brief/brief_loader.py`, `modules/video/ffmpeg_io.py`
- **Description:** Briefs can list `transitions:` windows (`start` / `cut` / `end` on the source clock). Compose mixes take A into take B with `fade_white`, `crossfade`, `slide_left`, or `roll_up`. `--transition-variants` encodes several styles in one decode pass. Accurate ffmpeg seek for hold frames. `scripts/test_transitions.py` covers mixers.
- **Rationale:** Talking-head jump cuts (pauses between takes) read as abrupt; the first cut on *A partir de los 40* needed a 0.6s mix, and we wanted a few looks without re-decoding.
- **Impact:** Existing briefs without `transitions:` are unchanged. Karaoke lines no longer stretch across a pause (max 0.28s hold), so jump-cut mixes do not split the previous sentence. New flag: `python pipelines/reel_compose.py --project … --full --transition-variants fade_white,crossfade,slide_left,roll_up`.
- **Links:** [pipelines](pipelines/README.md)

#### 2026-09-05 — Fix — Hint row no longer wipes «El reel empieza en»

- **Author:** Thorsten
- **Area:** `modules/brief/sheet_import.py`
- **Description:** Import only reads the three header cells for start/end. The Instrucciones-style hint also contains «empieza» and was overwriting `trim_start` with 0. Slugify now strips em-dashes (`ya_tienes_medicina_familiar`).
- **Rationale:** Smoke import of the filled «Ya tienes» workbook came back with `trim_start: 0`.
- **Impact:** `0:04` in the sheet maps to `source.trim_start: 4.0` again.

#### 2026-09-05 — Change — Brief marks where the reel starts; do not cut her file

- **Author:** Thorsten
- **Area:** `scripts/generate_template_xlsx.py`, `modules/brief/sheet_import.py`, `templates/angelica_brief/`, `.cursor/skills/angelica-reel-brief/`
- **Description:** Top cell is **El reel empieza en** (source-clock time, e.g. `0:04`), not “cut N seconds”. **Terminas de hablar** is when she stops talking. Source `mp4` stays uncut (she usually records 1–5s of pre-roll and tail). Compose still uses `trim_start` / `talk_end`.
- **Rationale:** Cutting the file first would invalidate every Desde/Hasta she wrote.
- **Impact:** Import accepts the new label and the old “Cortar al inicio”. Skill forbids trimming `talking_head.mp4`.
- **Links:** [Angélica brief](documentation/guides/angelica_brief.md) · [skill](.cursor/skills/angelica-reel-brief/SKILL.md)

#### 2026-09-05 — Change — Sheet times are ``1:29,5``; Instrucciones tab

- **Author:** Thorsten
- **Area:** `modules/video/timing.py`, `scripts/generate_template_xlsx.py`, `templates/angelica_brief/`
- **Description:** Angélica writes minutes:seconds with a comma for tenths (`1:29,5`, `10:25,5`). Not frames — karaoke captions are generated. Desde/Hasta cells are Excel **text** so `0:28` is not turned into a clock time. Workbook has a second tab, **Instrucciones**, from `00_instrucciones.txt`.
- **Rationale:** Frame timestamps are unused precision. A Spanish comma also stops Excel treating the cell as time-of-day.
- **Impact:** Import already accepted commas. Filled examples now show `0:05,5` instead of `0:05.50`. `python scripts/test_timing.py` covers the sheet format.
- **Links:** [Angélica brief](documentation/guides/angelica_brief.md) · [plantilla](templates/angelica_brief/README.md)

#### 2026-09-05 — Change — She describes sticker size in words; compose fits any paste

- **Author:** Thorsten
- **Area:** `modules/brief/sticker_size.py`, `modules/brief/sheet_import.py`, `modules/video/image_ops.py`, `modules/video/overlays.py`, `brands/dra_angelica/brand.yaml`, `templates/angelica_brief/`
- **Description:** «Qué quieres» can say **grande / mediano / chico** (also más chica, chiquito, no tan grande). Import maps that to `max_w`/`max_h`. She pastes any JPEG/PNG at any pixel size — Excel's cell thumbnail is ignored; compose contain-fits the file into the box. Default is mediano. Locked YAML that already has pixel sizes is unchanged.
- **Rationale:** She will not crop images to 480×340. How big it should *look* belongs in the same sentence as derecha/izquierda.
- **Impact:** New sheets get sizes without the agent inventing pixels. `python scripts/test_sticker_size.py` checks the word map.

#### 2026-09-05 — Change — Example «Ya tienes» Excel now reads as Angélica would fill it

- **Author:** Thorsten
- **Area:** `projects/31-aug-26-ya-tienes/brief_sheet/`, `examples/ya_tienes/brief_sheet/`, `scripts/generate_template_xlsx.py`
- **Description:** The sample workbook is the four-column plantilla (`Desde` / `Hasta` / `Foto` / `Qué quieres`). Each row describes the graphic in her words: what it is, which side of the head, when it appears in the story, and when a second photo is added on another overlapping row. Titles without photos (nombre, especialidad, ENFOQUE INTEGRAL) are spelled out. `notas_edicion` in the CSV twin is that same sentence so rebuilds stay in sync.
- **Rationale:** The previous file still had `Texto` / `Lado` / `Nota`, and photo rows were empty — a poor model for the sheet she actually fills.
- **Impact:** Import still infers placement from derecha / izquierda / arriba in «Qué quieres». Blank plantilla hint now mentions the two-row overlap rule.

#### 2026-09-05 — Change — Angélica's brief is a one-tab Excel; Cursor makes YAML

- **Author:** Thorsten
- **Area:** `templates/angelica_brief/`, `scripts/generate_template_xlsx.py`, `modules/brief/sheet_import.py`, `.cursor/skills/angelica-reel-brief/`
- **Description:** She fills `plantilla_reel_angelica.xlsx`: three cells at the top, then `Desde` / `Hasta` / `Foto` / `Qué quieres`. Photos paste in-cell; notes stay free Spanish. `import_brief.py --xlsx` extracts PNGs into `overlays/` and sketches YAML. Cursor amends that sketch to engine-ready `brief.yaml` (skill `angelica-reel-brief`). She does not fill `tipo`, `lado`, or pixel sizes.
- **Rationale:** A Drive folder of named files, plus engine vocabulary, was the hard part. The agent runs the pipelines.
- **Impact:** Import is a first pass only — do not compose until overlays match `examples/ya_tienes/brief.yaml`. Legacy CSV tabs remain the git-friendly twin.
- **Links:** [Angélica brief](documentation/guides/angelica_brief.md) · [plantilla](templates/angelica_brief/README.md) · [skill](.cursor/skills/angelica-reel-brief/SKILL.md)

#### 2026-09-05 — Add — Reusable reel-editor

- **Author:** Thorsten
- **Area:** `config/`, `modules/`, `pipelines/`, `brands/dra_angelica/`, `examples/ya_tienes/`, `auth/`, `documentation/`
- **Description:** Port the Dra. Angélica “Ya tienes” compose pipeline out of `dra-angelica-website` into a Locaria-shaped repo. Briefs drive timestamps and overlays; brand look lives in `brands/<id>/`. Entry scripts sit flat in `pipelines/` (`reel_compose.py`, `import_brief.py`, `transcribe.py`, `prepare_overlays.py`). Karaoke uses `gemini-3.5-transcribe` (word timestamps; `google-genai` instead of Whisper). API key in gitignored `auth/auth-config.json`; model IDs and AI Studio endpoint on `config_store`. Python names are spelled out; Google-style docstrings; onboarding in `documentation/guides/start_here.md`.
- **Rationale:** The locked reel was a one-off script. Next clips need the same engine. Gemini beat Whisper on *Ya tienes* (`alacena`, `elevada`, `revisé`, `WhatsApp`). Nested `pipelines/<name>/<name>.py` was heavier than this repo needs.
- **Impact:** New reels are a project folder + brief. `examples/ya_tienes` reproduces the locked overlay schedule (source clock, stickers beside the head, karaoke captions, full-frame endcard). Run `python pipelines/reel_compose.py …`. Copy the auth example before transcribe. On-disk YAML/JSON keys are unchanged (`asr_fix`, transcript `w`/`s`/`e`).
- **Links:** [README](README.md) · [Start here](documentation/guides/start_here.md) · [pipelines](pipelines/README.md) · [config_store](documentation/config/config_store.md) · [Gemini 3.5 Transcribe](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5-transcribe/)
