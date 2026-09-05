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

#### 2026-09-05 — Add — Initial reusable reel framework

- **Author:** Thorsten
- **Area:** `config/`, `modules/`, `pipelines/`, `brands/dra_angelica/`, `templates/angelica_brief/`, `examples/ya_tienes/`
- **Description:** Port the Dra. Angélica “Ya tienes” compose pipeline out of `dra-angelica-website` into a Locaria-shaped repo. Briefs drive timestamps and overlays; brand look lives in `brands/<id>/`. Spanish Google-Sheet template (CSV + xlsx) converts to `brief.yaml`.
- **Rationale:** The locked reel was a one-off script. Next clips need the same engine without copying `compose.py`.
- **Impact:** New reels are a project folder + sheet/YAML. Example `examples/ya_tienes` reproduces the locked overlay schedule (source clock, stickers beside the head, karaoke captions, full-frame endcard).
- **Links:** [README](README.md) · [Angélica brief](documentation/guides/angelica_brief.md) · [reel_compose](pipelines/reel_compose/pipeline_docu/README.md)
