# config_store

Repository paths, 9:16 Reels canvas, and Meta 2026 safe-zone constants.

**Location:** `config/config_store.py`

**Related:** [module_initialiser](../modules/module_initialiser.md) · [reel_compose](../../pipelines/reel_compose/pipeline_docu/README.md)

Brand colours, fonts, and assets are **not** here — they live in `brands/<id>/brand.yaml`.

## How to use

```python
from modules.modules_initialiser import get_module

config_store = get_module("config_store")
```

## Key attributes

| Attribute | Purpose |
|-----------|---------|
| `directory_path` | Repo root |
| `conda_env_name` | `angelica-website` |
| `frame_width` / `frame_height` / `fps` | 1080×1920 @ 30 |
| `top_safe_ratio` | 0.15 (IG crop + chrome) |
| `bottom_safe_ratio` | 0.68 (stay above Reels UI) |
| `side_safe_ratio` | 0.06 |
| `caption_inset_px` | 92 — karaoke must not clip the rails |
| `video_crf` | 17 |
| `brands_dir` / `examples_dir` / `projects_dir` | Layout roots |

Per-project overrides (trim, fade, filename) belong in `brief.yaml`, not here.
