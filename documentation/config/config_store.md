# config_store

Repository paths, 9:16 Reels canvas, and Meta 2026 safe-zone constants.

**Location:** `config/config_store.py`

**Related:** [module_initialiser](../modules/module_initialiser.md) · [pipelines](../../pipelines/README.md) · [Start here](../guides/start_here.md)

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
| `conda_environment_name` | `angelica-website` |
| `frame_width` / `frame_height` / `frames_per_second` | 1080×1920 @ 30 |
| `top_safe_ratio` | 0.15 (IG crop + chrome) |
| `bottom_safe_ratio` | 0.68 (stay above Reels UI) |
| `side_safe_ratio` | 0.06 |
| `caption_inset_pixels` | 92 — karaoke must not clip the rails |
| `video_constant_rate_factor` | 17 (ffmpeg CRF; visually lossless talking-head) |
| `brands_directory` / `examples_directory` / `projects_directory` | Layout roots |

Properties `top_safe_pixels`, `side_safe_pixels`, `caption_max_width_pixels`, `caption_floor_pixels` are derived from the ratios so pipelines never multiply by 1920 themselves.

Per-project overrides (trim, fade, filename) belong in `brief.yaml`, not here.
