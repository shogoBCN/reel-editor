# Transcribe

Word-timed Whisper pass for a project talking-head clip. Writes `source/transcript.json` for karaoke captions.

**Entry:** [`transcribe.py`](../transcribe.py)

Requires `openai-whisper` in the `angelica-website` conda env (optional extra).

```bash
conda activate angelica-website
python pipelines/transcribe/transcribe.py --project examples/ya_tienes --model medium
```

Language comes from `brief.yaml` (`project.language`, default `es`). ASR word fixes are **not** applied here — they live in the brief and run at compose time so the raw transcript stays auditable.
