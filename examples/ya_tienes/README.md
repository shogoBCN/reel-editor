# Ya tienes (example project)

Locked Dra. Angélica reel used to prove the framework. Brief times are **source clock**; final reel = source − 4.0s.

**Run** (conda env `angelica-website`):

```bash
python scripts/check_brief.py --project examples/ya_tienes
python pipelines/reel_compose.py --project examples/ya_tienes --preview
python pipelines/reel_compose.py --project examples/ya_tienes --full
```

`source/talking_head.mp4` is gitignored. Copy it locally from the original drop (`dra-angelica-website/reels/31-aug-26-ya-tienes/denoised.mp4`) if it is not already in `source/`.

Human brief (Spanish sheet tabs): `brief_sheet/`. Machine brief: `brief.yaml`.
