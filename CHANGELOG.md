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

#### 2026-09-05 — Change — Brief sheet is Excel; images go in the workbook

- **Author:** Thorsten
- **Area:** `templates/angelica_brief/`, `scripts/generate_template_xlsx.py`, `modules/brief/sheet_import.py`
- **Description:** Angélica's brief is `plantilla_reel_angelica.xlsx` (Excel; also opens in Google Sheets). New `imagen` column: paste PNG in-cell. Import extracts those pictures into `overlays/`.
- **Rationale:** Asking her for a separate Drive folder of named files was the hard part; the sheet already has one row per sticker.
- **Impact:** `python pipelines/import_brief.py --xlsx path/to/reel.xlsx --out projects/<slug>/brief.yaml` writes YAML and overlay PNGs. CSV tabs remain the git-friendly twin.
- **Links:** [Angélica brief](documentation/guides/angelica_brief.md) · [plantilla](templates/angelica_brief/README.md)

#### 2026-09-05 — Change — Gemini 3.5 Transcribe replaces Whisper

- **Author:** Thorsten
- **Area:** `pipelines/transcribe.py`, `modules/gemini/`, `config/config_store.py`, `auth/`, `requirements.txt`
- **Description:** Karaoke transcripts come from `gemini-3.5-transcribe` (word timestamps). API key lives in gitignored `auth/auth-config.json`; model IDs, AI Studio endpoint, and language map (`es` → `es-419`) live on `config_store`. `get_module("gemini_client")` is the shared SDK handle for later image/music work. Removed `auth/.gitkeep` and `projects/.gitkeep`.
- **Rationale:** Side-by-side on *Ya tienes* showed Gemini fixing the Whisper misses (`alacena`, `elevada`, `revisé`, `WhatsApp`) without a custom vocabulary.
- **Impact:** `pip install -r requirements.txt` pulls `google-genai` instead of `openai-whisper`. Copy the auth example before running `pipelines/transcribe.py`.
- **Links:** [config_store](documentation/config/config_store.md) · [pipelines](pipelines/README.md) · [Gemini 3.5 Transcribe](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5-transcribe/)

#### 2026-09-05 — Change — Flatten pipeline scripts into `pipelines/`

- **Author:** Thorsten
- **Area:** `pipelines/`, `README.md`, `documentation/`
- **Description:** Entry scripts sit directly in `pipelines/` (`reel_compose.py`, `import_brief.py`, `transcribe.py`, `prepare_overlays.py`). Per-pipeline `pipeline_docu/` folders are gone; one [pipelines/README.md](pipelines/README.md) covers all four.
- **Rationale:** Nested `pipelines/<name>/<name>.py` plus a doc folder each was heavier than this repo needs.
- **Impact:** Run `python pipelines/reel_compose.py …` (no extra path segment). Call sites and onboarding docs updated.
- **Links:** [pipelines/README.md](pipelines/README.md)

#### 2026-09-05 — Change — Descriptive names, Google-style docstrings, onboarding doc

- **Author:** Thorsten
- **Area:** `config/`, `modules/`, `pipelines/`, `scripts/`, `documentation/guides/start_here.md`, `README.md`, `requirements.txt`
- **Description:** Spell out Python identifiers (no `fps` / `asr` / `tw` locals). Every function has an industry-standard Google docstring (Args / Returns / Raises). Why-driven comments sit next to magic numbers and placement rules. Newcomer map: `documentation/guides/start_here.md`. `requirements.txt` now includes Whisper for transcribe.
- **Rationale:** The first pass was reusable but terse; the next person should understand clocks, safe zones, and call flow without archaeology.
- **Impact:** On-disk YAML/JSON keys are unchanged (`asr_fix`, transcript `w`/`s`/`e`) so existing briefs still load. Call sites use the new names.
- **Links:** [Start here](documentation/guides/start_here.md)

#### 2026-09-05 — Add — Initial reusable reel framework

- **Author:** Thorsten
- **Area:** `config/`, `modules/`, `pipelines/`, `brands/dra_angelica/`, `templates/angelica_brief/`, `examples/ya_tienes/`
- **Description:** Port the Dra. Angélica “Ya tienes” compose pipeline out of `dra-angelica-website` into a Locaria-shaped repo. Briefs drive timestamps and overlays; brand look lives in `brands/<id>/`. Spanish Google-Sheet template (CSV + xlsx) converts to `brief.yaml`.
- **Rationale:** The locked reel was a one-off script. Next clips need the same engine without copying `compose.py`.
- **Impact:** New reels are a project folder + sheet/YAML. Example `examples/ya_tienes` reproduces the locked overlay schedule (source clock, stickers beside the head, karaoke captions, full-frame endcard).
- **Links:** [README](README.md) · [Angélica brief](documentation/guides/angelica_brief.md) · [pipelines](pipelines/README.md)
